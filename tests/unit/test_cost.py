"""Cost tracker: price attribution and summary (no network)."""

import pytest

from deep_research.observability.cost import CostTracker


def _load(tracker: CostTracker, model: str, input_tokens: int, output_tokens: int) -> None:
    tracker.callback.usage_metadata[model] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def test_totals_and_cost_by_model_class() -> None:
    tracker = CostTracker()
    _load(tracker, "gemini-flash-latest", 1_000_000, 100_000)  # flash: $0.30 in + $0.25 out
    _load(tracker, "gemini-3.1-flash-lite", 1_000_000, 0)  # flash-lite: $0.10 in

    input_tokens, output_tokens = tracker.total_tokens()
    assert (input_tokens, output_tokens) == (2_000_000, 100_000)
    assert tracker.total_cost_usd() == pytest.approx(0.30 + 0.25 + 0.10, rel=1e-6)


def test_summary_mentions_models() -> None:
    tracker = CostTracker()
    _load(tracker, "gemini-flash-latest", 1000, 200)
    summary = tracker.summary()
    assert "gemini-flash-latest" in summary
    assert "1,000 in" in summary
