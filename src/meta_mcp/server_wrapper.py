#!/usr/bin/env python3
"""
MCP Server Wrapper with automatic dependency management
Ensures Qdrant is running and healthy before starting the server
"""

import os
import sys
import time
import subprocess
import signal
import atexit
from pathlib import Path
import logging
import requests
from typing import Optional, Tuple

# Disable tokenizer parallelism warning
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logger = logging.getLogger(__name__)


class MetaMCPWrapper:
    """Wrapper that ensures all dependencies are running"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.scripts_dir = self.project_root / "scripts"
        self.qdrant_process = None
        self.qdrant_host = "localhost"
        self.qdrant_port = 6333
        self.runtime = None

    def detect_runtime(self) -> str:
        """Detect available container runtime"""
        try:
            result = subprocess.run(
                [str(self.scripts_dir / "detect-container-runtime.sh")],
                capture_output=True,
                text=True,
            )
            runtime = result.stdout.strip()
            if runtime in ["docker", "apple"]:
                return runtime
        except Exception as e:
            logger.error(f"Failed to detect runtime: {e}")
        return "none"

    def check_qdrant_health(self, host: str = None) -> bool:
        """Check if Qdrant is healthy"""
        if host is None:
            host = self.qdrant_host
        try:
            response = requests.get(
                f"http://{host}:{self.qdrant_port}/collections", timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def start_qdrant_docker(self) -> Tuple[bool, str]:
        """Start Qdrant using Docker"""
        logger.info("Starting Qdrant with Docker...")

        # Check if already running
        if self.check_qdrant_health("localhost"):
            logger.info("Qdrant already running on localhost")
            return True, "localhost"

        # Start with docker-compose
        try:
            subprocess.run(
                ["docker-compose", "up", "-d", "qdrant"],
                cwd=self.project_root,
                check=True,
            )

            # Wait for startup
            for _ in range(30):
                if self.check_qdrant_health("localhost"):
                    logger.info("Qdrant started successfully")
                    return True, "localhost"
                time.sleep(1)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Qdrant with Docker: {e}")

        return False, ""

    def start_qdrant_apple(self) -> Tuple[bool, str]:
        """Start Qdrant using Apple Container"""
        logger.info("Starting Qdrant with Apple Container...")

        # Get container IP if running
        try:
            result = subprocess.run(
                [str(self.scripts_dir / "get-qdrant-ip.sh")],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                host = result.stdout.strip()
                if self.check_qdrant_health(host):
                    logger.info(f"Qdrant already running on {host}")
                    return True, host
        except:
            pass

        # Start container
        try:
            subprocess.run(
                [str(self.scripts_dir / "qdrant-apple-container.sh"), "start"],
                check=True,
            )

            # Get IP after starting
            result = subprocess.run(
                [str(self.scripts_dir / "get-qdrant-ip.sh")],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                host = result.stdout.strip()
                if self.check_qdrant_health(host):
                    logger.info(f"Qdrant started successfully on {host}")
                    return True, host

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Qdrant with Apple Container: {e}")

        return False, ""

    def ensure_qdrant(self) -> bool:
        """Ensure Qdrant is running and healthy"""
        self.runtime = self.detect_runtime()

        if self.runtime == "none":
            logger.error("No container runtime available!")
            logger.error("Please install Docker or Apple Container Framework")
            return False

        logger.info(f"Using {self.runtime} runtime")

        # Start Qdrant based on runtime
        if self.runtime == "docker":
            success, host = self.start_qdrant_docker()
        else:
            success, host = self.start_qdrant_apple()

        if success:
            self.qdrant_host = host
            # Update environment for the server
            os.environ["QDRANT_HOST"] = host
            return True

        return False

    def cleanup(self):
        """Cleanup function called on exit"""
        # We don't stop Qdrant on exit - it should persist
        logger.info("Meta MCP wrapper shutting down")

    def run(self):
        """Main entry point"""
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Register cleanup
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

        # Ensure Qdrant is running
        if not self.ensure_qdrant():
            logger.error("Failed to ensure Qdrant is running")
            sys.exit(1)

        logger.info(f"Qdrant is healthy at {self.qdrant_host}:{self.qdrant_port}")

        # Import and run the actual server
        try:
            from meta_mcp.cli import app

            # The CLI will handle all arguments
            app()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point for the wrapper"""
    wrapper = MetaMCPWrapper()
    wrapper.run()


if __name__ == "__main__":
    main()
