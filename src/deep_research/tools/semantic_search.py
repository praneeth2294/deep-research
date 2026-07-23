"""Semantic-memory search tool — RAG over previously gathered sources."""

from deep_research.memory.semantic import search_cached
from deep_research.schemas.research import Source


def search_memory(query: str) -> list[Source]:
    """Query the local research memory. Free, instant, offline-of-the-web."""
    return search_cached(query, k=5)
