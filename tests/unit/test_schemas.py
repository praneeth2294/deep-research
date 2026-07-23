"""Contract tests: the schemas enforce the invariants the graph relies on."""

import pytest
from pydantic import ValidationError

from deep_research.schemas.planner import PlannerOutput, SubTopic
from deep_research.schemas.research import Source


def _sub_topic(n: int = 1) -> SubTopic:
    return SubTopic(
        title=f"Sub-topic {n}",
        search_query=f"query {n}",
        rationale="needed for coverage",
    )


def test_planner_output_accepts_one_to_three() -> None:
    for count in (1, 2, 3):
        plan = PlannerOutput(sub_topics=[_sub_topic(i) for i in range(count)])
        assert len(plan.sub_topics) == count


def test_planner_output_rejects_zero_and_four() -> None:
    with pytest.raises(ValidationError):
        PlannerOutput(sub_topics=[])
    with pytest.raises(ValidationError):
        PlannerOutput(sub_topics=[_sub_topic(i) for i in range(4)])


def test_source_defaults() -> None:
    source = Source(url="https://example.com/article")
    assert source.title == "(untitled)"
    assert source.snippet == ""
    assert source.score is None


def test_source_rejects_junk_url() -> None:
    with pytest.raises(ValidationError):
        Source(url="x")
