"""Child server manager for spawning and managing MCP servers."""

import asyncio
import os
import shutil
from typing import Any

from ..config.models import ChildServerConfig, MetaMCPConfig, Tool
from ..utils.logging import get_logger
from .client import ChildServerClient


class ChildServerManager:
    """Manages child MCP server processes and their lifecycle."""

    def __init__(self, config: MetaMCPConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.servers: dict[str, dict[str, Any]] = {}
        self.clients: dict[str, ChildServerClient] = {}
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize and start all enabled child servers."""
        self.logger.info("Initializing child server manager")

        for server_config in self.config.child_servers:
            if server_config.enabled:
                await self._start_server(server_config)

        self.logger.info(
            f"Child server manager initialized with {len(self.servers)} servers"
        )

    async def _start_server(self, server_config: ChildServerConfig) -> None:
        """Start a single child server.

        Args:
            server_config: Configuration for the server to start.
        """
        try:
            self.logger.info(f"Starting child server: {server_config.name}")

            # Validate command exists
            command_name = server_config.command[0] if server_config.command else ""
            command_path = shutil.which(command_name)
            if not command_path:
                # Try with full environment
                full_env = {**os.environ, **server_config.env}
                command_path = shutil.which(command_name, path=full_env.get('PATH'))
                
            if not command_path:
                installation_help = self._get_installation_help(command_name)
                current_path = os.environ.get('PATH', '')
                raise FileNotFoundError(
                    f"Command '{command_name}' not found in PATH. {installation_help}\n"
                    f"Current PATH: {current_path[:200]}{'...' if len(current_path) > 200 else ''}"
                )
            else:
                self.logger.debug(f"Found command '{command_name}' at: {command_path}")

            # Start subprocess with inherited environment
            # Combine current environment with server-specific env vars
            full_env = {**os.environ, **server_config.env}
            
            self.logger.debug(f"Starting subprocess with command: {server_config.command}")
            try:
                process = await asyncio.create_subprocess_exec(
                    *server_config.command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=full_env,
                )
            except FileNotFoundError as e:
                # More specific error for subprocess creation failure
                raise FileNotFoundError(
                    f"Failed to start subprocess for '{command_name}'. "
                    f"Command path: {command_path}. "
                    f"Original error: {e}. "
                    f"Try running '{' '.join(server_config.command)}' manually to debug."
                ) from e

            # Create client for communication
            client = ChildServerClient(
                server_config.name, process, self.config, self.logger
            )

            # Initialize client and discover tools
            await client.initialize()

            # Store server info
            self.servers[server_config.name] = {
                "config": server_config,
                "process": process,
                "status": "running",
                "start_time": asyncio.get_event_loop().time(),
            }
            self.clients[server_config.name] = client

            self.logger.info(
                "Child server started successfully",
                server=server_config.name,
                pid=process.pid,
                tools_discovered=len(client.tools),
            )

        except Exception as e:
            self.logger.error(
                "Failed to start child server",
                server=server_config.name,
                error=str(e),
            )
            # Mark as failed
            self.servers[server_config.name] = {
                "config": server_config,
                "process": None,
                "status": "failed",
                "error": str(e),
            }

    async def get_all_tools(self) -> list[Tool]:
        """Get all tools from all running child servers.

        Returns:
            List of all available tools.
        """
        all_tools = []
        for client in self.clients.values():
            all_tools.extend(client.tools)
        return all_tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on the appropriate child server.

        Args:
            tool_name: Name of the tool (format: server.tool_name).
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If tool name format is invalid or server not found.
        """
        if "." not in tool_name:
            raise ValueError(f"Invalid tool name format: {tool_name}")

        server_name, actual_tool_name = tool_name.split(".", 1)

        if server_name not in self.clients:
            raise ValueError(f"Server not found: {server_name}")

        client = self.clients[server_name]
        return await client.call_tool(actual_tool_name, arguments)

    async def restart_server(self, server_name: str) -> bool:
        """Restart a specific child server.

        Args:
            server_name: Name of the server to restart.

        Returns:
            True if restart was successful, False otherwise.
        """
        try:
            self.logger.info(f"Restarting child server: {server_name}")

            # Stop existing server
            await self._stop_server(server_name)

            # Find config and restart
            server_config = None
            for config in self.config.child_servers:
                if config.name == server_name:
                    server_config = config
                    break

            if not server_config:
                self.logger.error(f"No config found for server: {server_name}")
                return False

            # Start server again
            await self._start_server(server_config)
            return True

        except Exception as e:
            self.logger.error(
                "Failed to restart server", server=server_name, error=str(e)
            )
            return False

    async def _stop_server(self, server_name: str) -> None:
        """Stop a specific child server.

        Args:
            server_name: Name of the server to stop.
        """
        if server_name in self.servers:
            server_info = self.servers[server_name]
            process = server_info.get("process")

            if process and process.returncode is None:
                try:
                    # Try graceful shutdown first
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    # Force kill if graceful shutdown failed
                    process.kill()
                    await process.wait()

            # Clean up
            if server_name in self.clients:
                await self.clients[server_name].cleanup()
                del self.clients[server_name]

            del self.servers[server_name]

    async def get_server_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all child servers.

        Returns:
            Dictionary with server status information.
        """
        status = {}
        for name, server_info in self.servers.items():
            process = server_info.get("process")
            client = self.clients.get(name)

            status[name] = {
                "status": server_info["status"],
                "pid": process.pid if process else None,
                "tools_count": len(client.tools) if client else 0,
                "uptime": (
                    asyncio.get_event_loop().time() - server_info.get("start_time", 0)
                    if server_info["status"] == "running"
                    else 0
                ),
                "error": server_info.get("error"),
            }

        return status

    async def health_check(self) -> None:
        """Perform health check on all servers and restart failed ones."""
        for server_name, server_info in list(self.servers.items()):
            if server_info["status"] == "running":
                process = server_info.get("process")
                if process and process.returncode is not None:
                    # Process has died
                    self.logger.warning(
                        "Child server died, restarting",
                        server=server_name,
                        return_code=process.returncode,
                    )
                    await self.restart_server(server_name)

    async def shutdown(self) -> None:
        """Shutdown all child servers gracefully."""
        self.logger.info("Shutting down child server manager")

        # Stop all servers
        shutdown_tasks = []
        for server_name in list(self.servers.keys()):
            shutdown_tasks.append(self._stop_server(server_name))

        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)

        self.logger.info("Child server manager shutdown complete")

    async def reload_configuration(self, new_config: MetaMCPConfig) -> None:
        """Reload configuration and restart servers if needed.

        Args:
            new_config: New configuration to apply.
        """
        self.logger.info("Reloading child server configuration")

        # Stop servers that are no longer in config or disabled
        current_names = {
            config.name for config in new_config.child_servers if config.enabled
        }
        for server_name in list(self.servers.keys()):
            if server_name not in current_names:
                await self._stop_server(server_name)

        # Start new servers or restart changed ones
        for server_config in new_config.child_servers:
            if server_config.enabled:
                if server_config.name not in self.servers:
                    # New server
                    await self._start_server(server_config)
                else:
                    # Check if config changed (simple comparison)
                    old_config = self.servers[server_config.name]["config"]
                    if (
                        old_config.command != server_config.command
                        or old_config.env != server_config.env
                    ):
                        # Restart with new config
                        await self.restart_server(server_config.name)

        self.config = new_config
        self.logger.info("Child server configuration reloaded")

    def _get_installation_help(self, command_name: str) -> str:
        """Get installation help for missing commands.
        
        Args:
            command_name: The missing command name.
            
        Returns:
            Installation help message.
        """
        if command_name == "uvx":
            return (
                "To install uvx, run: 'pip install uv && uv tool install uvx' or use 'pip install uv && uv tool install @astral-sh/uvx'. "
                "If uvx is already installed, ensure it's in your PATH environment variable. "
                "You can also use npx as an alternative by changing 'uvx' to 'npx' in your configuration, "
                "or use the JSON import feature in the web UI to add tools manually."
            )
        elif command_name == "npx":
            return (
                "To install npx, install Node.js from https://nodejs.org/ or run 'brew install node'. "
                "Alternatively, use the JSON import feature in the web UI to add tools manually."
            )
        else:
            return (
                f"Please install '{command_name}' or update your configuration to use an available command. "
                "You can also use the JSON import feature in the web UI to add tools manually."
            )
