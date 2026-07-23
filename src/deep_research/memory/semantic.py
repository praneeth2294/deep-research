"""Semantic memory — the knowledge the system has gathered (deck 2.4.4).

Every completed session caches its (already sanitized, deduplicated) sources.
Researchers can then query this cache through the `semantic_search` tool —
instant, free evidence for topics adjacent to past research. This is RAG over
our own accumulated corpus.
"""

from hashlib import sha256

from deep_research.memory.vector_store import get_store
from deep_research.schemas.research import Source

_COLLECTION = "semantic"
_SNIPPET_CAP = 1500


def cache_sources(sources: list[Source]) -> None:
    """Upsert sources keyed by URL hash (re-caching a URL is an update, not a dupe)."""
    if not sources:
        return
    get_store(_COLLECTION).upsert(
        ids=[sha256(source.url.encode()).hexdigest()[:24] for source in sources],
        texts=[f"{source.title}\n{source.snippet[:_SNIPPET_CAP]}" for source in sources],
        metadatas=[
            {
                "url": source.url,
                "title": source.title,
                "snippet": source.snippet[:_SNIPPET_CAP],
            }
            for source in sources
        ],
    )


def search_cached(query: str, k: int = 5) -> list[Source]:
    """Retrieve previously gathered sources relevant to the query."""
    return [
        Source(
            url=str(metadata.get("url", "")),
            title=str(metadata.get("title", "(cached)")),
            snippet=str(metadata.get("snippet", "")),
            score=similarity,
        )
        for metadata, similarity in get_store(_COLLECTION).search(query, k=k)
        if metadata.get("url")
    ]
