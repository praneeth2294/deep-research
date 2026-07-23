"""Memory subsystem: vector store roundtrip, episodic recall, semantic cache.

All offline: embeddings are faked with deterministic vectors, Chroma runs
embedded against a temp directory.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from deep_research.memory import episodic, semantic, vector_store
from deep_research.schemas.research import Source

# Deterministic fake embedding space: three orthogonal-ish topics.
_VECTORS = {
    "vector": [1.0, 0.0, 0.0],
    "regulation": [0.0, 1.0, 0.0],
    "cooking": [0.0, 0.0, 1.0],
}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        for needle, vector in _VECTORS.items():
            if needle in lowered:
                out.append(vector)
                break
        else:
            out.append([0.5, 0.5, 0.5])
    return out


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None]:
    monkeypatch.setattr(vector_store, "embed_texts", _fake_embed)
    vector_store.get_store.cache_clear()
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory"))
    from deep_research.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    vector_store.get_store.cache_clear()


def test_vector_store_roundtrip() -> None:
    store = vector_store.get_store("test-roundtrip")
    store.upsert(
        ids=["a", "b"],
        texts=["all about vector databases", "all about regulation law"],
        metadatas=[{"tag": "vec"}, {"tag": "reg"}],
    )
    hits = store.search("vector search engines", k=1)
    assert hits[0][0]["tag"] == "vec"
    assert hits[0][1] > 0.9  # cosine similarity of identical fake vectors


def test_episodic_store_and_recall() -> None:
    episodic.store_session(
        thread_id="t1",
        topic="Qdrant vs Chroma vector databases",
        report="Qdrant is production-grade...",
        key_findings=["Qdrant scales horizontally", "Chroma is single-node"],
    )
    block = episodic.recall_similar("best vector database for production")
    assert "Qdrant vs Chroma vector databases" in block
    assert "Qdrant scales horizontally" in block


def test_episodic_recall_ignores_unrelated() -> None:
    episodic.store_session(
        thread_id="t2",
        topic="Italian cooking techniques",
        report="Pasta...",
        key_findings=["Fresh pasta cooks fast"],
    )
    block = episodic.recall_similar("vector database indexing")
    assert "cooking" not in block.lower()


def test_semantic_cache_and_search() -> None:
    semantic.cache_sources(
        [
            Source(
                url="https://qdrant.tech/benchmarks",
                title="Vector Search Benchmarks",
                snippet="Qdrant achieves the highest RPS in vector benchmarks.",
            )
        ]
    )
    [hit] = semantic.search_cached("vector database performance", k=1)
    assert hit.url == "https://qdrant.tech/benchmarks"
    assert "RPS" in hit.snippet
    assert hit.score is not None and hit.score > 0.9


def test_semantic_recache_same_url_is_update_not_duplicate() -> None:
    source = Source(url="https://x.example/vector", title="V1", snippet="vector text one")
    semantic.cache_sources([source])
    semantic.cache_sources([source.model_copy(update={"title": "V2"})])
    hits = semantic.search_cached("vector", k=5)
    assert len([h for h in hits if h.url == "https://x.example/vector"]) == 1
    assert hits[0].title == "V2"
