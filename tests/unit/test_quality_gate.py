"""Quality gate: deterministic scoring and bounded replan flagging."""

from deep_research.graph.nodes.quality_gate import (
    domain_trust,
    quality_gate_node,
    score_result,
)
from deep_research.schemas.planner import SubTopic
from deep_research.schemas.research import ResearchResult, Source


def _sub(title: str) -> SubTopic:
    return SubTopic(title=title, search_query=f"query {title}", rationale="because")


def _good_sources(n: int = 3) -> list[Source]:
    return [
        Source(url=f"https://en.wikipedia.org/wiki/x{i}", title=f"W{i}", snippet="x" * 300)
        for i in range(n)
    ]


def _junk_sources() -> list[Source]:
    return [Source(url="https://facebook.com/groups/1/posts/2", title="post", snippet="short")]


def test_domain_trust_tiers() -> None:
    assert domain_trust("https://en.wikipedia.org/wiki/AI") == 1.0
    assert domain_trust("https://www.example.gov/report") == 1.0
    assert domain_trust("https://cs.stanford.edu/paper") == 1.0
    assert domain_trust("https://facebook.com/x") == 0.2
    assert domain_trust("https://random-blog.io/post") == 0.6  # neutral for unknown


def test_score_orders_good_above_junk() -> None:
    good = score_result(ResearchResult(sub_topic=_sub("alpha"), sources=_good_sources()))
    junk = score_result(ResearchResult(sub_topic=_sub("beta"), sources=_junk_sources()))
    assert good > 0.9
    assert junk < 0.4
    assert score_result(ResearchResult(sub_topic=_sub("gamma"), sources=[])) == 0.0


def test_gate_flags_only_failing_attempt_one() -> None:
    state = {
        "research_results": [
            ResearchResult(sub_topic=_sub("good"), sources=_good_sources(), attempt=1),
            ResearchResult(sub_topic=_sub("bad"), sources=_junk_sources(), attempt=1),
        ]
    }
    update = quality_gate_node(state)  # type: ignore[arg-type]
    assert [s.title for s in update["needs_replan"]] == ["bad"]


def test_gate_never_replans_twice() -> None:
    # 'bad' already has an attempt-2 result -> must not be flagged again,
    # even though its attempt-1 result still scores low.
    state = {
        "research_results": [
            ResearchResult(sub_topic=_sub("bad"), sources=_junk_sources(), attempt=1),
            ResearchResult(sub_topic=_sub("bad"), sources=_junk_sources(), attempt=2),
        ]
    }
    update = quality_gate_node(state)  # type: ignore[arg-type]
    assert update["needs_replan"] == []
