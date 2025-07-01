"""Dependency checker for external services and packages."""

import asyncio
import importlib.util
import shutil
from pathlib import Path
from typing import Any

import httpx

from ..utils.logging import get_logger


class DependencyChecker:
    """Checks dependencies and external service availability."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def check_python_packages(self) -> list[str]:
        """Check for required Python packages.

        Returns:
            List of missing package names.
        """
        required_packages = [
            "qdrant_client",
            "sentence_transformers",
            "httpx",
            "fastapi",
            "uvicorn",
            "pydantic",
            "typer",
            "rich",
            "yaml",
        ]

        missing_packages = []
        for package in required_packages:
            # Handle package name variations
            import_name = package
            if package == "yaml":
                import_name = "yaml"

            if importlib.util.find_spec(import_name) is None:
                missing_packages.append(package)

        return missing_packages

    async def check_command_available(self, command: str) -> bool:
        """Check if a command is available in the system PATH.

        Args:
            command: Command name to check.

        Returns:
            True if command is available.
        """
        return shutil.which(command) is not None

    async def check_lm_studio_connectivity(self, endpoint: str) -> bool:
        """Check LM Studio connectivity.

        Args:
            endpoint: LM Studio endpoint URL.

        Returns:
            True if LM Studio is responding.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check if the base endpoint is responding
                base_url = endpoint.rstrip("/v1").rstrip("/")
                response = await client.get(f"{base_url}/v1/models")
                return response.status_code == 200
        except Exception as e:
            self.logger.debug(f"LM Studio connectivity check failed: {e}")
            return False

    async def check_qdrant_connectivity(self, host: str, port: int) -> bool:
        """Check Qdrant connectivity.

        Args:
            host: Qdrant host.
            port: Qdrant port.

        Returns:
            True if Qdrant is responding.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Qdrant doesn't have /health endpoint, use /collections instead
                response = await client.get(f"http://{host}:{port}/collections")
                return response.status_code == 200
        except Exception as e:
            self.logger.debug(f"Qdrant connectivity check failed: {e}")
            return False

    async def get_available_models(self, endpoint: str) -> list[str]:
        """Get list of available models from LM Studio.

        Args:
            endpoint: LM Studio endpoint URL.

        Returns:
            List of available model names.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                base_url = endpoint.rstrip("/v1").rstrip("/")
                response = await client.get(f"{base_url}/v1/models")

                if response.status_code == 200:
                    data = response.json()
                    return [model.get("id", "") for model in data.get("data", [])]
                return []
        except Exception as e:
            self.logger.debug(f"Failed to get available models: {e}")
            return []

    async def check_fallback_model(self, model_name: str, cache_dir: str) -> bool:
        """Check if fallback embedding model is available.

        Args:
            model_name: Model name to check.
            cache_dir: Cache directory path.

        Returns:
            True if model is cached locally.
        """
        try:
            cache_path = Path(cache_dir)
            if not cache_path.exists():
                return False

            # Check for sentence-transformers model cache
            model_cache_path = cache_path / "sentence-transformers" / model_name
            if model_cache_path.exists():
                return True

            # Also check for HuggingFace transformers cache
            hf_cache_path = cache_path / "transformers" / model_name
            if hf_cache_path.exists():
                return True

            return False
        except Exception as e:
            self.logger.debug(f"Failed to check fallback model: {e}")
            return False

    async def test_embedding_generation(self, endpoint: str, model: str) -> bool:
        """Test embedding generation with LM Studio.

        Args:
            endpoint: LM Studio endpoint URL.
            model: Model name to test.

        Returns:
            True if embedding generation works.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{endpoint.rstrip('/')}/embeddings",
                    json={
                        "input": "test embedding",
                        "model": model,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return "data" in data and len(data["data"]) > 0
                return False
        except Exception as e:
            self.logger.debug(f"Embedding generation test failed: {e}")
            return False

    async def test_completion_generation(self, endpoint: str, model: str) -> bool:
        """Test completion generation with LM Studio.

        Args:
            endpoint: LM Studio endpoint URL.
            model: Model name to test.

        Returns:
            True if completion generation works.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{endpoint.rstrip('/')}/completions",
                    json={
                        "prompt": "Hello",
                        "model": model,
                        "max_tokens": 10,
                        "temperature": 0.1,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return "choices" in data and len(data["choices"]) > 0
                return False
        except Exception as e:
            self.logger.debug(f"Completion generation test failed: {e}")
            return False

    async def check_qdrant_collections(
        self, host: str, port: int, collections: list[str]
    ) -> dict[str, bool]:
        """Check if Qdrant collections exist.

        Args:
            host: Qdrant host.
            port: Qdrant port.
            collections: List of collection names to check.

        Returns:
            Dict mapping collection names to existence status.
        """
        results = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"http://{host}:{port}/collections")

                if response.status_code == 200:
                    data = response.json()
                    existing_collections = {
                        collection["name"]
                        for collection in data.get("result", {}).get("collections", [])
                    }

                    for collection in collections:
                        results[collection] = collection in existing_collections
                else:
                    # If we can't get collections, assume none exist
                    results = dict.fromkeys(collections, False)

        except Exception as e:
            self.logger.debug(f"Failed to check Qdrant collections: {e}")
            results = dict.fromkeys(collections, False)

        return results

    async def check_network_ports(self, host: str, ports: list[int]) -> dict[int, bool]:
        """Check if network ports are open.

        Args:
            host: Host to check.
            ports: List of ports to check.

        Returns:
            Dict mapping ports to availability status.
        """
        results = {}

        for port in ports:
            try:
                # Create connection with short timeout
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=5.0
                )
                writer.close()
                await writer.wait_closed()
                results[port] = True
            except Exception:
                results[port] = False

        return results

    async def verify_docker_health(
        self, service_names: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Verify Docker service health.

        Args:
            service_names: List of Docker service names to check.

        Returns:
            Dict mapping service names to health status.
        """
        results = {}

        for service in service_names:
            try:
                # Run docker-compose ps for the specific service
                process = await asyncio.create_subprocess_exec(
                    "docker-compose",
                    "ps",
                    "-q",
                    service,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()

                if process.returncode == 0 and stdout.strip():
                    container_id = stdout.decode().strip()

                    # Check container health
                    inspect_process = await asyncio.create_subprocess_exec(
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        container_id,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    health_stdout, _ = await inspect_process.communicate()

                    if inspect_process.returncode == 0:
                        health_status = health_stdout.decode().strip()
                        results[service] = {
                            "running": True,
                            "healthy": health_status == "healthy",
                            "health_status": health_status,
                            "container_id": container_id,
                        }
                    else:
                        results[service] = {
                            "running": True,
                            "healthy": None,  # Health check not configured
                            "health_status": "unknown",
                            "container_id": container_id,
                        }
                else:
                    results[service] = {
                        "running": False,
                        "healthy": False,
                        "health_status": "not_running",
                        "container_id": None,
                    }

            except Exception as e:
                self.logger.debug(f"Failed to check Docker service {service}: {e}")
                results[service] = {
                    "running": False,
                    "healthy": False,
                    "health_status": "error",
                    "container_id": None,
                    "error": str(e),
                }

        return results
