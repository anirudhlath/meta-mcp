"""Tests for Gradio web interface."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from meta_mcp.config.models import MetaMCPConfig, Tool
from meta_mcp.web_ui.gradio_app import GradioWebInterface


class TestGradioWebInterface:
    """Test Gradio web interface functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MetaMCPConfig()

    @pytest.fixture
    def mock_server_instance(self):
        """Mock server instance."""
        server = MagicMock()
        server._running = True
        server.get_status.return_value = {
            "running": True,
            "config": {"strategy": "vector"},
            "tools": {"total_available": 5},
            "performance": {"total_requests": 100},
        }
        server.list_tools = AsyncMock(
            return_value=[
                Tool(
                    id="test.tool",
                    name="test_tool",
                    server_name="test",
                    description="Test tool",
                    parameters={},
                )
            ]
        )
        server.call_tool = AsyncMock(return_value={"result": "success"})
        server.get_metrics = AsyncMock(return_value={
            "total_requests": 100,
            "avg_response_time_ms": 150.5,
            "uptime_seconds": 3600,
            "components": {}
        })
        
        # Mock routing engine for tool selection tests
        mock_routing_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.strategy_used = "vector"
        mock_result.confidence_score = 0.95
        mock_result.tools = [
            Tool(
                id="selected.tool",
                name="selected_tool",
                server_name="test",
                description="Selected test tool",
                parameters={},
            )
        ]
        mock_result.metadata = {"test": "metadata"}
        
        mock_routing_engine.select_tools = AsyncMock(return_value=mock_result)
        mock_routing_engine.routers = {
            "vector": MagicMock(),
            "llm": MagicMock(),
            "rag": MagicMock()
        }
        mock_routing_engine.routers["vector"].select_tools_with_metrics = AsyncMock(return_value=mock_result)
        
        server.routing_engine = mock_routing_engine
        
        # Mock child manager
        server.child_manager = MagicMock()
        server.child_manager.get_server_status = AsyncMock(return_value={
            "test_server": {
                "running": True,
                "pid": 1234,
                "uptime": 3600
            }
        })
        server.child_manager.restart_server = AsyncMock()
        
        return server

    @pytest.fixture
    def web_interface(self, config, mock_server_instance):
        """Create Gradio web interface."""
        return GradioWebInterface(config, mock_server_instance)

    def test_interface_creation(self, web_interface):
        """Test that Gradio interface is created successfully."""
        assert web_interface.app is not None
        assert hasattr(web_interface, 'config')
        assert hasattr(web_interface, 'server_instance')

    def test_tool_selection_functionality(self, web_interface):
        """Test tool selection functionality."""
        query = "test query"
        strategy = "vector"
        max_tools = 5
        threshold = 0.75
        server_filter = "all"
        
        results_dict, execution_info, tool_choices, tools_data = web_interface._test_tool_selection(
            query, strategy, max_tools, threshold, server_filter
        )
        
        # Check results
        assert isinstance(results_dict, dict)
        assert "query" in results_dict
        assert "strategy_used" in results_dict
        assert "confidence_score" in results_dict
        assert "tools_found" in results_dict
        
        # Check execution info
        assert isinstance(execution_info, str)
        assert "Strategy:" in execution_info
        assert "Execution Time:" in execution_info
        
        # Check tool choices (should be a Gradio update object)
        assert isinstance(tool_choices, dict)
        assert "choices" in tool_choices
        
        # Check tools data
        assert isinstance(tools_data, list)

    def test_tool_execution_functionality(self, web_interface):
        """Test tool execution functionality."""
        selected_tool = "test_tool (test)"
        tool_args = '{"param1": "value1"}'
        
        result = web_interface._execute_tool(selected_tool, tool_args)
        
        assert isinstance(result, dict)
        assert "tool" in result
        assert "arguments" in result
        assert "result" in result
        assert "status" in result
        assert result["status"] == "success"

    def test_load_available_tools(self, web_interface):
        """Test loading available tools."""
        tools_data = web_interface._load_available_tools()
        
        assert isinstance(tools_data, list)
        assert len(tools_data) > 0
        
        # Check tool data structure
        tool = tools_data[0]
        assert len(tool) == 4  # name, server, description, usage_count
        assert isinstance(tool[0], str)  # name
        assert isinstance(tool[1], str)  # server
        assert isinstance(tool[2], str)  # description
        assert isinstance(tool[3], int)  # usage_count

    def test_config_yaml_generation(self, web_interface):
        """Test YAML configuration generation."""
        yaml_config = web_interface._get_current_config_yaml()
        
        assert isinstance(yaml_config, str)
        assert "server:" in yaml_config
        assert "strategy:" in yaml_config
        assert "embeddings:" in yaml_config

    def test_config_validation(self, web_interface):
        """Test configuration validation."""
        # Valid YAML
        valid_yaml = """
server:
  name: test-server
  port: 3456
strategy:
  primary: vector
        """
        
        result = web_interface._validate_config(valid_yaml)
        assert "✅" in result
        
        # Invalid YAML
        invalid_yaml = "invalid: yaml: content: ["
        result = web_interface._validate_config(invalid_yaml)
        assert "❌" in result

    def test_config_summary(self, web_interface):
        """Test configuration summary generation."""
        summary = web_interface._get_config_summary()
        
        assert isinstance(summary, dict)
        assert "server" in summary
        assert "strategy" in summary
        assert "child_servers" in summary

    def test_server_status_html(self, web_interface):
        """Test server status HTML generation."""
        status_html = web_interface._get_server_status_html()
        
        assert isinstance(status_html, str)
        assert "<div" in status_html
        assert "Server" in status_html

    def test_status_refresh(self, web_interface):
        """Test status refresh functionality."""
        status_html, metrics, child_data, health = web_interface._refresh_status()
        
        assert isinstance(status_html, str)
        assert isinstance(metrics, dict)
        assert isinstance(child_data, list)
        assert isinstance(health, dict)

    def test_child_server_restart(self, web_interface):
        """Test child server restart functionality."""
        child_data = web_interface._restart_child_server("test_server")
        
        assert isinstance(child_data, list)
        # Should call restart_server on the mock
        web_interface.server_instance.child_manager.restart_server.assert_called_once_with("test_server")

    def test_health_check_execution(self, web_interface):
        """Test health check execution."""
        # Mock the health checker import to avoid dependency issues
        with pytest.MonkeyPatch().context() as m:
            mock_health_checker = MagicMock()
            mock_health_checker.return_value.run_health_check = AsyncMock(
                return_value={"status": "success"}
            )
            
            result = web_interface._run_health_check()
            assert isinstance(result, dict)

    def test_log_reading(self, web_interface, tmp_path):
        """Test log file reading functionality."""
        # Create a temporary log file
        log_file = tmp_path / "test.log"
        log_file.write_text("INFO: Test log entry\nERROR: Test error\nDEBUG: Test debug")
        
        # Update config to point to test log file
        web_interface.server_config.logging.file = str(log_file)
        
        logs = web_interface._get_recent_logs("INFO")
        assert isinstance(logs, str)
        assert "Test log entry" in logs

    def test_config_backup_restore(self, web_interface):
        """Test configuration backup and restore functionality."""
        # Create backup
        backup_result = web_interface._create_backup()
        assert "✅" in backup_result
        
        # Restore backup
        restored_yaml, restore_result = web_interface._restore_backup()
        assert isinstance(restored_yaml, str)
        assert "✅" in restore_result

    def test_config_reset(self, web_interface):
        """Test configuration reset functionality."""
        reset_yaml, reset_result = web_interface._reset_config()
        
        assert isinstance(reset_yaml, str)
        assert "server:" in reset_yaml
        assert "⚠️" in reset_result

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, web_interface, config):
        """Test interface startup and shutdown."""
        # Mock Gradio app launch method
        web_interface.app.launch = MagicMock()
        web_interface.app.close = MagicMock()
        
        # Test start
        await web_interface.start()
        
        # Test shutdown
        await web_interface.shutdown()

    def test_set_config_path(self, web_interface):
        """Test setting configuration file path."""
        test_path = "/path/to/config.yaml"
        web_interface.set_config_path(test_path)
        
        assert web_interface.config_path == test_path

    def test_error_handling_in_tool_selection(self, web_interface):
        """Test error handling in tool selection."""
        # Test with empty query
        results_dict, execution_info, tool_choices, tools_data = web_interface._test_tool_selection(
            "", "vector", 5, 0.75, "all"
        )
        
        assert results_dict == {}
        assert "Please enter a query" in execution_info

    def test_error_handling_in_tool_execution(self, web_interface):
        """Test error handling in tool execution."""
        # Test with no tool selected
        result = web_interface._execute_tool("", "")
        
        assert result["error"] == "No tool selected"
        
        # Test with invalid JSON
        result = web_interface._execute_tool("test_tool (test)", "invalid json")
        
        assert "Invalid JSON" in result["error"]

    def test_json_validation(self, web_interface):
        """Test JSON MCP configuration validation."""
        # Valid JSON
        valid_json = """
        {
          "mcpServers": {
            "filesystem": {
              "command": "npx",
              "args": ["-y", "@modelcontextprotocol/server-filesystem"]
            }
          }
        }
        """
        result = web_interface._validate_mcp_json(valid_json)
        assert "✅" in result
        
        # Invalid JSON
        invalid_json = "invalid json"
        result = web_interface._validate_mcp_json(invalid_json)
        assert "❌" in result
        
        # Missing mcpServers key
        missing_key_json = '{"other": "value"}'
        result = web_interface._validate_mcp_json(missing_key_json)
        assert "❌" in result
        assert "mcpServers" in result

    def test_tool_generation_for_servers(self, web_interface):
        """Test tool generation based on server type."""
        # Test filesystem server
        tools = web_interface._generate_tools_for_server("filesystem", "npx", [], True)
        assert len(tools) > 0
        assert any("read_file" in tool["name"] for tool in tools)
        assert any("write_file" in tool["name"] for tool in tools)
        
        # Test git server
        tools = web_interface._generate_tools_for_server("git", "uvx", [], True)
        assert len(tools) > 0
        assert any("git_status" in tool["name"] for tool in tools)
        
        # Test unknown server type
        tools = web_interface._generate_tools_for_server("unknown", "command", [], True)
        assert len(tools) > 0
        assert all("unknown" in tool["name"] for tool in tools)

    def test_json_import_functionality(self, web_interface):
        """Test JSON import functionality."""
        test_json = """
        {
          "mcpServers": {
            "filesystem": {
              "command": "npx",
              "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
            },
            "git": {
              "command": "uvx",
              "args": ["mcp-server-git"]
            }
          }
        }
        """
        
        status, stats, tools = web_interface._import_tools_from_json(
            test_json, True, True, False
        )
        
        assert "✅" in status
        assert stats["servers_processed"] == 2
        assert stats["tools_imported"] > 0
        assert len(tools) > 0
        
        # Check tool structure
        tool = tools[0]
        assert len(tool) == 4  # name, server, command, args
        assert isinstance(tool[0], str)  # name
        assert isinstance(tool[1], str)  # server

    def test_json_import_error_handling(self, web_interface):
        """Test JSON import error handling."""
        # Empty JSON
        status, stats, tools = web_interface._import_tools_from_json("", True, True, False)
        assert "⚠️" in status
        assert len(tools) == 0
        
        # Invalid JSON
        status, stats, tools = web_interface._import_tools_from_json("invalid", True, True, False)
        assert "❌" in status
        assert "error" in stats
        
        # Missing mcpServers
        status, stats, tools = web_interface._import_tools_from_json('{"other": "value"}', True, True, False)
        assert "❌" in status
