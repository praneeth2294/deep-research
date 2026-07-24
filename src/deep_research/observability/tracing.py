"""Tracing — every run becomes a trace of timed spans (deck 2.8).

Vendor-neutral by design: a LangChain callback handler records node spans and
LLM spans (with tokens + estimated cost) into a local JSONL file per thread —
`trace_id == thread_id`, which is also what feedback and checkpoints key on.
When Langfuse keys are configured (and the optional `langfuse` package is
installed), the same run is additionally exported there; nothing in the
codebase depends on it.

View a trace:  research --show-trace <thread_id>
"""

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from deep_research.config import get_settings
from deep_research.observability.cost import price_for

_NODE_NAMES = {
    "input_guard",
    "router",
    "simple_answer",
    "memory_recall",
    "planner",
    "hitl",
    "researcher",
    "quality_gate",
    "replanner",
    "analyst",
    "synthesizer",
    "writer",
    "reviewer",
    "memory_store",
}


def trace_path(trace_id: str) -> Path:
    return Path(get_settings().traces_path) / f"{trace_id}.jsonl"


class TraceRecorder(BaseCallbackHandler):
    """Collects node + LLM spans for one graph run; append-flushed to JSONL."""

    raise_error = False  # a tracing bug must never break a research run

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self._t0 = time.time()
        self._open: dict[UUID, dict[str, Any]] = {}
        self._spans: list[dict[str, Any]] = []

    # ------------------------------------------------------------- node spans

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        metadata = kwargs.get("metadata") or {}
        name = kwargs.get("name") or (serialized or {}).get("name") or ""
        if name in _NODE_NAMES and metadata.get("langgraph_node") == name:
            self._start(run_id, name=name, kind="node")

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end(run_id)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end(run_id, error=str(error))

    # -------------------------------------------------------------- LLM spans

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        metadata = kwargs.get("metadata") or {}
        model = metadata.get("ls_model_name") or (serialized or {}).get("name") or "llm"
        self._start(run_id, name=str(model), kind="llm")

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        usage: dict[str, int] = {}
        try:
            message = response.generations[0][0].message
            usage = dict(message.usage_metadata or {})
        except (AttributeError, IndexError, TypeError):
            pass
        extra: dict[str, Any] = {}
        if usage:
            input_tokens = int(usage.get("input_tokens", 0))
            output_tokens = int(usage.get("output_tokens", 0))
            span = self._open.get(run_id, {})
            in_price, out_price = price_for(str(span.get("name", "")))
            extra = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(
                    input_tokens / 1e6 * in_price + output_tokens / 1e6 * out_price, 6
                ),
            }
        self._end(run_id, **extra)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end(run_id, error=str(error))

    # --------------------------------------------------------------- plumbing

    def _start(self, run_id: UUID, *, name: str, kind: str) -> None:
        self._open[run_id] = {
            "name": name,
            "kind": kind,
            "offset_ms": round((time.time() - self._t0) * 1000, 1),
            "_started": time.time(),
        }

    def _end(self, run_id: UUID, **extra: Any) -> None:
        span = self._open.pop(run_id, None)
        if span is None:
            return
        started = span.pop("_started")
        span["duration_ms"] = round((time.time() - started) * 1000, 1)
        span.update(extra)
        self._spans.append(span)

    def flush(self) -> Path:
        """Append collected spans to the trace file (clears the buffer)."""
        path = trace_path(self.trace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        with path.open("a", encoding="utf-8") as handle:
            if is_new:
                header = {"type": "trace", "trace_id": self.trace_id, "started": self._t0}
                handle.write(json.dumps(header) + "\n")
            for span in self._spans:
                handle.write(json.dumps({"type": "span", **span}) + "\n")
        self._spans = []
        return path


def langfuse_handler() -> Any | None:
    """Langfuse export when configured AND installed; otherwise None (no-op)."""
    settings = get_settings()
    if settings.langfuse_public_key is None or settings.langfuse_secret_key is None:
        return None
    try:
        import os

        os.environ.setdefault(
            "LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key.get_secret_value()
        )
        os.environ.setdefault(
            "LANGFUSE_SECRET_KEY", settings.langfuse_secret_key.get_secret_value()
        )
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except ImportError:
        return None


def format_trace(trace_id: str) -> str:
    """Human-readable span timeline with token + cost rollup."""
    path = trace_path(trace_id)
    if not path.exists():
        return f"No trace found for '{trace_id}' ({path})"
    spans: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("type") == "span":
                spans.append(record)
            elif record.get("type") == "feedback":
                feedback.append(record)
    lines = [f"Trace {trace_id} — {len(spans)} spans"]
    total_cost = 0.0
    total_in = total_out = 0
    for span in sorted(spans, key=lambda s: s.get("offset_ms", 0.0)):
        tokens = ""
        if "input_tokens" in span:
            total_in += span["input_tokens"]
            total_out += span["output_tokens"]
            total_cost += span.get("cost_usd", 0.0)
            tokens = f"  {span['input_tokens']}/{span['output_tokens']} tok"
        error = f"  ERROR: {span['error']}" if "error" in span else ""
        lines.append(
            f"  {span.get('offset_ms', 0):>9.1f}ms  {span.get('duration_ms', 0):>8.1f}ms  "
            f"{span.get('kind', '?'):<5} {span.get('name', '?')}{tokens}{error}"
        )
    lines.append(f"Totals: {total_in:,} in / {total_out:,} out tokens, ~${total_cost:.4f}")
    for record in feedback:
        lines.append(f"Feedback: {record.get('rating')} {record.get('comment', '')!r}")
    return "\n".join(lines)
