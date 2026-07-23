"""End-to-end walking-skeleton test.

Runs the REAL pipeline (Gemini + Tavily) — costs a few API calls.
Skipped automatically when keys are absent (e.g. in CI).
Run locally with:  uv run pytest tests/integration -s
"""

import pytest

from deep_research.config import get_settings

_settings = get_settings()
requires_keys = pytest.mark.skipif(
    _settings.google_api_key is None or _settings.tavily_api_key is None,
    reason="GOOGLE_API_KEY / TAVILY_API_KEY not configured",
)


@requires_keys
def test_pipeline_produces_cited_report() -> None:
    from deep_research.graph.builder import build_graph

    result = build_graph().invoke({"topic": "What is LangGraph and what is it used for?"})

    assert 1 <= len(result["sub_topics"]) <= 3
    assert len(result["sources"]) >= 1
    report = result["report"]
    assert len(report) > 200
    assert "[1]" in report  # at least one inline citation
