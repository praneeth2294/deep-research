"""Episodic memory — what the system has researched before (deck 2.4.3).

Store: after a session completes, a compact summary (topic, key findings,
date) is embedded and persisted.
Recall: before planning a new session, similar past sessions are retrieved
and injected into the planner's context — "have we researched this before?".
"""

from datetime import date

from deep_research.memory.vector_store import get_store

_COLLECTION = "episodic"
_RECALL_K = 2
_MIN_SIMILARITY = 0.55  # below this, "similar" sessions are just noise


def store_session(thread_id: str, topic: str, report: str, key_findings: list[str]) -> None:
    """Persist one completed session's summary."""
    findings = "; ".join(key_findings) if key_findings else report[:300]
    get_store(_COLLECTION).upsert(
        ids=[thread_id],
        texts=[f"{topic}\n{findings}"],
        metadatas=[
            {
                "topic": topic,
                "findings": findings[:1000],
                "date": date.today().isoformat(),
                "report_head": report[:400],
            }
        ],
    )


def recall_similar(topic: str) -> str:
    """Formatted block of related past sessions ('' when nothing relevant)."""
    hits = get_store(_COLLECTION).search(topic, k=_RECALL_K)
    lines = [
        f"- [{metadata.get('date', '?')}] {metadata.get('topic', '?')}: "
        f"{metadata.get('findings', '')}"
        for metadata, similarity in hits
        if similarity >= _MIN_SIMILARITY
    ]
    return "\n".join(lines)
