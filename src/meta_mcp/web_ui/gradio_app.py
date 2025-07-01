"""Gradio-based web interface for Meta MCP Server."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import gradio as gr
import yaml

from ..config.loader import load_config, save_config
from ..config.models import MetaMCPConfig
from ..routing.base import SelectionContext
from ..utils.logging import get_logger


class GradioWebInterface:
    """Gradio-based web interface for Meta MCP Server."""

    def __init__(self, config: MetaMCPConfig, server_instance: Any) -> None:
        self.config = config
        self.server_config = config
        self.server_instance = server_instance
        self.logger = get_logger(__name__)

        # State variables
        self.config_backup: dict[str, Any] | None = None
        self.config_path: str | None = None

        # Create the Gradio interface
        self.app = self._create_interface()

    def _create_interface(self) -> gr.Blocks:
        """Create the main Gradio interface."""

        # Create a modern theme with better styling
        theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="gray",
            neutral_hue="slate",
            spacing_size="md",
            radius_size="lg",
        ).set(
            body_background_fill="white",
            panel_background_fill="*neutral_50",
            button_primary_background_fill="*primary_500",
            button_primary_background_fill_hover="*primary_600",
        )

        with gr.Blocks(
            title="Meta MCP Server Dashboard",
            theme=theme,
            css="""
            /* Modern styling for Gradio 5.x */
            .status-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 1.5rem;
                border-radius: 1rem;
                box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                margin: 1rem 0;
            }
            .metric-card {
                background: white;
                padding: 1.25rem;
                border-radius: 0.75rem;
                border: 1px solid #e2e8f0;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                transition: all 0.2s ease;
            }
            .metric-card:hover {
                box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                transform: translateY(-2px);
            }
            .metric-value {
                font-weight: 700;
                color: #3b82f6;
                font-size: 1.5rem;
            }
            .error-text { color: #ef4444; font-weight: 600; }
            .success-text { color: #10b981; font-weight: 600; }
            .warning-text { color: #f59e0b; font-weight: 600; }

            /* Enhanced button styling */
            .gradio-button {
                border-radius: 0.5rem !important;
                font-weight: 500 !important;
                transition: all 0.2s ease !important;
            }

            /* Better tab styling */
            .tab-nav {
                border-radius: 0.75rem 0.75rem 0 0 !important;
            }

            /* Code editor improvements */
            .code-editor {
                border-radius: 0.5rem !important;
                border: 1px solid #e2e8f0 !important;
            }

            /* JSON display improvements */
            .json-holder {
                border-radius: 0.5rem !important;
                background: #f8fafc !important;
            }
            """,
        ) as app:
            # Add a modern header with status indicator
            with gr.Row():
                with gr.Column(scale=3):
                    gr.Markdown("# 🚀 Meta MCP Server Dashboard")
                    gr.Markdown(
                        "*Interactive interface for testing tool retrieval and managing configuration*"
                    )
                with gr.Column(scale=1):
                    gr.HTML(
                        value='<div class="status-card">🟢 Server Running</div>',
                        elem_classes=["status-indicator"],
                    )

            with gr.Tabs():
                # Tool Testing Tab
                with gr.TabItem("🔧 Tool Testing"):
                    tools_df = self._create_tool_testing_tab()

                # JSON Tool Import Tab
                with gr.TabItem("📥 Import Tools"):
                    self._create_json_import_tab()

                # Configuration Tab
                with gr.TabItem("⚙️ Configuration"):
                    self._create_config_tab()

                # System Monitor Tab
                with gr.TabItem("📊 System Monitor"):
                    self._create_monitor_tab()

                # Logs Tab
                with gr.TabItem("📝 Logs"):
                    self._create_logs_tab()

            # Load available tools on startup
            app.load(fn=self._load_available_tools, outputs=[tools_df])

        return app

    def _create_tool_testing_tab(self) -> Any:
        """Create the tool testing interface."""
        # Add state management for better UX
        gr.State({"last_query": "", "last_results": {}})

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🎯 Query Parameters")

                # Enhanced query input with examples
                with gr.Group():
                    query_input = gr.Textbox(
                        label="Query",
                        placeholder="Enter your query to test tool selection...",
                        lines=3,
                        max_lines=5,
                        info="💡 Try: 'search for files', 'create a repository', 'analyze code'",
                    )

                    # Quick example buttons for common queries
                    with gr.Row():
                        gr.Button(
                            "📁 File Operations", size="sm", variant="secondary"
                        ).click(
                            lambda: "search for files and directories",
                            outputs=[query_input],
                        )
                        gr.Button(
                            "🔧 Development", size="sm", variant="secondary"
                        ).click(
                            lambda: "create a new repository and setup project",
                            outputs=[query_input],
                        )
                        gr.Button("📊 Analysis", size="sm", variant="secondary").click(
                            lambda: "analyze code quality and performance",
                            outputs=[query_input],
                        )

                # Enhanced parameter controls in groups
                with gr.Group():
                    gr.Markdown("**Strategy & Limits**")
                    with gr.Row():
                        strategy_dropdown = gr.Dropdown(
                            label="Routing Strategy",
                            choices=["auto", "vector", "llm", "rag"],
                            value="auto",
                            info="🤖 Auto selects best strategy",
                            interactive=True,
                        )

                        max_tools_slider = gr.Slider(
                            label="Max Tools",
                            minimum=1,
                            maximum=20,
                            value=5,
                            step=1,
                            info="Maximum tools to return",
                        )

                with gr.Group():
                    gr.Markdown("**Filtering & Thresholds**")
                    with gr.Row():
                        threshold_slider = gr.Slider(
                            label="Confidence Threshold",
                            minimum=0.0,
                            maximum=1.0,
                            value=0.75,
                            step=0.05,
                            info="Higher = more selective",
                        )

                        server_filter = gr.Dropdown(
                            label="Filter by Server",
                            choices=["all"]
                            + [s.name for s in self.config.child_servers],
                            value="all",
                            info="Filter tools by specific server",
                        )

                # Enhanced test button with loading state
                with gr.Row():
                    test_button = gr.Button(
                        "🚀 Test Tool Selection", variant="primary", size="lg", scale=2
                    )
                    clear_button = gr.Button(
                        "🗑️ Clear", variant="secondary", size="lg", scale=1
                    )

            with gr.Column(scale=2):
                gr.Markdown("### 📊 Results")

                # Add progress indicator for tool selection
                gr.Progress()

                # Results display with tabs for better organization
                with gr.Tabs():
                    with gr.TabItem("🎯 Selection Results"):
                        # Modern status indicator
                        status_indicator = gr.HTML(
                            value='<div class="metric-card">Ready to test tool selection</div>',
                            label="Status",
                        )

                        # Enhanced results display
                        results_json = gr.JSON(
                            label="Detailed Results", show_label=True, container=True
                        )

                        # Quick metrics display
                        with gr.Row():
                            with gr.Column():
                                confidence_display = gr.Number(
                                    label="Confidence Score",
                                    value=0.0,
                                    interactive=False,
                                    container=True,
                                )
                            with gr.Column():
                                execution_time_display = gr.Number(
                                    label="Execution Time (ms)",
                                    value=0.0,
                                    interactive=False,
                                    container=True,
                                )
                            with gr.Column():
                                tools_found_display = gr.Number(
                                    label="Tools Found",
                                    value=0,
                                    interactive=False,
                                    container=True,
                                )

                    with gr.TabItem("📋 Available Tools"):
                        tools_df = gr.Dataframe(
                            headers=["Name", "Server", "Description", "Usage Count"],
                            label="All Available Tools",
                            interactive=False,
                            wrap=True,
                            show_label=True,
                            show_copy_button=True,
                            show_search="search",
                        )

                        # Add refresh button for tools
                        refresh_tools_btn = gr.Button(
                            "🔄 Refresh Tools", variant="secondary", size="sm"
                        )

        # Enhanced tool execution section
        with gr.Group():
            gr.Markdown("### ⚡ Tool Execution")

            with gr.Row():
                with gr.Column(scale=1):
                    selected_tool = gr.Dropdown(
                        label="Select Tool to Execute",
                        choices=[],
                        info="Choose a tool from the results above",
                        interactive=True,
                        container=True,
                    )

                    # Enhanced JSON editor with better UX
                    gr.Markdown("💡 *Use valid JSON format for arguments*")
                    tool_args = gr.Code(
                        label="Tool Arguments (JSON)",
                        language="json",
                        value='{\n  "param1": "value1",\n  "param2": "value2"\n}',
                        lines=6,
                    )

                    # Modern execution controls
                    with gr.Row():
                        execute_button = gr.Button(
                            "⚡ Execute Tool", variant="primary", size="lg", scale=2
                        )
                        validate_json_btn = gr.Button(
                            "✅ Validate JSON", variant="secondary", size="lg", scale=1
                        )

                with gr.Column(scale=1):
                    # Execution status indicator
                    execution_status = gr.HTML(
                        value='<div class="metric-card">Ready to execute</div>',
                        label="Execution Status",
                    )

                    # Enhanced results display
                    execution_result = gr.JSON(
                        label="Execution Result", show_label=True, container=True
                    )

                    # Execution history (using State for persistence)
                    execution_history = gr.State([])

                    with gr.Accordion("📚 Execution History", open=False):
                        history_display = gr.JSON(
                            label="Recent Executions", value=[], container=True
                        )

        # Modern event handlers with progress indicators
        test_button.click(
            fn=self._test_tool_selection_with_progress,
            inputs=[
                query_input,
                strategy_dropdown,
                max_tools_slider,
                threshold_slider,
                server_filter,
            ],
            outputs=[
                results_json,
                status_indicator,
                selected_tool,
                tools_df,
                confidence_display,
                execution_time_display,
                tools_found_display,
            ],
            show_progress="full",
        )

        # Clear button functionality
        clear_button.click(
            fn=lambda: (
                "",
                {},
                [],
                [],
                0.0,
                0.0,
                0,
                '<div class="metric-card">Ready to test tool selection</div>',
            ),
            outputs=[
                query_input,
                results_json,
                selected_tool,
                tools_df,
                confidence_display,
                execution_time_display,
                tools_found_display,
                status_indicator,
            ],
        )

        # Enhanced tool execution handlers
        execute_button.click(
            fn=self._execute_tool_with_history,
            inputs=[selected_tool, tool_args, execution_history],
            outputs=[
                execution_result,
                execution_status,
                execution_history,
                history_display,
            ],
            show_progress="full",
        )

        # JSON validation handler
        validate_json_btn.click(
            fn=self._validate_json, inputs=[tool_args], outputs=[execution_status]
        )

        # Refresh tools handler
        refresh_tools_btn.click(fn=self._load_available_tools, outputs=[tools_df])

        return tools_df

    def _create_config_tab(self) -> Any:
        """Create the configuration management interface."""
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### Configuration Editor")

                config_editor = gr.Code(
                    label="YAML Configuration",
                    language="yaml",
                    lines=20,
                    value=self._get_current_config_yaml(),
                )

                with gr.Row():
                    save_button = gr.Button("💾 Save Configuration", variant="primary")
                    reload_button = gr.Button(
                        "🔄 Reload from File", variant="secondary"
                    )
                    validate_button = gr.Button("✅ Validate", variant="secondary")
                    reset_button = gr.Button("🔙 Reset to Defaults", variant="stop")

            with gr.Column(scale=1):
                gr.Markdown("### Configuration Status")

                config_status = gr.Textbox(
                    label="Status",
                    value="Configuration loaded successfully",
                    interactive=False,
                    lines=3,
                )

                gr.Markdown("### Configuration Sections")
                config_sections = gr.JSON(
                    label="Current Config Structure", value=self._get_config_summary()
                )

                gr.Markdown("### Quick Actions")

                with gr.Column():
                    backup_button = gr.Button("📋 Create Backup")
                    restore_button = gr.Button("♻️ Restore Backup")

                backup_status = gr.Textbox(
                    label="Backup Status", interactive=False, lines=2
                )

        # Event handlers
        validate_button.click(
            fn=self._validate_config, inputs=[config_editor], outputs=[config_status]
        )

        save_button.click(
            fn=self._save_config,
            inputs=[config_editor],
            outputs=[config_status, config_sections],
        )

        reload_button.click(
            fn=self._reload_config,
            outputs=[config_editor, config_status, config_sections],
        )

        reset_button.click(
            fn=self._reset_config, outputs=[config_editor, config_status]
        )

        backup_button.click(fn=self._create_backup, outputs=[backup_status])

        restore_button.click(
            fn=self._restore_backup, outputs=[config_editor, backup_status]
        )

    def _create_monitor_tab(self) -> Any:
        """Create the system monitoring interface."""
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Server Status")

                with gr.Row():
                    server_status = gr.HTML(value=self._get_server_status_html())

                refresh_button = gr.Button("🔄 Refresh Status", variant="secondary")

            with gr.Column():
                gr.Markdown("### Performance Metrics")

                metrics_json = gr.JSON(label="Current Metrics")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Child Servers")

                child_servers_df = gr.Dataframe(
                    headers=["Name", "Status", "PID", "Uptime", "Actions"],
                    label="Child Server Status",
                )

                with gr.Row():
                    restart_server = gr.Dropdown(
                        label="Select Server to Restart",
                        choices=[s.name for s in self.config.child_servers],
                        info="Choose a server to restart",
                    )
                    restart_button = gr.Button("🔄 Restart Server", variant="stop")

            with gr.Column():
                gr.Markdown("### System Health")

                health_status = gr.JSON(label="Health Check Results")

                run_health_check = gr.Button("🏥 Run Health Check", variant="primary")

        # Event handlers
        refresh_button.click(
            fn=self._refresh_status,
            outputs=[server_status, metrics_json, child_servers_df, health_status],
        )

        restart_button.click(
            fn=self._restart_child_server,
            inputs=[restart_server],
            outputs=[child_servers_df],
        )

        run_health_check.click(fn=self._run_health_check, outputs=[health_status])

        # Auto-refresh every 30 seconds
        gr.Timer(30.0).tick(
            fn=self._refresh_status,
            outputs=[server_status, metrics_json, child_servers_df, health_status],
        )

    def _create_logs_tab(self) -> Any:
        """Create the logs viewing interface."""
        with gr.Column():
            gr.Markdown("### Live Logs")

            with gr.Row():
                log_level_filter = gr.Dropdown(
                    label="Log Level",
                    choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                    value="INFO",
                )

                auto_refresh = gr.Checkbox(label="Auto-refresh", value=True)

                clear_logs = gr.Button("🗑️ Clear Display", variant="secondary")

            logs_display = gr.Textbox(
                label="System Logs",
                lines=20,
                max_lines=50,
                interactive=False,
                show_copy_button=True,
            )

            refresh_logs = gr.Button("🔄 Refresh Logs", variant="primary")

        # Event handlers
        refresh_logs.click(
            fn=self._get_recent_logs, inputs=[log_level_filter], outputs=[logs_display]
        )

        clear_logs.click(fn=lambda: "", outputs=[logs_display])

        # Auto-refresh logs if enabled
        def auto_refresh_logs():
            if auto_refresh.value:
                return self._get_recent_logs(log_level_filter.value)
            return gr.update()

        gr.Timer(5.0).tick(fn=auto_refresh_logs, outputs=[logs_display])

    def _create_json_import_tab(self) -> Any:
        """Create the JSON tool import interface."""
        with gr.Column():
            gr.Markdown("### 📥 Import Tools from JSON MCP Config")
            gr.Markdown("""
            Import tools from a standard MCP server JSON configuration when child servers fail to start.
            This is useful when `uvx` or other dependencies are missing.
            """)

            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("#### JSON Configuration Input")

                    # File upload option
                    config_file = gr.File(
                        label="Upload MCP Configuration File",
                        file_types=[".json"],
                        file_count="single",
                    )

                    gr.Markdown("**OR paste JSON configuration:**")

                    # JSON input area with example
                    gr.Markdown("*Standard MCP server configuration format*")
                    json_input = gr.Code(
                        label="MCP Server Configuration (JSON)",
                        language="json",
                        lines=15,
                        value="""{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
      "env": {}
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-api-key"
      }
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "/path/to/repo"],
      "env": {}
    }
  }
}""",
                    )

                    # Import controls
                    with gr.Row():
                        import_button = gr.Button(
                            "📥 Import Tools", variant="primary", size="lg", scale=2
                        )
                        validate_json_button = gr.Button(
                            "✅ Validate JSON", variant="secondary", size="lg", scale=1
                        )
                        clear_json_button = gr.Button(
                            "🗑️ Clear", variant="secondary", size="lg", scale=1
                        )

                with gr.Column(scale=1):
                    gr.Markdown("#### Import Status")

                    import_status = gr.HTML(
                        value='<div class="metric-card">Ready to import tools</div>',
                        label="Status",
                    )

                    # Import statistics
                    import_stats = gr.JSON(
                        label="Import Summary", value={}, container=True
                    )

                    gr.Markdown("#### Imported Tools Preview")
                    imported_tools_df = gr.Dataframe(
                        headers=["Name", "Server", "Command", "Args"],
                        label="Imported Tools",
                        interactive=False,
                        wrap=True,
                    )

            # Advanced options
            with gr.Accordion("🔧 Advanced Options", open=False):
                with gr.Row():
                    merge_with_existing = gr.Checkbox(
                        label="Merge with existing tools",
                        value=True,
                        info="Add to existing tools instead of replacing them",
                    )

                    auto_generate_descriptions = gr.Checkbox(
                        label="Auto-generate tool descriptions",
                        value=True,
                        info="Generate descriptions based on command and args",
                    )

                    validate_commands = gr.Checkbox(
                        label="Validate command availability",
                        value=False,
                        info="Check if commands exist on the system (slower)",
                    )

        # Event handlers
        import_button.click(
            fn=self._import_tools_from_json,
            inputs=[
                json_input,
                merge_with_existing,
                auto_generate_descriptions,
                validate_commands,
            ],
            outputs=[import_status, import_stats, imported_tools_df],
            show_progress="full",
        )

        validate_json_button.click(
            fn=self._validate_mcp_json, inputs=[json_input], outputs=[import_status]
        )

        clear_json_button.click(
            fn=lambda: (
                "",
                '<div class="metric-card">Ready to import tools</div>',
                {},
                [],
            ),
            outputs=[json_input, import_status, import_stats, imported_tools_df],
        )

        # File upload handler
        config_file.upload(
            fn=self._load_json_from_file,
            inputs=[config_file],
            outputs=[json_input, import_status],
        )

    # Implementation methods for the interface with modern Gradio 5.x features
    def _test_tool_selection_with_progress(
        self,
        query: str,
        strategy: str,
        max_tools: int,
        threshold: float,
        server_filter: str,
    ) -> tuple[dict, str, list, list, float, float, int]:
        """Enhanced tool selection with progress indicator."""

        async def _async_test_with_progress():
            if not query.strip():
                return (
                    {},
                    '<div class="metric-card error-text">❌ Please enter a query to test</div>',
                    [],
                    [],
                    0.0,
                    0.0,
                    0,
                )

            start_time = time.time()

            # Get available tools
            available_tools = await self.server_instance.list_tools()

            # Filter by server if specified
            if server_filter != "all":
                available_tools = [
                    t for t in available_tools if t.server_name == server_filter
                ]

            # Create selection context
            context = SelectionContext(query=query)

            # Select routing strategy
            if strategy == "auto":
                # Use the server's routing engine
                result = await self.server_instance.routing_engine.select_tools(
                    context, available_tools
                )
            else:
                # Use specific strategy
                router = self.server_instance.routing_engine.routers[strategy]
                result = await router.select_tools_with_metrics(
                    context, available_tools
                )

            execution_time = (time.time() - start_time) * 1000

            # Format results
            results_dict = {
                "query": query,
                "strategy_used": result.strategy_used,
                "confidence_score": result.confidence_score,
                "execution_time_ms": execution_time,
                "tools_found": len(result.tools),
                "tools": [
                    {
                        "name": tool.name,
                        "server": tool.server_name,
                        "description": tool.description[:100] + "..."
                        if len(tool.description) > 100
                        else tool.description,
                        "usage_count": tool.usage_count,
                    }
                    for tool in result.tools[:max_tools]
                ],
                "metadata": result.metadata,
            }

            status_html = f"""
            <div class="metric-card success-text">
                ✅ Found {len(result.tools)} tools using {result.strategy_used} strategy
                <br>Confidence: {result.confidence_score:.3f} | Time: {execution_time:.2f}ms
            </div>
            """

            # Tool choices for execution
            tool_choices = [
                f"{tool.name} ({tool.server_name})" for tool in result.tools[:max_tools]
            ]

            # All tools dataframe
            tools_data = [
                [
                    tool.name,
                    tool.server_name,
                    tool.description[:50] + "...",
                    tool.usage_count,
                ]
                for tool in available_tools
            ]

            return (
                results_dict,
                status_html,
                tool_choices,
                tools_data,
                result.confidence_score,
                execution_time,
                len(result.tools),
            )

        try:
            return asyncio.run(_async_test_with_progress())
        except Exception as e:
            self.logger.error(f"Tool selection test failed: {e}")
            error_status = (
                f'<div class="metric-card error-text">❌ Error: {str(e)}</div>'
            )
            return {}, error_status, [], [], 0.0, 0.0, 0

    def _test_tool_selection(
        self,
        query: str,
        strategy: str,
        max_tools: int,
        threshold: float,
        server_filter: str,
    ) -> tuple[dict[str, Any], str, Any, list[Any]]:
        """Test tool selection with given parameters."""

        async def _async_test():
            if not query.strip():
                return {}, "Please enter a query to test", [], []

            start_time = time.time()

            # Get available tools
            available_tools = await self.server_instance.list_tools()

            # Filter by server if specified
            if server_filter != "all":
                available_tools = [
                    t for t in available_tools if t.server_name == server_filter
                ]

            # Create selection context
            context = SelectionContext(query=query)

            # Select routing strategy
            if strategy == "auto":
                # Use the server's routing engine
                result = await self.server_instance.routing_engine.select_tools(
                    context, available_tools
                )
            else:
                # Use specific strategy
                router = self.server_instance.routing_engine.routers[strategy]
                result = await router.select_tools_with_metrics(
                    context, available_tools
                )

            execution_time = (time.time() - start_time) * 1000

            # Format results
            results_dict = {
                "query": query,
                "strategy_used": result.strategy_used,
                "confidence_score": result.confidence_score,
                "execution_time_ms": execution_time,
                "tools_found": len(result.tools),
                "tools": [
                    {
                        "name": tool.name,
                        "server": tool.server_name,
                        "description": tool.description[:100] + "..."
                        if len(tool.description) > 100
                        else tool.description,
                        "usage_count": tool.usage_count,
                    }
                    for tool in result.tools[:max_tools]
                ],
                "metadata": result.metadata,
            }

            execution_info = f"Strategy: {result.strategy_used}\nExecution Time: {execution_time:.2f}ms\nConfidence: {result.confidence_score:.3f}\nTools Found: {len(result.tools)}"

            # Tool choices for execution
            tool_choices = [
                f"{tool.name} ({tool.server_name})" for tool in result.tools[:max_tools]
            ]

            # All tools dataframe
            tools_data = [
                [
                    tool.name,
                    tool.server_name,
                    tool.description[:50] + "...",
                    tool.usage_count,
                ]
                for tool in available_tools
            ]

            return results_dict, execution_info, tool_choices, tools_data

        try:
            results_dict, execution_info, tool_choices, tools_data = asyncio.run(
                _async_test()
            )
            return (
                results_dict,
                execution_info,
                gr.update(choices=tool_choices),
                tools_data,
            )
        except Exception as e:
            self.logger.error(f"Tool selection test failed: {e}")
            return {}, f"Error: {str(e)}", [], []

    def _execute_tool(self, selected_tool: str, tool_args: str) -> dict:
        """Execute a selected tool with given arguments."""

        async def _async_execute():
            if not selected_tool:
                return {"error": "No tool selected"}

            # Parse tool name and server from selection
            tool_name = selected_tool.split(" (")[0]

            # Parse arguments
            try:
                args = json.loads(tool_args) if tool_args.strip() else {}
            except json.JSONDecodeError:
                return {"error": "Invalid JSON in tool arguments"}

            # Execute tool
            result = await self.server_instance.call_tool(tool_name, args)

            return {
                "tool": tool_name,
                "arguments": args,
                "result": result,
                "status": "success",
            }

        try:
            return asyncio.run(_async_execute())
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    def _execute_tool_with_history(
        self, selected_tool: str, tool_args: str, execution_history: list
    ) -> tuple[dict, str, list, list]:
        """Enhanced tool execution with history tracking."""

        async def _async_execute_with_history():
            if not selected_tool:
                return (
                    {"error": "No tool selected"},
                    '<div class="metric-card error-text">❌ No tool selected</div>',
                    execution_history,
                    execution_history,
                )

            # Parse tool name and server from selection
            tool_name = selected_tool.split(" (")[0]

            # Parse arguments
            try:
                args = json.loads(tool_args) if tool_args.strip() else {}
            except json.JSONDecodeError as e:
                return (
                    {"error": f"Invalid JSON: {str(e)}"},
                    '<div class="metric-card error-text">❌ Invalid JSON format</div>',
                    execution_history,
                    execution_history,
                )

            start_time = time.time()

            # Execute tool
            result = await self.server_instance.call_tool(tool_name, args)

            execution_time = (time.time() - start_time) * 1000

            # Create execution record
            execution_record = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tool": tool_name,
                "arguments": args,
                "result": result,
                "execution_time_ms": execution_time,
                "status": "success",
            }

            # Add to history (keep last 10)
            new_history = execution_history + [execution_record]
            if len(new_history) > 10:
                new_history = new_history[-10:]

            success_status = f"""
            <div class="metric-card success-text">
                ✅ Tool executed successfully
                <br>Time: {execution_time:.2f}ms
            </div>
            """

            return (
                {
                    "tool": tool_name,
                    "arguments": args,
                    "result": result,
                    "execution_time_ms": execution_time,
                    "status": "success",
                },
                success_status,
                new_history,
                new_history,
            )

        try:
            return asyncio.run(_async_execute_with_history())
        except Exception as e:
            error_status = f'<div class="metric-card error-text">❌ Execution failed: {str(e)}</div>'
            return (
                {"error": str(e), "status": "failed"},
                error_status,
                execution_history,
                execution_history,
            )

    def _validate_json(self, json_text: str) -> str:
        """Validate JSON format."""
        try:
            json.loads(json_text)
            return '<div class="metric-card success-text">✅ Valid JSON format</div>'
        except json.JSONDecodeError as e:
            return (
                f'<div class="metric-card error-text">❌ Invalid JSON: {str(e)}</div>'
            )

    def _load_available_tools(self) -> list:
        """Load all available tools for display."""

        async def _async_load():
            tools = await self.server_instance.list_tools()
            return [
                [
                    tool.name,
                    tool.server_name,
                    tool.description[:50] + "...",
                    tool.usage_count,
                ]
                for tool in tools
            ]

        try:
            return asyncio.run(_async_load())
        except Exception as e:
            self.logger.error(f"Failed to load tools: {e}")
            return []

    def _get_current_config_yaml(self) -> str:
        """Get current configuration as YAML string."""
        try:
            config_dict = self.server_config.model_dump()
            return yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
        except Exception as e:
            self.logger.error(f"Failed to serialize config: {e}")
            return "# Error loading configuration"

    def _validate_config(self, config_yaml: str) -> str:
        """Validate YAML configuration."""
        try:
            # Parse YAML
            config_dict = yaml.safe_load(config_yaml)

            # Validate with Pydantic
            MetaMCPConfig(**config_dict)

            return "✅ Configuration is valid!"

        except yaml.YAMLError as e:
            return f"❌ YAML Parse Error: {str(e)}"
        except Exception as e:
            return f"❌ Validation Error: {str(e)}"

    def _save_config(self, config_yaml: str) -> tuple[str, dict]:
        """Save configuration to file."""
        try:
            # Validate first
            config_dict = yaml.safe_load(config_yaml)
            new_config = MetaMCPConfig(**config_dict)

            # Save to file (if we have a config path)
            if self.config_path:
                save_config(new_config, self.config_path)

            # Update server config
            self.server_config = new_config

            return "✅ Configuration saved successfully!", self._get_config_summary()

        except Exception as e:
            return f"❌ Save failed: {str(e)}", {}

    def _reload_config(self) -> tuple[str, str, dict]:
        """Reload configuration from file."""
        try:
            if self.config_path and Path(self.config_path).exists():
                self.server_config = load_config(self.config_path)
                return (
                    self._get_current_config_yaml(),
                    "✅ Configuration reloaded from file",
                    self._get_config_summary(),
                )
            else:
                return (
                    self._get_current_config_yaml(),
                    "⚠️ No config file found, showing current config",
                    self._get_config_summary(),
                )
        except Exception as e:
            return "", f"❌ Reload failed: {str(e)}", {}

    def _reset_config(self) -> tuple[str, str]:
        """Reset configuration to defaults."""
        try:
            default_config = MetaMCPConfig()
            config_yaml = yaml.dump(
                default_config.model_dump(), default_flow_style=False
            )
            return config_yaml, "⚠️ Configuration reset to defaults (not saved)"
        except Exception as e:
            return "", f"❌ Reset failed: {str(e)}"

    def _create_backup(self) -> str:
        """Create a backup of current configuration."""
        try:
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.config_backup = {
                "timestamp": timestamp,
                "config": self.server_config.model_dump(),
            }
            return f"✅ Backup created at {timestamp}"
        except Exception as e:
            return f"❌ Backup failed: {str(e)}"

    def _restore_backup(self) -> tuple[str, str]:
        """Restore configuration from backup."""
        try:
            if not self.config_backup:
                return "", "❌ No backup available"

            config_yaml = yaml.dump(
                self.config_backup["config"], default_flow_style=False
            )
            return (
                config_yaml,
                f"✅ Restored from backup ({self.config_backup['timestamp']})",
            )
        except Exception as e:
            return "", f"❌ Restore failed: {str(e)}"

    def _get_config_summary(self) -> dict:
        """Get configuration summary."""
        try:
            return {
                "server": f"{self.server_config.server.host}:{self.server_config.server.port}",
                "web_ui": f"{'Enabled' if self.server_config.web_ui.enabled else 'Disabled'}",
                "strategy": f"Primary: {self.server_config.strategy.primary}, Fallback: {self.server_config.strategy.fallback}",
                "child_servers": len(self.server_config.child_servers),
                "embeddings": self.server_config.embeddings.lm_studio_model,
                "vector_store": f"{self.server_config.vector_store.host}:{self.server_config.vector_store.port}",
            }
        except Exception:
            return {}

    def _get_server_status_html(self) -> str:
        """Get server status as HTML."""
        try:
            status = self.server_instance.get_status()
            uptime = status.get("uptime_seconds", 0)
            hours = uptime // 3600
            minutes = (uptime % 3600) // 60

            return f"""
            <div class="status-card">
                <h4>🟢 Server Running</h4>
                <p><strong>Name:</strong> {self.server_config.server.name}</p>
                <p><strong>Address:</strong> {self.server_config.server.host}:{self.server_config.server.port}</p>
                <p><strong>Uptime:</strong> {hours}h {minutes}m</p>
                <p><strong>Strategy:</strong> {self.server_config.strategy.primary}</p>
            </div>
            """
        except Exception:
            return '<div class="status-card"><h4>🔴 Server Status Unknown</h4></div>'

    def _refresh_status(self) -> tuple[str, dict, list, dict]:
        """Refresh all status information."""

        async def _async_refresh():
            # Server status
            status_html = self._get_server_status_html()

            # Metrics
            metrics = {}
            if hasattr(self.server_instance, "get_metrics"):
                metrics = await self.server_instance.get_metrics()

            # Child servers
            child_data = []
            if hasattr(self.server_instance, "child_manager"):
                child_status = (
                    await self.server_instance.child_manager.get_server_status()
                )
                for name, info in child_status.items():
                    child_data.append(
                        [
                            name,
                            "🟢 Running" if info.get("running") else "🔴 Stopped",
                            info.get("pid", "N/A"),
                            f"{info.get('uptime', 0)}s",
                            "Available",
                        ]
                    )

            # Health status
            health = {"status": "unknown", "message": "Health check not available"}

            return status_html, metrics, child_data, health

        try:
            return asyncio.run(_async_refresh())
        except Exception as e:
            return f"Error: {str(e)}", {}, [], {"error": str(e)}

    def _restart_child_server(self, server_name: str) -> list:
        """Restart a child server."""

        async def _async_restart():
            if hasattr(self.server_instance, "child_manager") and server_name:
                await self.server_instance.child_manager.restart_server(server_name)

            # Return updated child server status
            child_data = []
            if hasattr(self.server_instance, "child_manager"):
                child_status = (
                    await self.server_instance.child_manager.get_server_status()
                )
                for name, info in child_status.items():
                    child_data.append(
                        [
                            name,
                            "🟢 Running" if info.get("running") else "🔴 Stopped",
                            info.get("pid", "N/A"),
                            f"{info.get('uptime', 0)}s",
                            "Available",
                        ]
                    )

            return child_data

        try:
            return asyncio.run(_async_restart())
        except Exception as e:
            self.logger.error(f"Failed to restart server {server_name}: {e}")
            return []

    def _run_health_check(self) -> dict:
        """Run health check."""

        async def _async_health_check():
            # Import health checker
            from rich.console import Console

            from ..health.checker import HealthChecker

            # Run health check
            console = Console(file=open("/dev/null", "w"))  # Suppress output
            checker = HealthChecker(console)

            result = await checker.run_health_check(output_format="json", verbose=False)

            return result

        try:
            return asyncio.run(_async_health_check())
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    def _get_recent_logs(self, log_level: str = "INFO") -> str:
        """Get recent log entries."""
        try:
            log_file = Path(self.server_config.logging.file or "./logs/meta-server.log")

            if not log_file.exists():
                return "Log file not found"

            # Read last 100 lines
            with open(log_file) as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines

                # Filter by log level if specified
                if log_level != "ALL":
                    filtered_lines = [
                        line for line in recent_lines if log_level in line
                    ]
                    return "".join(filtered_lines)

                return "".join(recent_lines)

        except Exception as e:
            return f"Error reading logs: {str(e)}"

    def _validate_mcp_json(self, json_content: str) -> str:
        """Validate MCP server JSON configuration."""
        if not json_content.strip():
            return '<div class="metric-card warning-text">⚠️ Please enter JSON configuration</div>'

        try:
            config = json.loads(json_content)

            # Check for required structure
            if "mcpServers" not in config:
                return '<div class="metric-card error-text">❌ Missing "mcpServers" key in configuration</div>'

            servers = config["mcpServers"]
            if not isinstance(servers, dict):
                return '<div class="metric-card error-text">❌ "mcpServers" must be an object</div>'

            # Validate each server configuration
            server_count = 0
            for server_name, server_config in servers.items():
                if not isinstance(server_config, dict):
                    return f'<div class="metric-card error-text">❌ Server "{server_name}" configuration must be an object</div>'

                if "command" not in server_config:
                    return f'<div class="metric-card error-text">❌ Server "{server_name}" missing "command" field</div>'

                server_count += 1

            return f'<div class="metric-card success-text">✅ Valid MCP configuration with {server_count} servers</div>'

        except json.JSONDecodeError as e:
            return (
                f'<div class="metric-card error-text">❌ Invalid JSON: {str(e)}</div>'
            )
        except Exception as e:
            return f'<div class="metric-card error-text">❌ Validation error: {str(e)}</div>'

    def _load_json_from_file(self, file_path) -> tuple[str, str]:
        """Load JSON configuration from uploaded file."""
        if file_path is None:
            return "", '<div class="metric-card warning-text">⚠️ No file uploaded</div>'

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Validate the JSON content
            validation_result = self._validate_mcp_json(content)
            return content, validation_result

        except Exception as e:
            return (
                "",
                f'<div class="metric-card error-text">❌ Error reading file: {str(e)}</div>',
            )

    def _import_tools_from_json(
        self,
        json_content: str,
        merge_with_existing: bool,
        auto_generate_descriptions: bool,
        validate_commands: bool,
    ) -> tuple[str, dict[str, Any], list[Any]]:
        """Import tools from MCP server JSON configuration."""
        if not json_content.strip():
            return (
                '<div class="metric-card warning-text">⚠️ Please enter JSON configuration</div>',
                {},
                [],
            )

        try:
            config = json.loads(json_content)

            if "mcpServers" not in config:
                return (
                    '<div class="metric-card error-text">❌ Invalid configuration format</div>',
                    {},
                    [],
                )

            servers = config["mcpServers"]
            imported_tools: list[list[str]] = []
            import_stats: dict[str, Any] = {
                "servers_processed": 0,
                "tools_imported": 0,
                "errors": [],
                "warnings": [],
            }

            for server_name, server_config in servers.items():
                try:
                    command = server_config.get("command", "")
                    args = server_config.get("args", [])
                    # env = server_config.get("env", {})  # Currently unused

                    # Validate command if requested
                    if validate_commands:
                        import shutil

                        if not shutil.which(command):
                            import_stats["warnings"].append(
                                f"Command '{command}' not found in PATH for server '{server_name}'"
                            )

                    # Generate mock tools based on server type
                    tools = self._generate_tools_for_server(
                        server_name, command, args, auto_generate_descriptions
                    )

                    for tool in tools:
                        imported_tools.append(
                            [
                                tool["name"],
                                server_name,
                                command,
                                " ".join(args) if args else "",
                            ]
                        )

                    import_stats["servers_processed"] += 1
                    import_stats["tools_imported"] += len(tools)

                except Exception as e:
                    import_stats["errors"].append(
                        f"Error processing server '{server_name}': {str(e)}"
                    )
                    continue

            # Add tools to the server if merge_with_existing is True
            if merge_with_existing and hasattr(self.server_instance, "available_tools"):
                self._merge_imported_tools(imported_tools)
                merge_msg = " and merged with existing tools"
            else:
                merge_msg = ""

            status_html = f'<div class="metric-card success-text">✅ Imported {import_stats["tools_imported"]} tools from {import_stats["servers_processed"]} servers{merge_msg}</div>'

            if import_stats["errors"]:
                error_count = len(import_stats["errors"])
                status_html = f'<div class="metric-card warning-text">⚠️ Imported {import_stats["tools_imported"]} tools with {error_count} errors</div>'

            return status_html, import_stats, imported_tools

        except json.JSONDecodeError as e:
            return (
                f'<div class="metric-card error-text">❌ Invalid JSON: {str(e)}</div>',
                {"error": str(e)},
                [],
            )
        except Exception as e:
            return (
                f'<div class="metric-card error-text">❌ Import error: {str(e)}</div>',
                {"error": str(e)},
                [],
            )

    def _generate_tools_for_server(
        self,
        server_name: str,
        command: str,
        args: list,
        auto_generate_descriptions: bool,
    ) -> list[dict]:
        """Generate mock tools based on server configuration."""
        tools = []

        # Define common tool patterns for different MCP servers
        tool_patterns = {
            "filesystem": [
                {"name": "read_file", "description": "Read contents of a file"},
                {"name": "write_file", "description": "Write content to a file"},
                {"name": "list_directory", "description": "List files and directories"},
                {"name": "create_directory", "description": "Create a new directory"},
                {"name": "delete_file", "description": "Delete a file"},
                {"name": "move_file", "description": "Move or rename a file"},
                {"name": "search_files", "description": "Search for files by pattern"},
            ],
            "git": [
                {"name": "git_status", "description": "Get repository status"},
                {"name": "git_commit", "description": "Create a new commit"},
                {"name": "git_push", "description": "Push changes to remote"},
                {"name": "git_pull", "description": "Pull changes from remote"},
                {"name": "git_branch", "description": "Manage branches"},
                {"name": "git_log", "description": "View commit history"},
                {"name": "git_diff", "description": "Show differences between commits"},
            ],
            "brave-search": [
                {
                    "name": "web_search",
                    "description": "Search the web using Brave Search",
                },
                {"name": "news_search", "description": "Search for news articles"},
                {"name": "image_search", "description": "Search for images"},
            ],
            "github": [
                {
                    "name": "create_repository",
                    "description": "Create a new GitHub repository",
                },
                {"name": "list_repositories", "description": "List user repositories"},
                {"name": "create_issue", "description": "Create a new issue"},
                {"name": "list_issues", "description": "List repository issues"},
                {"name": "create_pull_request", "description": "Create a pull request"},
                {"name": "search_code", "description": "Search code in repositories"},
            ],
            "postgres": [
                {"name": "execute_query", "description": "Execute SQL query"},
                {"name": "list_tables", "description": "List database tables"},
                {"name": "describe_table", "description": "Get table schema"},
                {"name": "create_table", "description": "Create a new table"},
                {"name": "insert_data", "description": "Insert data into table"},
            ],
        }

        # Try to match server name or command to known patterns
        detected_type = None
        for pattern_name in tool_patterns.keys():
            if pattern_name in server_name.lower() or pattern_name in command.lower():
                detected_type = pattern_name
                break

        # Check args for patterns too
        if not detected_type and args:
            args_str = " ".join(args).lower()
            for pattern_name in tool_patterns.keys():
                if pattern_name in args_str:
                    detected_type = pattern_name
                    break

        if detected_type:
            tools = tool_patterns[detected_type].copy()
        else:
            # Generate generic tools if no pattern matches
            tools = [
                {"name": f"{server_name}_tool_1", "description": "Generic tool 1"},
                {"name": f"{server_name}_tool_2", "description": "Generic tool 2"},
                {
                    "name": f"{server_name}_execute",
                    "description": "Execute server command",
                },
            ]

        # Add server prefix to tool names and enhance descriptions
        for tool in tools:
            tool["name"] = f"{server_name}.{tool['name']}"
            if auto_generate_descriptions and detected_type:
                tool["description"] = (
                    f"{tool['description']} (via {server_name} server)"
                )

        return tools

    def _merge_imported_tools(self, imported_tools: list) -> None:
        """Merge imported tools with existing server tools."""
        try:
            from ..config.models import Tool

            # Convert imported tool data to Tool objects
            new_tools = []
            for tool_data in imported_tools:
                tool = Tool(
                    id=tool_data[0],  # name
                    name=tool_data[0].split(".")[-1],  # remove server prefix
                    server_name=tool_data[1],  # server
                    description=f"Tool from {tool_data[1]} server",
                    parameters={},
                    usage_count=0,
                    embedding=None,
                    last_used=None,
                )
                new_tools.append(tool)

            # Add to server's available tools
            if hasattr(self.server_instance, "available_tools"):
                # Remove duplicates by tool ID
                existing_ids = {
                    tool.id for tool in self.server_instance.available_tools
                }
                unique_new_tools = [
                    tool for tool in new_tools if tool.id not in existing_ids
                ]

                self.server_instance.available_tools.extend(unique_new_tools)
                self.logger.info(f"Added {len(unique_new_tools)} new tools to server")

        except Exception as e:
            self.logger.warning(f"Failed to merge imported tools: {e}")

    async def start(self) -> None:
        """Start the Gradio interface."""
        if not self.config.web_ui.enabled:
            return

        self.logger.info(
            "Starting Gradio web interface",
            host=self.config.web_ui.host,
            port=self.config.web_ui.port,
        )

        # Launch Gradio app
        self.app.launch(
            server_name=self.config.web_ui.host,
            server_port=self.config.web_ui.port,
            share=False,
            debug=False,
            prevent_thread_lock=True,
        )

    async def shutdown(self) -> None:
        """Shutdown the Gradio interface."""
        self.logger.info("Shutting down Gradio web interface")

        # Close Gradio app
        if hasattr(self.app, "close"):
            self.app.close()

        self.logger.info("Gradio web interface shutdown complete")

    def set_config_path(self, config_path: str) -> None:
        """Set the configuration file path."""
        self.config_path = config_path
