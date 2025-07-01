"""
Health check system for Meta MCP Server
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


class HealthChecker:
    """System health checker"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.scripts_dir = self.project_root / "scripts"

    def check_python_deps(self) -> tuple[bool, str]:
        """Check if Python dependencies are installed"""
        try:
            import meta_mcp

            return True, "Python dependencies OK"
        except ImportError as e:
            return False, f"Missing Python dependencies: {e}"

    def check_container_runtime(self) -> tuple[bool, str]:
        """Check container runtime availability"""
        try:
            result = subprocess.run(
                [str(self.scripts_dir / "detect-container-runtime.sh")],
                capture_output=True,
                text=True,
            )
            runtime = result.stdout.strip()
            if runtime in ["docker", "apple"]:
                return True, f"Container runtime: {runtime}"
            else:
                return False, "No container runtime detected"
        except Exception as e:
            return False, f"Runtime check failed: {e}"

    def check_qdrant(self) -> tuple[bool, str]:
        """Check Qdrant accessibility"""
        # Try localhost first (Docker)
        try:
            response = requests.get("http://localhost:6333/collections", timeout=2)
            if response.status_code == 200:
                return True, "Qdrant accessible on localhost:6333"
        except:
            pass

        # Try Apple Container IP
        try:
            result = subprocess.run(
                [str(self.scripts_dir / "get-qdrant-ip.sh")],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                host = result.stdout.strip()
                response = requests.get(f"http://{host}:6333/collections", timeout=2)
                if response.status_code == 200:
                    return True, f"Qdrant accessible on {host}:6333"
        except:
            pass

        return False, "Qdrant not accessible"

    def check_lm_studio(self) -> tuple[bool, str]:
        """Check LM Studio availability (optional)"""
        try:
            response = requests.get("http://localhost:1234/v1/models", timeout=2)
            if response.status_code == 200:
                return True, "LM Studio accessible on localhost:1234"
        except:
            pass

        return False, "LM Studio not accessible (optional)"

    def run_health_check(self) -> dict[str, Any]:
        """Run comprehensive health check"""
        checks = {
            "python_deps": self.check_python_deps(),
            "container_runtime": self.check_container_runtime(),
            "qdrant": self.check_qdrant(),
            "lm_studio": self.check_lm_studio(),
        }

        results = {}
        all_critical_passed = True

        for check_name, (passed, message) in checks.items():
            results[check_name] = {
                "passed": passed,
                "message": message,
                "critical": check_name
                in ["python_deps", "container_runtime", "qdrant"],
            }

            if not passed and results[check_name]["critical"]:
                all_critical_passed = False

        results["overall"] = {
            "healthy": all_critical_passed,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        return results

    def print_health_report(self):
        """Print human-readable health report"""
        results = self.run_health_check()

        print("Meta MCP Server Health Check")
        print("=" * 40)

        for check_name, result in results.items():
            if check_name == "overall":
                continue

            status = "✓" if result["passed"] else "✗"
            criticality = "(critical)" if result["critical"] else "(optional)"

            print(
                f"{status} {check_name.replace('_', ' ').title()}: {result['message']} {criticality}"
            )

        print("-" * 40)
        overall_status = "HEALTHY" if results["overall"]["healthy"] else "UNHEALTHY"
        print(f"Overall Status: {overall_status}")

        if not results["overall"]["healthy"]:
            print("\nTo fix issues:")
            print("1. Run: uv sync --extra web --extra dev")
            print("2. Install Docker or Apple Container Framework")
            print("3. Run: ./install.sh")
            return False

        return True


def main():
    """Main health check entry point"""
    logging.basicConfig(level=logging.INFO)
    checker = HealthChecker()

    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        import json

        results = checker.run_health_check()
        print(json.dumps(results, indent=2))
        sys.exit(0 if results["overall"]["healthy"] else 1)
    else:
        healthy = checker.print_health_report()
        sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
