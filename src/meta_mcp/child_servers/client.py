"""MCP client for communicating with child servers over stdio."""

import asyncio
import json
from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..utils.logging import StructuredLogger


class MCPProtocolError(Exception):
    """Exception raised for MCP protocol errors."""

    pass


class ChildServerClient:
    """Client for communicating with a child MCP server via stdio."""

    def __init__(
        self,
        server_name: str,
        process: asyncio.subprocess.Process,
        config: MetaMCPConfig,
        logger: StructuredLogger,
    ):
        self.server_name = server_name
        self.process = process
        self.config = config
        self.logger = logger
        self.tools: list[Tool] = []
        self.resources: list[dict[str, Any]] = []
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize the client and perform handshake."""
        try:
            # Start reading responses
            self._read_task = asyncio.create_task(self._read_responses())

            # Perform MCP handshake
            await self._handshake()

            # Discover available tools and resources
            await self._discover_capabilities()

            self.logger.info(
                "MCP client initialized",
                server=self.server_name,
                tools=len(self.tools),
                resources=len(self.resources),
            )

        except Exception as e:
            self.logger.error(
                "Failed to initialize MCP client",
                server=self.server_name,
                error=str(e),
            )
            raise

    async def _handshake(self) -> None:
        """Perform MCP initialization handshake."""
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "clientInfo": {
                    "name": "meta-mcp-client",
                    "version": "0.1.0",
                },
            },
        }

        response = await self._send_request(init_request)

        if "error" in response:
            raise MCPProtocolError(f"Handshake failed: {response['error']}")

        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }

        await self._send_notification(initialized_notification)

    async def _discover_capabilities(self) -> None:
        """Discover tools and resources from the server."""
        # Discover tools
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": self._get_request_id(),
                "method": "tools/list",
            }

            response = await self._send_request(tools_request)
            if "result" in response and "tools" in response["result"]:
                for tool_data in response["result"]["tools"]:
                    tool = self._create_tool_from_response(tool_data)
                    self.tools.append(tool)

        except Exception as e:
            self.logger.warning(
                "Failed to discover tools",
                server=self.server_name,
                error=str(e),
            )

        # Discover resources
        try:
            resources_request = {
                "jsonrpc": "2.0",
                "id": self._get_request_id(),
                "method": "resources/list",
            }

            response = await self._send_request(resources_request)
            if "result" in response and "resources" in response["result"]:
                self.resources = response["result"]["resources"]

        except Exception as e:
            self.logger.warning(
                "Failed to discover resources",
                server=self.server_name,
                error=str(e),
            )

    def _create_tool_from_response(self, tool_data: dict[str, Any]) -> Tool:
        """Create a Tool object from MCP response data.

        Args:
            tool_data: Tool data from MCP response.

        Returns:
            Tool object with meta-server specific fields.
        """
        return Tool(
            id=f"{self.server_name}.{tool_data['name']}",
            name=tool_data["name"],
            server_name=self.server_name,
            description=tool_data.get("description", ""),
            parameters=tool_data.get("inputSchema", {}),
            examples=[],  # Will be populated from documentation if available
        )

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on the child server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            MCPProtocolError: If the tool call fails.
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            response = await self._send_request(request)

            if "error" in response:
                raise MCPProtocolError(f"Tool call failed: {response['error']}")

            self.logger.debug(
                "Tool call successful",
                server=self.server_name,
                tool=tool_name,
            )

            return response.get("result", {})

        except Exception as e:
            self.logger.error(
                "Tool call failed",
                server=self.server_name,
                tool=tool_name,
                error=str(e),
            )
            raise

    async def _send_request(
        self, request: dict[str, Any], timeout: float = 30.0
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response.

        Args:
            request: JSON-RPC request object.
            timeout: Request timeout in seconds.

        Returns:
            JSON-RPC response object.

        Raises:
            MCPProtocolError: If request fails or times out.
        """
        request_id = request["id"]
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Send request
            await self._write_message(request)

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except TimeoutError:
            raise MCPProtocolError(f"Request timeout: {request_id}")
        finally:
            self._pending_requests.pop(request_id, None)

    async def _send_notification(self, notification: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            notification: JSON-RPC notification object.
        """
        await self._write_message(notification)

    async def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the process stdin.

        Args:
            message: JSON-RPC message to send.

        Raises:
            MCPProtocolError: If writing fails.
        """
        try:
            json_str = json.dumps(message) + "\n"
            self.process.stdin.write(json_str.encode("utf-8"))
            await self.process.stdin.drain()

        except Exception as e:
            raise MCPProtocolError(f"Failed to write message: {e}")

    async def _read_responses(self) -> None:
        """Read and process responses from the child server."""
        try:
            while self.process.returncode is None:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode("utf-8").strip())
                    await self._handle_message(message)

                except json.JSONDecodeError as e:
                    self.logger.warning(
                        "Invalid JSON received",
                        server=self.server_name,
                        error=str(e),
                        line=line.decode("utf-8", errors="replace"),
                    )

        except Exception as e:
            self.logger.error(
                "Error reading responses",
                server=self.server_name,
                error=str(e),
            )

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle an incoming JSON-RPC message.

        Args:
            message: Parsed JSON-RPC message.
        """
        if "id" in message:
            # Response to a request
            request_id = message["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests[request_id]
                if not future.done():
                    future.set_result(message)
        else:
            # Notification - log it
            self.logger.debug(
                "Received notification",
                server=self.server_name,
                method=message.get("method"),
            )

    def _get_request_id(self) -> int:
        """Get next request ID.

        Returns:
            Unique request ID.
        """
        self._request_id += 1
        return self._request_id

    async def cleanup(self) -> None:
        """Clean up the client and close connections."""
        self.logger.debug("Cleaning up MCP client", server=self.server_name)

        # Cancel read task
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # Cancel any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()

        self._pending_requests.clear()

        # Close process streams
        if self.process.stdin and not self.process.stdin.is_closing():
            self.process.stdin.close()
            await self.process.stdin.wait_closed()
