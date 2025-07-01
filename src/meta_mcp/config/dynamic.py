"""
Dynamic configuration system for Meta MCP
Automatically detects and configures Qdrant host based on runtime
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DynamicConfig:
    """Handles dynamic configuration based on runtime environment"""

    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.parent.parent
        else:
            self.project_root = project_root
        self.scripts_dir = self.project_root / "scripts"

    def detect_qdrant_host(self) -> str:
        """Detect Qdrant host based on available runtime"""
        # Check environment variable first
        if "QDRANT_HOST" in os.environ:
            host = os.environ["QDRANT_HOST"]
            logger.info(f"Using Qdrant host from environment: {host}")
            return host

        # Try to detect from running containers
        try:
            # Check if Docker Qdrant is running
            result = subprocess.run(
                ["curl", "-s", "-f", "http://localhost:6333/collections"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                logger.info("Detected Qdrant running on localhost (Docker)")
                return "localhost"
        except:
            pass

        # Check Apple Container
        try:
            if self.scripts_dir.exists():
                result = subprocess.run(
                    [str(self.scripts_dir / "get-qdrant-ip.sh")],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    host = result.stdout.strip()
                    logger.info(f"Detected Qdrant running on Apple Container: {host}")
                    return host
        except:
            pass

        # Default fallback
        logger.warning("Could not detect Qdrant host, using localhost")
        return "localhost"

    def get_runtime_config(self) -> dict[str, Any]:
        """Get runtime-specific configuration"""
        qdrant_host = self.detect_qdrant_host()

        config = {
            "vector_store": {
                "type": "qdrant",
                "host": qdrant_host,
                "port": 6333,
                "collection_prefix": "meta_mcp",
            },
            "embeddings": {
                "lm_studio_endpoint": "http://localhost:1234/v1/embeddings",
                "lm_studio_model": "nomic-embed-text-v1.5",
                "fallback_model": "all-MiniLM-L6-v2",
                "batch_size": 32,
                "cache_dir": "./embedding-models",
            },
        }

        logger.info(f"Dynamic config: Qdrant at {qdrant_host}:6333")
        return config

    def merge_with_config(self, base_config: dict[str, Any]) -> dict[str, Any]:
        """Merge dynamic config with base configuration"""
        runtime_config = self.get_runtime_config()

        # Deep merge
        merged = base_config.copy()
        for key, value in runtime_config.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key].update(value)
            else:
                merged[key] = value

        return merged


# Global instance
_dynamic_config = None


def get_dynamic_config() -> DynamicConfig:
    """Get the global dynamic config instance"""
    global _dynamic_config
    if _dynamic_config is None:
        _dynamic_config = DynamicConfig()
    return _dynamic_config
