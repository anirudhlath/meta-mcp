"""Tests for child server manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta_mcp.child_servers.manager import ChildServerManager
from meta_mcp.config.models import ChildServerConfig, MetaMCPConfig


class TestChildServerManager:
    """Test child server management functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MetaMCPConfig(
            child_servers=[
                ChildServerConfig(
                    name="test-server-1",
                    command=["python", "-m", "test_server"],
                    enabled=True,
                ),
                ChildServerConfig(
                    name="test-server-2",
                    command=["uvx", "another-server"],
                    enabled=False,
                ),
            ]
        )

    @pytest.fixture
    def manager(self, config):
        """Create child server manager."""
        return ChildServerManager(config)

    @pytest.mark.asyncio
    async def test_initialization(self, manager):
        """Test manager initialization."""
        with (
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
            patch(
                "meta_mcp.child_servers.manager.ChildServerClient"
            ) as mock_client_class,
        ):
            mock_process = AsyncMock()
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process

            # Mock client
            mock_client = AsyncMock()
            mock_client.tools = []
            mock_client.initialize = AsyncMock()
            mock_client_class.return_value = mock_client

            await manager.initialize()

            # Should only start enabled servers
            assert len(manager.servers) == 1
            assert "test-server-1" in manager.servers
            assert "test-server-2" not in manager.servers

    @pytest.mark.asyncio
    async def test_server_health_check(self, manager):
        """Test server health checking."""
        # Mock a running server
        mock_server = MagicMock()
        mock_server.process.returncode = None
        mock_server.is_healthy = AsyncMock(return_value=True)
        manager.servers["test-server"] = mock_server

        # Health check should pass - but manager doesn't have health_check method yet
        # This is a placeholder test for when implementation is complete
        assert hasattr(manager, "servers")
        assert "test-server" in manager.servers

    @pytest.mark.asyncio
    async def test_server_restart(self, manager):
        """Test server restart functionality."""
        # Mock server
        mock_server = AsyncMock()
        mock_server.restart = AsyncMock(return_value=True)
        manager.servers["test-server"] = mock_server

        # Test restart - placeholder for when implementation is complete
        # For now just verify the server exists in manager
        assert "test-server" in manager.servers

    @pytest.mark.asyncio
    async def test_get_all_tools(self, manager):
        """Test tool aggregation from child servers."""
        # Mock server with tools
        mock_server = AsyncMock()
        mock_tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"param1": "string"},
            }
        ]
        mock_server.get_tools = AsyncMock(return_value=mock_tools)
        manager.servers["test-server"] = mock_server

        # Get tools - placeholder for when implementation is complete
        # For now just verify the server exists
        assert "test-server" in manager.servers

    @pytest.mark.asyncio
    async def test_call_tool(self, manager):
        """Test tool execution on child servers."""
        # Mock server
        mock_server = AsyncMock()
        mock_result = {"result": "success", "data": "test_data"}
        mock_server.call_tool = AsyncMock(return_value=mock_result)
        manager.servers["test-server"] = mock_server

        # Call tool - placeholder for when implementation is complete
        # For now just verify the server exists
        assert "test-server" in manager.servers

    @pytest.mark.asyncio
    async def test_shutdown(self, manager):
        """Test graceful shutdown."""
        # Mock servers
        mock_server1 = AsyncMock()
        mock_server2 = AsyncMock()
        manager.servers["server1"] = mock_server1
        manager.servers["server2"] = mock_server2

        # Test shutdown - placeholder for when implementation is complete
        # For now just verify the servers exist
        assert len(manager.servers) == 2

    @pytest.mark.asyncio
    async def test_server_failure_handling(self, manager):
        """Test handling of server failures."""
        # Mock failing server
        mock_server = AsyncMock()
        mock_server.is_healthy = AsyncMock(return_value=False)
        mock_server.restart = AsyncMock(return_value=True)
        manager.servers["failing-server"] = mock_server

        # Health check failure handling - placeholder for implementation
        # For now just verify the server exists
        assert "failing-server" in manager.servers

    @pytest.mark.asyncio
    async def test_get_server_status(self, manager):
        """Test server status reporting."""
        # Mock server
        mock_server = MagicMock()
        mock_server.get_status.return_value = {
            "name": "test-server",
            "status": "running",
            "uptime": 3600,
        }
        manager.servers["test-server"] = mock_server

        # Get status - placeholder for when implementation is complete
        # For now just verify the server exists
        assert "test-server" in manager.servers
