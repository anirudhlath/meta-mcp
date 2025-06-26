"""LLM-based routing strategy using local language models."""

from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..llm.lm_studio_client import LMStudioClient
from .base import BaseRouter, SelectionContext, SelectionResult


class LLMRouter(BaseRouter):
    """Router that uses a local LLM for intelligent tool selection."""

    def __init__(self, config: MetaMCPConfig, llm_client: LMStudioClient):
        super().__init__(config, "llm")
        self.llm_client = llm_client

    async def initialize(self) -> None:
        """Initialize the LLM router."""
        self.logger.info("Initializing LLM router")

        # Ensure LLM client is initialized
        if not self.llm_client.client:
            await self.llm_client.initialize()

        self.logger.info("LLM router initialized")

    async def select_tools(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Select tools using LLM-based reasoning.

        Args:
            context: Selection context with query and metadata.
            available_tools: List of all available tools.

        Returns:
            Selection result with LLM-selected tools.
        """
        try:
            # Prepare tool data for LLM
            tool_data = []
            for tool in available_tools:
                tool_info = {
                    "id": tool.id,
                    "name": tool.name,
                    "server": tool.server_name,
                    "description": tool.description,
                    "usage_count": tool.usage_count,
                }

                # Add parameter information
                if tool.parameters:
                    param_info = self._summarize_parameters(tool.parameters)
                    if param_info:
                        tool_info["parameters"] = param_info

                # Add examples if available
                if tool.examples:
                    tool_info["examples"] = tool.examples[:2]  # Limit for context

                tool_data.append(tool_info)

            # Enhance query with context
            enhanced_query = self._build_enhanced_query(context)

            # Get tool selection from LLM
            selection_response = await self.llm_client.generate_tool_selection(
                query=enhanced_query,
                available_tools=tool_data,
                max_tools=self.config.strategy.max_tools,
            )

            # Convert selected tool IDs back to Tool objects
            selected_tool_ids = selection_response.get("selected_tools", [])
            tool_lookup = {tool.id: tool for tool in available_tools}
            selected_tools = [
                tool_lookup[tool_id]
                for tool_id in selected_tool_ids
                if tool_id in tool_lookup
            ]

            confidence = selection_response.get("confidence", 0.5)
            reasoning = selection_response.get("reasoning", "No reasoning provided")

            return SelectionResult(
                tools=selected_tools,
                strategy_used="llm",
                confidence_score=confidence,
                metadata={
                    "reasoning": reasoning,
                    "total_tools_considered": len(available_tools),
                    "llm_selections": len(selected_tool_ids),
                    "valid_selections": len(selected_tools),
                    "enhanced_query_length": len(enhanced_query),
                    "context_included": {
                        "recent_messages": len(context.recent_messages),
                        "active_tools": len(context.active_tools),
                        "user_preferences": len(context.user_preferences),
                    },
                },
            )

        except Exception as e:
            self.logger.error("LLM tool selection failed", error=str(e))
            # Return empty result on error
            return SelectionResult(
                tools=[],
                strategy_used="llm",
                confidence_score=0.0,
                metadata={
                    "error": str(e),
                    "fallback": True,
                },
            )

    def _build_enhanced_query(self, context: SelectionContext) -> str:
        """Build enhanced query with context information.

        Args:
            context: Selection context.

        Returns:
            Enhanced query string.
        """
        parts = [context.query]

        # Add recent messages for context
        if context.recent_messages:
            parts.append("Previous conversation:")
            parts.extend(f"- {msg}" for msg in context.recent_messages[-3:])

        # Add information about recently used tools
        if context.active_tools:
            parts.append(f"Recently used tools: {', '.join(context.active_tools)}")

        # Add user preferences if available
        if context.user_preferences:
            pref_str = ", ".join(
                f"{k}: {v}" for k, v in context.user_preferences.items()
            )
            parts.append(f"User preferences: {pref_str}")

        return "\n".join(parts)

    def _summarize_parameters(self, parameters: dict[str, Any]) -> str | None:
        """Summarize tool parameters for LLM context.

        Args:
            parameters: Tool parameters schema.

        Returns:
            Summarized parameter description or None.
        """
        if not isinstance(parameters, dict):
            return None

        param_parts = []

        # Handle JSON schema format
        if "properties" in parameters:
            properties = parameters["properties"]
            required = parameters.get("required", [])

            for param_name, param_info in properties.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get("type", "unknown")
                    param_desc = param_info.get("description", "")
                    required_mark = "*" if param_name in required else ""

                    param_parts.append(
                        f"{param_name}{required_mark} ({param_type}): {param_desc}"
                    )

        # Handle simple parameter descriptions
        elif isinstance(parameters, dict):
            for param_name, param_desc in parameters.items():
                if isinstance(param_desc, str):
                    param_parts.append(f"{param_name}: {param_desc}")

        return "; ".join(param_parts) if param_parts else None

    async def explain_selection(
        self,
        query: str,
        selected_tools: list[Tool],
        available_tools: list[Tool],
    ) -> str:
        """Generate explanation for tool selection.

        Args:
            query: Original query.
            selected_tools: Tools that were selected.
            available_tools: All available tools.

        Returns:
            Explanation of the selection.
        """
        try:
            selected_names = [tool.name for tool in selected_tools]
            available_names = [
                tool.name for tool in available_tools[:20]
            ]  # Limit for context

            explanation_prompt = f"""
Explain why these tools were selected for the user query:

Query: "{query}"
Selected tools: {", ".join(selected_names)}
Other available tools: {", ".join(available_names)}

Provide a brief, clear explanation of why these specific tools are most relevant for the query.
"""

            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant explaining tool selections to users.",
                },
                {"role": "user", "content": explanation_prompt},
            ]

            explanation = await self.llm_client.chat_complete(
                messages=messages, temperature=0.3, max_tokens=200
            )

            return explanation

        except Exception as e:
            self.logger.warning(
                "Failed to generate selection explanation", error=str(e)
            )
            return (
                f"Selected {len(selected_tools)} tools based on relevance to the query."
            )

    async def suggest_follow_up_tools(
        self,
        completed_tool: Tool,
        result: dict[str, Any],
        available_tools: list[Tool],
    ) -> list[Tool]:
        """Suggest follow-up tools based on completed tool execution.

        Args:
            completed_tool: Tool that was just executed.
            result: Result from the tool execution.
            available_tools: Available tools for suggestions.

        Returns:
            List of suggested follow-up tools.
        """
        try:
            # Build context for follow-up suggestions
            result_summary = str(result)[:500]  # Limit result size for context
            available_names = [
                f"{tool.id}: {tool.description}" for tool in available_tools[:30]
            ]

            suggestion_prompt = f"""
A tool was just executed with this result:

Tool: {completed_tool.name} ({completed_tool.description})
Result: {result_summary}

Based on this result, which tools would be most useful for follow-up actions?

Available tools:
{chr(10).join(available_names)}

Suggest up to 3 tools that would be most relevant for next steps. Respond with just the tool IDs, one per line.
"""

            messages = [
                {
                    "role": "system",
                    "content": "You are an assistant that suggests relevant follow-up tools based on previous tool results.",
                },
                {"role": "user", "content": suggestion_prompt},
            ]

            response = await self.llm_client.chat_complete(
                messages=messages, temperature=0.2, max_tokens=100
            )

            # Parse tool IDs from response
            suggested_ids = []
            for line in response.strip().split("\n"):
                line = line.strip()
                if line and "." in line:  # Should be in format server.tool
                    suggested_ids.append(line)

            # Convert to Tool objects
            tool_lookup = {tool.id: tool for tool in available_tools}
            suggested_tools = [
                tool_lookup[tool_id]
                for tool_id in suggested_ids[:3]
                if tool_id in tool_lookup
            ]

            self.logger.debug(
                "Generated follow-up suggestions",
                completed_tool=completed_tool.id,
                suggestions=len(suggested_tools),
            )

            return suggested_tools

        except Exception as e:
            self.logger.warning(
                "Failed to generate follow-up suggestions", error=str(e)
            )
            return []

    async def cleanup(self) -> None:
        """Clean up LLM router resources."""
        await super().cleanup()
        # LLM client cleanup is handled by the main server
