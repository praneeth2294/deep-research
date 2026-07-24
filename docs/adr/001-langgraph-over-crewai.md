# ADR 001 — LangGraph over CrewAI/AutoGen for orchestration

**Status:** accepted (Sprint 01) · **Context:** we need an orchestration layer for a
multi-agent pipeline with parallel fan-out, conditional routing, bounded loops,
durable execution, and human-in-the-loop approval.

## Decision
Use LangGraph's `StateGraph` as the orchestration core.

## Rationale
- **The graph model maps 1:1 to the patterns** we set out to implement: conditional
  edges = routing/gates, `Send()` = parallel fan-out with reducers, cycles = the
  evaluator-optimiser and replan loops.
- **Checkpointing and `interrupt()` are built in** — durable execution (Phase 5) and
  HITL (Phase 7) were wiring work, not infrastructure builds.
- **Deterministic control flow.** CrewAI's role-based delegation and AutoGen's
  conversational hand-offs put routing decisions inside model outputs; we wanted
  control flow in reviewable Python (`builder.py` reads as the architecture diagram).

## Consequences
- We own more explicit wiring than a "crew of agents" abstraction would need — the
  cost of determinism, and worth it.
- LangGraph API churn is a real maintenance tax (pinned via uv.lock, integration
  points concentrated in `builder.py` and node signatures).
