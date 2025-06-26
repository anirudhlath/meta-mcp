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
        server_config = load_config(config_path)
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
) -> None:
    """Validate a configuration file."""
    try:
        server_config = load_config(config)
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
