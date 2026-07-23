"""Tiering layer: fallback fault-injection and budget gating (no network)."""

from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from deep_research.config import Settings
from deep_research.guardrails.budget import BudgetExceededError, check_budget
from deep_research.llm import tiering
from deep_research.observability import cost as cost_mod
from deep_research.schemas.routing import RouteDecision


class _FakeModel:
    """Stands in for a chat model: fails N times or answers."""

    def __init__(self, name: str, fail: bool) -> None:
        self.name = name
        self.fail = fail

    def with_structured_output(self, _schema: Any) -> RunnableLambda[Any, Any]:
        def run(_input: Any) -> Any:
            if self.fail:
                raise RuntimeError(f"503 UNAVAILABLE from {self.name}")
            return RouteDecision(route="simple_lookup", reason=f"answered by {self.name}")

        return RunnableLambda(run)

    def with_fallbacks(self, fallbacks: Any) -> Any:  # pragma: no cover - not used directly
        raise NotImplementedError


def test_fallback_takes_over_when_primary_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fault injection: primary model 503s on every call -> fallback answers."""
    primary = _FakeModel("primary", fail=True)
    backup = _FakeModel("backup", fail=False)

    def fake_model_chain(_tier: str, _temperature: float) -> list[Any]:
        return [primary, backup]

    monkeypatch.setattr(tiering, "_model_chain", fake_model_chain)

    result = tiering.structured_llm(RouteDecision, tier="cheap").invoke("question")
    assert result.reason == "answered by backup"


def test_all_models_failing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_model_chain(_tier: str, _temperature: float) -> list[Any]:
        return [_FakeModel("a", fail=True), _FakeModel("b", fail=True)]

    monkeypatch.setattr(tiering, "_model_chain", fake_model_chain)
    with pytest.raises(RuntimeError, match="503"):
        tiering.structured_llm(RouteDecision, tier="cheap").invoke("question")


def test_budget_gate_blocks_before_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once spend >= cap, the next LLM call raises BEFORE reaching any model."""
    monkeypatch.setattr(cost_mod.session_cost, "total_cost_usd", lambda: 99.0)

    called = {"model": False}

    class _Spy(_FakeModel):
        def with_structured_output(self, _schema: Any) -> RunnableLambda[Any, Any]:
            def run(_input: Any) -> Any:
                called["model"] = True
                return RouteDecision(route="simple_lookup", reason="should never happen")

            return RunnableLambda(run)

    monkeypatch.setattr(tiering, "_model_chain", lambda _t, _temp: [_Spy("primary", fail=False)])
    with pytest.raises(BudgetExceededError, match="budget exhausted"):
        tiering.structured_llm(RouteDecision).invoke("question")
    assert called["model"] is False  # the gate fired before any model ran


def test_check_budget_passes_under_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost_mod.session_cost, "total_cost_usd", lambda: 0.01)
    check_budget()  # must not raise (default cap is $1)


def test_model_chain_config_parsing() -> None:
    settings = Settings(
        _env_file=None,
        cheap_model="m-main",
        cheap_fallbacks="m-fb1, m-fb2 ,",
        strong_model="m-strong",
        strong_fallbacks="",
    )
    assert settings.cheap_model_chain == ["m-main", "m-fb1", "m-fb2"]
    assert settings.strong_model_chain == ["m-strong"]
