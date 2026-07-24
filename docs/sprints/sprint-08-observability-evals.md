# Sprint 08 — Observability + Evals

> **Phase:** 8 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** see everything (traces, spans, cost, feedback tied to runs) and gate quality with evals (deterministic citation checks + LLM-as-judge over a golden dataset, wired into CI).
> **Status:** ✅ Complete — 131 unit tests green; live DoD: a real run's trace shows every node/LLM span with tokens+cost; feedback attached to the trace; live eval scored 10/10/10 by the judge.

---

## 1. What we built

```
Every run (CLI + API):
  callbacks = [ cost tracker, TraceRecorder, (Langfuse when configured) ]
  -> data/traces/<thread_id>.jsonl     one span per node + per LLM call
  -> view: research --show-trace <id>  |  GET /research/{id}/trace

  Trace ff93efe8a2df — 5 spans
        62.7ms      1.0ms  node  input_guard
        64.7ms   6849.9ms  node  router
       259.4ms   6625.6ms  llm   gemini-flash-lite-latest  189/38 tok
      6915.7ms   4620.8ms  node  simple_answer
      8844.6ms   2679.0ms  llm   gemini-flash-lite-latest  596/95 tok
  Totals: 785 in / 133 out tokens, ~$0.0001
  Feedback: up 'clear and cited'

Evals:
  golden_dataset.jsonl (12 topics, expected routes + facets)
  deterministic gate:  every [n] must resolve to a real source  (free, offline)
  LLM-as-judge gate:   faithfulness / coverage / citation_quality >= 7
  CI: `evals` job runs when repo secrets exist; small sample on PR, full nightly
```

| Artifact | Role |
|---|---|
| `observability/tracing.py` | `TraceRecorder` (LangChain callback → node/LLM spans with tokens+cost), `format_trace` viewer, `langfuse_handler()` opt-in export |
| `observability/feedback.py` | `record_feedback` — 👍/👎 keyed by thread_id, mirrored into the trace file |
| CLI `--show-trace` / API `GET /trace` | Human-readable span timeline anywhere |
| `tests/evals/golden_dataset.jsonl` | 12 topics with expected routes and facets |
| `tests/evals/judges.py` | `check_citations` (deterministic) + `judge_report` (LLM-as-judge, structured verdict) |
| `tests/evals/test_evals.py` | marked `evals`, self-skips without keys, deterministic + judged gates |
| `prompts/judge.md` | The judge's rubric (grounded scoring, no own-knowledge) |
| CI `evals` job | Runs on secrets-configured repos; `EVAL_SAMPLE_SIZE` scales PR vs nightly |

## 2. Why — every decision, interview-depth

### trace_id == thread_id — one identifier joins everything
The same id keys the checkpoint (resume), the trace file (debugging), and the
feedback record (quality signal). When a user thumbs-down a run, you open
*that run's* trace and see *that run's* spans, costs, and errors — the deck's
observability loop (trace → feedback → fix) with zero id-mapping glue.
**Interview line:** *"correlation ids are cheap when you pick them early and
expensive when you retrofit them."*

### Vendor-neutral tracing with Langfuse as config-only opt-in (deviation, documented)
The plan said "Langfuse via docker-compose". This machine has no Docker (same
constraint as Phase 5), and hard-wiring a vendor SDK through the codebase would
couple every node to it. Instead: a ~150-line LangChain **callback handler** owns
span capture locally (JSONL per run), and `langfuse_handler()` attaches the
Langfuse exporter **when keys exist and the package is installed** — import-
guarded, zero code paths depend on it. Swap-in is: `uv add langfuse` + two env
keys. Same architectural move as Chroma-behind-an-interface.

### Why a callback handler (not instrumenting nodes by hand)
LangChain/LangGraph already emit lifecycle events for every node (chain runs
carry `langgraph_node` metadata) and every model call (with `usage_metadata`).
Hand-instrumenting 14 nodes means 14 chances to forget one; the handler gets
every event **by construction** — enforcement-by-architecture again. Filtering
matters: nested runnables fire chain events too, so node spans are recorded only
when the run's name matches its `langgraph_node` metadata (tested against a
`RunnableSequence` decoy).

