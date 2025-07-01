"""Main entry point for Meta MCP Server."""

import asyncio
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console

from .config.loader import load_config
from .config.models import MetaMCPConfig
from .health.checker import HealthChecker
from .server.meta_server import MetaMCPServer
from .utils.logging import setup_logging

console = Console()
app = typer.Typer(
    name="meta-mcp",
    help="Meta MCP Server with intelligent tool routing",
    no_args_is_help=True,
)


@app.command("run")
def run_server(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    mcp_servers_json: str | None = typer.Option(
        None,
        "--mcp-servers-json",
        help="Path to JSON file with MCP servers config (Claude Desktop format)",
    ),
    web_ui: bool = typer.Option(
        False,
        "--web-ui",
        help="Enable web UI interface",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        help="Server host (overrides config)",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="Server port (overrides config)",
    ),
    log_level: str | None = typer.Option(
        None,
        "--log-level",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload for development",
    ),
) -> None:
    """Start the Meta MCP Server."""

    # Load configuration
    try:
        config_path = config.value if hasattr(config, "value") else config
        server_config = load_config(config_path, mcp_servers_json)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Override config with CLI arguments
    if host:
        server_config.server.host = host
    if port:
        server_config.server.port = port
    if log_level:
        server_config.logging.level = log_level.upper()
    if web_ui:
        server_config.web_ui.enabled = True

    # Setup logging
    setup_logging(server_config.logging)
    logger = logging.getLogger(__name__)

    logger.info("Starting Meta MCP Server")
    logger.info(f"Configuration: {config or 'default'}")
    logger.info(f"Web UI: {'enabled' if server_config.web_ui.enabled else 'disabled'}")

    # Create and run server
    config_path_str = config.value if hasattr(config, "value") else config
    server = MetaMCPServer(server_config, config_path_str)

    try:
        if reload:
            # Development mode with auto-reload
            logger.info("Running in development mode with auto-reload")
            run_with_reload(server)
        else:
            # Production mode
            asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


def run_with_reload(server: MetaMCPServer) -> None:
    """Run server with auto-reload for development."""
    try:
        import watchdog.events  # noqa: F401
        import watchdog.observers  # noqa: F401
    except ImportError:
        console.print(
            "[yellow]Watchdog not installed, running without auto-reload[/yellow]"
        )
        asyncio.run(server.run())
        return

    # TODO: Implement file watching and auto-reload
    # For now, just run normally
    console.print("[yellow]Auto-reload not yet implemented, running normally[/yellow]")
    asyncio.run(server.run())


@app.command()
def validate_config(
    config: str = typer.Argument(help="Path to configuration file to validate"),
    mcp_servers_json: str | None = typer.Option(
        None,
        "--mcp-servers-json",
        help="Path to JSON file with MCP servers config (Claude Desktop format)",
    ),
) -> None:
    """Validate a configuration file."""
    try:
        server_config = load_config(config, mcp_servers_json)
        console.print("[green]✓ Configuration is valid[/green]")

        # Print summary
        console.print(f"Server: {server_config.server.name}")
        console.print(f"Strategy: {server_config.strategy.primary}")
        console.print(f"Child servers: {len(server_config.child_servers)}")
        console.print(
            f"Web UI: {'enabled' if server_config.web_ui.enabled else 'disabled'}"
        )

    except Exception as e:
        console.print(f"[red]✗ Configuration error: {e}[/red]")
        sys.exit(1)


@app.command()
def list_strategies() -> None:
    """List available tool selection strategies."""
    strategies = [
        ("vector", "Fast semantic similarity using embeddings"),
        ("llm", "AI-powered tool selection using local LLMs"),
        ("rag", "Context-augmented selection using retrieved documentation"),
    ]

    console.print("[bold]Available tool selection strategies:[/bold]\n")
    for name, description in strategies:
        console.print(f"  [blue]{name}[/blue]: {description}")


