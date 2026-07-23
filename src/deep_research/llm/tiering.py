"""LLM access layer — tiering v2 (Phase 3).

Every node gets its model through two functions:

    structured_llm(Schema, tier="cheap")  -> Runnable returning a validated Schema
    text_llm(tier="strong")               -> Runnable returning an AIMessage

What the returned runnable includes, outside-in:
1. **Budget gate** — raises BudgetExceededError before the call once the
   session cost cap is reached (no runaway loop can outspend it).
2. **Fallback chain** — primary model, then the configured fallbacks; any
   failure (429 quota, 5xx overload, 404 retirement) falls through to the
   next model. Retries with backoff happen *inside* each model first.
3. **Rate limiter** — one shared token bucket across all models/parallel
   branches, respecting the provider RPM cap.

No node ever constructs a client or names a model.
"""

from typing import Any, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from deep_research.config import get_settings
from deep_research.guardrails.budget import check_budget
from deep_research.guardrails.rate_limit import get_rate_limiter

Tier = Literal["cheap", "strong"]

_MAX_RETRIES = 2  # per-model backoff retries; fallbacks handle persistent failure


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
        max_retries=_MAX_RETRIES,
        rate_limiter=get_rate_limiter(),
    )


def _model_chain(tier: Tier, temperature: float) -> list[BaseChatModel]:
    settings = get_settings()
    names = settings.cheap_model_chain if tier == "cheap" else settings.strong_model_chain
    return [_build(name, temperature) for name in names]


def _guarded(chain: Runnable[Any, Any]) -> Runnable[Any, Any]:
    """Prepend the budget gate to a runnable."""

    def _gate(value: Any) -> Any:
        check_budget()
        return value

    return cast("Runnable[Any, Any]", RunnableLambda(_gate) | chain)


def structured_llm(
    schema: type[BaseModel], *, tier: Tier = "cheap", temperature: float = 0.0
) -> Runnable[Any, Any]:
    """Budget-gated, fallback-chained model that returns a validated `schema`."""
    models = _model_chain(tier, temperature)
    runnables = [m.with_structured_output(schema) for m in models]
    chain = runnables[0].with_fallbacks(runnables[1:]) if len(runnables) > 1 else runnables[0]
    return _guarded(chain)


def text_llm(*, tier: Tier = "strong", temperature: float = 0.0) -> Runnable[Any, Any]:
    """Budget-gated, fallback-chained model that returns a raw AIMessage."""
    models = _model_chain(tier, temperature)
    chain: Runnable[Any, Any] = (
        models[0].with_fallbacks(models[1:]) if len(models) > 1 else models[0]
    )
    return _guarded(chain)
