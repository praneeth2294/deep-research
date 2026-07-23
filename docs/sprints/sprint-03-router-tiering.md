# Sprint 03 — Router + Model Tiering

> **Phase:** 3 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** cost engineering — LLM triage with a cheap short path, model tiering with automatic fallbacks, rate limiting, budget cap, and cost accounting.
> **Status:** ✅ Complete — 48 unit tests green; DoD measured live: trivial query = **7.6%** of a deep run's cost (target < 10%); fallback proven by fault-injection test.

---

## 1. What we built

```
START -> router --simple_lookup--> simple_answer -> END        (2 LLM calls, ~$0.002)
            |
            +--deep_research / comparison--> full Phase-2 pipeline (~$0.026)
```

| Artifact | Role |
|---|---|
| `nodes/router.py` + `schemas/routing.py` | LLM-based Routing (deck 1.3): cheap structured triage into simple_lookup / comparison / deep_research |
| `nodes/simple_answer.py` | Augmented-LLM short path (deck 1.1): one search + one cheap call, citations included |
| `llm/tiering.py` v2 | `structured_llm(Schema, tier=...)` / `text_llm(tier=...)` — budget gate → fallback chain → rate-limited models |
| `llm/content.py` | `extract_text` moved out of the writer (shared by simple_answer) |
| `guardrails/budget.py` | `check_budget()` raises `BudgetExceededError` *before* each LLM call once the session cap is hit |
| `guardrails/rate_limit.py` | One shared token-bucket limiter across all models and parallel branches |
| `observability/cost.py` | `CostTracker`: token usage via LangChain callback + per-model price table → $ estimate |
| Config | `CHEAP_FALLBACKS` / `STRONG_FALLBACKS` (comma-separated chains), parsed into `*_model_chain` |

Live measurements: simple_lookup ~$0.0020 (1,021 in / 678 out tokens); deep run
~$0.0262 — and the per-model breakdown shows the strong tier carrying the heavy
analyst/synthesizer/writer tokens while the cheap tier handled router/planner/reviewer.

## 2. Why — every decision, interview-depth

### Why an LLM router when Phase 2's gate was deliberately not an LLM?
The rule from Sprint 02 was: *never spend an LLM call on a decision a heuristic can
make.* Triage is the opposite case — "is this topic trivial or multi-faceted?" is a
judgment call no regex can make reliably. So the router IS an LLM, but the **cheapest
possible one**, and its verdict gates whether ~10 more LLM calls happen at all. One
$0.0002 call deciding whether to spend $0.026 is a 100:1 leverage ratio.
**Interview line:** *"Heuristics for mechanical decisions, cheap LLMs for judgment
decisions, and put the judgment call in front of the expensive machinery."*

### The layered runnable — order matters
Every model access is composed outside-in as **budget gate → fallback chain →
(per-model: retries → rate limiter → model)**:
- **Budget gate first**: it must fire before *any* provider is touched, including
  fallbacks — otherwise a runaway loop could keep spending via the backup model.
  Proven by a spy test: when over budget, zero models are invoked.
- **Retries inside, fallbacks outside**: each model first retries transient errors
  with exponential backoff (`max_retries=2`); only *persistent* failure falls
  through to the next model. Retry handles blips; fallback handles outages,
  quota exhaustion (429), and model retirement (404) — the exact failure we hit
  live in Sprint 01.
- **One shared rate limiter**: a single token bucket injected into every client, so
  three parallel researchers collectively respect the provider's RPM cap. A
  per-client limiter would multiply the effective rate by the number of clients —
  a classic distributed-limiter mistake in miniature.
**Interview terms:** retry-vs-fallback separation, token bucket, backpressure,
graceful degradation, bulkhead thinking.

### Why the budget check is *pre-call* rather than post-call accounting
Post-call accounting tells you that you overspent; a pre-call gate prevents the next
overspend. The invariant: the session can never exceed the cap by more than one
call's cost. Cost data comes from LangChain's `UsageMetadataCallbackHandler`
(attached at `graph.invoke`), multiplied through a per-model price table.
**Honest limitation (documented in code):** the price table is approximate and the
tracker is process-global — correct for the one-run CLI, but it must become
per-request state when the API server arrives (Phase 7). Naming current limitations
before the interviewer finds them is a seniority signal.

### Why `structured_llm()` / `text_llm()` replaced the raw model factories
With fallbacks, "a model" became "a chain of models each wrapped with structured
output." If nodes still called `cheap_llm().with_structured_output(...)`, every node
would rebuild that composition (and get it subtly wrong). The tiering layer now owns
the whole recipe; nodes declare *what they want* (schema + tier), not *how to build
it*. This is the same dependency-inversion move as Sprint 01, one level higher.
Side benefit: test fakes got simpler (`fake_structured(response)`), because the
seam is now a single function per node.

### Why the router's fail-open default routes to the full pipeline
`route_after_router` sends unknown/missing routes to the planner, not the short
path. Failing toward the *expensive but thorough* path degrades cost; failing toward
the cheap path would degrade *answer quality* silently. When a guard fails, fail in
the direction whose damage you can see on a bill rather than the one users silently
absorb.

## 3. Usage

```bash
uv run research "What does RAG stand for?"        # -> Route: simple_lookup, ~$0.002
uv run research "Impact of the EU AI Act on startups"  # -> full pipeline, ~$0.026
```

Every run now ends with a cost summary (total $ + per-model token breakdown).
Config knobs (`.env`): `CHEAP_FALLBACKS`, `STRONG_FALLBACKS`,
`MAX_SESSION_BUDGET_USD`, `REQUESTS_PER_MINUTE`.

## 4. Test strategy

- **Fault injection (`test_tiering.py`)** — a fake primary model that 503s on every
  call: asserts the fallback answers; both failing: asserts the error surfaces.
  This is the "chaos test" interviewers ask about, in miniature.
- **Budget spy** — force `total_cost_usd()` to 99: the gate raises AND the spy
  proves no model was ever invoked (ordering, not just outcome).
- **Config parsing** — comma/whitespace/trailing-comma handling for fallback chains.
- **Cost math** — price attribution per model class, token totals, summary format.
- **Flow tests** — deep route runs the full pipeline; simple_lookup runs the short
  path with a booby-trapped planner proving it is never touched.
- 48 unit tests total, all offline.

## 5. Things added beyond the plan

1. **Fail-open routing default** (missing route → full pipeline) — the plan never
   specified failure direction.
2. **`llm/content.py`** — extract_text extracted to a shared module instead of
   cross-importing between nodes.
3. **Budget gate composed into the runnable itself** rather than sprinkled into
   nodes — one enforcement point, impossible to forget in a new node.
4. **Per-model cost breakdown** in the CLI summary — makes the tiering visible
   (you can *see* the strong model carrying the heavy tokens).

## 6. Definition of Done — checklist

- [x] Trivial query < 10% of deep-run cost (measured: 7.6%)
- [x] Fallback proven by fault-injection test (primary 503 → fallback answers)
- [x] Budget cap enforced pre-call (spy test: zero models invoked when over cap)
- [x] Shared rate limiter across all clients and parallel branches
- [x] All gates green: ruff, mypy --strict, 48 unit tests
- [x] Live verification of both paths with cost summaries
- [x] Sprint log + RUNBOOK updated

## 7. Next sprint (Phase 4 — ReAct Researchers + Tool Registry)

Tool registry with machine-readable definitions; wikipedia + scraper tools (with
timeouts and a circuit breaker); researcher upgraded to a bounded ReAct loop that
chooses tools per step; injection heuristics on scraped text.