@app.command()
def debug_vector(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    query: str = typer.Option(
        "list files",
        "--query",
        "-q",
        help="Test query for vector search",
    ),
) -> None:
    """Debug vector search functionality."""

    async def run_debug():
        try:
            from .config.loader import load_config
            from .vector_store.qdrant_client import QdrantVectorStore

            server_config = load_config(config)
            console.print(f"[blue]Testing vector search with query: '{query}'[/blue]")
            console.print(
                f"[blue]Threshold: {server_config.strategy.vector_threshold}[/blue]\n"
            )

            # Initialize vector store
            vector_store = QdrantVectorStore(server_config)
            await vector_store.initialize()

            # Get collection info
            collection_info = await vector_store.get_collection_info()
            console.print("[bold]Collection Info:[/bold]")
            for collection, info in collection_info.items():
                console.print(f"  {collection}: {info.get('points_count', 0)} points")

            console.print()

        except Exception as e:
            console.print(f"[red]Debug failed: {e}[/red]")

    asyncio.run(run_debug())


@app.command()
def regenerate_embeddings(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    mcp_servers_json: str | None = typer.Option(
        None,
        "--mcp-servers-json", 
        help="Path to JSON file with MCP servers config",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force regeneration even if embeddings exist",
    ),
) -> None:
    """Regenerate tool embeddings to fix model mismatches."""
    
    async def run_regeneration():
        try:
            from .config.loader import load_config
            from .server.meta_server import MetaMCPServer
            
            console.print("[blue]Regenerating tool embeddings...[/blue]")
            
            # Load config and create server
            server_config = load_config(config, mcp_servers_json)
            server = MetaMCPServer(server_config, config)
            
            # Initialize server components
            await server.initialize()
            
            # Get all available tools
            tools = []
            for manager in server.child_server_managers.values():
                if manager.tools:
                    tools.extend(manager.tools.values())
            
            console.print(f"Found {len(tools)} tools to re-embed")
            
            if force:
                # Clear existing embeddings
                for tool in tools:
                    tool.embedding = None
                console.print("Cleared existing embeddings")
            
            # Regenerate embeddings using current embedding service
            if hasattr(server.tool_router, 'update_tool_embeddings'):
                await server.tool_router.update_tool_embeddings(tools)
                console.print(f"[green]✓ Successfully regenerated embeddings for {len(tools)} tools[/green]")
            else:
                console.print("[red]✗ Current router doesn't support embedding updates[/red]")
                
            await server.cleanup()
            
        except Exception as e:
            console.print(f"[red]Regeneration failed: {e}[/red]")
            import traceback
            if force:  # Show full traceback in debug mode
                traceback.print_exc()
    
    asyncio.run(run_regeneration())


@app.command()
def init_config(
    output: str = typer.Option(
        "meta-server.yaml",
        "--output",
        "-o",
        help="Output configuration file path",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing file",
    ),
) -> None:
    """Initialize a new configuration file with defaults."""
    output_path = Path(output)

    if output_path.exists() and not force:
        console.print(
            f"[red]File {output} already exists. Use --force to overwrite.[/red]"
        )
        sys.exit(1)

    # Create default config
    default_config = MetaMCPConfig()

    # Save to file
    from .config.loader import save_config

    save_config(default_config, str(output_path))

    console.print(f"[green]✓ Configuration file created: {output}[/green]")
    console.print("Edit the file to add your child servers and customize settings.")


@app.command()
def health(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    mcp_servers_json: str | None = typer.Option(
        None,
        "--mcp-servers-json",
        help="Path to JSON file with MCP servers config (Claude Desktop format)",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Automatically fix issues where possible",
    ),
    setup_docker: bool = typer.Option(
        False,
        "--setup-docker",
        help="Start required Docker services",
    ),
    download_models: bool = typer.Option(
        False,
        "--download-models",
        help="Download missing models",
    ),
    output_format: str = typer.Option(
        "text",
        "--output-format",
        help="Output format (text|json)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """Check system health and dependencies."""

    async def run_health_check():
        checker = HealthChecker(console)
        result = await checker.run_health_check(
            config_path=config,
            mcp_servers_json=mcp_servers_json,
            fix_issues=fix,
            setup_docker=setup_docker,
            download_models=download_models,
            verbose=verbose,
            output_format=output_format,
        )

        # Handle output format
        if output_format == "json":
            import json

            # Print JSON to stdout for proper parsing
            print(json.dumps(result, indent=2))
            if result.get("summary", {}).get("issues_found", 0) > 0:
                sys.exit(1)
        else:
            # Text output already displayed by the checker
            summary = result.get("summary", {})
            if summary.get("issues_found", 0) > 0:
                sys.exit(1)

    try:
        asyncio.run(run_health_check())
    except KeyboardInterrupt:
        console.print("\n[yellow]Health check interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        if verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    app()
