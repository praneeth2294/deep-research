# Sprint 02 — Core Patterns

> **Phase:** 2 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** the full pattern set working together: parallel fan-out, quality gate, replanning, analysis chain, and the evaluator-optimiser loop.
> **Status:** ✅ Complete — 39 unit tests green (incl. an offline full-graph flow test forcing every path); real run verified (3 parallel researchers, conflict detection in output, 10/10 review).

---

## 1. What we built

```
                     Send() per sub-topic (parallel)
  START -> planner ================================> researcher(s)
                                                          |  (fan-in)
            +--------------------------------------- quality_gate     [pure Python]
            | fail (attempt 1 only)                       | pass
            v                                             |
        replanner ==Send() revised, attempt 2==> researcher(s) -> gate
                                                          |
            analyst  <------------------------------------+
               |            (dedupe -> numbered evidence -> claims)
               v
          synthesizer -> writer -> reviewer --pass or budget exhausted--> END
                            ^          |
                            +--issues--+   (max 2 revisions)
```

| Artifact | Pattern (deck section) |
|---|---|
| `builder.py` fan-out via `Send()` + `operator.add` reducer | Parallelisation (1.4) |
| `planner` decides N, `synthesizer` merges | Orchestrator-Workers (1.5) |
| `quality_gate.py` — zero-LLM scoring | Gate / cost engineering (1.2) |
| `replanner.py` — revises failed queries, keeps titles | Planning → Revised Plan (2.5) |
| `analyst.py` → `synthesizer.py` → `writer.py` | Prompt Chaining (1.2) |
| `writer` ↔ `reviewer` loop, bounded | Evaluator-Optimiser (1.6) |
| Routing functions in `builder.py` | (rule-based) Routing (1.3) |

New schemas: `ResearchResult` (sub-topic + sources + attempt), `Claim`/`ClaimSet`,
`SynthesisOutput` (summary/key_findings/conflicts), `ReviewVerdict` (score/issues).
New config: `gate_quality_threshold` (0.4), `reviewer_pass_score` (7).
`strong_llm()` added to tiering (analyst/synthesizer/writer).

## 2. Why — every decision, interview-depth

### Send() fan-out — how parallelism actually works here
`add_conditional_edges("planner", fan_out_researchers)` returns a **list of `Send`
objects** — each `Send("researcher", payload)` schedules one researcher instance with
its own **private payload state** (`ResearcherInput`: sub_topic + attempt). LangGraph
runs all of them in the same **superstep** (concurrently) and then — this is the
fan-in — every parallel branch's partial update is merged into shared state. Merging
concurrent writes to the *same key* would normally be a lost-update race; the
**reducer** `Annotated[list[ResearchResult], operator.add]` resolves it by
concatenation. The gate node runs only after all researchers finish (superstep
barrier semantics).
**Interview terms:** map-reduce over a graph, fan-out/fan-in, reducer, superstep,
lost-update problem.

### Why the quality gate has zero LLM calls
Judging "is this evidence any good?" needs no intelligence — domain trust, snippet
substance, and source count are computable in microseconds for $0. Deterministic
scoring is also *testable* (we assert exact behaviors) and *explainable* (a score of
0.31 decomposes into its three components). Rule of thumb an interviewer will
appreciate: **never spend an LLM call on a decision a heuristic can make.** The
LLM-based router (Phase 3) is the counterpart for decisions that DO need judgment.

