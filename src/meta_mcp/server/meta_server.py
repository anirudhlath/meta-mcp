"""Meta MCP Server implementation with full integration."""

import asyncio
import signal
import time
from typing import Any

import uvicorn

from ..child_servers.manager import ChildServerManager
from ..config.models import MetaMCPConfig, Tool
from ..embeddings.service import EmbeddingService
from ..llm.lm_studio_client import LMStudioClient
from ..rag.pipeline import RAGPipeline
from ..routing.base import SelectionContext
from ..routing.llm_router import LLMRouter
from ..routing.rag_router import RAGRouter
from ..routing.vector_router import VectorSearchRouter
from ..utils.logging import get_logger
from ..vector_store.qdrant_client import QdrantVectorStore
from ..web_ui.gradio_app import GradioWebInterface

logger = get_logger(__name__)


class RoutingEngine:
    """Manages multiple routing strategies."""

    def __init__(self, config: MetaMCPConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.routers: dict[str, Any] = {}
        self.primary_strategy = config.strategy.primary
        self.fallback_strategy = config.strategy.fallback

    async def initialize(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
        llm_client: LMStudioClient,
        rag_pipeline: RAGPipeline,
    ) -> None:
        """Initialize all routing strategies."""
        self.logger.info("Initializing routing engine")

        # Initialize vector search router
        self.routers["vector"] = VectorSearchRouter(
            self.config, embedding_service, vector_store
        )
        await self.routers["vector"].initialize()

        # Initialize LLM router
        self.routers["llm"] = LLMRouter(self.config, llm_client)
        await self.routers["llm"].initialize()

        # Initialize RAG router
        self.routers["rag"] = RAGRouter(self.config, rag_pipeline, llm_client)
        await self.routers["rag"].initialize()

        self.logger.info(
            f"Routing engine initialized with {len(self.routers)} strategies"
        )

    async def select_tools(
        self, context: SelectionContext, available_tools: list[Tool]
    ) -> Any:
        """Select tools using the configured strategy with fallback."""
        # Try primary strategy
        try:
            router = self.routers[self.primary_strategy]
            result = await router.select_tools_with_metrics(context, available_tools)
            if result.tools or result.confidence_score > 0.3:
                return result
        except Exception as e:
            self.logger.warning(
                "Primary strategy failed",
                strategy=self.primary_strategy,
                error=str(e),
            )

        # Try fallback strategy if different
        if self.fallback_strategy != self.primary_strategy:
            try:
                router = self.routers[self.fallback_strategy]
                result = await router.select_tools_with_metrics(
                    context, available_tools
                )
                result.metadata["used_fallback"] = True
                return result
            except Exception as e:
                self.logger.error(
                    "Fallback strategy failed",
                    strategy=self.fallback_strategy,
                    error=str(e),
                )

        # Final fallback - return all tools limited by max_tools
        from ..routing.base import FallbackRouter

        fallback_router = FallbackRouter(self.config)
        await fallback_router.initialize()
        return await fallback_router.select_tools_with_metrics(context, available_tools)

    async def cleanup(self) -> None:
        """Clean up all routers."""
        for router in self.routers.values():
            await router.cleanup()


class MetaMCPServer:
    """Meta MCP Server that intelligently routes requests to child servers."""

    def __init__(self, config: MetaMCPConfig, config_path: str | None = None):
        self.config = config
        self.config_path = config_path
        self.logger = get_logger(__name__)
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._start_time = time.time()
        self._total_requests = 0
        self._total_response_time = 0.0

        # Core components
        self.child_manager: ChildServerManager | None = None
        self.embedding_service: EmbeddingService | None = None
        self.vector_store: QdrantVectorStore | None = None
        self.llm_client: LMStudioClient | None = None
        self.rag_pipeline: RAGPipeline | None = None
        self.routing_engine: RoutingEngine | None = None
        self.web_interface: GradioWebInterface | None = None

        # State
        self.available_tools: list[Tool] = []

    async def initialize(self) -> None:
        """Initialize all server components."""
        self.logger.info("Initializing Meta MCP Server")

        try:
            # Initialize embedding service
            self.embedding_service = EmbeddingService(self.config)
            await self.embedding_service.initialize()

            # Initialize vector store
            self.vector_store = QdrantVectorStore(self.config)
            await self.vector_store.initialize()

            # Initialize LLM client
            self.llm_client = LMStudioClient(self.config)
            await self.llm_client.initialize()

            # Initialize RAG pipeline
            self.rag_pipeline = RAGPipeline(
                self.config, self.embedding_service, self.vector_store, self.llm_client
            )
            await self.rag_pipeline.initialize()

            # Initialize routing engine
            self.routing_engine = RoutingEngine(self.config)
            await self.routing_engine.initialize(
                self.embedding_service,
                self.vector_store,
                self.llm_client,
                self.rag_pipeline,
            )

            # Initialize child server manager
            self.child_manager = ChildServerManager(self.config)
            await self.child_manager.initialize()

            # Update available tools and their embeddings
            await self._update_available_tools()

            # Initialize web interface
            if self.config.web_ui.enabled:
                self.web_interface = GradioWebInterface(self.config, self)
                if self.config_path:
                    self.web_interface.set_config_path(self.config_path)
                await self.web_interface.start()

            self.logger.info("Meta MCP Server initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize server", error=str(e))
            raise

    async def _update_available_tools(self) -> None:
        """Update available tools from child servers and generate embeddings."""
        if not self.child_manager:
            return

        try:
            # Get all tools from child servers
            self.available_tools = await self.child_manager.get_all_tools()

            # Update embeddings for vector search
            if self.routing_engine and "vector" in self.routing_engine.routers:
                vector_router = self.routing_engine.routers["vector"]
                await vector_router.update_tool_embeddings(self.available_tools)

            self.logger.info(f"Updated {len(self.available_tools)} available tools")

        except Exception as e:
            self.logger.error("Failed to update available tools", error=str(e))

    async def run(self) -> None:
        """Run the Meta MCP Server."""
        try:
            # Setup signal handlers for graceful shutdown
            for sig in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(sig, self._signal_handler)

            # Initialize server
            await self.initialize()

            self._running = True
            self.logger.info(
                "Meta MCP Server started",
                host=self.config.server.host,
                port=self.config.server.port,
                strategy=self.config.strategy.primary,
                child_servers=len(self.config.child_servers),
                tools_available=len(self.available_tools),
            )

            # Start web interface if enabled
            if self.web_interface:
                web_task = asyncio.create_task(self._run_web_interface())
            else:
                web_task = None

            # Start health check task
            health_task = asyncio.create_task(self._health_check_loop())

            try:
                # Wait for shutdown signal
                await self._shutdown_event.wait()
            finally:
                # Cancel background tasks
                if web_task and not web_task.done():
                    web_task.cancel()
                if health_task and not health_task.done():
                    health_task.cancel()

        except Exception as e:
            self.logger.error(f"Server error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def _run_web_interface(self) -> None:
        """Run the web interface using Gradio."""
        if not self.web_interface:
            return

        # Gradio interface runs in its own thread, so just wait for shutdown
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass

    async def _health_check_loop(self) -> None:
        """Periodic health check for child servers."""
        while self._running:
            try:
                if self.child_manager:
                    await self.child_manager.health_check()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning("Health check failed", error=str(e))
                await asyncio.sleep(30)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating shutdown")
        self._shutdown_event.set()

    async def shutdown(self) -> None:
        """Shutdown the server gracefully."""
        if not self._running:
            return

        self.logger.info("Shutting down Meta MCP Server")
        self._running = False

        try:
            # Shutdown components in reverse order
            if self.web_interface:
                await self.web_interface.shutdown()

            if self.child_manager:
                await self.child_manager.shutdown()

            if self.routing_engine:
                await self.routing_engine.cleanup()

            if self.rag_pipeline:
                await self.rag_pipeline.cleanup()

            if self.llm_client:
                await self.llm_client.cleanup()

            if self.embedding_service:
                await self.embedding_service.cleanup()

            # Vector store doesn't need explicit cleanup for Qdrant client

        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))

        self.logger.info("Meta MCP Server shutdown complete")

    async def list_tools(self) -> list[Tool]:
        """List all available tools from child servers.

        Returns:
            List of available tools.
        """
        return self.available_tools

    async def select_tools_for_context(
        self, query: str, context: dict[str, Any] = None
    ) -> list[Tool]:
        """Select tools based on query and context.

        Args:
            query: User query or context.
            context: Additional context information.

        Returns:
            List of selected tools.
        """
        if not self.routing_engine:
            return self.available_tools[: self.config.strategy.max_tools]

        # Build selection context
        selection_context = SelectionContext(
            query=query,
            recent_messages=context.get("recent_messages", []) if context else [],
            active_tools=context.get("active_tools", []) if context else [],
            user_preferences=context.get("user_preferences", {}) if context else {},
        )

        # Select tools using routing engine
        result = await self.routing_engine.select_tools(
            selection_context, self.available_tools
        )

        # Log selection result
        self.logger.info(
            "Tool selection completed",
            strategy=result.strategy_used,
            tools_selected=len(result.tools),
            confidence=result.confidence_score,
            query_length=len(query),
        )

        return result.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the appropriate child server.

        Args:
            tool_name: Name of the tool to call (format: server.tool).
            arguments: Tool arguments.

        Returns:
            Tool execution result.
        """
        start_time = time.time()
        self._total_requests += 1

        try:
            self.logger.info(f"Tool call requested: {tool_name}")

            if not self.child_manager:
                raise RuntimeError("Child server manager not initialized")

            # Forward to child manager
            result = await self.child_manager.call_tool(tool_name, arguments)

            # Update metrics
            response_time = (time.time() - start_time) * 1000
            self._total_response_time += response_time
            self._avg_response_time = self._total_response_time / self._total_requests

            # Update tool usage statistics
            if self.routing_engine and "vector" in self.routing_engine.routers:
                vector_router = self.routing_engine.routers["vector"]
                # Find tool and update usage
                for tool in self.available_tools:
                    if tool.id == tool_name:
                        tool.usage_count += 1
                        tool.last_used = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                        await vector_router.update_tool_usage(
                            tool.id, tool.usage_count, tool.last_used
                        )
                        break

            return result

        except Exception as e:
            self.logger.error("Tool call failed", tool=tool_name, error=str(e))
            raise

    def get_status(self) -> dict:
        """Get server status information.

        Returns:
            Server status dictionary.
        """
        return {
            "running": self._running,
            "config": {
                "strategy": self.config.strategy.primary,
                "fallback_strategy": self.config.strategy.fallback,
                "child_servers": len(self.config.child_servers),
                "web_ui_enabled": self.config.web_ui.enabled,
            },
            "tools": {
                "total_available": len(self.available_tools),
            },
            "components": {
                "child_manager": self.child_manager is not None,
                "embedding_service": self.embedding_service is not None,
                "vector_store": self.vector_store is not None,
                "llm_client": self.llm_client is not None,
                "rag_pipeline": self.rag_pipeline is not None,
                "routing_engine": self.routing_engine is not None,
                "web_interface": self.web_interface is not None,
            },
            "performance": {
                "total_requests": self._total_requests,
                "avg_response_time_ms": round(
                    getattr(self, "_avg_response_time", 0.0), 2
                ),
                "uptime_seconds": int(time.time() - self._start_time),
            },
        }

    async def get_metrics(self) -> dict:
        """Get detailed performance metrics.
        
        Returns:
            Performance metrics dictionary.
        """
        base_metrics = {
            "total_requests": self._total_requests,
            "avg_response_time_ms": round(getattr(self, "_avg_response_time", 0.0), 2),
            "uptime_seconds": int(time.time() - self._start_time),
            "active_connections": 0,  # Not applicable for Gradio
        }
        
        # Add component-specific metrics
        component_metrics = {}
        
        if self.embedding_service:
            try:
                component_metrics["embeddings"] = self.embedding_service.get_metrics()
            except AttributeError:
                component_metrics["embeddings"] = {"status": "running"}
        
        if self.llm_client:
            try:
                component_metrics["llm"] = self.llm_client.get_metrics()
            except AttributeError:
                component_metrics["llm"] = {"status": "running"}
        
        if self.rag_pipeline:
            try:
                component_metrics["rag"] = self.rag_pipeline.get_metrics()
            except AttributeError:
                component_metrics["rag"] = {"status": "running"}
        
        return {
            **base_metrics,
            "components": component_metrics,
        }
