"""LLM client factories: model tiering, fallbacks, retries, caching.

`tiering.py` (P1, extended P3) exposes `cheap_llm()` / `strong_llm()` so no
node ever constructs a raw client or hardcodes a model name.
"""
