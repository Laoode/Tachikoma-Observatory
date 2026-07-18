"""Thin async wrapper over the LiteLLM OpenAI-compatible proxy."""

import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from observatory.config import LLMConfig

REQUEST_TIMEOUT_S = 90.0


@dataclass(frozen=True)
class ChatResult:
    """One chat completion round-trip.

    Args:
        message: The assistant message as a plain dict (content, tool_calls).
        latency_ms: Wall-clock request latency.
        prompt_tokens: Usage reported by the server, 0 if absent.
        completion_tokens: Usage reported by the server, 0 if absent.
    """

    message: dict
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def tool_calls(self) -> list[dict]:
        """Tool calls on the message, empty list when none."""
        return self.message.get("tool_calls") or []


@dataclass
class LLMClient:
    """Async client bound to one OpenAI-compatible endpoint.

    Args:
        config: Endpoint base URL and master key.
    """

    config: LLMConfig
    _client: AsyncOpenAI = field(init=False, repr=False)

    def __post_init__(self):
        """Create the underlying AsyncOpenAI client."""
        self._client = AsyncOpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=REQUEST_TIMEOUT_S,
        )

    async def list_models(self) -> list[str]:
        """List model IDs registered on the proxy.

        Returns:
            Sorted model ID strings from GET /v1/models.
        """
        page = await self._client.models.list()
        return sorted(m.id for m in page.data)

    async def chat(
        self, model: str, messages: list[dict], tools: list[dict]
    ) -> ChatResult:
        """Send one chat completion request with tools enabled.

        Args:
            model: Model ID on the proxy.
            messages: Full conversation so far (OpenAI message dicts).
            tools: Tool definitions to expose.

        Returns:
            The assistant reply with usage and latency.
        """
        started = time.monotonic()
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        usage = response.usage
        message = response.choices[0].message.model_dump(exclude_none=True)
        return ChatResult(
            message=message,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
