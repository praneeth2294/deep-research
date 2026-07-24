# Sprint 09 — Packaging & Story

> **Phase:** 9 of 9 — the final phase (see PROJECT_PLAN.md §6)
> **Goal:** make the project communicable and deployable: Docker, one-command demo, the real README, ADRs, and the pattern→code→test map.
> **Status:** ✅ Complete — demo verified live (all 3 scenarios), 131 unit tests green, all documentation shipped. **The project is done: 10 sprints, every planned pattern implemented and tested.**

---

## 1. What we built

| Artifact | Role |
|---|---|
| `Dockerfile` | Multi-stage uv build (locked deps layer cached separately), slim runtime, non-root user, serves the API |
| `docker-compose.yml` | API + persisted `data/` volume; optional `qdrant` profile (the ADR 004 swap path) |
| `scripts/run_demo.py` | One command, three scenarios: guardrail refusal ($0) → routed short path → full pipeline with plan approval; degrades to scenario 1 without keys |
| `README.md` (rewritten) | Real output sample, architecture diagram, pattern map link, quick start, API, Docker, **measured cost table**, doc index |
| `docs/adr/001–005` | LangGraph choice · no-LLM gate · tiering+fallbacks · embedded Chroma · vendor-neutral tracing |
| `docs/patterns.md` | Every deck concept → implementation file → pinning test, plus the beyond-deck patterns and the deliberately-deferred list |

## 2. Why — the communication decisions, interview-depth

### The README leads with real output, not features
The first thing a reader sees is an actual run — with the conflict-detection
paragraph and the "sources do not cover X" honesty visible. Features tell;
behavior shows. The cost table contains **measured** numbers from traced runs,
not estimates — a claim with a receipt.

### ADRs record *rejected* alternatives, not just choices
Each ADR names what we didn't do (CrewAI's delegation, LLM-scoring the gate,
per-client rate limiters, Chroma's bundled embedder, hard vendor coupling) and
the consequences we accepted, including the ones that bit us (LangGraph API
churn; fallbacks needing independent failure domains — learned live in Sprint 04).
An ADR that only records the winner is a press release; the trade-off is the
engineering content.

### patterns.md is the project's thesis
The claim of this project is "every industry agentic pattern, implemented and
proven." That claim is only checkable if every pattern maps to a file AND a
test. The three-column map (concept → code → proof) is the artifact an
interviewer can spot-check in five minutes — and the honest "deliberately
deferred" list at the bottom is what separates scoped judgment from
tutorial-completeness.

### Docker: written to standard, honestly unverified here
The dev machine has no Docker (the constraint that shaped ADRs 004/005), so the
image follows the canonical uv multi-stage pattern (locked dependency layer
cached separately from source, bytecode compiled at build, non-root runtime)
but has not been build-verified on this machine — stated here rather than
discovered by the next person. The *verified* clean-machine path is uv:
`uv sync && uv run pytest` proves the environment in two commands.

### The demo is three behaviors, not one happy path
Refusal-for-$0 (guardrails), routed short path (cost engineering), and the full
pipeline (the whole graph) — chosen so the demo *demonstrates the architecture*,
not just an output. It also degrades gracefully: without keys it still proves
the guardrails offline.

## 3. Definition of Done — checklist

- [x] Dockerfile + compose (API + data volume + optional qdrant profile)
- [x] `uv run python scripts/run_demo.py` — verified live, all 3 scenarios
- [x] README: problem, real output, diagram, pattern map, costs, doc index
- [x] 5 ADRs with rejected alternatives and consequences
- [x] docs/patterns.md: every deck concept → file → test, + deferred list
- [x] All gates green: ruff, mypy --strict, 131 unit tests
- [x] Sprint log + RUNBOOK updated

## 4. Project retrospective (the 30-second interview summary)

**Built:** a deep-research agent as a LangGraph graph — router, planner, HITL
approval, parallel bounded-ReAct researchers with a 4-tool registry, pure-Python
quality gate with bounded replanning, analyst→synthesizer→writer chain,
reviewer loop; layered memory (durable checkpoints, episodic, semantic,
procedural); guardrails at every boundary (input gate, PII, injection, SSRF,
URL policy, budget, rate limit); tiered models with fallback chains; FastAPI +
SSE serving; tracing with feedback tied to runs; a two-layer eval suite in CI.

**Numbers:** 10 sprints · 14 graph nodes · 4 tools · 131 offline unit tests +
live integration/evals · trivial query = 7.6% of deep-run cost · live eval
10/10/10 · every pattern documented with its test.

**The five stories worth telling:** Zscaler TLS interception (fixed with
truststore, not verify=False) · model retirement mid-project (fallback chains,
probe-then-pin) · free-tier quota exhaustion (fallbacks need independent
failure domains) · the gate that needs no LLM (heuristics vs judgment vs
generation) · interrupt() as checkpointing wearing a different hat.
