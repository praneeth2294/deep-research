# ADR 005 — Vendor-neutral tracing; Langfuse as config-only opt-in

**Status:** accepted (Sprint 08) · **Context:** every run must be inspectable
(spans, tokens, cost, feedback); the plan originally said "Langfuse via
docker-compose"; no Docker on the dev machine; vendor SDKs tend to creep through
codebases.

## Decision
A ~150-line LangChain callback handler (`observability/tracing.py`) records node
and LLM spans to a local JSONL file per run, viewable via `research --show-trace`
and `GET /research/{id}/trace`. `trace_id == thread_id` — the same id keys the
checkpoint, the trace, and the feedback record. Langfuse export attaches
automatically when its keys are configured AND the optional package is installed;
no code path depends on it.

## Rationale
- **Callbacks capture every node/LLM event by construction** — no hand
  instrumentation of 14 nodes, no forgetting the 15th.
- **Correlation ids chosen early are free**; retrofitting them is expensive.
  Thread id already keyed resume and feedback — reusing it makes 👍/👎 land on the
  exact run that earned it.
- **Tracing must never break a run**: `raise_error=False`, defensive parsing,
  flush in `finally` (a crashed run leaves a partial trace — exactly when you
  want one).

## Consequences
- The local viewer is a timeline, not a UI — Langfuse (or any OTel backend later)
  is the rich-UI story; enabling it is `uv add langfuse` + two env vars.
- Span coverage is nodes + LLM calls; individual tool calls live in the
  researcher's recorded history rather than as separate spans (revisit if tool
  latency ever needs per-call attribution).
