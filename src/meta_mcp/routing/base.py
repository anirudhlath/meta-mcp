"""Base router interface for tool selection strategies."""

import time
from abc import ABC, abstractmethod
from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SelectionContext:
    """Context information for tool selection."""

    def __init__(
        self,
        query: str,
        recent_messages: list[str] | None = None,
        active_tools: list[str] | None = None,
        user_preferences: dict[str, Any] | None = None,
    ):
        self.query = query
        self.recent_messages = recent_messages or []
        self.active_tools = active_tools or []
        self.user_preferences = user_preferences or {}
        self.timestamp = time.time()

    def get_context_text(self) -> str:
        """Get concatenated context text for embedding/analysis."""
        context_parts = [self.query]

        if self.recent_messages:
            context_parts.extend(self.recent_messages[-3:])  # Last 3 messages

        return " ".join(context_parts)


class SelectionResult:
    """Result of tool selection process."""

    def __init__(
        self,
        tools: list[Tool],
        strategy_used: str,
        confidence_score: float = 1.0,
        selection_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ):
        self.tools = tools
        self.strategy_used = strategy_used
        self.confidence_score = confidence_score
        self.selection_time_ms = selection_time_ms
        self.metadata = metadata or {}


class BaseRouter(ABC):
    """Abstract base class for tool selection strategies."""

    def __init__(self, config: MetaMCPConfig, strategy_name: str):
        self.config = config
        self.strategy_name = strategy_name
        self.logger = get_logger(f"{__name__}.{strategy_name}")

        # Performance metrics
        self.total_requests = 0
        self.total_time_ms = 0.0
        self.error_count = 0

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the router (load models, connect to services, etc.)."""
        pass

    @abstractmethod
    async def select_tools(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Select relevant tools based on the provided context.

        Args:
            context: Selection context with query and additional information.
            available_tools: List of all available tools to choose from.

        Returns:
            Selection result with chosen tools and metadata.
        """
        pass

    async def select_tools_with_metrics(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Wrapper that adds performance metrics to tool selection.

        Args:
            context: Selection context with query and additional information.
            available_tools: List of all available tools to choose from.

        Returns:
            Selection result with timing information.
        """
        start_time = time.time()
        self.total_requests += 1

        try:
            result = await self.select_tools(context, available_tools)

            # Calculate timing
            end_time = time.time()
            selection_time_ms = (end_time - start_time) * 1000
            result.selection_time_ms = selection_time_ms

            # Update metrics
            self.total_time_ms += selection_time_ms

            self.logger.info(
                "Tool selection completed",
                strategy=self.strategy_name,
                tools_selected=len(result.tools),
                time_ms=round(selection_time_ms, 2),
                confidence=round(result.confidence_score, 3),
            )

            return result

        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Tool selection failed",
                strategy=self.strategy_name,
                error=str(e),
            )
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get performance metrics for this router.

        Returns:
            Dictionary containing performance metrics.
        """
        avg_time_ms = (
            self.total_time_ms / self.total_requests if self.total_requests > 0 else 0.0
        )

        return {
            "strategy": self.strategy_name,
            "total_requests": self.total_requests,
            "total_time_ms": round(self.total_time_ms, 2),
            "average_time_ms": round(avg_time_ms, 2),
            "error_count": self.error_count,
            "success_rate": (
                (self.total_requests - self.error_count) / self.total_requests
                if self.total_requests > 0
                else 1.0
            ),
        }

    async def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        self.logger.info(f"Cleaning up {self.strategy_name} router")

    def _filter_tools_by_threshold(
        self,
        tools_with_scores: list[tuple[Tool, float]],
        threshold: float,
    ) -> list[Tool]:
        """Filter tools by confidence/similarity threshold.

        Args:
            tools_with_scores: List of (tool, score) tuples.
            threshold: Minimum score threshold.

        Returns:
            List of tools that meet the threshold.
        """
        filtered_tools = [
            tool for tool, score in tools_with_scores if score >= threshold
        ]

        self.logger.debug(
            "Filtered tools by threshold",
            threshold=threshold,
            input_count=len(tools_with_scores),
            output_count=len(filtered_tools),
        )

        return filtered_tools

    def _limit_tools(self, tools: list[Tool], max_tools: int) -> list[Tool]:
        """Limit the number of tools returned.

        Args:
            tools: List of tools to limit.
            max_tools: Maximum number of tools to return.

        Returns:
            Limited list of tools.
        """
        if len(tools) <= max_tools:
            return tools

        limited_tools = tools[:max_tools]

        self.logger.debug(
            "Limited tool count",
            input_count=len(tools),
            output_count=len(limited_tools),
            max_tools=max_tools,
        )

        return limited_tools


class FallbackRouter(BaseRouter):
    """Fallback router that returns all tools when other strategies fail."""

    def __init__(self, config: MetaMCPConfig):
        super().__init__(config, "fallback")

    async def initialize(self) -> None:
        """Initialize the fallback router."""
        self.logger.info("Fallback router initialized")

    async def select_tools(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Return all available tools with low confidence.

        Args:
            context: Selection context (not used in fallback).
            available_tools: List of all available tools.

        Returns:
            All tools with fallback metadata.
        """
        self.logger.warning(
            "Using fallback strategy - returning all tools",
            tool_count=len(available_tools),
        )

        # Apply max tools limit from config
        max_tools = self.config.strategy.max_tools
        limited_tools = self._limit_tools(available_tools, max_tools)

        return SelectionResult(
            tools=limited_tools,
            strategy_used="fallback",
            confidence_score=0.1,  # Low confidence for fallback
            metadata={
                "reason": "fallback_strategy",
                "original_tool_count": len(available_tools),
                "returned_tool_count": len(limited_tools),
            },
        )
