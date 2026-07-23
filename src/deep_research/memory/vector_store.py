"""Vector store wrapper (long-term memory backend).

Embedded Chroma in dev: no server, no Docker, persisted under `data/memory`.
The wrapper is deliberately thin and interface-shaped — swapping to Qdrant or
pgvector in production changes this module only. Embeddings are computed by
us (memory/embeddings.py); Chroma is used purely as an ANN index.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings as ChromaSettings

from deep_research.config import get_settings
from deep_research.memory.embeddings import embed_texts


class VectorStore:
    """One named collection with upsert + cosine-similarity search."""

    def __init__(self, collection: str, path: str | None = None) -> None:
        base = path or get_settings().memory_path
        Path(base).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=base, settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            collection, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict[str, str]]) -> None:
        """Insert-or-update by id (re-adding the same id is a cheap no-op update)."""
        if not ids:
            return
        self._collection.upsert(
            ids=ids,
            embeddings=cast(Any, embed_texts(texts)),
            documents=texts,
            metadatas=cast(Any, metadatas),
        )

    def search(self, query: str, k: int = 5) -> list[tuple[dict[str, Any], float]]:
        """Return up to k (metadata, similarity) pairs, best first."""
        count = self._collection.count()
        if count == 0:
            return []
        result = self._collection.query(
            query_embeddings=cast(Any, embed_texts([query])), n_results=min(k, count)
        )
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        return [
            (dict(metadata), 1.0 - distance)
            for metadata, distance in zip(metadatas[0], distances[0], strict=True)
        ]


@lru_cache(maxsize=8)
def get_store(collection: str) -> VectorStore:
    """Process-wide store per collection (Chroma requires one client per path)."""
    return VectorStore(collection)
