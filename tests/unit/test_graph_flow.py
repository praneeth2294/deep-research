"""Full-graph flow tests — offline, every LLM and tool faked.

Exercises the Phase 2+3 Definition of Done:
- router sends deep topics into the pipeline and trivial ones to the short path,
- 3 researchers fan out in parallel,
- one sub-topic fails the quality gate -> replanner -> attempt-2 research,
- the reviewer rejects the first draft -> writer revision -> accepted.
"""

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from deep_research.graph import builder
from deep_research.graph.nodes import (
    analyst,
    planner,
    replanner,
    researcher,
    reviewer,
    router,
    simple_answer,
)
from deep_research.graph.nodes import synthesizer as synth_node
from deep_research.graph.nodes import writer as writer_node_mod
from deep_research.schemas.analysis import Claim, ClaimSet, SynthesisOutput
from deep_research.schemas.planner import PlannerOutput, SubTopic
from deep_research.schemas.research import Source
from deep_research.schemas.review import ReviewVerdict
from deep_research.schemas.routing import RouteDecision


class _Invoker:
    def __init__(self, response: Any, queue: list[Any] | None) -> None:
        self._response = response
        self._queue = queue

    def invoke(self, _messages: Any) -> Any:
        if self._queue is not None:
            return self._queue.pop(0)
        return self._response


def fake_structured(response: Any = None, *, sequence: list[Any] | None = None) -> Any:
    """Fake for `structured_llm(schema, **kw)` — returns the canned response(s)."""
    queue = list(sequence) if sequence is not None else None

    def factory(_schema: Any, **_kwargs: Any) -> _Invoker:
        return _Invoker(response, queue)

    return factory


def fake_text(response: Any = None, *, sequence: list[Any] | None = None) -> Any:
    """Fake for `text_llm(**kw)` — returns the canned AIMessage(s)."""
    queue = list(sequence) if sequence is not None else None

    def factory(**_kwargs: Any) -> _Invoker:
        return _Invoker(response, queue)

    return factory


def _sub(title: str, query: str) -> SubTopic:
    return SubTopic(title=title, search_query=query, rationale="coverage")


def _good_sources(tag: str) -> list[Source]:
    return [
        Source(url=f"https://en.wikipedia.org/wiki/{tag}{i}", title=f"{tag}{i}", snippet="x" * 300)
        for i in range(3)
    ]


def test_full_flow_with_replan_and_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router,
        "structured_llm",
        fake_structured(RouteDecision(route="deep_research", reason="multi-faceted topic")),
    )

    plan = PlannerOutput(
        sub_topics=[
            _sub("Good-A", "query-a"),
            _sub("Bad", "bad-query"),
            _sub("Good-B", "query-b"),
        ]
    )
    monkeypatch.setattr(planner, "structured_llm", fake_structured(plan))

    def fake_search(query: str, max_results: int = 5) -> list[Source]:
        if query == "bad-query":
            return [Source(url="https://facebook.com/groups/1/posts/2", title="p", snippet="thin")]
        return _good_sources(query.replace("query-", ""))

    monkeypatch.setattr(researcher, "search_web", fake_search)

    monkeypatch.setattr(
        replanner,
        "structured_llm",
        fake_structured(PlannerOutput(sub_topics=[_sub("Bad", "revised-query")])),
    )

    claims = ClaimSet(
        claims=[
            Claim(
                statement="LangGraph models workflows as graphs.", confidence="high", source_ids=[1]
            )
        ]
    )
    monkeypatch.setattr(analyst, "structured_llm", fake_structured(claims))
    monkeypatch.setattr(
        synth_node,
        "structured_llm",
        fake_structured(
            SynthesisOutput(
                summary="The evidence consistently describes graph-based orchestration. " * 2,
                key_findings=["Graphs beat chains for agents [1]"],
                conflicts=[],
            )
        ),
    )
    monkeypatch.setattr(
        writer_node_mod,
        "text_llm",
        fake_text(
            sequence=[AIMessage(content="Draft v1 [1]"), AIMessage(content="Draft v2, fixed [1]")]
        ),
    )
    monkeypatch.setattr(
        reviewer,
        "structured_llm",
        fake_structured(
            sequence=[
                ReviewVerdict(score=5, issues=["Cite the claim in paragraph 1"]),
                ReviewVerdict(score=9, issues=[]),
            ]
        ),
    )

    result = builder.build_graph().invoke({"topic": "What is LangGraph?"})

    assert result["route"] == "deep_research"
    results = result["research_results"]
    assert len(results) == 4  # 3 parallel + 1 replanned
    attempt_two = [r for r in results if r.attempt == 2]
    assert len(attempt_two) == 1
    assert attempt_two[0].sub_topic.title == "Bad"
    assert attempt_two[0].sub_topic.search_query == "revised-query"

    assert result["revision_count"] == 1
    assert result["review"].score == 9
    assert result["report"] == "Draft v2, fixed [1]"

    assert len(result["sources"]) >= 6
    assert result["claims"][0].source_ids == [1]


def test_simple_lookup_short_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trivial questions: router -> simple_answer -> END. No planner, no fan-out."""
    monkeypatch.setattr(
        router,
        "structured_llm",
        fake_structured(RouteDecision(route="simple_lookup", reason="single-fact question")),
    )
    monkeypatch.setattr(
        simple_answer, "search_web", lambda _q, max_results=3: _good_sources("fact")
    )
    monkeypatch.setattr(
        simple_answer, "text_llm", fake_text(AIMessage(content="RAG means retrieval [1]."))
    )

    # Planner must never run - make it explode if touched.
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("planner must not run on the simple_lookup path")

    monkeypatch.setattr(planner, "structured_llm", _boom)

    result = builder.build_graph().invoke({"topic": "What does RAG stand for?"})

    assert result["route"] == "simple_lookup"
    assert result["report"] == "RAG means retrieval [1]."
    assert len(result["sources"]) == 3
    assert "sub_topics" not in result
