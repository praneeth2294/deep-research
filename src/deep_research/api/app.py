"""FastAPI service — the HTTP face of the research graph.

Flow:  POST /research  ->  {thread_id}
       GET  /research/{id}          (status + plan + result)
       GET  /research/{id}/stream   (SSE progress events)
       POST /research/{id}/approve  ({decision: approve|edit|cancel, sub_topics?})
       POST /feedback               ({thread_id, rating: up|down, comment?})

Run:   uv run uvicorn deep_research.api.app:app
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deep_research.api.manager import SessionManager
from deep_research.schemas.planner import SubTopic

_FEEDBACK_PATH = Path("data/feedback.jsonl")
_STREAM_POLL_S = 0.3


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=2000)


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "edit", "cancel"]
    sub_topics: list[SubTopic] | None = Field(
        default=None, description="Required when decision == 'edit'."
    )


class FeedbackRequest(BaseModel):
    thread_id: str
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=2000)


def _default_manager() -> SessionManager:
    from deep_research.graph.builder import build_graph
    from deep_research.memory.checkpointing import sqlite_checkpointer
    from deep_research.net import setup_tls

    setup_tls()
    return SessionManager(build_graph(checkpointer=sqlite_checkpointer()))


def create_app(manager: SessionManager | None = None) -> FastAPI:
    app = FastAPI(title="deep-research", version="0.1.0")
    app.state.manager = manager  # lazily created on first use when None

    def _manager() -> SessionManager:
        if app.state.manager is None:
            app.state.manager = _default_manager()
        return app.state.manager  # type: ignore[no-any-return]

    def _session(thread_id: str) -> Any:
        session = _manager().get(thread_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Unknown thread_id: {thread_id}")
        return session

    @app.post("/research")
    def start_research(request: ResearchRequest) -> dict[str, str]:
        session = _manager().start(request.topic)
        return {"thread_id": session.thread_id, "status": session.status}

    @app.get("/research/{thread_id}")
    def get_research(thread_id: str) -> dict[str, Any]:
        session = _session(thread_id)
        return {
            "thread_id": session.thread_id,
            "topic": session.topic,
            "status": session.status,
            "plan": session.plan,
            "result": session.result,
            "error": session.error,
        }

    @app.post("/research/{thread_id}/approve")
    def approve(thread_id: str, request: ApprovalRequest) -> dict[str, str]:
        session = _session(thread_id)
        if request.decision == "edit" and not request.sub_topics:
            raise HTTPException(status_code=422, detail="edit requires sub_topics")
        decision: dict[str, Any] = {"decision": request.decision}
        if request.sub_topics:
            decision["sub_topics"] = [st.model_dump() for st in request.sub_topics]
        try:
            _manager().resume(thread_id, decision)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"thread_id": session.thread_id, "status": "running"}

    @app.get("/research/{thread_id}/stream")
    async def stream(thread_id: str) -> StreamingResponse:
        session = _session(thread_id)

        async def events() -> Any:
            index = 0
            while True:
                while index < len(session.events):
                    yield f"data: {json.dumps(session.events[index])}\n\n"
                    index += 1
                if session.is_terminal() or session.status == "awaiting_approval":
                    yield "data: [DONE]\n\n"
                    return
                await asyncio.sleep(_STREAM_POLL_S)

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/feedback")
    def feedback(request: FeedbackRequest) -> dict[str, str]:
        _session(request.thread_id)  # 404 for unknown threads
        _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "thread_id": request.thread_id,
            "rating": request.rating,
            "comment": request.comment,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        with _FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return {"status": "recorded"}

    return app


app = create_app()
