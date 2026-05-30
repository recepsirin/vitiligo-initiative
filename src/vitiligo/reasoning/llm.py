"""LLM client wrapper.

Anthropic-first because Claude is well-suited to careful, citation-aware
biomedical reasoning. The interface is small enough to swap in another
provider later (OpenAI, local, etc.) without touching the RAG or
hypothesis layers.
"""

from __future__ import annotations

from dataclasses import dataclass

from vitiligo.config import Settings, get_settings
from vitiligo.logging import get_logger
from vitiligo.reasoning.exceptions import LLMUnavailable

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class LLMClient:
    """Thin wrapper around the Anthropic Messages API.

    Reads the API key and model from configuration. Raises
    `LLMUnavailable` with a clear message if the key is missing — we
    never silently fall back to a degraded mode.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.anthropic_api_key:
            raise LLMUnavailable(
                "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example) to enable reasoning features."
            )
        from anthropic import Anthropic

        self._client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = self.settings.anthropic_model

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send a single-turn message and return the assistant's text + usage."""
        logger.debug(
            "LLM call: model=%s system_len=%d user_len=%d", self.model, len(system), len(user)
        )
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Extract text content (the SDK returns a list of content blocks).
        text_parts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
        text = "".join(text_parts).strip()

        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
        )
