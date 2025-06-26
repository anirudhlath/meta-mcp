"""Configuration loader for Meta MCP Server."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .models import MetaMCPConfig

logger = logging.getLogger(__name__)


def expand_env_vars(obj: Any) -> Any:
    """Recursively expand environment variables in configuration values."""
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    elif isinstance(obj, dict):
        return {key: expand_env_vars(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [expand_env_vars(item) for item in obj]
    else:
        return obj


def load_config(config_path: str | None = None) -> MetaMCPConfig:
    """Load configuration from YAML file with environment variable expansion.

    Args:
        config_path: Path to configuration file. If None, searches for default locations.

    Returns:
        Loaded and validated configuration.

    Raises:
        FileNotFoundError: If config file not found.
        ValueError: If config is invalid.
    """
    if config_path is None:
        # Search for default config locations
        default_paths = [
            "config/meta-server.yaml",
            "meta-server.yaml",
            os.path.expanduser("~/.meta-mcp/config.yaml"),
            "/etc/meta-mcp/config.yaml",
        ]

        for path in default_paths:
            if Path(path).exists():
                config_path = path
                break
        else:
            logger.info("No config file found, using defaults")
            return MetaMCPConfig()

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading configuration from: {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        if raw_config is None:
            raw_config = {}

        # Expand environment variables
        expanded_config = expand_env_vars(raw_config)

        # Validate and create config object
        config = MetaMCPConfig(**expanded_config)

        logger.info("Configuration loaded successfully")
        return config

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}") from e
    except Exception as e:
        raise ValueError(f"Error loading configuration: {e}") from e


def save_config(config: MetaMCPConfig, config_path: str) -> None:
    """Save configuration to YAML file.

    Args:
        config: Configuration object to save.
        config_path: Path to save configuration file.
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and save
    config_dict = config.model_dump(exclude_unset=False)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config_dict,
            f,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )

    logger.info(f"Configuration saved to: {config_path}")


def get_default_config() -> dict[str, Any]:
    """Get default configuration as dictionary for documentation."""
    config = MetaMCPConfig()
    return config.model_dump(exclude_unset=False)
