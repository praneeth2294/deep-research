"""API endpoint flow: submit -> awaiting approval -> edit -> done -> feedback.

The graph under the API is the REAL compiled graph with faked LLMs/tools and
an in-memory checkpointer; sessions run in real background threads, so the
tests poll with a timeout exactly like an HTTP client would.
"""

import json
import sqlite3
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from deep_research.api import app as app_module
from deep_research.api.manager import SessionManager
from deep_research.config import get_settings
from deep_research.graph import builder
from tests.unit.fakes import wire_deep_pipeline

_TIMEOUT_S = 10.0


@pytest.fixture(autouse=True)
def _tmp_observability(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None]:
    monkeypatch.setenv("TRACES_PATH", str(tmp_path / "traces"))
    monkeypatch.setenv("FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _client(monkeypatch: pytest.MonkeyPatch, queries: list[str] | None = None) -> TestClient:
    wire_deep_pipeline(monkeypatch, searched_queries=queries)
    saver = SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False))
    manager = SessionManager(builder.build_graph(checkpointer=saver))
    return TestClient(app_module.create_app(manager))


def _wait_for_status(client: TestClient, thread_id: str, wanted: str) -> dict[str, Any]:
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        body = client.get(f"/research/{thread_id}").json()
        if body["status"] == wanted:
            return dict(body)
        if body["status"] == "error":
            raise AssertionError(f"session errored: {body['error']}")
        time.sleep(0.05)
    raise AssertionError(f"timeout waiting for status={wanted}")


def test_full_http_flow_with_plan_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []
    client = _client(monkeypatch, queries)

    # 1. submit
    submitted = client.post("/research", json={"topic": "A multi-faceted research topic"})
    assert submitted.status_code == 200
    thread_id = submitted.json()["thread_id"]

    # 2. the run pauses at plan approval; the plan is visible
    body = _wait_for_status(client, thread_id, "awaiting_approval")
    titles = [st["title"] for st in body["plan"]]
    assert titles == ["Alpha", "Beta"]

    # 3. edit one query, approve
    edited = [dict(st) for st in body["plan"]]
    edited[0]["search_query"] = "human-corrected-query"
    approved = client.post(
        f"/research/{thread_id}/approve",
        json={"decision": "edit", "sub_topics": edited},
    )
    assert approved.status_code == 200

    # 4. completes; the edited query is what actually ran
    body = _wait_for_status(client, thread_id, "done")
    assert body["result"]["report"] == "Final report [1]"
    assert body["result"]["review_score"] == 9
    assert "human-corrected-query" in queries
    assert "query-alpha" not in queries

    # 5. SSE stream replays progress events and terminates
    with client.stream("GET", f"/research/{thread_id}/stream") as response:
        lines = [line for line in response.iter_lines() if line.startswith("data:")]
    events = [json.loads(line[5:]) for line in lines if "[DONE]" not in line]
    nodes_seen = {e.get("node") for e in events if e.get("event") == "node_completed"}
    assert {"planner", "writer", "reviewer"} <= nodes_seen
    assert lines[-1] == "data: [DONE]"

    # 6. feedback lands in the store (isolated to a temp dir)
    response = client.post(
        "/feedback", json={"thread_id": thread_id, "rating": "up", "comment": "solid"}
    )
    assert response.json() == {"status": "recorded"}
    feedback_file = Path(get_settings().feedback_path)
    assert thread_id in feedback_file.read_text(encoding="utf-8")

    # 7. the trace endpoint shows the run's spans
    trace_text = client.get(f"/research/{thread_id}/trace").json()["trace"]
    assert "spans" in trace_text


def test_cancel_via_http(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    thread_id = client.post("/research", json={"topic": "Another deep research topic"}).json()[
        "thread_id"
    ]
    _wait_for_status(client, thread_id, "awaiting_approval")
    client.post(f"/research/{thread_id}/approve", json={"decision": "cancel"})
    body = _wait_for_status(client, thread_id, "cancelled")
    assert "cancelled by the user" in body["result"]["refusal"]


def test_refused_topic_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    thread_id = client.post("/research", json={"topic": "hi"}).json()["thread_id"]
    body = _wait_for_status(client, thread_id, "cancelled")
    assert "too short" in body["result"]["refusal"]


def test_approve_wrong_state_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    thread_id = client.post("/research", json={"topic": "hi"}).json()["thread_id"]
    _wait_for_status(client, thread_id, "cancelled")
    response = client.post(f"/research/{thread_id}/approve", json={"decision": "approve"})
    assert response.status_code == 409


def test_unknown_thread_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    assert client.get("/research/nope").status_code == 404
    assert client.post("/feedback", json={"thread_id": "nope", "rating": "up"}).status_code == 404
