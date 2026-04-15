"""LLM Provider Client Service."""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from sentinel.core.config import settings

logger = logging.getLogger(__name__)


def _get_meter():
    """Lazy load meter."""
    try:
        from sentinel.core.telemetry import telemetry_manager
        return telemetry_manager.get_meter(__name__)
    except RuntimeError:
        import opentelemetry.metrics as metrics
        return metrics.get_meter(__name__)


class LLMClient:
    """Async LLM provider client wrapper.

    Supports multiple providers (OpenAI, Gemini, Claude) with
    streaming and non-streaming interfaces.
    """

    def __init__(self, provider: str = "openai", timeout: float = 30.0):
        """Initialize LLM client.

        Args:
            provider: LLM provider name (openai, gemini, anthropic).
            timeout: Request timeout in seconds.
        """
        self.provider = provider.lower()
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._initialize_provider_config()

    def _initialize_provider_config(self) -> None:
        """Initialize provider-specific configuration."""
        if self.provider == "openai":
            self.base_url = settings.openai_base_url
            self.api_key = settings.openai_api_key
            self.model = "gpt-4"
        elif self.provider == "gemini":
            self.base_url = "https://generativelanguage.googleapis.com"
            self.api_key = settings.gemini_api_key
            self.model = "gemini-pro"
        elif self.provider == "anthropic":
            self.base_url = "https://api.anthropic.com"
            self.api_key = settings.anthropic_api_key
            self.model = "claude-3-sonnet"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        if not self.api_key:
            logger.warning(f"No API key configured for {self.provider}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Send non-streaming chat completion request.

        Args:
            messages: List of message dicts with role/content.
            model: Model to use (overrides default).
            temperature: Sampling temperature.
            max_tokens: Max tokens in response.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Completion response dict.
        """
        model = model or self.model

        if self.provider == "openai":
            return await self._openai_chat_completion(
                messages, model, temperature, max_tokens, **kwargs
            )
        elif self.provider == "gemini":
            return await self._gemini_chat_completion(
                messages, model, temperature, max_tokens, **kwargs
            )
        elif self.provider == "anthropic":
            return await self._anthropic_chat_completion(
                messages, model, temperature, max_tokens, **kwargs
            )

        raise RuntimeError(f"Provider {self.provider} not implemented")

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Send streaming chat completion request.

        Args:
            messages: List of message dicts with role/content.
            model: Model to use (overrides default).
            temperature: Sampling temperature.
            max_tokens: Max tokens in response.
            **kwargs: Additional provider-specific parameters.

        Yields:
            Streaming response chunks.
        """
        model = model or self.model

        if self.provider == "openai":
            async for chunk in self._openai_stream(
                messages, model, temperature, max_tokens, **kwargs
            ):
                yield chunk
        elif self.provider == "gemini":
            async for chunk in self._gemini_stream(
                messages, model, temperature, max_tokens, **kwargs
            ):
                yield chunk
        elif self.provider == "anthropic":
            async for chunk in self._anthropic_stream(
                messages, model, temperature, max_tokens, **kwargs
            ):
                yield chunk

    async def _openai_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """OpenAI chat completion request."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def _openai_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """OpenAI streaming chat completion."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str != "[DONE]":
                        try:
                            import json

                            yield json.loads(data_str)
                        except Exception as e:
                            logger.warning(f"Failed to parse stream chunk: {e}")

    async def _gemini_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Gemini chat completion request."""
        # Placeholder implementation
        logger.warning("Gemini implementation not yet complete")
        raise NotImplementedError("Gemini provider not yet implemented")

    async def _gemini_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Gemini streaming chat completion."""
        # Placeholder implementation
        raise NotImplementedError("Gemini streaming not yet implemented")

    async def _anthropic_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Anthropic chat completion request."""
        # Placeholder implementation
        raise NotImplementedError("Anthropic provider not yet implemented")

    async def _anthropic_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Anthropic streaming chat completion."""
        # Placeholder implementation
        raise NotImplementedError("Anthropic streaming not yet implemented")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "LLMClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
