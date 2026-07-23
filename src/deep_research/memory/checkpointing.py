"""Durable execution — the graph's short-term memory made crash-proof.

A SQLite checkpointer persists the state after every superstep. Re-invoking
the graph with the same `thread_id` resumes from the last completed step
instead of restarting (and re-billing) the whole run. This is also the
foundation Phase 7's human-in-the-loop interrupt/resume builds on.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from deep_research.config import get_settings


def sqlite_checkpointer(path: str | None = None) -> SqliteSaver:
    """Checkpointer backed by a local SQLite file (Postgres in prod is a swap)."""
    target = Path(path or get_settings().checkpoint_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), check_same_thread=False)
    return SqliteSaver(connection)
