"""LLM client factory — tiering v0 (Phase 1).

Phase 1 uses a single tier: the cheap/fast model for every node. Phase 3
extends this with `strong_llm()`, provider fallbacks, and cost tracking.
No node constructs a raw client or hardcodes a model name — everything goes
through this factory, which is the single place retries and (later) fallbacks
are configured.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from deep_research.config import get_settings

_MAX_RETRIES = 3


def cheap_llm(temperature: float = 0.0) -> BaseChatModel:
    """Fast/cheap model (router, planner, reviewer, walking-skeleton nodes).

    Raises a clear error at call time (not import time) if the key is missing,
    so tooling and tests run without credentials.
    """
    settings = get_settings()
    if settings.google_api_key is None:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://aistudio.google.com/apikey)."
        )
    return ChatGoogleGenerativeAI(
        model=settings.cheap_model,
        api_key=settings.google_api_key,
        temperature=temperature,
        max_retries=_MAX_RETRIES,  # exponential backoff on 429/5xx, handled by the client
    )
