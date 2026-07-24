"""Live eval suite — runs the REAL pipeline against the golden dataset.

Costs API calls; excluded from the default pytest run (marker `evals`) and
self-skips without keys. Sample size comes from EVAL_SAMPLE_SIZE (small on
PR, full nightly).

    uv run pytest tests/evals -m evals -s
"""

import json
from pathlib import Path
from typing import Any

import pytest

from deep_research.config import get_settings
from tests.evals.judges import check_citations, judge_report

_DATASET = Path(__file__).parent / "golden_dataset.jsonl"
_MIN_FAITHFULNESS = 7
_MIN_COVERAGE = 7

_settings = get_settings()
requires_keys = pytest.mark.skipif(
    _settings.google_api_key is None or _settings.tavily_api_key is None,
    reason="GOOGLE_API_KEY / TAVILY_API_KEY not configured",
)


def _sample() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in _DATASET.read_text(encoding="utf-8").splitlines()]
    # Deterministic sample: first N deep/comparison rows (they exercise the full graph).
    deep_rows = [r for r in rows if r["expected_route"] != "simple_lookup"]
    return deep_rows[: _settings.eval_sample_size]


@pytest.mark.evals
@requires_keys
@pytest.mark.parametrize("case", _sample(), ids=lambda c: c["topic"][:40])
def test_golden_topic(case: dict[str, Any]) -> None:
    from deep_research.graph.builder import build_graph

    result = build_graph(hitl=False).invoke({"topic": case["topic"]})

    report = result.get("report", "")
    sources = result.get("sources", [])
    assert len(report) > 200, "report too short"
    assert sources, "no sources gathered"

    # Deterministic gate: every citation must resolve (hallucinated ids fail hard).
    citations = check_citations(report, len(sources))
    assert citations.has_citations, "report has no citations at all"
    assert citations.all_valid, f"invalid citation ids: {citations.invalid}"

    # Route expectation (when the dataset pins one).
    expected_route = case["expected_route"]
    if expected_route != "any":
        assert result.get("route") == expected_route

    # LLM-as-judge gate.
    verdict = judge_report(case["topic"], report, sources)
    print(
        f"\n[{case['topic'][:50]}] faithfulness={verdict.faithfulness} "
        f"coverage={verdict.coverage} citations={verdict.citation_quality} "
        f"passed={verdict.passed} issues={verdict.issues}"
    )
    assert verdict.faithfulness >= _MIN_FAITHFULNESS, verdict.issues
    assert verdict.coverage >= _MIN_COVERAGE, verdict.issues
