"""RAG (Retrieval Augmented Generation) pipeline for enhanced tool selection."""

import re
from pathlib import Path
from typing import Any

from ..config.models import MetaMCPConfig, Tool
from ..embeddings.service import EmbeddingService
from ..llm.lm_studio_client import LMStudioClient
from ..utils.logging import get_logger
from ..vector_store.qdrant_client import QdrantVectorStore


class DocumentChunk:
    """Represents a chunk of documentation."""

    def __init__(
        self,
        text: str,
        source: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ):
        self.text = text
        self.source = source
        self.metadata = metadata or {}
        self.embedding = embedding


class RAGPipeline:
    """RAG pipeline for document indexing and context-aware retrieval."""

    def __init__(
        self,
        config: MetaMCPConfig,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
        llm_client: LMStudioClient,
    ):
        self.config = config.rag
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.logger = get_logger(__name__)

    async def initialize(self) -> None:
        """Initialize the RAG pipeline."""
        self.logger.info("Initializing RAG pipeline")

        # Ensure dependencies are initialized
        if not self.vector_store.client:
            await self.vector_store.initialize()

        self.logger.info("RAG pipeline initialized")

    async def index_documentation(self, doc_path: str, source_id: str) -> None:
        """Index documentation file for RAG retrieval.

        Args:
            doc_path: Path to documentation file.
            source_id: Unique identifier for the documentation source.
        """
        try:
            doc_file = Path(doc_path)
            if not doc_file.exists():
                self.logger.warning(f"Documentation file not found: {doc_path}")
                return

            # Read documentation content
            content = doc_file.read_text(encoding="utf-8")

            # Split into chunks
            chunks = await self._create_chunks(content, source_id)

            if chunks:
                # Generate embeddings for chunks
                chunk_texts = [chunk.text for chunk in chunks]
                embeddings = await self.embedding_service.embed_batch(chunk_texts)

                # Prepare chunks with embeddings for storage
                chunks_with_embeddings = []
                for chunk, embedding in zip(chunks, embeddings, strict=False):
                    chunks_with_embeddings.append(
                        {
                            "text": chunk.text,
                            "embedding": embedding,
                            "metadata": chunk.metadata,
                        }
                    )

                # Store in vector database
                await self.vector_store.store_document_chunks(
                    chunks_with_embeddings, source_id
                )

                self.logger.info(
                    "Indexed documentation",
                    source=source_id,
                    chunks=len(chunks),
                    file_size=len(content),
                )

        except Exception as e:
            self.logger.error(
                "Failed to index documentation",
                source=source_id,
                path=doc_path,
                error=str(e),
            )

    async def _create_chunks(self, content: str, source_id: str) -> list[DocumentChunk]:
        """Split documentation content into chunks.

        Args:
            content: Documentation content.
            source_id: Source identifier.

        Returns:
            List of document chunks.
        """
        chunks = []

        # Split by sections first (markdown headers)
        sections = self._split_by_headers(content)

        for section_title, section_content in sections:
            # Further split large sections by paragraphs
            if len(section_content) > self.config.chunk_size * 2:
                sub_chunks = self._split_by_paragraphs(section_content)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunk = DocumentChunk(
                        text=sub_chunk,
                        source=source_id,
                        metadata={
                            "section": section_title,
                            "chunk_type": "paragraph",
                            "chunk_index": i,
                        },
                    )
                    chunks.append(chunk)
            else:
                # Use entire section as chunk
                chunk = DocumentChunk(
                    text=section_content,
                    source=source_id,
                    metadata={
                        "section": section_title,
                        "chunk_type": "section",
                    },
                )
                chunks.append(chunk)

        return chunks

    def _split_by_headers(self, content: str) -> list[tuple[str, str]]:
        """Split content by markdown headers.

        Args:
            content: Markdown content.

        Returns:
            List of (header, content) tuples.
        """
        sections = []
        current_section = ""
        current_header = "Introduction"

        lines = content.split("\n")
        for line in lines:
            # Check for markdown headers
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                # Save previous section
                if current_section.strip():
                    sections.append((current_header, current_section.strip()))

                # Start new section
                current_header = header_match.group(2)
                current_section = ""
            else:
                current_section += line + "\n"

        # Add final section
        if current_section.strip():
            sections.append((current_header, current_section.strip()))

        return sections

    def _split_by_paragraphs(self, content: str) -> list[str]:
        """Split content into paragraph chunks.

        Args:
            content: Content to split.

        Returns:
            List of paragraph chunks.
        """
        # Split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        # Combine small paragraphs and split large ones
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size
            if len(current_chunk) + len(paragraph) > self.config.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # If single paragraph is too large, split it further
                if len(paragraph) > self.config.chunk_size:
                    # Split by sentences
                    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                    temp_chunk = ""
                    for sentence in sentences:
                        if len(temp_chunk) + len(sentence) > self.config.chunk_size:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = sentence
                        else:
                            temp_chunk += " " + sentence if temp_chunk else sentence
                    if temp_chunk:
                        current_chunk = temp_chunk
                else:
                    current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def retrieve_relevant_context(
        self, query: str, sources: list[str] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documentation context for a query.

        Args:
            query: Query to search for.
            sources: Optional list of source IDs to filter by.
            limit: Maximum number of chunks to retrieve.

        Returns:
            List of relevant document chunks.
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed(query)

            # Search for relevant documents
            limit = limit or self.config.top_k
            relevant_docs = []

            if sources:
                # Search each source separately
                for source in sources:
                    docs = await self.vector_store.search_documents(
                        query_vector=query_embedding,
                        limit=limit // len(sources) + 1,
                        score_threshold=self.config.score_threshold,
                        source_filter=source,
                    )
                    relevant_docs.extend(docs)
            else:
                # Search all documents
                relevant_docs = await self.vector_store.search_documents(
                    query_vector=query_embedding,
                    limit=limit,
                    score_threshold=self.config.score_threshold,
                )

            # Sort by score and limit
            relevant_docs.sort(key=lambda x: x["score"], reverse=True)
            return relevant_docs[:limit]

        except Exception as e:
            self.logger.error("Failed to retrieve relevant context", error=str(e))
            return []

    async def augment_query_with_context(
        self, query: str, tools: list[Tool]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Augment query with relevant documentation context.

        Args:
            query: Original query.
            tools: Available tools.

        Returns:
            Tuple of (augmented_query, context_documents).
        """
        try:
            # Get sources from tools
            tool_sources = []
            for tool in tools:
                # Map tool server to documentation source
                source_id = f"{tool.server_name}_docs"
                if source_id not in tool_sources:
                    tool_sources.append(source_id)

            # Retrieve relevant context
            context_docs = await self.retrieve_relevant_context(
                query, sources=tool_sources
            )

            if not context_docs:
                return query, []

            # Build augmented query
            context_parts = []
            for doc in context_docs:
                context_parts.append(f"From {doc['source']}: {doc['text']}")

            augmented_query = f"""
User Query: {query}

Relevant Documentation Context:
{chr(10).join(context_parts)}

Based on the above context and user query, select the most appropriate tools.
"""

            self.logger.debug(
                "Augmented query with context",
                original_length=len(query),
                augmented_length=len(augmented_query),
                context_chunks=len(context_docs),
            )

            return augmented_query, context_docs

        except Exception as e:
            self.logger.error("Failed to augment query with context", error=str(e))
            return query, []

    async def generate_enhanced_tool_descriptions(
        self, tools: list[Tool]
    ) -> dict[str, str]:
        """Generate enhanced tool descriptions using RAG context.

        Args:
            tools: List of tools to enhance.

        Returns:
            Dictionary mapping tool IDs to enhanced descriptions.
        """
        enhanced_descriptions = {}

        try:
            for tool in tools:
                # Retrieve context for this specific tool
                tool_query = f"{tool.name} {tool.description}"
                context_docs = await self.retrieve_relevant_context(
                    tool_query, sources=[f"{tool.server_name}_docs"], limit=2
                )

                if context_docs:
                    # Generate enhanced description
                    context_text = "\n".join(doc["text"] for doc in context_docs)

                    enhancement_prompt = f"""
Tool: {tool.name}
Original Description: {tool.description}

Additional Context:
{context_text}

Create an enhanced, comprehensive description for this tool that incorporates the additional context while keeping the original meaning. Be concise but informative.
"""

                    messages = [
                        {
                            "role": "system",
                            "content": "You are a technical writer creating enhanced tool descriptions.",
                        },
                        {"role": "user", "content": enhancement_prompt},
                    ]

                    enhanced_desc = await self.llm_client.chat_complete(
                        messages=messages, temperature=0.3, max_tokens=200
                    )

                    enhanced_descriptions[tool.id] = enhanced_desc.strip()

                    self.logger.debug(
                        "Enhanced tool description",
                        tool_id=tool.id,
                        context_chunks=len(context_docs),
                    )

        except Exception as e:
            self.logger.error("Failed to generate enhanced descriptions", error=str(e))

        return enhanced_descriptions

    async def cleanup(self) -> None:
        """Clean up RAG pipeline resources."""
        self.logger.info("Cleaning up RAG pipeline")
        # Vector store and other services cleanup handled by main server

    def get_metrics(self) -> dict[str, Any]:
        """Get RAG pipeline metrics.

        Returns:
            Dictionary with metrics information.
        """
        return {
            "chunk_size": self.config.chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
            "top_k": self.config.top_k,
            "score_threshold": self.config.score_threshold,
            "include_examples": self.config.include_examples,
        }
