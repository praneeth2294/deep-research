# deep-research

A production-grade **deep research agent**: give it a topic, get back a cited,
conflict-checked, reviewed research report — built as a LangGraph multi-agent
system that implements every industry-standard agentic pattern (routing,
parallel fan-out, orchestrator-workers, evaluator-optimiser loops, bounded
ReAct agents, layered memory, guardrails, human-in-the-loop, observability).

> Full README with architecture diagram and demo arrives in Phase 9.

## Documents

| File | What it is |
|---|---|
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | Problem statement, architecture, pattern map, phased build plan |
| [DECK_EXPLAINED.md](DECK_EXPLAINED.md) | Plain-English explanation of every concept (from Agenticai-1.pdf) |
| [RUNBOOK.md](RUNBOOK.md) | Commands to set up, verify, and run — per phase and end-to-end |
| [docs/sprints/](docs/sprints/) | One sprint log per phase: what was built, why, how to use it |

## Quick start (current state: Phase 0)

```bash
uv sync
uv run research
uv run pytest
```

See [RUNBOOK.md](RUNBOOK.md) for everything else.
