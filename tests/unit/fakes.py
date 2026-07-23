"""Shared offline fakes for graph-level tests (HITL, API)."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from deep_research.graph.nodes import (
    analyst,
    memory_recall,
    memory_store,
    planner,
    researcher,
    reviewer,
    router,
)
from deep_research.graph.nodes import synthesizer as synth_node
from deep_research.graph.nodes import writer as writer_node_mod
from deep_research.schemas.analysis import Claim, ClaimSet, SynthesisOutput
from deep_research.schemas.planner import PlannerOutput, SubTopic
from deep_research.schemas.research import ReactStep, Source
from deep_research.schemas.review import ReviewVerdict
from deep_research.schemas.routing import RouteDecision
from deep_research.tools.registry import ToolSpec
from tests.unit.test_graph_flow import fake_structured, fake_text


def default_plan() -> PlannerOutput:
    return PlannerOutput(
        sub_topics=[
            SubTopic(title="Alpha", search_query="query-alpha", rationale="coverage"),
            SubTopic(title="Beta", search_query="query-beta", rationale="coverage"),
        ]
    )


def wire_deep_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: PlannerOutput | None = None,
    searched_queries: list[str] | None = None,
) -> None:
    """Patch every LLM/tool so a deep run completes offline and deterministically.

    `searched_queries` (optional) records every query the researchers execute —
    useful for asserting that edited plans actually drive the research.
    """
    monkeypatch.setattr(memory_recall, "recall_similar", lambda _t: "")
    monkeypatch.setattr(memory_store, "store_session", lambda **_kw: None)
    monkeypatch.setattr(memory_store, "cache_sources", lambda _s: None)

    monkeypatch.setattr(
        router,
        "structured_llm",
        fake_structured(RouteDecision(route="deep_research", reason="multi-faceted")),
    )
    monkeypatch.setattr(planner, "structured_llm", fake_structured(plan or default_plan()))

    def _search(query: str) -> list[Source]:
        if searched_queries is not None:
            searched_queries.append(query)
        return [
            Source(
                url=f"https://en.wikipedia.org/wiki/{query}-{i}",
                title=f"{query}-{i}",
                snippet="x" * 300,
            )
            for i in range(3)
        ]

    monkeypatch.setattr(
        researcher, "get_tool", lambda name: ToolSpec(name=name, description="fake", run=_search)
    )
    monkeypatch.setattr(
        researcher,
        "structured_llm",
        fake_structured(ReactStep(reasoning="seed is enough", action="finish")),
    )
    monkeypatch.setattr(
        analyst,
        "structured_llm",
        fake_structured(
            ClaimSet(
                claims=[
                    Claim(statement="A factual statement here.", confidence="high", source_ids=[1])
                ]
            )
        ),
    )
    monkeypatch.setattr(
        synth_node,
        "structured_llm",
        fake_structured(
            SynthesisOutput(
                summary="The gathered evidence paints one consistent overall picture.",
                key_findings=["Key finding [1]"],
                conflicts=[],
            )
        ),
    )
    monkeypatch.setattr(
        writer_node_mod, "text_llm", fake_text(AIMessage(content="Final report [1]"))
    )
    monkeypatch.setattr(
        reviewer, "structured_llm", fake_structured(ReviewVerdict(score=9, issues=[]))
    )


def make_boom(label: str) -> Any:
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError(f"{label} must not run in this scenario")

    return _boom
