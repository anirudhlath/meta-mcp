"""Vector search routing strategy using semantic similarity."""

from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..embeddings.service import EmbeddingService
from ..vector_store.qdrant_client import QdrantVectorStore
from .base import BaseRouter, SelectionContext, SelectionResult


class VectorSearchRouter(BaseRouter):
    """Router that uses vector similarity search for tool selection."""

    def __init__(
        self,
        config: MetaMCPConfig,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
    ):
        super().__init__(config, "vector")
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def initialize(self) -> None:
        """Initialize the vector search router."""
        self.logger.info("Initializing vector search router")

        # Ensure vector store is initialized
        if not self.vector_store.client:
            await self.vector_store.initialize()

        self.logger.info("Vector search router initialized")

    async def select_tools(
        self,
        context: SelectionContext,
        available_tools: list[Tool],
    ) -> SelectionResult:
        """Select tools using vector similarity search.

        Args:
            context: Selection context with query and metadata.
            available_tools: List of all available tools.

        Returns:
            Selection result with most similar tools.
        """
        try:
            # Get context text for embedding
            context_text = context.get_context_text()

            # Generate embedding for the context
            query_embedding = await self.embedding_service.embed(context_text)
            self.logger.debug(
                f"Generated query embedding with {len(query_embedding)} dimensions"
            )

            # Search for similar tools in vector store
            similar_tools_data = await self.vector_store.search_similar_tools(
                query_vector=query_embedding,
                limit=self.config.strategy.max_tools * 2,  # Get more for filtering
                score_threshold=self.config.strategy.vector_threshold,
            )

            self.logger.debug(
                f"Vector search returned {len(similar_tools_data)} results above threshold {self.config.strategy.vector_threshold}"
            )
            
            # If no results with configured threshold, try adaptive threshold
            if not similar_tools_data:
                self.logger.info("No results with configured threshold, trying adaptive search...")
                
                # Get top results without threshold to see what's available
                adaptive_results = await self.vector_store.search_similar_tools(
                    query_vector=query_embedding,
                    limit=min(5, self.config.strategy.max_tools),
                    score_threshold=0.0,  # No threshold
                )
                
                if adaptive_results:
                    # Use results if top score is reasonable (>0.1)
                    top_score = adaptive_results[0]["score"]
                    if top_score > 0.1:
                        similar_tools_data = adaptive_results
                        self.logger.info(
                            f"Using adaptive threshold - found {len(similar_tools_data)} results "
                            f"with top score {top_score:.3f}"
                        )

            # Convert search results back to Tool objects
            selected_tools = []
            tool_lookup = {tool.id: tool for tool in available_tools}

            for tool_data in similar_tools_data:
                tool_id = tool_data["tool_id"]
                if tool_id in tool_lookup:
                    tool = tool_lookup[tool_id]
                    # Update usage info if available
                    if "usage_count" in tool_data:
                        tool.usage_count = tool_data["usage_count"]
                    if "last_used" in tool_data:
                        tool.last_used = tool_data["last_used"]
                    selected_tools.append(tool)

            # Apply max tools limit
            limited_tools = self._limit_tools(
                selected_tools, self.config.strategy.max_tools
            )

            # Calculate confidence based on scores
            confidence = self._calculate_confidence(similar_tools_data)

            return SelectionResult(
                tools=limited_tools,
                strategy_used="vector",
                confidence_score=confidence,
                metadata={
                    "query_embedding_size": len(query_embedding),
                    "search_results_count": len(similar_tools_data),
                    "threshold_used": self.config.strategy.vector_threshold,
                    "max_tools": self.config.strategy.max_tools,
                    "context_length": len(context_text),
                    "top_scores": [
                        round(tool_data["score"], 3)
                        for tool_data in similar_tools_data[:5]
                    ],
                },
            )

        except Exception as e:
            self.logger.error("Vector search failed", error=str(e))
            # Return empty result on error
            return SelectionResult(
                tools=[],
                strategy_used="vector",
                confidence_score=0.0,
                metadata={
                    "error": str(e),
                    "fallback": True,
                },
            )

    def _calculate_confidence(self, search_results: list[dict[str, Any]]) -> float:
        """Calculate confidence score based on search results.

        Args:
            search_results: List of search results with scores.

        Returns:
            Confidence score between 0 and 1.
        """
        if not search_results:
            return 0.0

        # Use the highest score as base confidence
        max_score = max(result["score"] for result in search_results)

        # Adjust based on number of results and score distribution
        num_results = len(search_results)
        if num_results >= self.config.strategy.max_tools:
            # Good number of relevant results
            confidence = min(max_score * 1.1, 1.0)
        else:
            # Fewer results, slightly lower confidence
            confidence = max_score * (
                0.8 + 0.2 * num_results / self.config.strategy.max_tools
            )

        return round(confidence, 3)

    async def update_tool_embeddings(self, tools: list[Tool]) -> None:
        """Update tool embeddings in the vector store.

        Args:
            tools: List of tools to update embeddings for.
        """
        try:
            # Generate embeddings for tools that don't have them
            tools_to_embed = [tool for tool in tools if not tool.embedding]

            if tools_to_embed:
                self.logger.info(
                    f"Generating embeddings for {len(tools_to_embed)} tools"
                )

                # Prepare texts for embedding
                texts = []
                for tool in tools_to_embed:
                    # Combine description and parameter info for better embeddings
                    text_parts = [tool.description]

                    # Add parameter names and descriptions
                    if tool.parameters and isinstance(tool.parameters, dict):
                        if "properties" in tool.parameters:
                            for param_name, param_info in tool.parameters[
                                "properties"
                            ].items():
                                if isinstance(param_info, dict):
                                    param_desc = param_info.get("description", "")
                                    text_parts.append(f"{param_name}: {param_desc}")

                    # Add examples if available
                    if tool.examples:
                        text_parts.extend(tool.examples)

                    texts.append(" ".join(text_parts))

                # Generate embeddings in batch
                embeddings = await self.embedding_service.embed_batch(texts)

                # Update tool objects
                for tool, embedding in zip(tools_to_embed, embeddings, strict=False):
                    tool.embedding = embedding

            # Store all tool embeddings in vector store
            await self.vector_store.store_tool_embeddings(tools)

            self.logger.info(
                f"Updated embeddings for {len(tools)} tools",
                new_embeddings=len(tools_to_embed),
            )

        except Exception as e:
            self.logger.error("Failed to update tool embeddings", error=str(e))

    async def update_tool_usage(
        self, tool_id: str, usage_count: int, last_used: str
    ) -> None:
        """Update tool usage statistics in vector store.

        Args:
            tool_id: Tool identifier.
            usage_count: New usage count.
            last_used: Last used timestamp.
        """
        try:
            await self.vector_store.update_tool_usage(tool_id, usage_count, last_used)
        except Exception as e:
            self.logger.warning(
                "Failed to update tool usage", tool_id=tool_id, error=str(e)
            )

    async def get_similar_tools(
        self,
        reference_tool: Tool,
        available_tools: list[Tool],
        limit: int = 5,
    ) -> list[Tool]:
        """Get tools similar to a reference tool.

        Args:
            reference_tool: Tool to find similar tools for.
            available_tools: List of available tools.
            limit: Maximum number of similar tools to return.

        Returns:
            List of similar tools.
        """
        if not reference_tool.embedding:
            return []

        try:
            similar_tools_data = await self.vector_store.search_similar_tools(
                query_vector=reference_tool.embedding,
                limit=limit + 1,  # +1 to exclude the reference tool itself
                score_threshold=0.5,  # Lower threshold for similarity search
            )

            # Convert to Tool objects and exclude the reference tool
            similar_tools = []
            tool_lookup = {tool.id: tool for tool in available_tools}

            for tool_data in similar_tools_data:
                tool_id = tool_data["tool_id"]
                if tool_id != reference_tool.id and tool_id in tool_lookup:
                    similar_tools.append(tool_lookup[tool_id])

            return similar_tools[:limit]

        except Exception as e:
            self.logger.error("Failed to find similar tools", error=str(e))
            return []

    async def cleanup(self) -> None:
        """Clean up vector search router resources."""
        await super().cleanup()
        # Vector store cleanup is handled by the main server
