"""LLM client factory — tiering v1 (Phases 1-2).

Two tiers: `cheap_llm()` for high-frequency/low-difficulty calls (planner,
replanner, reviewer) and `strong_llm()` for judgment-heavy calls (analyst,
synthesizer, writer). Phase 3 adds provider fallbacks and cost tracking.
No node constructs a raw client or hardcodes a model name — everything goes
through this factory, which is the single place retries and (later) fallbacks
are configured.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from deep_research.config import get_settings

_MAX_RETRIES = 3


def _build(model: str, temperature: float) -> BaseChatModel:
    settings = get_settings()
    if settings.google_api_key is None:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://aistudio.google.com/apikey)."
        )
    return ChatGoogleGenerativeAI(
        model=model,
        api_key=settings.google_api_key,
        temperature=temperature,
        max_retries=_MAX_RETRIES,  # exponential backoff on 429/5xx, handled by the client
    )


def cheap_llm(temperature: float = 0.0) -> BaseChatModel:
    """Fast/cheap model: planner, replanner, reviewer, (later) router.

    Raises a clear error at call time (not import time) if the key is missing,
    so tooling and tests run without credentials.
    """
    return _build(get_settings().cheap_model, temperature)


def strong_llm(temperature: float = 0.0) -> BaseChatModel:
    """Strong model: analyst, synthesizer, writer (judgment-heavy work)."""
    return _build(get_settings().strong_model, temperature)
