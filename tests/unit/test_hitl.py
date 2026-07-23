"""Human-in-the-loop: the graph pauses at plan approval; approve/edit/cancel."""

import sqlite3
from typing import Any, cast

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from deep_research.graph import builder
from tests.unit.fakes import wire_deep_pipeline


def _graph_and_config() -> tuple[Any, Any]:
    saver = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
    graph = builder.build_graph(checkpointer=saver)  # hitl=True is the default
    config = cast("Any", {"configurable": {"thread_id": "hitl-test"}})
    return graph, config


def test_graph_pauses_at_plan_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    wire_deep_pipeline(monkeypatch)
    graph, config = _graph_and_config()

    result = graph.invoke({"topic": "A multi-faceted research topic"}, config=config)

    assert "__interrupt__" in result  # paused, not finished
    payload = result["__interrupt__"][0].value
    assert payload["type"] == "plan_approval"
    assert [st["title"] for st in payload["sub_topics"]] == ["Alpha", "Beta"]
    assert "report" not in result  # nothing downstream ran


def test_approve_resumes_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []
    wire_deep_pipeline(monkeypatch, searched_queries=queries)
    graph, config = _graph_and_config()

    graph.invoke({"topic": "A multi-faceted research topic"}, config=config)
    result = graph.invoke(Command(resume={"decision": "approve"}), config=config)

    assert result["report"] == "Final report [1]"
    assert sorted(queries) == ["query-alpha", "query-beta"]  # original plan ran


def test_edit_changes_what_researchers_actually_run(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []
    wire_deep_pipeline(monkeypatch, searched_queries=queries)
    graph, config = _graph_and_config()

    result = graph.invoke({"topic": "A multi-faceted research topic"}, config=config)
    edited = [dict(st) for st in result["__interrupt__"][0].value["sub_topics"]]
    edited[0]["search_query"] = "human-corrected-query"

    result = graph.invoke(Command(resume={"decision": "edit", "sub_topics": edited}), config=config)

    assert result["report"] == "Final report [1]"
    assert "human-corrected-query" in queries  # the edit drove the research
    assert "query-alpha" not in queries  # the replaced query never ran


def test_cancel_ends_run_without_researchers(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []
    wire_deep_pipeline(monkeypatch, searched_queries=queries)
    graph, config = _graph_and_config()

    graph.invoke({"topic": "A multi-faceted research topic"}, config=config)
    result = graph.invoke(Command(resume={"decision": "cancel"}), config=config)

    assert "cancelled by the user" in result["refusal"]
    assert queries == []  # zero researcher cost after cancel
