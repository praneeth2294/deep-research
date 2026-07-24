"""Session manager — runs graph sessions in background threads.

Each session = one thread_id. The graph streams node-by-node; every update
becomes a progress event (consumed by the SSE endpoint). When the HITL
interrupt fires, the session parks in `awaiting_approval` until the client
posts a decision, which resumes the same checkpointed thread.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Literal, cast
from uuid import uuid4

from langgraph.types import Command

from deep_research.observability.cost import CostTracker
from deep_research.observability.tracing import TraceRecorder, langfuse_handler

SessionStatus = Literal["running", "awaiting_approval", "done", "cancelled", "error"]

_TERMINAL: set[str] = {"done", "cancelled", "error"}


@dataclass
class Session:
    thread_id: str
    topic: str
    status: SessionStatus = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, Any]] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    tracker: CostTracker = field(default_factory=CostTracker)
    recorder: TraceRecorder | None = None

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


class SessionManager:
    """Owns sessions and drives the (injected) compiled graph."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, thread_id: str) -> Session | None:
        return self._sessions.get(thread_id)

    def start(self, topic: str) -> Session:
        session = Session(thread_id=uuid4().hex[:12], topic=topic)
        session.recorder = TraceRecorder(session.thread_id)
        with self._lock:
            self._sessions[session.thread_id] = session
        self._spawn(session, {"topic": topic})
        return session

    def resume(self, thread_id: str, decision: dict[str, Any]) -> Session:
        session = self._sessions[thread_id]
        if session.status != "awaiting_approval":
            raise ValueError(f"Session {thread_id} is '{session.status}', not awaiting approval")
        session.status = "running"
        self._spawn(session, Command(resume=decision))
        return session

    # ------------------------------------------------------------------ internal

    def _spawn(self, session: Session, payload: Any) -> None:
        thread = threading.Thread(target=self._drive, args=(session, payload), daemon=True)
        thread.start()

    def _config(self, session: Session) -> dict[str, Any]:
        callbacks: list[Any] = [session.tracker.callback]
        if session.recorder is not None:
            callbacks.append(session.recorder)
        langfuse = langfuse_handler()
        if langfuse is not None:
            callbacks.append(langfuse)
        return {
            "configurable": {"thread_id": session.thread_id},
            "callbacks": callbacks,
        }

    def _drive(self, session: Session, payload: Any) -> None:
        try:
            config = self._config(session)
            for chunk in self._graph.stream(payload, config=config, stream_mode="updates"):
                for node_name, update in cast("dict[str, Any]", chunk).items():
                    if node_name == "__interrupt__":
                        interrupt = update[0] if isinstance(update, tuple | list) else update
                        value = getattr(interrupt, "value", {}) or {}
                        session.plan = list(value.get("sub_topics", []))
                        session.status = "awaiting_approval"
                        session.events.append({"event": "awaiting_approval", "plan": session.plan})
                        return
                    session.events.append({"event": "node_completed", "node": node_name})
            self._finish(session, config)
        except Exception as exc:
            session.status = "error"
            session.error = str(exc)
            session.events.append({"event": "error", "detail": str(exc)})
        finally:
            if session.recorder is not None:
                session.recorder.flush()

    def _finish(self, session: Session, config: dict[str, Any]) -> None:
        state = self._graph.get_state(config).values or {}
        review = state.get("review")
        session.result = {
            "route": state.get("route"),
            "refusal": state.get("refusal"),
            "report": state.get("report", ""),
            "sources": [{"url": s.url, "title": s.title} for s in state.get("sources", [])],
            "review_score": review.score if review is not None else None,
            "revision_count": state.get("revision_count", 0),
            "cost_usd": round(session.tracker.total_cost_usd(), 6),
        }
        session.status = "cancelled" if state.get("refusal") else "done"
        session.events.append({"event": session.status})
