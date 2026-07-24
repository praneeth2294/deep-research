# ADR 004 — Embedded Chroma (dev) behind a thin interface, not Docker-Qdrant

**Status:** accepted (Sprint 05) · **Context:** episodic + semantic memory need a
vector store; the dev machine has no Docker; the plan originally said "Qdrant via
docker-compose".

## Decision
Use embedded Chroma as a pure ANN index behind a ~60-line wrapper
(`memory/vector_store.py`). Embeddings are computed by us (Google embedding API —
its own quota pool), never by the store. Qdrant remains the production target: a
compose profile exists, and the swap touches exactly one module.

## Rationale
- **Zero infrastructure for dev** — `uv sync` is the whole setup; memory works on
  any machine, including CI.
- **The architecture is the interface, not the vendor.** Upsert-by-id + cosine
  search is all we consume; everything vendor-specific is quarantined.
- **Own embeddings** keep the embedding model an explicit, swappable choice and
  avoid Chroma's bundled local model download.

## Consequences
- Embedded Chroma is single-process — fine for CLI + single-instance API, not for
  horizontal scale (that's the Qdrant migration trigger).
- Tests fake `embed_texts` with deterministic vectors: memory logic is tested
  offline; the ANN math itself is the store's responsibility.
