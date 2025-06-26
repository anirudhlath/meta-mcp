"""Docker service management for Meta MCP Server."""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger


class DockerManager:
    """Manages Docker services for the Meta MCP Server."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def is_docker_available(self) -> bool:
        """Check if Docker is available on the system.
        
        Returns:
            True if Docker is available.
        """
        return (
            shutil.which("docker") is not None and 
            shutil.which("docker-compose") is not None
        )

    async def is_docker_running(self) -> bool:
        """Check if Docker daemon is running.
        
        Returns:
            True if Docker daemon is responding.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception as e:
            self.logger.debug(f"Docker daemon check failed: {e}")
            return False

    async def check_compose_file(self) -> dict[str, Any]:
        """Check docker-compose.yml file.
        
        Returns:
            Information about the compose file.
        """
        compose_file = Path("docker-compose.yml")
        
        if not compose_file.exists():
            return {
                "exists": False,
                "path": str(compose_file),
                "services": [],
            }

        try:
            # Parse docker-compose file to get service names
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "config", "--services",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                services = [s.strip() for s in stdout.decode().split('\n') if s.strip()]
                return {
                    "exists": True,
                    "path": str(compose_file),
                    "services": services,
                    "valid": True,
                }
            else:
                return {
                    "exists": True,
                    "path": str(compose_file),
                    "services": [],
                    "valid": False,
                    "error": stderr.decode(),
                }
        except Exception as e:
            self.logger.debug(f"Failed to parse docker-compose file: {e}")
            return {
                "exists": True,
                "path": str(compose_file),
                "services": [],
                "valid": False,
                "error": str(e),
            }

    async def check_services_status(self) -> dict[str, bool]:
        """Check status of docker-compose services.
        
        Returns:
            Dict mapping service names to running status.
        """
        try:
            # Get list of services
            compose_info = await self.check_compose_file()
            if not compose_info["exists"] or not compose_info["valid"]:
                return {}

            services = compose_info["services"]
            results = {}

            # Check each service
            for service in services:
                is_running = await self._is_service_running(service)
                results[service] = is_running

            return results
        except Exception as e:
            self.logger.debug(f"Failed to check services status: {e}")
            return {}

    async def _is_service_running(self, service_name: str) -> bool:
        """Check if a specific service is running.
        
        Args:
            service_name: Name of the service to check.
            
        Returns:
            True if service is running.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "ps", "-q", service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            
            if process.returncode == 0 and stdout.strip():
                # Service container exists, check if it's running
                container_id = stdout.decode().strip()
                
                inspect_process = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "--format={{.State.Running}}", container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                inspect_stdout, _ = await inspect_process.communicate()
                
                if inspect_process.returncode == 0:
                    return inspect_stdout.decode().strip() == "true"
            
            return False
        except Exception as e:
            self.logger.debug(f"Failed to check service {service_name}: {e}")
            return False

    async def start_services(self, service_names: list[str] = None) -> dict[str, bool]:
        """Start Docker services.
        
        Args:
            service_names: List of service names to start. If None, starts all services.
            
        Returns:
            Dict mapping service names to start success status.
        """
        results = {}
        
        try:
            # If no specific services provided, start all
            if service_names is None:
                compose_info = await self.check_compose_file()
                if compose_info["exists"] and compose_info["valid"]:
                    service_names = compose_info["services"]
                else:
                    return {}

            # Start each service
            for service in service_names:
                success = await self._start_service(service)
                results[service] = success
                
                if success:
                    self.logger.info(f"Started Docker service: {service}")
                else:
                    self.logger.error(f"Failed to start Docker service: {service}")

        except Exception as e:
            self.logger.error(f"Failed to start services: {e}")
            
        return results

    async def _start_service(self, service_name: str) -> bool:
        """Start a specific Docker service.
        
        Args:
            service_name: Name of the service to start.
            
        Returns:
            True if service started successfully.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "up", "-d", service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Wait a moment for the service to initialize
                await asyncio.sleep(2)
                
                # Verify the service is actually running
                return await self._is_service_running(service_name)
            else:
                self.logger.debug(f"Failed to start {service_name}: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.debug(f"Exception starting {service_name}: {e}")
            return False

    async def stop_services(self, service_names: list[str] = None) -> dict[str, bool]:
        """Stop Docker services.
        
        Args:
            service_names: List of service names to stop. If None, stops all services.
            
        Returns:
            Dict mapping service names to stop success status.
        """
        results = {}
        
        try:
            if service_names is None:
                # Stop all services
                process = await asyncio.create_subprocess_exec(
                    "docker-compose", "down",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                results["all"] = process.returncode == 0
            else:
                # Stop specific services
                for service in service_names:
                    success = await self._stop_service(service)
                    results[service] = success

        except Exception as e:
            self.logger.error(f"Failed to stop services: {e}")
            
        return results

    async def _stop_service(self, service_name: str) -> bool:
        """Stop a specific Docker service.
        
        Args:
            service_name: Name of the service to stop.
            
        Returns:
            True if service stopped successfully.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "stop", service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception as e:
            self.logger.debug(f"Exception stopping {service_name}: {e}")
            return False

    async def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs from a Docker service.
        
        Args:
            service_name: Name of the service.
            lines: Number of lines to retrieve.
            
        Returns:
            Service logs as string.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "logs", "--tail", str(lines), service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode()
            return ""
        except Exception as e:
            self.logger.debug(f"Failed to get logs for {service_name}: {e}")
            return ""

    async def pull_images(self) -> bool:
        """Pull latest Docker images.
        
        Returns:
            True if pull was successful.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "pull",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to pull images: {e}")
            return False

    async def get_service_health(self, service_name: str) -> dict[str, Any]:
        """Get detailed health information for a service.
        
        Args:
            service_name: Name of the service.
            
        Returns:
            Detailed health information.
        """
        try:
            # Get container ID
            process = await asyncio.create_subprocess_exec(
                "docker-compose", "ps", "-q", service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            
            if process.returncode != 0 or not stdout.strip():
                return {
                    "running": False,
                    "healthy": False,
                    "container_id": None,
                }

            container_id = stdout.decode().strip()
            
            # Get container inspection data
            inspect_process = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            inspect_stdout, _ = await inspect_process.communicate()
            
            if inspect_process.returncode == 0:
                import json
                inspect_data = json.loads(inspect_stdout.decode())[0]
                state = inspect_data.get("State", {})
                
                return {
                    "running": state.get("Running", False),
                    "healthy": state.get("Health", {}).get("Status") == "healthy",
                    "health_status": state.get("Health", {}).get("Status"),
                    "container_id": container_id,
                    "start_time": state.get("StartedAt"),
                    "pid": state.get("Pid"),
                    "exit_code": state.get("ExitCode"),
                }
            else:
                return {
                    "running": False,
                    "healthy": False,
                    "container_id": container_id,
                    "error": "Failed to inspect container",
                }
                
        except Exception as e:
            self.logger.debug(f"Failed to get health for {service_name}: {e}")
            return {
                "running": False,
                "healthy": False,
                "container_id": None,
                "error": str(e),
            }