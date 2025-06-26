"""Embedding service with LM Studio primary and sentence-transformers fallback."""

import asyncio
import hashlib
import pickle
from pathlib import Path
from typing import Any

import httpx

from ..config.models import MetaMCPConfig
from ..utils.logging import get_logger


class EmbeddingService:
    """Unified embedding service with multiple backends."""

    def __init__(self, config: MetaMCPConfig):
        self.config = config.embeddings
        self.logger = get_logger(__name__)
        self.lm_studio_client: httpx.AsyncClient | None = None
        self.sentence_transformer_model: Any | None = None
        self._cache: dict[str, list[float]] = {}
        self._cache_dir = Path(self.config.cache_dir)
        self._cache_file = self._cache_dir / "embeddings_cache.pkl"

    async def initialize(self) -> None:
        """Initialize the embedding service with fallback strategy."""
        self.logger.info("Initializing embedding service")

        # Create cache directory
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        await self._load_cache()

        # Try to initialize LM Studio client
        if self.config.lm_studio_endpoint:
            await self._initialize_lm_studio()

        # Initialize sentence transformers fallback
        await self._initialize_sentence_transformers()

        self.logger.info(
            "Embedding service initialized",
            lm_studio_available=self.lm_studio_client is not None,
            fallback_model=self.config.fallback_model,
            cache_size=len(self._cache),
        )

    async def _initialize_lm_studio(self) -> None:
        """Initialize LM Studio client if available."""
        try:
            self.lm_studio_client = httpx.AsyncClient(
                base_url=self.config.lm_studio_endpoint.rstrip("/"),
                timeout=30.0,
            )

            # Test connection with a simple embedding request
            test_response = await self.lm_studio_client.post(
                "/embeddings",
                json={
                    "input": "test",
                    "model": self.config.lm_studio_model,
                },
            )

            if test_response.status_code == 200:
                self.logger.info("LM Studio embedding service connected successfully")
            else:
                raise httpx.HTTPError(f"HTTP {test_response.status_code}")

        except Exception as e:
            self.logger.warning(
                "LM Studio not available, using fallback",
                endpoint=self.config.lm_studio_endpoint,
                error=str(e),
            )
            if self.lm_studio_client:
                await self.lm_studio_client.aclose()
                self.lm_studio_client = None

    async def _initialize_sentence_transformers(self) -> None:
        """Initialize sentence transformers fallback model."""
        try:
            # Import and load model in a thread to avoid blocking
            def load_model():
                from sentence_transformers import SentenceTransformer

                return SentenceTransformer(self.config.fallback_model)

            self.sentence_transformer_model = (
                await asyncio.get_event_loop().run_in_executor(None, load_model)
            )

            self.logger.info(
                "Sentence transformer model loaded",
                model=self.config.fallback_model,
            )

        except Exception as e:
            self.logger.error(
                "Failed to load sentence transformer model",
                model=self.config.fallback_model,
                error=str(e),
            )
            raise

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text using available backend.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.

        Raises:
            RuntimeError: If no embedding backend is available.
        """
        # Check cache first
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try LM Studio first
        if self.lm_studio_client:
            try:
                embedding = await self._embed_lm_studio(text)
                self._cache[cache_key] = embedding
                return embedding
            except Exception as e:
                self.logger.warning(
                    "LM Studio embedding failed, using fallback",
                    error=str(e),
                )

        # Use sentence transformers fallback
        if self.sentence_transformer_model:
            embedding = await self._embed_sentence_transformers(text)
            self._cache[cache_key] = embedding
            return embedding

        raise RuntimeError("No embedding backend available")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        # Check which texts are already cached
        cached_embeddings = {}
        uncached_texts = []

        for text in texts:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                cached_embeddings[text] = self._cache[cache_key]
            else:
                uncached_texts.append(text)

        # Generate embeddings for uncached texts
        if uncached_texts:
            if self.lm_studio_client and len(uncached_texts) <= self.config.batch_size:
                try:
                    new_embeddings = await self._embed_batch_lm_studio(uncached_texts)
                    for text, embedding in zip(
                        uncached_texts, new_embeddings, strict=False
                    ):
                        cache_key = self._get_cache_key(text)
                        self._cache[cache_key] = embedding
                        cached_embeddings[text] = embedding
                except Exception as e:
                    self.logger.warning(
                        "LM Studio batch embedding failed",
                        error=str(e),
                    )
                    # Fall back to individual embeddings
                    for text in uncached_texts:
                        embedding = await self.embed(text)
                        cached_embeddings[text] = embedding
            else:
                # Use sentence transformers or individual embeddings
                for text in uncached_texts:
                    embedding = await self.embed(text)
                    cached_embeddings[text] = embedding

        # Return embeddings in original order
        return [cached_embeddings[text] for text in texts]

    async def _embed_lm_studio(self, text: str) -> list[float]:
        """Generate embedding using LM Studio.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        response = await self.lm_studio_client.post(
            "/embeddings",
            json={
                "input": text,
                "model": self.config.lm_studio_model,
            },
        )

        response.raise_for_status()
        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        else:
            raise ValueError("Invalid embedding response from LM Studio")

    async def _embed_batch_lm_studio(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using LM Studio.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        response = await self.lm_studio_client.post(
            "/embeddings",
            json={
                "input": texts,
                "model": self.config.lm_studio_model,
            },
        )

        response.raise_for_status()
        data = response.json()

        if "data" in data:
            return [item["embedding"] for item in data["data"]]
        else:
            raise ValueError("Invalid batch embedding response from LM Studio")

    async def _embed_sentence_transformers(self, text: str) -> list[float]:
        """Generate embedding using sentence transformers.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """

        def encode_text():
            return self.sentence_transformer_model.encode([text])[0].tolist()

        embedding = await asyncio.get_event_loop().run_in_executor(None, encode_text)
        return embedding

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text.

        Args:
            text: Text to generate key for.

        Returns:
            Cache key string.
        """
        # Include model info in cache key
        model_info = (
            self.config.lm_studio_model
            if self.lm_studio_client
            else self.config.fallback_model
        )
        combined = f"{model_info}:{text}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def _load_cache(self) -> None:
        """Load embedding cache from disk."""
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "rb") as f:
                    self._cache = pickle.load(f)
                self.logger.debug(f"Loaded {len(self._cache)} cached embeddings")
        except Exception as e:
            self.logger.warning("Failed to load embedding cache", error=str(e))
            self._cache = {}

    async def save_cache(self) -> None:
        """Save embedding cache to disk."""
        try:
            with open(self._cache_file, "wb") as f:
                pickle.dump(self._cache, f)
            self.logger.debug(f"Saved {len(self._cache)} embeddings to cache")
        except Exception as e:
            self.logger.warning("Failed to save embedding cache", error=str(e))

    async def cleanup(self) -> None:
        """Clean up embedding service resources."""
        self.logger.info("Cleaning up embedding service")

        # Save cache
        await self.save_cache()

        # Close LM Studio client
        if self.lm_studio_client:
            await self.lm_studio_client.aclose()

        self.logger.info("Embedding service cleanup complete")

    def get_metrics(self) -> dict[str, Any]:
        """Get embedding service metrics.

        Returns:
            Dictionary with metrics information.
        """
        return {
            "cache_size": len(self._cache),
            "lm_studio_available": self.lm_studio_client is not None,
            "fallback_model": self.config.fallback_model,
            "cache_hit_rate": getattr(self, "_cache_hits", 0)
            / max(getattr(self, "_total_requests", 1), 1),
        }
