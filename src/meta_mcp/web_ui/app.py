"""FastAPI web interface for Meta MCP Server monitoring and configuration."""

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ..config.models import MetaMCPConfig, MetricsData
from ..utils.logging import get_logger


class WebInterface:
    """Web interface for Meta MCP Server."""

    def __init__(self, config: MetaMCPConfig, server_instance):
        self.config = config.web_ui
        self.server_config = config
        self.server_instance = server_instance
        self.logger = get_logger(__name__)
        self.app = FastAPI(
            title="Meta MCP Server",
            description="Web interface for Meta MCP Server monitoring and configuration",
            version="0.1.0",
        )
        self.active_connections: list[WebSocket] = []

        # Setup middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Setup routes
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup API routes."""

        @self.app.get("/")
        async def root():
            """Root endpoint with basic info."""
            return {"message": "Meta MCP Server Web Interface", "status": "running"}

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "server_running": self.server_instance._running,
            }

        @self.app.get("/api/config")
        async def get_config():
            """Get current server configuration."""
            try:
                return {
                    "server": self.server_config.server.model_dump(),
                    "strategy": self.server_config.strategy.model_dump(),
                    "embeddings": {
                        **self.server_config.embeddings.model_dump(),
                        "lm_studio_endpoint": self.server_config.embeddings.lm_studio_endpoint,
                    },
                    "vector_store": self.server_config.vector_store.model_dump(),
                    "llm": {
                        **self.server_config.llm.model_dump(),
                        "api_key": "***" if self.server_config.llm.api_key else None,
                    },
                    "rag": self.server_config.rag.model_dump(),
                    "web_ui": self.server_config.web_ui.model_dump(),
                    "child_servers": [
                        {
                            **server.model_dump(),
                            "env": dict.fromkeys(
                                server.env.keys(), "***"
                            ),  # Hide env vars
                        }
                        for server in self.server_config.child_servers
                    ],
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/status")
        async def get_status():
            """Get detailed server status."""
            try:
                status = self.server_instance.get_status()

                # Add child server status if available
                if hasattr(self.server_instance, "child_manager"):
                    child_status = (
                        await self.server_instance.child_manager.get_server_status()
                    )
                    status["child_servers"] = child_status

                # Add routing metrics if available
                if hasattr(self.server_instance, "routing_engine"):
                    routing_metrics = {}
                    for (
                        strategy_name,
                        router,
                    ) in self.server_instance.routing_engine.routers.items():
                        routing_metrics[strategy_name] = router.get_metrics()
                    status["routing_metrics"] = routing_metrics

                return status
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/tools")
        async def get_tools():
            """Get all available tools."""
            try:
                tools = await self.server_instance.list_tools()
                return {
                    "tools": [tool.model_dump() for tool in tools],
                    "count": len(tools),
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get performance metrics."""
            try:
                metrics = MetricsData(
                    active_connections=len(self.active_connections),
                    total_requests=getattr(self.server_instance, "_total_requests", 0),
                    avg_response_time=getattr(
                        self.server_instance, "_avg_response_time", 0.0
                    ),
                    uptime_seconds=int(
                        asyncio.get_event_loop().time()
                        - getattr(self.server_instance, "_start_time", 0)
                    ),
                )

                # Add component-specific metrics
                component_metrics = {}

                if hasattr(self.server_instance, "embedding_service"):
                    component_metrics["embeddings"] = (
                        self.server_instance.embedding_service.get_metrics()
                    )

                if hasattr(self.server_instance, "llm_client"):
                    component_metrics["llm"] = (
                        self.server_instance.llm_client.get_metrics()
                    )

                if hasattr(self.server_instance, "rag_pipeline"):
                    component_metrics["rag"] = (
                        self.server_instance.rag_pipeline.get_metrics()
                    )

                return {
                    **metrics.model_dump(),
                    "components": component_metrics,
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/tools/{tool_name}/call")
        async def call_tool(tool_name: str, arguments: dict[str, Any]):
            """Call a specific tool."""
            try:
                result = await self.server_instance.call_tool(tool_name, arguments)
                return {"result": result, "tool": tool_name}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/api/servers/{server_name}/restart")
        async def restart_server(server_name: str):
            """Restart a child server."""
            try:
                if hasattr(self.server_instance, "child_manager"):
                    success = await self.server_instance.child_manager.restart_server(
                        server_name
                    )
                    return {"success": success, "server": server_name}
                else:
                    raise HTTPException(
                        status_code=501, detail="Child server management not available"
                    )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/strategies")
        async def get_strategies():
            """Get available routing strategies."""
            return {
                "strategies": [
                    {
                        "name": "vector",
                        "description": "Fast semantic similarity using embeddings",
                        "features": [
                            "embedding_search",
                            "similarity_threshold",
                            "caching",
                        ],
                    },
                    {
                        "name": "llm",
                        "description": "AI-powered tool selection using local LLMs",
                        "features": ["reasoning", "context_awareness", "explanation"],
                    },
                    {
                        "name": "rag",
                        "description": "Context-augmented selection using retrieved documentation",
                        "features": [
                            "documentation_search",
                            "context_augmentation",
                            "enhanced_reasoning",
                        ],
                    },
                ],
                "current": self.server_config.strategy.primary,
                "fallback": self.server_config.strategy.fallback,
            }

        @self.app.websocket("/ws/logs")
        async def websocket_logs(websocket: WebSocket):
            """WebSocket endpoint for real-time log streaming."""
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                while True:
                    # Keep connection alive and send any queued log messages
                    await asyncio.sleep(1)
                    # In a real implementation, you'd stream actual log messages here
                    await websocket.send_json(
                        {
                            "timestamp": asyncio.get_event_loop().time(),
                            "level": "INFO",
                            "message": "Heartbeat",
                            "logger": "web_interface",
                        }
                    )
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)

        @self.app.get("/dashboard")
        async def dashboard():
            """Serve the dashboard HTML page."""
            return HTMLResponse(content=self._get_dashboard_html())

    def _get_dashboard_html(self) -> str:
        """Get simple dashboard HTML."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meta MCP Server Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            margin: 0; padding: 20px; background: #f5f5f5;
        }
        .container {
            max-width: 1200px; margin: 0 auto; background: white;
            padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px;
        }
        .header h1 {
            margin: 0; color: #333;
        }
        .status {
            display: inline-block; padding: 4px 12px; border-radius: 20px;
            font-size: 14px; font-weight: 500;
        }
        .status.running {
            background: #d4edda; color: #155724;
        }
        .grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px; margin-top: 20px;
        }
        .card {
            background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px;
            padding: 16px;
        }
        .card h3 {
            margin: 0 0 12px 0; color: #495057; font-size: 16px;
        }
        .metric {
            display: flex; justify-content: space-between; align-items: center;
            margin: 8px 0;
        }
        .metric-value {
            font-weight: 600; color: #007bff;
        }
        button {
            background: #007bff; color: white; border: none; padding: 8px 16px;
            border-radius: 4px; cursor: pointer; font-size: 14px;
        }
        button:hover {
            background: #0056b3;
        }
        .logs {
            height: 200px; overflow-y: auto; border: 1px solid #ddd;
            padding: 10px; background: #000; color: #0f0; font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Meta MCP Server Dashboard</h1>
            <span class="status running" id="status">●  Running</span>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Server Status</h3>
                <div class="metric">
                    <span>Strategy:</span>
                    <span class="metric-value" id="strategy">Loading...</span>
                </div>
                <div class="metric">
                    <span>Child Servers:</span>
                    <span class="metric-value" id="child-servers">Loading...</span>
                </div>
                <div class="metric">
                    <span>Available Tools:</span>
                    <span class="metric-value" id="tools-count">Loading...</span>
                </div>
                <div class="metric">
                    <span>Uptime:</span>
                    <span class="metric-value" id="uptime">Loading...</span>
                </div>
            </div>

            <div class="card">
                <h3>Performance</h3>
                <div class="metric">
                    <span>Active Connections:</span>
                    <span class="metric-value" id="connections">Loading...</span>
                </div>
                <div class="metric">
                    <span>Total Requests:</span>
                    <span class="metric-value" id="requests">Loading...</span>
                </div>
                <div class="metric">
                    <span>Avg Response Time:</span>
                    <span class="metric-value" id="response-time">Loading...</span>
                </div>
                <button onclick="refreshMetrics()">Refresh Metrics</button>
            </div>

            <div class="card">
                <h3>Quick Actions</h3>
                <button onclick="testTool()" style="margin: 4px;">Test Tool Selection</button><br>
                <button onclick="viewConfig()" style="margin: 4px;">View Configuration</button><br>
                <button onclick="restartServer()" style="margin: 4px;">Restart Child Servers</button><br>
                <button onclick="viewLogs()" style="margin: 4px;">View Logs</button>
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <h3>Live Logs</h3>
            <div class="logs" id="logs"></div>
        </div>
    </div>

    <script>
        let ws = null;

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/logs`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const logs = document.getElementById('logs');
                const timestamp = new Date(data.timestamp * 1000).toLocaleTimeString();
                logs.innerHTML += `[${timestamp}] ${data.level}: ${data.message}\\n`;
                logs.scrollTop = logs.scrollHeight;
            };

            ws.onclose = function() {
                setTimeout(connectWebSocket, 5000); // Reconnect after 5 seconds
            };
        }

        async function loadStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                document.getElementById('strategy').textContent = data.config?.strategy || 'Unknown';
                document.getElementById('child-servers').textContent =
                    Object.keys(data.child_servers || {}).length;
                document.getElementById('tools-count').textContent =
                    data.tools?.total_available || 0;
            } catch (error) {
                console.error('Failed to load status:', error);
            }
        }

        async function loadMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();

                document.getElementById('connections').textContent = data.active_connections;
                document.getElementById('requests').textContent = data.total_requests;
                document.getElementById('response-time').textContent =
                    `${data.avg_response_time.toFixed(2)}ms`;
                document.getElementById('uptime').textContent =
                    `${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m`;
            } catch (error) {
                console.error('Failed to load metrics:', error);
            }
        }

        function refreshMetrics() {
            loadStatus();
            loadMetrics();
        }

        function testTool() {
            alert('Tool testing functionality would be implemented here');
        }

        function viewConfig() {
            window.open('/api/config', '_blank');
        }

        function restartServer() {
            if (confirm('Are you sure you want to restart child servers?')) {
                alert('Server restart functionality would be implemented here');
            }
        }

        function viewLogs() {
            alert('Detailed log viewer would be implemented here');
        }

        // Initialize
        connectWebSocket();
        loadStatus();
        loadMetrics();

        // Refresh every 30 seconds
        setInterval(refreshMetrics, 30000);
    </script>
</body>
</html>
        """

    async def start(self) -> None:
        """Start the web interface."""
        if not self.config.enabled:
            return

        self.logger.info(
            "Starting web interface",
            host=self.config.host,
            port=self.config.port,
        )

    async def shutdown(self) -> None:
        """Shutdown the web interface."""
        self.logger.info("Shutting down web interface")

        # Close all WebSocket connections
        for connection in self.active_connections:
            await connection.close()

        self.active_connections.clear()

        self.logger.info("Web interface shutdown complete")

    async def broadcast_log(self, log_entry: dict[str, Any]) -> None:
        """Broadcast log entry to all connected WebSocket clients.

        Args:
            log_entry: Log entry to broadcast.
        """
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(log_entry)
            except Exception:
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.active_connections.remove(connection)
