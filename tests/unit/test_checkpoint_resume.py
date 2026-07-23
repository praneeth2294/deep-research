"""Durable execution: a crashed run resumes from its checkpoint, not from scratch.

Simulates the kill-9 scenario: the writer explodes mid-run; re-invoking the
same thread with the writer fixed completes the run WITHOUT re-running the
planner/researchers (proven by call counters).
"""

import sqlite3
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from deep_research.graph import builder
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


def test_crash_then_resume_from_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"planner": 0, "search": 0, "writer": 0}

    def counting_planner_llm(_schema: Any, **_kw: Any) -> Any:
        class _I:
            def invoke(self, _m: Any) -> PlannerOutput:
                calls["planner"] += 1
                return PlannerOutput(
                    sub_topics=[SubTopic(title="Only", search_query="q-only", rationale="coverage")]
                )

        return _I()

    def counting_search(_query: str) -> list[Source]:
        calls["search"] += 1
        return [
            Source(url=f"https://en.wikipedia.org/wiki/{i}", title=f"W{i}", snippet="x" * 300)
            for i in range(3)
        ]

    monkeypatch.setattr(
        router,
        "structured_llm",
        fake_structured(RouteDecision(route="deep_research", reason="multi-part")),
    )
    monkeypatch.setattr(planner, "structured_llm", counting_planner_llm)
    monkeypatch.setattr(
        researcher,
        "get_tool",
        lambda name: ToolSpec(name=name, description="fake", run=counting_search),
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
                    Claim(statement="Something factual here.", confidence="high", source_ids=[1])
                ]
            )
        ),
    )
    monkeypatch.setattr(
        synth_node,
        "structured_llm",
        fake_structured(
            SynthesisOutput(
                summary="A consistent picture emerges from the gathered evidence overall.",
                key_findings=["Finding one [1]"],
                conflicts=[],
            )
        ),
    )
    monkeypatch.setattr(
        reviewer, "structured_llm", fake_structured(ReviewVerdict(score=9, issues=[]))
    )
    # memory nodes: no-op (no embeddings in unit tests)
    monkeypatch.setattr(memory_recall, "recall_similar", lambda _topic: "")
    monkeypatch.setattr(memory_store, "store_session", lambda **_kw: None)
    monkeypatch.setattr(memory_store, "cache_sources", lambda _s: None)

    # --- writer crashes on first invocation (the simulated kill -9 point)
    def crashing_writer(**_kw: Any) -> Any:
        class _I:
            def invoke(self, _m: Any) -> AIMessage:
                calls["writer"] += 1
                raise RuntimeError("process killed mid-run")

        return _I()

    monkeypatch.setattr(writer_node_mod, "text_llm", crashing_writer)

    saver = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
    graph = builder.build_graph(checkpointer=saver)
    config = cast("Any", {"configurable": {"thread_id": "resume-test"}})

    with pytest.raises(RuntimeError, match="process killed"):
        graph.invoke({"topic": "Durable execution in practice"}, config=config)

    assert calls == {"planner": 1, "search": 1, "writer": 1}

    # --- "restart the process" with the writer fixed; resume the SAME thread
    monkeypatch.setattr(
        writer_node_mod, "text_llm", fake_text(AIMessage(content="Recovered report [1]"))
    )
    result = graph.invoke(cast("Any", None), config=config)  # None = resume from checkpoint

    assert result["report"] == "Recovered report [1]"
    assert result["review"].score == 9
    # THE durability proof: planner and researcher did NOT run again.
    assert calls["planner"] == 1
    assert calls["search"] == 1
