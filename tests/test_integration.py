"""Integration tests for the complete Meta MCP Server system."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta_mcp.config.models import ChildServerConfig, MetaMCPConfig
from meta_mcp.routing.base import SelectionContext
from meta_mcp.server.meta_server import MetaMCPServer, RoutingEngine


class TestMetaMCPServerIntegration:
    """Test complete server integration."""

    @pytest.fixture
    def config(self):
        """Create comprehensive test configuration."""
        return MetaMCPConfig(
            child_servers=[
                ChildServerConfig(
                    name="file-server",
                    command=["python", "-m", "file_server"],
                    enabled=True,
                    documentation="docs/file-server.md",
                ),
                ChildServerConfig(
                    name="web-server",
                    command=["uvx", "web-tools"],
                    enabled=True,
                    documentation="docs/web-server.md",
                ),
            ]
        )

    @pytest.fixture
    def server(self, config):
        """Create Meta MCP Server instance."""
        return MetaMCPServer(config)

    @pytest.mark.asyncio
    async def test_server_initialization(self, server):
        """Test complete server initialization."""
        with (
            patch("meta_mcp.server.meta_server.ChildServerManager") as mock_manager,
            patch("meta_mcp.server.meta_server.EmbeddingService") as mock_embedding,
            patch("meta_mcp.server.meta_server.QdrantVectorStore") as mock_vector,
            patch("meta_mcp.server.meta_server.LMStudioClient") as mock_llm,
            patch("meta_mcp.server.meta_server.RAGPipeline") as mock_rag,
            patch("meta_mcp.server.meta_server.WebInterface") as mock_web,
        ):
            # Setup mocks
            for mock in [
                mock_manager,
                mock_embedding,
                mock_vector,
                mock_llm,
                mock_rag,
                mock_web,
            ]:
                mock_instance = AsyncMock()
                mock_instance.initialize = AsyncMock()
                mock.return_value = mock_instance

            await server.initialize()

            # Verify all components initialized
            assert server.child_manager is not None
            assert server.embedding_service is not None
            assert server.vector_store is not None
            assert server.llm_client is not None
            assert server.rag_pipeline is not None
            assert server.routing_engine is not None

    @pytest.mark.asyncio
    async def test_routing_engine_integration(self, config):
        """Test routing engine with multiple strategies."""
        routing_engine = RoutingEngine(config)

        # Mock dependencies
        mock_embedding = AsyncMock()
        mock_vector_store = AsyncMock()
        mock_llm_client = AsyncMock()
        mock_rag_pipeline = AsyncMock()

        with (
            patch.multiple(
                "meta_mcp.routing.vector_router.VectorSearchRouter",
                initialize=AsyncMock(),
            ),
            patch.multiple(
                "meta_mcp.routing.llm_router.LLMRouter",
                initialize=AsyncMock(),
            ),
            patch.multiple(
                "meta_mcp.routing.rag_router.RAGRouter",
                initialize=AsyncMock(),
            ),
        ):
            await routing_engine.initialize(
                mock_embedding, mock_vector_store, mock_llm_client, mock_rag_pipeline
            )

            # Verify all routers initialized
            assert "vector" in routing_engine.routers
            assert "llm" in routing_engine.routers
            assert "rag" in routing_engine.routers

    @pytest.mark.asyncio
    async def test_tool_selection_flow(self, server, config):
        """Test complete tool selection workflow."""
        # Mock components
        mock_routing_engine = AsyncMock()
        mock_selection_result = MagicMock()
        mock_selection_result.tools = []
        mock_selection_result.strategy_used = "vector"
        mock_selection_result.confidence_score = 0.8
        mock_selection_result.metadata = {}

        mock_routing_engine.select_tools.return_value = mock_selection_result
        server.routing_engine = mock_routing_engine

        # Test tool selection
        result = await server.select_tools_for_context(
            "read a configuration file",
            {"recent_messages": ["I need help with settings"]},
        )
        # Use the result to avoid unused variable warning
        assert isinstance(result, list)

        # Verify selection was called
        mock_routing_engine.select_tools.assert_called_once()
        call_args = mock_routing_engine.select_tools.call_args[0]
        context = call_args[0]
        assert isinstance(context, SelectionContext)
        assert context.query == "read a configuration file"

    @pytest.mark.asyncio
    async def test_tool_execution_flow(self, server):
        """Test complete tool execution workflow."""
        # Mock child manager
        mock_child_manager = AsyncMock()
        mock_child_manager.call_tool.return_value = {"result": "file_content"}
        server.child_manager = mock_child_manager

        # Mock routing engine for usage tracking
        mock_routing_engine = MagicMock()
        mock_router = AsyncMock()
        mock_routing_engine.routers = {"vector": mock_router}
        server.routing_engine = mock_routing_engine

        # Test tool execution
        result = await server.call_tool("file-server.read", {"path": "/test/file.txt"})

        assert result == {"result": "file_content"}
        mock_child_manager.call_tool.assert_called_once_with(
            "file-server.read", {"path": "/test/file.txt"}
        )

    @pytest.mark.asyncio
    async def test_fallback_strategy_execution(self, config):
        """Test fallback strategy when primary fails."""
        routing_engine = RoutingEngine(config)

        # Mock routers with primary failing
        mock_primary = AsyncMock()
        mock_primary.select_tools_with_metrics.side_effect = Exception("Primary failed")

        mock_fallback = AsyncMock()
        mock_fallback_result = MagicMock()
        mock_fallback_result.tools = []
        mock_fallback_result.confidence_score = 0.6
        mock_fallback_result.metadata = {}
        mock_fallback.select_tools_with_metrics.return_value = mock_fallback_result

        routing_engine.routers = {
            "vector": mock_primary,
            "llm": mock_fallback,
        }
        routing_engine.primary_strategy = "vector"
        routing_engine.fallback_strategy = "llm"

        context = SelectionContext(
            query="test", recent_messages=[], active_tools=[], user_preferences={}
        )
        result = await routing_engine.select_tools(context, [])

        # Should have used fallback
        assert result.metadata.get("used_fallback") is True
        mock_fallback.select_tools_with_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_status_reporting(self, server):
        """Test comprehensive status reporting."""
        # Mock components
        server._running = True
        server._total_requests = 100
        server._start_time = 1000000
        server.available_tools = [MagicMock(), MagicMock()]

        status = server.get_status()

        assert status["running"] is True
        assert status["config"]["strategy"] == "vector"
        assert status["tools"]["total_available"] == 2
        assert status["performance"]["total_requests"] == 100
        assert "components" in status

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, server):
        """Test graceful server shutdown."""
        # Mock all components
        server.web_interface = AsyncMock()
        server.child_manager = AsyncMock()
        server.routing_engine = AsyncMock()
        server.rag_pipeline = AsyncMock()
        server.llm_client = AsyncMock()
        server.embedding_service = AsyncMock()
        server._running = True

        await server.shutdown()

        # Verify all components shut down
        server.web_interface.shutdown.assert_called_once()
        server.child_manager.shutdown.assert_called_once()
        server.routing_engine.cleanup.assert_called_once()
        server.rag_pipeline.cleanup.assert_called_once()
        server.llm_client.cleanup.assert_called_once()
        server.embedding_service.cleanup.assert_called_once()
        assert server._running is False

    @pytest.mark.asyncio
    async def test_health_check_integration(self, server):
        """Test health checking integration."""
        # Mock child manager
        mock_child_manager = AsyncMock()
        server.child_manager = mock_child_manager
        server._running = True

        # Simulate health check loop execution
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Run one iteration
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            try:
                await server._health_check_loop()
            except asyncio.CancelledError:
                pass

            # Verify that health check was called at least once
            # Note: health_check may be called twice due to loop execution
            assert mock_child_manager.health_check.call_count >= 1

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, server):
        """Test error handling across components."""
        # Test initialization failure
        with patch(
            "meta_mcp.embeddings.service.EmbeddingService.__init__",
            side_effect=Exception("Init failed"),
        ):
            with pytest.raises(Exception, match="Init failed"):
                await server.initialize()

        # Test tool call failure
        mock_child_manager = AsyncMock()
        mock_child_manager.call_tool.side_effect = Exception("Tool failed")
        server.child_manager = mock_child_manager

        with pytest.raises(Exception, match="Tool failed"):
            await server.call_tool("test.tool", {})

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self, server):
        """Test metrics collection across components."""
        # Mock components with metrics
        server.embedding_service = MagicMock()
        server.embedding_service.get_metrics.return_value = {"cache_hits": 50}

        server.llm_client = MagicMock()
        server.llm_client.get_metrics.return_value = {"requests": 25}

        server._total_requests = 75
        server._total_response_time = 15000

        # This would be tested through the web interface metrics endpoint
        status = server.get_status()
        assert status["performance"]["total_requests"] == 75

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, server):
        """Test concurrent tool selections and executions."""
        # Mock routing engine
        mock_routing_engine = AsyncMock()
        mock_result = MagicMock()
        mock_result.tools = []
        mock_result.strategy_used = "vector"
        mock_result.confidence_score = 0.8
        mock_result.metadata = {}
        mock_routing_engine.select_tools.return_value = mock_result
        server.routing_engine = mock_routing_engine

        # Run concurrent selections
        tasks = [server.select_tools_for_context(f"query {i}") for i in range(5)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert mock_routing_engine.select_tools.call_count == 5
