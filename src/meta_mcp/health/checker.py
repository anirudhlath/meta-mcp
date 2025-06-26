"""Main health checker for Meta MCP Server system."""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config.loader import load_config
from ..config.models import MetaMCPConfig
from .dependency_checker import DependencyChecker
from .docker_manager import DockerManager
from .setup_manager import SetupManager


class HealthStatus(Enum):
    """Health check status."""

    PASS = "✓"
    FAIL = "✗"
    WARN = "⚠️"
    NA = "N/A"


@dataclass
class HealthResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    details: dict[str, Any] = None
    fix_suggestion: str = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class HealthChecker:
    """Main health checker for the Meta MCP Server system."""

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self.results: list[HealthResult] = []
        self.dependency_checker = DependencyChecker()
        self.docker_manager = DockerManager()
        self.setup_manager = SetupManager()

    async def run_health_check(
        self,
        config_path: str = None,
        fix_issues: bool = False,
        setup_docker: bool = False,
        download_models: bool = False,
        verbose: bool = False,
        output_format: str = "text",
    ) -> dict[str, Any]:
        """Run comprehensive health check.

        Args:
            config_path: Path to configuration file
            fix_issues: Automatically fix issues where possible
            setup_docker: Start required Docker services
            download_models: Download missing models
            verbose: Show detailed output
            output_format: Output format (text|json)

        Returns:
            Health check results
        """
        self.results.clear()

        # Load configuration
        config = await self._check_configuration(config_path)
        if not config:
            return self._generate_output(output_format)

        # Run all health checks
        await self._check_file_system(config, fix_issues)
        await self._check_docker_services(setup_docker, verbose)
        await self._check_dependencies(config, download_models, verbose)
        await self._check_network_connectivity(config, verbose)
        await self._check_models_and_services(config, download_models, verbose)

        # Apply fixes if requested
        if fix_issues:
            await self._apply_fixes(config, verbose)

        return self._generate_output(output_format)

    async def _check_configuration(self, config_path: str = None) -> MetaMCPConfig | None:
        """Check configuration file validity."""
        try:
            config = load_config(config_path)
            self.results.append(
                HealthResult(
                    name="Configuration",
                    status=HealthStatus.PASS,
                    message=f"Configuration valid ({config_path or 'default'})",
                    details={
                        "server_name": config.server.name,
                        "strategy": config.strategy.primary,
                        "child_servers": len(config.child_servers),
                        "web_ui_enabled": config.web_ui.enabled,
                    },
                )
            )
            return config
        except Exception as e:
            self.results.append(
                HealthResult(
                    name="Configuration",
                    status=HealthStatus.FAIL,
                    message=f"Configuration error: {e}",
                    fix_suggestion="Run 'meta-mcp init-config' to create a valid configuration",
                )
            )
            return None

    async def _check_file_system(self, config: MetaMCPConfig, fix_issues: bool):
        """Check file system requirements."""
        required_dirs = [
            Path(config.logging.file).parent,
            Path(config.embeddings.cache_dir),
            Path("./docs"),
        ]

        missing_dirs = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing_dirs.append(str(dir_path))

        if missing_dirs:
            status = HealthStatus.WARN if fix_issues else HealthStatus.FAIL
            message = f"Missing directories: {', '.join(missing_dirs)}"
            fix_suggestion = "Directories will be created automatically" if fix_issues else "Run with --fix to create directories"
            
            self.results.append(
                HealthResult(
                    name="File System",
                    status=status,
                    message=message,
                    details={"missing_dirs": missing_dirs},
                    fix_suggestion=fix_suggestion,
                )
            )
        else:
            self.results.append(
                HealthResult(
                    name="File System",
                    status=HealthStatus.PASS,
                    message="All required directories exist",
                )
            )

    async def _check_docker_services(self, setup_docker: bool, verbose: bool):
        """Check Docker daemon and services."""
        docker_available = await self.docker_manager.is_docker_available()
        
        if not docker_available:
            self.results.append(
                HealthResult(
                    name="Docker",
                    status=HealthStatus.NA,
                    message="Docker not available",
                    details={"docker_available": False},
                    fix_suggestion="Install Docker to use containerized services",
                )
            )
            return

        # Check docker-compose file
        compose_file = Path("docker-compose.yml")
        if not compose_file.exists():
            self.results.append(
                HealthResult(
                    name="Docker Compose",
                    status=HealthStatus.WARN,
                    message="docker-compose.yml not found",
                    fix_suggestion="Ensure docker-compose.yml is in the project root",
                )
            )
            return

        # Check service status
        services_status = await self.docker_manager.check_services_status()
        
        running_services = [name for name, running in services_status.items() if running]
        stopped_services = [name for name, running in services_status.items() if not running]

        if stopped_services:
            status = HealthStatus.WARN if setup_docker else HealthStatus.FAIL
            message = f"Services not running: {', '.join(stopped_services)}"
            fix_suggestion = "Services will be started" if setup_docker else "Run with --setup-docker to start services"
        else:
            status = HealthStatus.PASS
            message = f"All services running: {', '.join(running_services)}"
            fix_suggestion = None

        self.results.append(
            HealthResult(
                name="Docker Services",
                status=status,
                message=message,
                details={
                    "running_services": running_services,
                    "stopped_services": stopped_services,
                },
                fix_suggestion=fix_suggestion,
            )
        )

    async def _check_dependencies(self, config: MetaMCPConfig, download_models: bool, verbose: bool):
        """Check system dependencies."""
        # Check Python packages
        missing_packages = await self.dependency_checker.check_python_packages()
        if missing_packages:
            self.results.append(
                HealthResult(
                    name="Python Dependencies",
                    status=HealthStatus.FAIL,
                    message=f"Missing packages: {', '.join(missing_packages)}",
                    details={"missing_packages": missing_packages},
                    fix_suggestion="Run 'uv sync' to install missing packages",
                )
            )
        else:
            self.results.append(
                HealthResult(
                    name="Python Dependencies",
                    status=HealthStatus.PASS,
                    message="All required packages installed",
                )
            )

        # Check child server commands
        for server_config in config.child_servers:
            if server_config.enabled:
                is_available = await self.dependency_checker.check_command_available(server_config.command[0])
                status = HealthStatus.PASS if is_available else HealthStatus.WARN
                message = f"Command '{server_config.command[0]}' {'available' if is_available else 'not found'}"
                
                self.results.append(
                    HealthResult(
                        name=f"Child Server: {server_config.name}",
                        status=status,
                        message=message,
                        details={"command": server_config.command},
                        fix_suggestion=None if is_available else f"Install or configure {server_config.command[0]}",
                    )
                )

    async def _check_network_connectivity(self, config: MetaMCPConfig, verbose: bool):
        """Check network connectivity to configured services."""
        # Check LM Studio
        if config.embeddings.lm_studio_endpoint:
            lm_studio_healthy = await self.dependency_checker.check_lm_studio_connectivity(
                config.embeddings.lm_studio_endpoint
            )
            status = HealthStatus.PASS if lm_studio_healthy else HealthStatus.WARN
            message = f"LM Studio {'available' if lm_studio_healthy else 'not responding'}"
            
            self.results.append(
                HealthResult(
                    name="LM Studio Connectivity",
                    status=status,
                    message=message,
                    details={"endpoint": config.embeddings.lm_studio_endpoint},
                    fix_suggestion=None if lm_studio_healthy else "Start LM Studio or check endpoint configuration",
                )
            )

        # Check Qdrant
        qdrant_healthy = await self.dependency_checker.check_qdrant_connectivity(
            config.vector_store.host, config.vector_store.port
        )
        status = HealthStatus.PASS if qdrant_healthy else HealthStatus.FAIL
        message = f"Qdrant {'available' if qdrant_healthy else 'not responding'}"
        
        self.results.append(
            HealthResult(
                name="Qdrant Connectivity",
                status=status,
                message=message,
                details={
                    "host": config.vector_store.host,
                    "port": config.vector_store.port,
                },
                fix_suggestion=None if qdrant_healthy else "Start Qdrant with 'docker-compose up qdrant' or check configuration",
            )
        )

    async def _check_models_and_services(self, config: MetaMCPConfig, download_models: bool, verbose: bool):
        """Check model availability and service functionality."""
        # Check LM Studio models
        if config.embeddings.lm_studio_endpoint:
            models = await self.dependency_checker.get_available_models(
                config.embeddings.lm_studio_endpoint
            )
            
            if models:
                target_model = config.embeddings.lm_studio_model
                model_available = target_model in models
                status = HealthStatus.PASS if model_available else HealthStatus.WARN
                message = f"LM Studio model '{target_model}' {'available' if model_available else 'not found'}"
                
                self.results.append(
                    HealthResult(
                        name="LM Studio Models",
                        status=status,
                        message=message,
                        details={
                            "target_model": target_model,
                            "available_models": models,
                        },
                        fix_suggestion=None if model_available else f"Load model '{target_model}' in LM Studio",
                    )
                )

        # Check fallback model
        fallback_available = await self.dependency_checker.check_fallback_model(
            config.embeddings.fallback_model,
            config.embeddings.cache_dir,
        )
        
        status = HealthStatus.PASS if fallback_available else HealthStatus.WARN
        message = f"Fallback model '{config.embeddings.fallback_model}' {'available' if fallback_available else 'not cached'}"
        fix_suggestion = None if fallback_available else "Model will be downloaded on first use" if download_models else "Run with --download-models to pre-download"
        
        self.results.append(
            HealthResult(
                name="Fallback Model",
                status=status,
                message=message,
                details={"model": config.embeddings.fallback_model},
                fix_suggestion=fix_suggestion,
            )
        )

    async def _apply_fixes(self, config: MetaMCPConfig, verbose: bool):
        """Apply automatic fixes for detected issues."""
        if verbose:
            self.console.print("\n[bold blue]Applying fixes...[/bold blue]")

        # Create missing directories
        await self.setup_manager.create_directories(config)
        
        # Start Docker services if needed
        docker_result = next((r for r in self.results if r.name == "Docker Services"), None)
        if docker_result and docker_result.status == HealthStatus.WARN:
            await self.docker_manager.start_services(["qdrant"])

        # Initialize Qdrant collections
        qdrant_result = next((r for r in self.results if r.name == "Qdrant Connectivity"), None)
        if qdrant_result and qdrant_result.status == HealthStatus.PASS:
            await self.setup_manager.initialize_qdrant_collections(config)

    def _generate_output(self, output_format: str) -> dict[str, Any]:
        """Generate formatted output."""
        if output_format == "json":
            return self._generate_json_output()
        else:
            self._display_text_output()
            return self._generate_summary()

    def _generate_json_output(self) -> dict[str, Any]:
        """Generate JSON output."""
        return {
            "status": "pass" if all(r.status == HealthStatus.PASS for r in self.results) else "fail",
            "summary": self._generate_summary(),
            "results": [
                {
                    "name": result.name,
                    "status": result.status.name.lower(),
                    "message": result.message,
                    "details": result.details,
                    "fix_suggestion": result.fix_suggestion,
                }
                for result in self.results
            ],
        }

    def _display_text_output(self):
        """Display formatted text output."""
        self.console.print("\n[bold blue]Meta MCP Server Health Check[/bold blue]")
        self.console.print("═" * 30)

        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Message", style="white")

        for result in self.results:
            # Color status based on result
            if result.status == HealthStatus.PASS:
                status_text = Text(result.status.value, style="green")
            elif result.status == HealthStatus.FAIL:
                status_text = Text(result.status.value, style="red")
            elif result.status == HealthStatus.WARN:
                status_text = Text(result.status.value, style="yellow")
            else:
                status_text = Text(result.status.value, style="dim")

            table.add_row(result.name, status_text, result.message)

        self.console.print(table)

        # Show fix suggestions
        fix_suggestions = [r for r in self.results if r.fix_suggestion]
        if fix_suggestions:
            self.console.print("\n[bold yellow]Suggestions:[/bold yellow]")
            for result in fix_suggestions:
                self.console.print(f"  • {result.name}: {result.fix_suggestion}")

        # Show summary
        summary = self._generate_summary()
        self.console.print(f"\n[bold]Summary:[/bold] {summary['issues_found']} issues found")
        
        if summary['issues_found'] > 0:
            self.console.print("Run with --fix to automatically resolve some issues")

    def _generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == HealthStatus.PASS)
        failed = sum(1 for r in self.results if r.status == HealthStatus.FAIL)
        warnings = sum(1 for r in self.results if r.status == HealthStatus.WARN)
        na = sum(1 for r in self.results if r.status == HealthStatus.NA)

        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "not_applicable": na,
            "issues_found": failed + warnings,
            "overall_health": "healthy" if failed == 0 else "issues_detected",
        }