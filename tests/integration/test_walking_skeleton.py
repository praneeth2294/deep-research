"""End-to-end integration tests.

Run the REAL pipeline (Gemini + Tavily) — costs a few API calls.
Skipped automatically when keys are absent (e.g. in CI).
Run locally with:  uv run pytest tests/integration -s
"""

import re

import pytest

from deep_research.config import get_settings

_settings = get_settings()
requires_keys = pytest.mark.skipif(
    _settings.google_api_key is None or _settings.tavily_api_key is None,
    reason="GOOGLE_API_KEY / TAVILY_API_KEY not configured",
)


@requires_keys
def test_deep_pipeline_produces_cited_report() -> None:
    from deep_research.graph.builder import build_graph

    result = build_graph(hitl=False).invoke(
        {"topic": "Compare LangGraph and CrewAI for building production multi-agent systems"}
    )

    assert result["route"] in ("deep_research", "comparison")
    assert 1 <= len(result["sub_topics"]) <= 3
    assert len(result["sources"]) >= 1
    report = result["report"]
    assert len(report) > 200
    # At least one inline citation, any style: [1], [8], [2, 5] ...
    assert re.search(r"\[\d{1,3}[\],]", report), "report has no inline citations"


@requires_keys
def test_simple_lookup_short_path() -> None:
    from deep_research.graph.builder import build_graph

    result = build_graph(hitl=False).invoke({"topic": "What does RAG stand for in AI?"})

    assert result["route"] == "simple_lookup"
    assert "sub_topics" not in result  # planner never ran
    assert len(result.get("report", "")) > 20
