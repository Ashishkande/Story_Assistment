"""LLM abstraction layer – configurable provider/model via env vars."""
from __future__ import annotations

import time
import logging
from typing import Any

import tiktoken
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cost per 1000 tokens (input, output) for common models
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    # Anthropic
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-haiku-20240307": (0.00025, 0.00125),
    # Google
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
}


def get_llm() -> BaseChatModel:
    """Return a configured LLM based on environment settings."""
    settings = get_settings()

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
            max_tokens=settings.max_tokens_per_episode,
        )
    elif settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.max_tokens_per_episode,
        )
    elif settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            google_api_key=settings.google_api_key,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Estimate token count for a text string."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _message_text(content: Any) -> str:
    """Normalize provider content blocks to a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def estimate_cost(input_tokens: int, output_tokens: int, model: str | None = None) -> float:
    """Estimate generation cost in USD."""
    settings = get_settings()
    model = model or settings.llm_model
    costs = MODEL_COSTS.get(model, (0.001, 0.002))
    return (input_tokens / 1000) * costs[0] + (output_tokens / 1000) * costs[1]


class LLMRunner:
    """Wraps LLM calls with token counting, cost estimation, and latency tracking."""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or get_llm()
        self.settings = get_settings()

    def invoke(
        self,
        messages: list[BaseMessage] | list[dict],
        *,
        agent_name: str = "unknown",
    ) -> tuple[str, dict[str, Any]]:
        """
        Call the LLM and return (content, metadata).
        metadata includes: input_tokens, output_tokens, cost, latency_ms
        """
        # Stringify for token counting
        prompt_text = " ".join(
            m.content if hasattr(m, "content") else str(m) for m in messages
        )
        input_tokens = count_tokens(prompt_text)

        start = time.monotonic()
        response = self.llm.invoke(messages)
        latency_ms = int((time.monotonic() - start) * 1000)

        content = _message_text(response.content if hasattr(response, "content") else response)
        output_tokens = count_tokens(content)
        cost = estimate_cost(input_tokens, output_tokens)
        response_meta = getattr(response, "response_metadata", None) or {}
        finish_reason = response_meta.get("finish_reason") or response_meta.get("stop_reason")

        # Cost guard
        if cost > self.settings.max_cost_per_episode:
            logger.warning(
                f"[{agent_name}] Cost ${cost:.4f} exceeds per-episode limit "
                f"${self.settings.max_cost_per_episode}"
            )

        metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "latency_ms": latency_ms,
            "model": self.settings.llm_model,
            "finish_reason": finish_reason,
        }
        logger.debug(f"[{agent_name}] tokens={input_tokens}+{output_tokens} cost=${cost:.4f} latency={latency_ms}ms")
        return content, metadata
