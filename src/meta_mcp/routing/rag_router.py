"""RAG-based routing strategy using retrieval augmented generation."""

from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..llm.lm_studio_client import LMStudioClient
from ..rag.pipeline import RAGPipeline
from .base import BaseRouter, SelectionContext, SelectionResult


class RAGRouter(BaseRouter):
    """Router that uses RAG (Retrieval Augmented Generation) for tool selection."""

    def __init__(
        self,
        config: MetaMCPConfig,
        rag_pipeline: RAGPipeline,
        llm_client: LMStudioClient,
    ):
        super().__init__(config, "rag")
        self.rag_pipeline = rag_pipeline
        self.llm_client = llm_client

    async def initialize(self) -> None:
        """Initialize the RAG router."""
        self.logger.info("Initializing RAG router")

        # Ensure RAG pipeline is initialized
        await self.rag_pipeline.initialize()

        # Index documentation for child servers
        await self._index_server_documentation()

        self.logger.info("RAG router initialized")

    async def _index_server_documentation(self) -> None:
        """Index documentation for all configured child servers."""
        for server_config in self.config.child_servers:
            if server_config.documentation and server_config.enabled:
                source_id = f"{server_config.name}_docs"
                await self.rag_pipeline.index_documentation(
                    server_config.documentation, source_id
                )

    async def select_tools(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Select tools using RAG-enhanced context.

        Args:
            context: Selection context with query and metadata.
            available_tools: List of all available tools.

        Returns:
            Selection result with RAG-selected tools.
        """
        try:
            # Build enhanced query with retrieved context
            (
                enhanced_query,
                context_docs,
            ) = await self.rag_pipeline.augment_query_with_context(
                context.get_context_text(), available_tools
            )

            # Prepare tool data for LLM selection
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

                # Add examples if available and configured
                if tool.examples and self.config.rag.include_examples:
                    tool_info["examples"] = tool.examples[:2]

                tool_data.append(tool_info)

            # Use LLM with enhanced context for tool selection
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

            # Calculate confidence based on context quality and LLM confidence
            llm_confidence = selection_response.get("confidence", 0.5)
            context_quality = self._calculate_context_quality(context_docs)
            combined_confidence = (llm_confidence + context_quality) / 2

            reasoning = selection_response.get("reasoning", "No reasoning provided")

            return SelectionResult(
                tools=selected_tools,
                strategy_used="rag",
                confidence_score=combined_confidence,
                metadata={
                    "reasoning": reasoning,
                    "context_docs_used": len(context_docs),
                    "context_sources": list({doc["source"] for doc in context_docs}),
                    "llm_confidence": llm_confidence,
                    "context_quality": context_quality,
                    "enhanced_query_length": len(enhanced_query),
                    "original_query_length": len(context.get_context_text()),
                    "total_tools_considered": len(available_tools),
                    "rag_selections": len(selected_tool_ids),
                    "valid_selections": len(selected_tools),
                    "context_scores": [
                        round(doc["score"], 3) for doc in context_docs[:5]
                    ],
                },
            )

        except Exception as e:
            self.logger.error("RAG tool selection failed", error=str(e))
            # Return empty result on error
            return SelectionResult(
                tools=[],
                strategy_used="rag",
                confidence_score=0.0,
                metadata={
                    "error": str(e),
                    "fallback": True,
                },
            )

    def _calculate_context_quality(self, context_docs: list[dict[str, Any]]) -> float:
        """Calculate quality score for retrieved context.

        Args:
            context_docs: Retrieved context documents.

        Returns:
            Quality score between 0 and 1.
        """
        if not context_docs:
            return 0.0

        # Calculate based on number of documents and their scores
        num_docs = len(context_docs)
        avg_score = sum(doc["score"] for doc in context_docs) / num_docs

        # Bonus for having multiple relevant sources
        unique_sources = len({doc["source"] for doc in context_docs})
        source_bonus = min(unique_sources * 0.1, 0.3)

        # Bonus for high-scoring documents
        score_bonus = max(0, (avg_score - 0.7) * 0.5)

        quality = min(avg_score + source_bonus + score_bonus, 1.0)
        return round(quality, 3)

    def _summarize_parameters(self, parameters: dict[str, Any]) -> str | None:
        """Summarize tool parameters for context.

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

    async def generate_contextual_explanation(
        self,
        query: str,
        selected_tools: list[Tool],
        context_docs: list[dict[str, Any]],
    ) -> str:
        """Generate explanation based on RAG context.

        Args:
            query: Original query.
            selected_tools: Selected tools.
            context_docs: Context documents used.

        Returns:
            Contextual explanation.
        """
        try:
            context_summary = []
            for doc in context_docs[:3]:  # Limit for prompt size
                context_summary.append(f"- {doc['source']}: {doc['text'][:200]}...")

            selected_names = [tool.name for tool in selected_tools]

            explanation_prompt = f"""
Based on the following context and user query, explain why these tools were selected:

Query: "{query}"
Selected tools: {", ".join(selected_names)}

Relevant documentation context:
{chr(10).join(context_summary)}

Provide a clear explanation that references the documentation context and explains why these tools are most suitable for the user's query.
"""

            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant explaining tool selections using documentation context.",
                },
                {"role": "user", "content": explanation_prompt},
            ]

            explanation = await self.llm_client.chat_complete(
                messages=messages, temperature=0.3, max_tokens=300
            )

            return explanation

        except Exception as e:
            self.logger.warning(
                "Failed to generate contextual explanation", error=str(e)
            )
            return f"Selected {len(selected_tools)} tools based on documentation analysis and query relevance."

    async def get_relevant_documentation(
        self, tool: Tool, query: str | None = None
    ) -> list[dict[str, Any]]:
        """Get relevant documentation for a specific tool.

        Args:
            tool: Tool to get documentation for.
            query: Optional query to focus the search.

        Returns:
            List of relevant documentation chunks.
        """
        search_query = query or f"{tool.name} {tool.description}"
        source_filter = f"{tool.server_name}_docs"

        return await self.rag_pipeline.retrieve_relevant_context(
            search_query, sources=[source_filter], limit=3
        )

    async def update_documentation_index(self) -> None:
        """Re-index documentation for all servers."""
        self.logger.info("Updating documentation index")
        await self._index_server_documentation()
        self.logger.info("Documentation index updated")

    async def cleanup(self) -> None:
        """Clean up RAG router resources."""
        await super().cleanup()
        await self.rag_pipeline.cleanup()
