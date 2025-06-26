"""Logging configuration and utilities."""

import logging
import logging.handlers
from pathlib import Path

from rich.logging import RichHandler

from ..config.models import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Configure logging based on the provided configuration.

    Args:
        config: Logging configuration object.
    """
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Console handler with Rich formatting
    if config.console:
        console_handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=True,
        )
        console_handler.setLevel(getattr(logging, config.level.upper()))

        # Format for console
        console_formatter = logging.Formatter("%(name)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if config.file:
        file_path = Path(config.file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=config.max_size_mb * 1024 * 1024,
            backupCount=config.max_files,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, config.level.upper()))

        # Detailed format for file
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)


class StructuredLogger:
    """Structured logger for the Meta MCP Server."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str, **kwargs) -> None:
        """Log info message with structured data."""
        extra_data = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        full_message = f"{message} | {extra_data}" if extra_data else message
        self.logger.info(full_message)

    def error(self, message: str, **kwargs) -> None:
        """Log error message with structured data."""
        extra_data = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        full_message = f"{message} | {extra_data}" if extra_data else message
        self.logger.error(full_message)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with structured data."""
        extra_data = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        full_message = f"{message} | {extra_data}" if extra_data else message
        self.logger.warning(full_message)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with structured data."""
        extra_data = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        full_message = f"{message} | {extra_data}" if extra_data else message
        self.logger.debug(full_message)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, typically __name__.

    Returns:
        Configured structured logger.
    """
    return StructuredLogger(name)
