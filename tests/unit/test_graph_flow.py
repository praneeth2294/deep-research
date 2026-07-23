"""Full-graph flow test — offline, every LLM and tool faked.

Exercises the Phase 2 Definition of Done in one run:
- 3 researchers fan out in parallel,
- one sub-topic fails the quality gate -> replanner -> attempt-2 research,
- the reviewer rejects the first draft -> writer revision -> accepted.
"""

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from deep_research.graph import builder
from deep_research.graph.nodes import analyst, planner, replanner, researcher, reviewer
from deep_research.graph.nodes import synthesizer as synth_node
from deep_research.graph.nodes import writer as writer_node_mod
from deep_research.schemas.analysis import Claim, ClaimSet, SynthesisOutput
from deep_research.schemas.planner import PlannerOutput, SubTopic
from deep_research.schemas.research import Source
from deep_research.schemas.review import ReviewVerdict


def _fake_llm(response: Any = None, *, sequence: list[Any] | None = None) -> Any:
    """Factory for a fake chat model.

    `response` is returned by every call; `sequence` pops one item per call
    (for stateful fakes like the reviewer). Works for both structured output
    and plain .invoke().
    """
    queue = list(sequence) if sequence is not None else None

    class _Invoker:
        def invoke(self, _messages: Any) -> Any:
            if queue is not None:
                return queue.pop(0)
            return response

    class _Fake(_Invoker):
        def with_structured_output(self, _schema: Any) -> _Invoker:
            return _Invoker()

    def factory(*_args: Any, **_kwargs: Any) -> _Fake:
        return _Fake()

    return factory


def _sub(title: str, query: str) -> SubTopic:
    return SubTopic(title=title, search_query=query, rationale="coverage")


def _good_sources(tag: str) -> list[Source]:
    return [
        Source(url=f"https://en.wikipedia.org/wiki/{tag}{i}", title=f"{tag}{i}", snippet="x" * 300)
        for i in range(3)
    ]


def test_full_flow_with_replan_and_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    # --- planner: 3 sub-topics; 'Bad' has a query that will return junk
    plan = PlannerOutput(
        sub_topics=[
            _sub("Good-A", "query-a"),
            _sub("Bad", "bad-query"),
            _sub("Good-B", "query-b"),
        ]
    )
    monkeypatch.setattr(planner, "cheap_llm", _fake_llm(plan))

    # --- search tool: junk for the bad query, solid results otherwise
    def fake_search(query: str, max_results: int = 5) -> list[Source]:
        if query == "bad-query":
            return [Source(url="https://facebook.com/groups/1/posts/2", title="p", snippet="thin")]
        return _good_sources(query.replace("query-", ""))

    monkeypatch.setattr(researcher, "search_web", fake_search)

    # --- replanner: revises the failed query (title preserved by the node)
    monkeypatch.setattr(
        replanner,
        "cheap_llm",
        _fake_llm(PlannerOutput(sub_topics=[_sub("Bad", "revised-query")])),
    )

    # --- analyst / synthesizer / writer / reviewer fakes
    claims = ClaimSet(
        claims=[
            Claim(
                statement="LangGraph models workflows as graphs.", confidence="high", source_ids=[1]
            )
        ]
    )
    monkeypatch.setattr(analyst, "strong_llm", _fake_llm(claims))
    monkeypatch.setattr(
        synth_node,
        "strong_llm",
        _fake_llm(
            SynthesisOutput(
                summary="The evidence consistently describes graph-based orchestration. " * 2,
                key_findings=["Graphs beat chains for agents [1]"],
                conflicts=[],
            )
        ),
    )
    monkeypatch.setattr(
        writer_node_mod,
        "strong_llm",
        _fake_llm(
            sequence=[AIMessage(content="Draft v1 [1]"), AIMessage(content="Draft v2, fixed [1]")]
        ),
    )
    monkeypatch.setattr(
        reviewer,
        "cheap_llm",
        _fake_llm(
            sequence=[
                ReviewVerdict(score=5, issues=["Cite the claim in paragraph 1"]),
                ReviewVerdict(score=9, issues=[]),
            ]
        ),
    )

    result = builder.build_graph().invoke({"topic": "What is LangGraph?"})

    # 3 parallel researchers + 1 replanned attempt
    results = result["research_results"]
    assert len(results) == 4
    attempt_two = [r for r in results if r.attempt == 2]
    assert len(attempt_two) == 1
    assert attempt_two[0].sub_topic.title == "Bad"
    assert attempt_two[0].sub_topic.search_query == "revised-query"

    # evaluator-optimiser loop ran exactly one revision
    assert result["revision_count"] == 1
    assert result["review"].score == 9
    assert result["report"] == "Draft v2, fixed [1]"

    # analyst deduped and numbered the evidence
    assert len(result["sources"]) >= 6
    assert result["claims"][0].source_ids == [1]
