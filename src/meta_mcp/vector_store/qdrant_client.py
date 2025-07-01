"""Qdrant vector store client for storing and searching tool embeddings."""

import asyncio
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from ..config.models import MetaMCPConfig, Tool
from ..utils.logging import get_logger


class QdrantVectorStore:
    """Qdrant vector database client for tool embeddings."""

    def __init__(self, config: MetaMCPConfig):
        self.config = config.vector_store
        self.logger = get_logger(__name__)
        self.client: QdrantClient | None = None
        self.tools_collection = f"{self.config.collection_prefix}_tools"
        self.docs_collection = f"{self.config.collection_prefix}_docs"

    @staticmethod
    def _get_tool_point_id(tool_id: str) -> int:
        """Generate a valid Qdrant point ID from tool ID.

        Args:
            tool_id: Tool identifier string.

        Returns:
            Positive integer suitable for use as Qdrant point ID.
        """
        return abs(hash(tool_id))

    async def initialize(self) -> None:
        """Initialize Qdrant client and create collections."""
        self.logger.info("Initializing Qdrant vector store")

        try:
            # Create client
            if self.config.url:
                self.client = QdrantClient(url=self.config.url)
            else:
                self.client = QdrantClient(
                    host=self.config.host,
                    port=self.config.port,
                )

            # Test connection
            await self._test_connection()

            # Create collections if they don't exist
            await self._ensure_collections()

            self.logger.info(
                "Qdrant vector store initialized",
                host=self.config.host,
                port=self.config.port,
                tools_collection=self.tools_collection,
                docs_collection=self.docs_collection,
            )

        except Exception as e:
            self.logger.error("Failed to initialize Qdrant", error=str(e))
            raise

    async def _test_connection(self) -> None:
        """Test Qdrant connection."""

        def test():
            return self.client.get_collections()

        collections = await asyncio.get_event_loop().run_in_executor(None, test)
        self.logger.debug(
            f"Qdrant connection successful, found {len(collections.collections)} collections"
        )

    async def _ensure_collections(self) -> None:
        """Create collections if they don't exist."""

        def create_collection_if_not_exists(collection_name: str, vector_size: int):
            try:
                self.client.get_collection(collection_name)
                self.logger.debug(f"Collection {collection_name} already exists")
            except (ResponseHandlingException, UnexpectedResponse) as e:
                # Collection doesn't exist, create it
                if "doesn't exist" in str(e) or "Not found" in str(e):
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=vector_size,
                            distance=models.Distance.COSINE,
                        ),
                    )
                    self.logger.info(f"Created collection: {collection_name}")
                else:
                    # Re-raise if it's a different error
                    raise

        # Create collections with default vector sizes
        # Tools collection (for tool embeddings)
        await asyncio.get_event_loop().run_in_executor(
            None, create_collection_if_not_exists, self.tools_collection, 384
        )

        # Documents collection (for RAG documentation)
        await asyncio.get_event_loop().run_in_executor(
            None, create_collection_if_not_exists, self.docs_collection, 384
        )

    async def store_tool_embeddings(self, tools: list[Tool]) -> None:
        """Store tool embeddings in Qdrant.

        Args:
            tools: List of tools with embeddings to store.
        """
        if not tools:
            return

        points = []
        for tool in tools:
            if tool.embedding:
                point = models.PointStruct(
                    id=self._get_tool_point_id(
                        tool.id
                    ),  # Use helper method for consistent point ID generation
                    vector=tool.embedding,
                    payload={
                        "tool_id": tool.id,
                        "name": tool.name,
                        "server_name": tool.server_name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "usage_count": tool.usage_count,
                        "last_used": tool.last_used,
                    },
                )
                points.append(point)

        if points:

            def upsert_points():
                self.client.upsert(
                    collection_name=self.tools_collection,
                    points=points,
                )

            await asyncio.get_event_loop().run_in_executor(None, upsert_points)

            self.logger.info(
                f"Stored {len(points)} tool embeddings",
                collection=self.tools_collection,
            )

    async def search_similar_tools(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        server_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar tools using vector similarity.

        Args:
            query_vector: Query embedding vector.
            limit: Maximum number of results to return.
            score_threshold: Minimum similarity score threshold.
            server_filter: Optional server name to filter results.

        Returns:
            List of similar tools with metadata and scores.
        """

        def search():
            query_filter = None
            if server_filter:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="server_name",
                            match=models.MatchValue(value=server_filter),
                        )
                    ]
                )

            return self.client.search(
                collection_name=self.tools_collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )

        try:
            results = await asyncio.get_event_loop().run_in_executor(None, search)

            similar_tools = []
            for result in results:
                tool_data = {
                    "tool_id": result.payload["tool_id"],
                    "name": result.payload["name"],
                    "server_name": result.payload["server_name"],
                    "description": result.payload["description"],
                    "parameters": result.payload["parameters"],
                    "score": result.score,
                    "usage_count": result.payload.get("usage_count", 0),
                    "last_used": result.payload.get("last_used"),
                }
                similar_tools.append(tool_data)

            # Log search results for debugging
            if similar_tools:
                top_scores = [round(tool["score"], 3) for tool in similar_tools[:5]]
                self.logger.debug(
                    "Vector search completed",
                    query_size=len(query_vector),
                    results_count=len(similar_tools),
                    threshold=score_threshold,
                    top_scores=top_scores,
                )
            else:
                # Get a few results without threshold to see what scores we're getting
                try:
                    no_threshold_results = (
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.client.search(
                                collection_name=self.tools_collection,
                                query_vector=query_vector,
                                limit=min(5, limit),
                                with_payload=True,
                            ),
                        )
                    )
                    if no_threshold_results:
                        actual_scores = [
                            round(r.score, 3) for r in no_threshold_results
                        ]
                        self.logger.warning(
                            f"Vector search returned 0 results with threshold {score_threshold}, "
                            f"but found {len(no_threshold_results)} results without threshold. "
                            f"Actual top scores: {actual_scores}"
                        )
                    else:
                        self.logger.warning(
                            "Vector search returned 0 results even without threshold - no tools in collection?"
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to get debug scores: {e}")

                self.logger.debug(
                    "Vector search completed with no results",
                    query_size=len(query_vector),
                    threshold=score_threshold,
                )

            return similar_tools

        except Exception as e:
            self.logger.error("Vector search failed", error=str(e))
            return []

    async def store_document_chunks(
        self,
        chunks: list[dict[str, Any]],
        source: str,
    ) -> None:
        """Store document chunks for RAG.

        Args:
            chunks: List of document chunks with embeddings.
            source: Source identifier for the documents.
        """
        if not chunks:
            return

        points = []
        for i, chunk in enumerate(chunks):
            if "embedding" in chunk:
                point = models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=chunk["embedding"],
                    payload={
                        "source": source,
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                        "chunk_index": i,
                    },
                )
                points.append(point)

        if points:

            def upsert_points():
                self.client.upsert(
                    collection_name=self.docs_collection,
                    points=points,
                )

            await asyncio.get_event_loop().run_in_executor(None, upsert_points)

            self.logger.info(
                f"Stored {len(points)} document chunks",
                source=source,
                collection=self.docs_collection,
            )

    async def search_documents(
        self,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.7,
        source_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant document chunks.

        Args:
            query_vector: Query embedding vector.
            limit: Maximum number of results to return.
            score_threshold: Minimum similarity score threshold.
            source_filter: Optional source filter.

        Returns:
            List of relevant document chunks.
        """

        def search():
            query_filter = None
            if source_filter:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source",
                            match=models.MatchValue(value=source_filter),
                        )
                    ]
                )

            return self.client.search(
                collection_name=self.docs_collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )

        try:
            results = await asyncio.get_event_loop().run_in_executor(None, search)

            documents = []
            for result in results:
                doc_data = {
                    "text": result.payload["text"],
                    "source": result.payload["source"],
                    "metadata": result.payload.get("metadata", {}),
                    "score": result.score,
                    "chunk_index": result.payload.get("chunk_index", 0),
                }
                documents.append(doc_data)

            self.logger.debug(
                "Document search completed",
                results_count=len(documents),
                threshold=score_threshold,
            )

            return documents

        except Exception as e:
            self.logger.error("Document search failed", error=str(e))
            return []

    async def update_tool_usage(
        self, tool_id: str, usage_count: int, last_used: str
    ) -> None:
        """Update tool usage statistics.

        Args:
            tool_id: Tool identifier.
            usage_count: New usage count.
            last_used: Last used timestamp.
        """

        def update():
            self.client.set_payload(
                collection_name=self.tools_collection,
                payload={
                    "usage_count": usage_count,
                    "last_used": last_used,
                },
                points=[self._get_tool_point_id(tool_id)],
            )

        try:
            await asyncio.get_event_loop().run_in_executor(None, update)
            self.logger.debug("Updated tool usage", tool_id=tool_id)
        except Exception as e:
            self.logger.warning(
                "Failed to update tool usage", tool_id=tool_id, error=str(e)
            )

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection.

        Args:
            collection_name: Name of collection to delete.
        """

        def delete():
            self.client.delete_collection(collection_name)

        try:
            await asyncio.get_event_loop().run_in_executor(None, delete)
            self.logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            self.logger.error(
                "Failed to delete collection", collection=collection_name, error=str(e)
            )

    async def get_collection_info(self) -> dict[str, Any]:
        """Get information about collections.

        Returns:
            Dictionary with collection information.
        """

        def get_info():
            tools_info = self.client.get_collection(self.tools_collection)
            docs_info = self.client.get_collection(self.docs_collection)
            return {
                "tools": {
                    "name": self.tools_collection,
                    "points_count": tools_info.points_count,
                    "vectors_count": tools_info.vectors_count,
                    "status": tools_info.status,
                },
                "docs": {
                    "name": self.docs_collection,
                    "points_count": docs_info.points_count,
                    "vectors_count": docs_info.vectors_count,
                    "status": docs_info.status,
                },
            }

        try:
            return await asyncio.get_event_loop().run_in_executor(None, get_info)
        except Exception as e:
            self.logger.error("Failed to get collection info", error=str(e))
            return {}
