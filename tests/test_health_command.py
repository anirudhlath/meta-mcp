"""Tests for the health command functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console

from meta_mcp.config.models import MetaMCPConfig
from meta_mcp.health.checker import HealthChecker, HealthStatus


class TestHealthChecker:
    """Test health checker functionality."""

    @pytest.fixture
    def health_checker(self):
        """Create health checker instance."""
        console = Console(file=open("/dev/null", "w"))  # Suppress output during tests
        return HealthChecker(console)

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return MetaMCPConfig()

    @pytest.mark.asyncio
    async def test_health_checker_initialization(self, health_checker):
        """Test health checker initializes correctly."""
        assert health_checker.results == []
        assert health_checker.dependency_checker is not None
        assert health_checker.docker_manager is not None
        assert health_checker.setup_manager is not None

    @pytest.mark.asyncio
    async def test_configuration_check_valid(self, health_checker):
        """Test configuration check with valid config."""
        with patch("meta_mcp.health.checker.load_config") as mock_load:
            mock_load.return_value = MetaMCPConfig()

            config = await health_checker._check_configuration("test-config.yaml")

            assert config is not None
            assert len(health_checker.results) == 1
            assert health_checker.results[0].name == "Configuration"
            assert health_checker.results[0].status == HealthStatus.PASS

    @pytest.mark.asyncio
    async def test_configuration_check_invalid(self, health_checker):
        """Test configuration check with invalid config."""
        with patch("meta_mcp.health.checker.load_config") as mock_load:
            mock_load.side_effect = Exception("Invalid config")

            config = await health_checker._check_configuration("bad-config.yaml")

            assert config is None
            assert len(health_checker.results) == 1
            assert health_checker.results[0].name == "Configuration"
            assert health_checker.results[0].status == HealthStatus.FAIL

    @pytest.mark.asyncio
    async def test_file_system_check(self, health_checker, mock_config):
        """Test file system check."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            await health_checker._check_file_system(mock_config, fix_issues=False)

            result = next(r for r in health_checker.results if r.name == "File System")
            assert result.status == HealthStatus.PASS

    @pytest.mark.asyncio
    async def test_docker_services_check(self, health_checker):
        """Test Docker services check."""
        health_checker.docker_manager.is_docker_available = AsyncMock(return_value=True)
        health_checker.docker_manager.check_compose_file = AsyncMock(
            return_value={"exists": True, "valid": True, "services": ["qdrant"]}
        )
        health_checker.docker_manager.check_services_status = AsyncMock(
            return_value={"qdrant": False}
        )

        await health_checker._check_docker_services(setup_docker=False, verbose=False)

        result = next(r for r in health_checker.results if r.name == "Docker Services")
        assert result.status == HealthStatus.FAIL
        assert "qdrant" in result.details["stopped_services"]

    @pytest.mark.asyncio
    async def test_dependency_check(self, health_checker, mock_config):
        """Test dependency check."""
        health_checker.dependency_checker.check_python_packages = AsyncMock(
            return_value=[]
        )

        await health_checker._check_dependencies(
            mock_config, download_models=False, verbose=False
        )

        result = next(
            r for r in health_checker.results if r.name == "Python Dependencies"
        )
        assert result.status == HealthStatus.PASS

    @pytest.mark.asyncio
    async def test_network_connectivity_check(self, health_checker, mock_config):
        """Test network connectivity check."""
        health_checker.dependency_checker.check_qdrant_connectivity = AsyncMock(
            return_value=True
        )

        await health_checker._check_network_connectivity(mock_config, verbose=False)

        result = next(
            r for r in health_checker.results if r.name == "Qdrant Connectivity"
        )
        assert result.status == HealthStatus.PASS

    @pytest.mark.asyncio
    async def test_json_output_generation(self, health_checker):
        """Test JSON output generation."""
        # Add some mock results
        from meta_mcp.health.checker import HealthResult

        health_checker.results = [
            HealthResult("Test", HealthStatus.PASS, "Test message"),
            HealthResult("Test2", HealthStatus.FAIL, "Test failure"),
        ]

        result = health_checker._generate_json_output()

        assert result["status"] == "fail"  # Has failures
        assert result["summary"]["total_checks"] == 2
        assert result["summary"]["passed"] == 1
        assert result["summary"]["failed"] == 1
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_summary_generation(self, health_checker):
        """Test summary generation."""
        from meta_mcp.health.checker import HealthResult

        health_checker.results = [
            HealthResult("Test1", HealthStatus.PASS, "Pass"),
            HealthResult("Test2", HealthStatus.FAIL, "Fail"),
            HealthResult("Test3", HealthStatus.WARN, "Warn"),
        ]

        summary = health_checker._generate_summary()

        assert summary["total_checks"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["warnings"] == 1
        assert summary["issues_found"] == 2
        assert summary["overall_health"] == "issues_detected"

    @pytest.mark.asyncio
    async def test_run_health_check_integration(self, health_checker):
        """Test complete health check run."""
        # Mock all dependencies
        with (
            patch.object(
                health_checker, "_check_configuration", return_value=MetaMCPConfig()
            ),
            patch.object(health_checker, "_check_file_system"),
            patch.object(health_checker, "_check_docker_services"),
            patch.object(health_checker, "_check_dependencies"),
            patch.object(health_checker, "_check_network_connectivity"),
            patch.object(health_checker, "_check_models_and_services"),
        ):
            result = await health_checker.run_health_check(
                config_path=None,
                fix_issues=False,
                setup_docker=False,
                download_models=False,
                verbose=False,
                output_format="json",
            )

            assert "status" in result
            assert "summary" in result
            assert "results" in result
