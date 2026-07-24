# deep-research

A production-grade **deep research agent**: give it a topic, get back a cited,
conflict-checked, reviewed research report. Built as a LangGraph multi-agent
system that implements the full set of industry-standard agentic patterns —
each one isolated, documented, and tested.

```
$ research "Compare Qdrant and Chroma for production vector search"

Plan (3 sub-topics):        [pauses here for your approval - approve/edit/cancel]
  - Qdrant Production Architecture and Scaling
  - Chroma Production Capabilities and Architecture
  - Qdrant vs Chroma Benchmarks and Comparison
  Qdrant...: 29 sources via semantic_search, tavily_search
  Chroma...: 28 sources via tavily_search
Review: 10/10 after 0 revision(s)
========================================================================
Qdrant and Chroma serve distinct roles ... [3, 14]
...
Several conflicts exist in the provided sources:
*   Scalability: Chroma's own documentation describes a "Distributed
    Architecture" [6][8]. However, other sources explicitly state that Chroma
    lacks horizontal scalability [3][7][14].
The sources do not cover specific hardware requirements ...
========================================================================
Cost: ~$0.0027 (19,626 in / 1,926 out tokens)
Trace: research --show-trace d7a84c44087d
```

Real output. Note the behaviors that separate this from a chatbot: every claim
cited, **source conflicts surfaced instead of hidden**, honest gaps stated,
quality-reviewed, cost-accounted, and fully traced.

## Architecture

```
topic ──> input_guard ──refused (explained, $0)──> END
             │  PII scrubbed, injection refused          [pure Python]
             v
           router ──simple_lookup──> simple_answer ──> END   (~7% of deep cost)
             │  deep_research / comparison
             v
        memory_recall ──> planner ──> HITL: approve / edit / cancel
             │ episodic:                        │ (durable interrupt)
             │ "seen this before?"              v  Send() fan-out, parallel
             │                    ┌──────────┬──────────┐
             │                researcher researcher researcher   [bounded ReAct:
             │                    └──────────┴──────────┘   reason→tool→observe ≤N]
             │                              v
             │                        quality_gate ──fail──> replanner ─┐
             │                              │ pass    [pure Python]     │ retry once,
             │                              v                           │ revised query
             │                    analyst ──> synthesizer <─────────────┘
             │                    (claims +    (cross-reference,
             │                     confidence)  conflict detection)
             │                              v
             │                    writer <──issues── reviewer (0-10, ≤2 revisions)
             │                              │ accepted
             v                              v
         [semantic memory] <────────── memory_store ──> END
         cached sources as                  │
         a researcher tool            report + trace + feedback
```

Cross-cutting: model tiering with fallback chains, shared rate limiting,
pre-call budget cap, SQLite checkpointing (resume any run by thread id),
tracing on every run, SSRF/URL/injection guardrails at choke points.

## Every pattern, mapped

All 7 workflow patterns + the full agent anatomy (tool registry, 4 memory
types, planning, reflection, ReAct, observability) + 13 industry patterns
beyond the deck — each with its implementation file and its test:
**[docs/patterns.md](docs/patterns.md)**.

## Quick start

Prereqs: [uv](https://docs.astral.sh/uv) and git. Python installs itself.

```bash
git clone <repo> && cd deep-research
uv sync
cp .env.example .env      # add GOOGLE_API_KEY (aistudio.google.com/apikey)
                          # and TAVILY_API_KEY (app.tavily.com) - both free
uv run python scripts/run_demo.py     # 3-scenario demo
uv run research "your topic here"     # interactive (plan approval prompt)
```

Offline verification (no keys needed): `uv run pytest` — 131 tests.

## The API

```bash
uv run uvicorn deep_research.api.app:app --port 8000
```

`POST /research` → thread id · `GET /research/{id}` (status/plan/result) ·
SSE `GET /research/{id}/stream` · `POST /research/{id}/approve`
(approve/edit/cancel) · `GET /research/{id}/trace` · `POST /feedback`.
Full curl walkthrough in [RUNBOOK.md](RUNBOOK.md).

## Docker

```bash
docker compose up --build             # API on :8000, data/ persisted
docker compose --profile qdrant up    # + optional Qdrant (see ADR 004)
```

## Observability & quality

- **Traces:** every run → spans per node/LLM call with tokens + cost.
  `research --show-trace <id>`. Langfuse export = `uv add langfuse` + 2 env keys.
- **Feedback:** 👍/👎 keyed to the trace id, shown inside the trace.
- **Evals:** 12-topic golden dataset; deterministic citation gate (every `[n]`
  must resolve) + LLM-as-judge (faithfulness/coverage/citations ≥ 7).
  `uv run pytest tests/evals -m evals`. CI runs them when secrets exist.

## Measured cost profile (free-tier Gemini)

| Scenario | LLM calls | Cost |
|---|---|---|
| Refused input (guardrails) | 0 | $0.0000 |
| Simple lookup (short path) | 2 | ~$0.0020 |
| Full deep run (3 researchers, review) | ~10–18 | ~$0.0027–0.026 |

The router's short path costs **7.6%** of a deep run — the single biggest cost
lever in the system.

## Documentation

| Doc | What it is |
|---|---|
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | Problem statement, architecture, phased build plan |
| [DECK_EXPLAINED.md](DECK_EXPLAINED.md) | Plain-English explanation of every underlying concept |
| [docs/patterns.md](docs/patterns.md) | Pattern → implementation → test map |
| [RUNBOOK.md](RUNBOOK.md) | Every command, per phase + end-to-end |
| [docs/sprints/](docs/sprints/) | 10 sprint logs: what was built, why, interview-depth |
| [docs/adr/](docs/adr/) | 5 architecture decision records |

## Deliberately deferred

Supervisor multi-agent · MCP tool servers · hybrid BM25+rerank retrieval ·
semantic caching · A/B prompt experiments. Known, named, and out of scope on
purpose — see the end of [docs/patterns.md](docs/patterns.md).
