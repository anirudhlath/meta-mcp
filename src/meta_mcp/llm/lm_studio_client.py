"""LM Studio client for local LLM integration."""

import json
from typing import Any

import httpx

from ..config.models import MetaMCPConfig
from ..utils.logging import get_logger


class LMStudioClient:
    """Client for interacting with LM Studio's local LLM API."""

    def __init__(self, config: MetaMCPConfig):
        self.config = config.llm
        self.logger = get_logger(__name__)
        self.client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the LM Studio client."""
        self.logger.info("Initializing LM Studio client")

        try:
            self.client = httpx.AsyncClient(
                base_url=self.config.endpoint.rstrip("/"),
                timeout=60.0,
            )

            # Test connection
            await self._test_connection()

            self.logger.info(
                "LM Studio client initialized",
                endpoint=self.config.endpoint,
                model=self.config.model,
            )

        except Exception as e:
            self.logger.error("Failed to initialize LM Studio client", error=str(e))
            raise

    async def _test_connection(self) -> None:
        """Test connection to LM Studio."""
        try:
            if self.client is None:
                raise RuntimeError("Client not initialized")

            response = await self.client.get("/models")
            if response.status_code == 200:
                models_data = response.json()
                self.logger.debug(
                    "LM Studio connection successful",
                    available_models=len(models_data.get("data", [])),
                )
            else:
                raise httpx.HTTPError(f"HTTP {response.status_code}")
        except Exception as e:
            self.logger.warning("LM Studio connection test failed", error=str(e))
            # Don't raise here as the service might still work

    async def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """Generate text completion using LM Studio.

        Args:
            prompt: Input prompt for completion.
            temperature: Generation temperature (overrides config).
            max_tokens: Maximum tokens to generate (overrides config).
            stop: Stop sequences for generation.

        Returns:
            Generated text completion.

        Raises:
            RuntimeError: If completion fails.
        """
        if not self.client:
            raise RuntimeError("LM Studio client not initialized")

        try:
            request_data = {
                "model": self.config.model,
                "prompt": prompt,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
                "stream": False,
            }

            if stop:
                request_data["stop"] = stop

            response = await self.client.post("/completions", json=request_data)
            response.raise_for_status()

            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["text"].strip()
            else:
                raise ValueError("Invalid completion response")

        except Exception as e:
            self.logger.error("LM Studio completion failed", error=str(e))
            raise RuntimeError(f"Completion failed: {e}") from e

    async def chat_complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate chat completion using LM Studio.

        Args:
            messages: List of chat messages.
            temperature: Generation temperature (overrides config).
            max_tokens: Maximum tokens to generate (overrides config).

        Returns:
            Generated chat completion.

        Raises:
            RuntimeError: If completion fails.
        """
        if not self.client:
            raise RuntimeError("LM Studio client not initialized")

        try:
            request_data = {
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
                "stream": False,
            }

            response = await self.client.post("/chat/completions", json=request_data)
            response.raise_for_status()

            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            else:
                raise ValueError("Invalid chat completion response")

        except Exception as e:
            self.logger.error("LM Studio chat completion failed", error=str(e))
            raise RuntimeError(f"Chat completion failed: {e}") from e

    async def generate_tool_selection(
        self,
        query: str,
        available_tools: list[dict[str, Any]],
        max_tools: int = 10,
    ) -> dict[str, Any]:
        """Generate tool selection using structured prompting.

        Args:
            query: User query/context.
            available_tools: List of available tools with metadata.
            max_tools: Maximum tools to select.

        Returns:
            Structured tool selection response.

        Raises:
            RuntimeError: If tool selection fails.
        """
        # Build tool selection prompt
        prompt = self._build_tool_selection_prompt(query, available_tools, max_tools)

        try:
            # Use chat completion for better structured output
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert tool selector. Your job is to analyze a user query "
                        "and select the most relevant tools from the available options. "
                        "Always respond with valid JSON format."
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            response = await self.chat_complete(
                messages=messages, temperature=0.1, max_tokens=1000
            )

            # Parse JSON response
            try:
                result = json.loads(response)
                return self._validate_tool_selection_response(result, available_tools)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)
                    return self._validate_tool_selection_response(
                        result, available_tools
                    )
                else:
                    raise ValueError("No valid JSON found in response") from None

        except Exception as e:
            self.logger.error("Tool selection generation failed", error=str(e))
            # Return empty selection on error
            return {
                "selected_tools": [],
                "reasoning": f"Error in tool selection: {str(e)}",
                "confidence": 0.0,
            }

    def _build_tool_selection_prompt(
        self,
        query: str,
        available_tools: list[dict[str, Any]],
        max_tools: int,
    ) -> str:
        """Build prompt for tool selection.

        Args:
            query: User query.
            available_tools: Available tools.
            max_tools: Maximum tools to select.

        Returns:
            Formatted prompt string.
        """
        tools_text = "\n".join(
            f"- {tool['id']}: {tool['description']}"
            for tool in available_tools[:50]  # Limit for context
        )

        prompt = f"""
Analyze this user query and select the most relevant tools:

USER QUERY: "{query}"

AVAILABLE TOOLS:
{tools_text}

Select up to {max_tools} most relevant tools for this query. Consider:
1. Direct relevance to the query
2. Complementary tools that work well together
3. Tools that might be needed for follow-up actions

Respond with JSON in this exact format:
{{
    "selected_tools": ["tool.id1", "tool.id2", ...],
    "reasoning": "Brief explanation of why these tools were selected",
    "confidence": 0.85
}}

The confidence should be between 0.0 and 1.0 based on how certain you are about the selections.
"""
        return prompt

    def _validate_tool_selection_response(
        self,
        response: dict[str, Any],
        available_tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate and sanitize tool selection response.

        Args:
            response: Raw response from LLM.
            available_tools: Available tools for validation.

        Returns:
            Validated response.
        """
        # Get available tool IDs
        available_ids = {tool["id"] for tool in available_tools}

        # Validate selected tools
        selected_tools = response.get("selected_tools", [])
        if not isinstance(selected_tools, list):
            selected_tools = []

        # Filter to only valid tool IDs
        valid_tools = [
            tool_id for tool_id in selected_tools if tool_id in available_ids
        ]

        # Validate confidence
        confidence = response.get("confidence", 0.5)
        if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
            confidence = 0.5

        # Validate reasoning
        reasoning = response.get("reasoning", "No reasoning provided")
        if not isinstance(reasoning, str):
            reasoning = "Invalid reasoning format"

        return {
            "selected_tools": valid_tools,
            "reasoning": reasoning,
            "confidence": float(confidence),
            "original_count": len(selected_tools),
            "valid_count": len(valid_tools),
        }

    async def cleanup(self) -> None:
        """Clean up LM Studio client resources."""
        self.logger.info("Cleaning up LM Studio client")

        if self.client:
            await self.client.aclose()

        self.logger.info("LM Studio client cleanup complete")

    def get_metrics(self) -> dict[str, Any]:
        """Get LM Studio client metrics.

        Returns:
            Dictionary with metrics information.
        """
        return {
            "endpoint": self.config.endpoint,
            "model": self.config.model,
            "available": self.client is not None,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
