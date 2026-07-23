"""Routing functions: the graph's control flow, tested as plain functions."""

from langgraph.graph import END

from deep_research.graph.builder import (
    fan_out_researchers,
    route_after_gate,
    route_after_input_guard,
    route_after_review,
    route_after_router,
)
from deep_research.schemas.planner import SubTopic
from deep_research.schemas.review import ReviewVerdict


def _sub(title: str) -> SubTopic:
    return SubTopic(title=title, search_query=f"q {title}", rationale="because")


def test_fan_out_one_send_per_sub_topic() -> None:
    sends = fan_out_researchers({"sub_topics": [_sub("alpha"), _sub("beta"), _sub("gamma")]})
    assert len(sends) == 3
    assert all(send.node == "researcher" for send in sends)
    assert all(send.arg["attempt"] == 1 for send in sends)


def test_route_after_input_guard() -> None:
    assert route_after_input_guard({"refusal": "nope"}) == END
    assert route_after_input_guard({}) == "router"


def test_route_after_router() -> None:
    assert route_after_router({"route": "simple_lookup"}) == "simple_answer"
    assert route_after_router({"route": "deep_research"}) == "memory_recall"
    assert route_after_router({"route": "comparison"}) == "memory_recall"
    assert route_after_router({}) == "memory_recall"  # missing route -> safe default


def test_route_after_gate() -> None:
    assert route_after_gate({"needs_replan": [_sub("xray")]}) == "replanner"
    assert route_after_gate({"needs_replan": []}) == "analyst"
    assert route_after_gate({}) == "analyst"


def test_route_after_review_accepts_passing_score() -> None:
    state = {"review": ReviewVerdict(score=8, issues=[]), "revision_count": 0}
    assert route_after_review(state) == "memory_store"  # type: ignore[arg-type]


def test_route_after_review_sends_back_for_revision() -> None:
    state = {"review": ReviewVerdict(score=5, issues=["fix X"]), "revision_count": 0}
    assert route_after_review(state) == "writer"  # type: ignore[arg-type]


def test_route_after_review_stops_when_budget_exhausted() -> None:
    # default max_writer_revisions = 2 -> accept best effort, still write memory
    state = {"review": ReviewVerdict(score=5, issues=["fix X"]), "revision_count": 2}
    assert route_after_review(state) == "memory_store"  # type: ignore[arg-type]