### `raise_error = False` — tracing must never break the run
A tracing bug that kills research inverts the value hierarchy (same rule as
memory in Phase 5). The recorder swallows malformed events (garbage LLM
responses, ends-without-starts — tested) and `flush()` is called in `finally`
blocks, so even a crashed run leaves its partial trace behind — which is
precisely when you want one.

### The two-layer eval design (the part interviewers dig into)
- **Deterministic layer** (`check_citations`): every `[n]` in the report must
  resolve to an existing source. Free, instant, objective — and it catches the
  worst failure class (fabricated citations) with zero LLM involvement. Run it
  on everything, always.
- **Judged layer** (`judge_report`): faithfulness / coverage / citation-quality
  scored 0–10 by a cheap model against **the actual sources** (rubric forbids
  outside knowledge). Catches what regexes can't: claims that cite a source
  which doesn't support them.
Order matters: cheap-and-certain gates run before expensive-and-probabilistic
ones. The "deliberately-broken report fails" DoD is pinned by the offline test
where `[99]` against 5 sources fails hard.
**Interview terms:** LLM-as-judge, golden dataset, deterministic vs model-based
metrics, faithfulness/groundedness, eval-as-CI-gate.

### Evals as a separate pytest marker + CI job
`-m "not evals"` in addopts keeps the default run free and offline; the CI
`evals` job supplies secrets and runs a 2-topic sample on PR (nightly = bump
`EVAL_SAMPLE_SIZE`). Evals are tests that cost money — so they get the same
treatment as slow integration suites: always runnable, never accidental.

## 3. Live DoD verification

- Real run traced end-to-end: 5 spans (nodes + LLM calls) with offsets,
  durations, tokens, and ~$0.0001 rollup — one command: `--show-trace`.
- `record_feedback(...)` → the same trace now ends with
  `Feedback: up 'clear and cited'`; the global feedback store has the record.
- Live eval (`EVAL_SAMPLE_SIZE=1`): full pipeline on a golden topic + judge —
  **faithfulness=10 coverage=10 citations=10 passed=True**, in 4 minutes.
- Broken-report failure proven offline (hallucinated `[99]` → `all_valid=False`).

## 4. Test strategy

- **Recorder** — simulated callback sequences: node span + LLM span with token
  usage captured; nested-runnable decoy ignored; flush-across-resume appends
  without duplicates; garbage events never raise.
- **Feedback** — tied into the trace file AND the global store (temp-dir
  isolated via settings, like the memory tests).
- **Citation checker** — valid/hallucinated/citation-free reports.
- **API** — trace endpoint added to the HTTP flow test; feedback assertions now
  check the actual stores (temp-isolated) instead of just the 200.
- 131 unit tests offline; 2 integration + evals live-gated.

## 5. Things added/changed beyond the plan

1. **Local JSONL trace store + viewer** replacing hard Langfuse dependency
   (rationale above); Langfuse stays one config flip away.
2. **`GET /research/{id}/trace`** endpoint — the API can serve its own traces.
3. **Feedback mirrored into the trace file** — `--show-trace` shows the human
   verdict inline (the deck's 👍/👎-on-the-trace picture, literally).
4. **Deterministic citation gate** in front of the judge — the plan only had
   LLM scoring; the free gate catches the worst class first.
5. **Fixed in passing:** live integration tests now build with `hitl=False`
   (the Phase-7 gate requires a checkpointer the tests don't carry).

## 6. Definition of Done — checklist

- [x] Every run traced: spans per node + LLM call, tokens, cost, duration
- [x] One command shows a whole run with costs (`--show-trace` / API endpoint)
- [x] Feedback (👍/👎) tied to the trace id and visible in the trace
- [x] Golden dataset (12 topics) + deterministic and judged gates
- [x] Broken report provably fails (offline citation-gate test)
- [x] Live eval passed through the real pipeline (10/10/10)
- [x] CI evals job (secrets-gated, sample-sized)
- [x] All gates green: ruff, mypy --strict, 131 unit tests
- [x] Sprint log + RUNBOOK updated

## 7. Next sprint (Phase 9 — Packaging & Story)

Dockerfile + compose stack, demo script, full README (problem → architecture →
pattern map → cost figures), ADRs, docs/patterns.md deck-to-code map.