### Why replan instead of retry
A failed search re-run identically returns the same junk. The replanner spends one
cheap LLM call to change the *search angle* (the deck's Plan → Revised Plan). Two
subtle design points:
1. **The title is the join key.** The replanner may rewrite the query but the node
   forcibly preserves the original title (`model_copy(update=...)`) — because the
   gate bounds the loop by checking "does this title already have an attempt-2
   result?". Letting the LLM drift the title would break loop termination.
2. **Bounded by construction, not by counter.** The gate only ever flags
   `attempt == 1` results whose title has no attempt-2 sibling. There is no global
   "retries" variable to get wrong — the state itself proves termination.
**Interview terms:** idempotent retry vs. corrective retry, loop invariant,
termination proof.

### Why analyst and synthesizer are separate nodes (not one big prompt)
Chaining decomposition: the analyst does *extraction* (sources → atomic claims with
confidence + source ids — a precision task, temperature 0), the synthesizer does
*integration* (claims → narrative, agreements, conflicts — a judgment task). One
mega-prompt doing both does each worse and can't be tested independently. The analyst
also post-validates: **claims citing non-existent source numbers are dropped in
code** — never trust model-emitted indices ("hallucinated citations" is a real
production failure class).

### Why the reviewer is a cheap-model call with a rubric
Evaluator-Optimiser works when the evaluator has *concrete criteria* (grounding,
coverage, conflicts surfaced, clarity — each costing points). Critiquing against a
rubric is much easier than writing, so the cheap model suffices — and the loop is
bounded twice: accept at `score >= 7`, hard stop at `max_writer_revisions = 2`.
The writer receives the reviewer's *specific issues* as revision instructions, not
just "do better" — feedback quality is what makes the loop converge.

### Why routing functions live in builder.py (not in node files)
All control flow — fan-outs, gate branch, review loop — is readable in one file next
to the wiring diagram. Nodes stay **pure functions** (state in → partial update out),
which is what makes the offline flow test possible: fake the factories, run the real
compiled graph, assert the real routing.

## 3. What the real run showed (proof the patterns matter)

Topic: *"Compare Qdrant and Chroma for production vector search"* — 3 parallel
researchers, 14 deduped sources, review 10/10 with zero revisions. The synthesizer
**caught a genuine source conflict**: Chroma's own docs describe a "Distributed
Architecture" while three independent sources call it single-node-only — and the
report presented *both positions with citations* instead of silently picking one.
It also stated what the sources do NOT cover (hardware requirements, cost-per-query).
That behavior — conflict surfacing + gap honesty — is exactly what the analyst →
synthesizer → writer chain was built to produce.

## 4. Test strategy

- **`test_quality_gate.py`** — trust tiers, score ordering (good > 0.9, junk < 0.4,
  empty = 0), gate flags only failing attempt-1 results, **never replans twice**
  (the loop-termination invariant, tested directly).
- **`test_routing.py`** — every routing function as a plain function: one Send per
  sub-topic, gate branch, review accept / revise / budget-exhausted.
- **`test_graph_flow.py`** — the DoD in one offline test: real compiled graph, faked
  LLM factories + search tool; forces junk results for one sub-topic (gate fail →
  replanner → attempt 2) and a reviewer rejection (writer revision). Asserts: 4
  research results (3 + 1 replanned), revised query ran, exactly 1 revision, final
  score 9, sources deduped. **Zero network, zero cost, runs in CI.**
- Faking pattern: nodes import factories by name (`from ...tiering import cheap_llm`
  → `monkeypatch.setattr(module, "cheap_llm", fake)`), so tests inject behavior
  without touching node logic — the payoff of the factory-function decision.

## 5. Things added beyond the plan

1. **Hallucinated-citation filter** in the analyst (drop claims with out-of-range
   source ids) — the plan never mentioned it; production experience demands it.
2. **Title-preservation guard** in the replanner — protects the loop invariant even
   if the LLM drifts.
3. **Source cap (top 20 by score)** before analysis — bounds prompt size/cost on
   query-happy topics.
4. CLI now surfaces replans and the review score — observability breadcrumbs until
   Phase 8's real tracing.

## 6. Definition of Done — checklist

- [x] 3 researchers run in parallel via Send() (proven in offline flow test + live run)
- [x] Forced gate-failure path exercised (junk sources → replanner → attempt 2)
- [x] Forced revision path exercised (reviewer 5/10 → writer revision → 9/10)
- [x] Replan loop provably bounded (unit test: never flags a replanned title again)
- [x] All gates green: ruff, mypy --strict, 39 unit tests
- [x] Live run verified with conflict detection in output
- [x] Sprint log + RUNBOOK updated

## 7. Next sprint (Phase 3 — Router + Model Tiering)

LLM triage router (simple_lookup short-path vs. full pipeline), budget middleware and
rate limiting, cost accounting v0, and provider fallback on 429/5xx.
