"""User feedback — the 👍/👎 that closes the observability loop (deck 2.8).

Each feedback record is keyed by thread_id, which IS the trace id: the same
identifier joins the checkpoint, the trace file, and the feedback record.
Feedback is appended both to the global feedback store (for analysis across
runs) and into the run's trace file (so viewing a trace shows its verdict).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from deep_research.config import get_settings
from deep_research.observability.tracing import trace_path


def record_feedback(thread_id: str, rating: str, comment: str = "") -> None:
    record = {
        "type": "feedback",
        "thread_id": thread_id,
        "rating": rating,
        "comment": comment,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
    feedback_path = Path(get_settings().feedback_path)
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with feedback_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    # Mirror into the trace so `--show-trace` displays the human verdict.
    run_trace = trace_path(thread_id)
    if run_trace.exists():
        with run_trace.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
