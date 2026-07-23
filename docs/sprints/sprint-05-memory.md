# Sprint 05 — Memory

> **Phase:** 5 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** the deck's full memory taxonomy in production form — durable working memory (checkpoints + resume), episodic memory (past sessions), semantic memory (accumulated sources as a researcher tool), procedural memory (already in place).
> **Status:** ✅ Complete — 83 unit tests green incl. the kill-9 resume proof; DoD demonstrated live: a related topic **recalled the prior session** and a researcher **chose semantic_search on its own** (17 sources via semantic_search + tavily_search).

---

## 1. What we built

```
                         deep path
START -> router ----------------------> memory_recall -> planner -> ...
                                        (episodic: "researched before?")
... reviewer --accept/budget--> memory_store -> END
                                (episodic: session summary
                                 semantic:  cache all sources)

researcher tools:  tavily_search | wikipedia | fetch_url | semantic_search  <- NEW
durability:        SqliteSaver checkpoints every superstep; resume by --thread
```

| Artifact | Memory type (deck) |
|---|---|
| `memory/checkpointing.py` — SqliteSaver; `build_graph(checkpointer=...)`; CLI `--thread` resume | Working memory, made durable |
| `memory/episodic.py` — store session summary; recall similar (top-2, ≥0.55 similarity) | Episodic |
| `memory/semantic.py` + `tools/semantic_search.py` (4th registry tool) | Semantic |
| `prompts/` + `tools/registry.py` (since Sprints 1 & 4) | Procedural |
| `memory/vector_store.py` — thin Chroma wrapper (cosine ANN), swap-ready interface | Backend |
| `memory/embeddings.py` — Google embedding API (separate quota pool) | Backend |
| `graph/nodes/memory_recall.py`, `memory_store.py` — best-effort nodes | Wiring |

## 2. Why — every decision, interview-depth

### Durable execution: what the checkpointer actually buys
The SqliteSaver persists the whole graph state **after every superstep**. Re-invoking
with the same `thread_id` and `None` as input resumes from the last completed step.
Three consequences:
1. **Crash economics** — a failure at the writer (step ~9) no longer re-bills the
   planner + three researchers; the resume test proves planner/search run exactly
   once across crash + resume.
2. **The CLI prints the thread id up front** — the "receipt" for any run; budget
   exhaustion mid-run now says *"resume with --thread X"* instead of losing work.
3. **Phase 7's HITL is already paid for** — `interrupt()` is just a deliberate pause
   in the same mechanism.
**Interview terms:** durable execution, checkpointing, superstep granularity,
idempotent resume, thread as unit of state.

### The kill-9 test design (worth describing in interviews)
You can't send a real SIGKILL inside pytest portably — instead the writer's LLM
factory *raises* mid-run, which is indistinguishable from a crash **from the
checkpointer's point of view** (the superstep never commits). Then "the process
restarts": same graph, same thread, fixed writer, `invoke(None)`. Call counters
prove the resume semantics. Testing the *semantics* rather than the mechanism is
what makes this test fast, deterministic, and portable.

### Episodic vs semantic — why two collections, not one
They answer different questions with different payloads:
- **Episodic** ("have we *done* this before?") stores one summary per *session*,
  keyed by thread id; recalled as planner context.
- **Semantic** ("do we *know* this already?") stores one entry per *source URL*,
  keyed by URL hash (re-caching = upsert, not duplicate — tested); recalled by the
  researcher as evidence.
Mixing them in one collection would blur ranking (a session summary competing with
a source snippet for the same query). This mirrors the deck's taxonomy exactly.

### Why `semantic_search` is a tool, not an automatic pre-step
We could auto-inject cached sources into every researcher. Making it a *tool the
agent chooses* keeps the ReAct contract uniform (all evidence flows through
observed tool calls, visible in history), lets the agent judge when memory is
likely to help, and — as the live run showed — it *does* choose it when the topic
overlaps past work. The prompt nudges: "instant and free — try it first."

### Memory is best-effort, by design
Both memory nodes swallow all exceptions (no key, empty store, network down →
empty context / skipped write-back). Losing a finished report because a *memory
write* failed would invert the value hierarchy: research output is the product,
memory is an accelerator. Same reasoning as graceful degradation anywhere:
optional subsystems must fail soft.
**Honest trade-off:** silent `except Exception: pass` hides real bugs; Phase 8's
tracing will record these failures as span events instead of silence.

### Chroma embedded instead of the plan's "Qdrant via docker-compose"
Deliberate deviation, documented: the dev machine shouldn't need Docker to run
memory, and embedded Chroma gives the same architecture (cosine ANN over our own
embeddings) behind a 60-line wrapper. Everything Qdrant-specific would live in
`vector_store.py` alone — the swap is config-plus-one-module. We also compute
embeddings **ourselves** (Google embedding API) and use Chroma purely as an ANN
index — avoiding Chroma's default local ONNX model download and keeping the
embedding choice in our control.

### Similarity threshold (0.55) on episodic recall
Vector search always returns *something* — the nearest neighbor of "vector
databases" in a store containing only "Italian cooking" is still Italian cooking.
The threshold turns "nearest" into "actually related"; the unrelated-topic test
pins this behavior. Recall precision > recall volume when the payload lands in a
prompt.

## 3. What the live runs showed (DoD)

Run 1 — *"Qdrant vs Chroma for production RAG systems"*: normal deep run
(10/10 review, ~$0.0027); on completion, memory_store wrote the session summary +
22 sources.
Run 2 — *"Which vector database should a startup choose for semantic search?"*:
- CLI printed **"Episodic memory recalled related past research"** with run 1's
  findings (dated, cited) — planner seeded.
- The first researcher **chose `semantic_search` itself**: *"17 sources via
  semantic_search, tavily_search"* — cached evidence reused at zero web cost.
- Review 10/10, ~$0.0028.
Also live: quota exhaustion forced a model-tier reshuffle (see §5) — the
**flash-lite** class had a separate untouched quota pool, so cheap tier moved to
lite permanently (it is the semantically correct assignment anyway).

## 4. Test strategy

- **Resume proof** (`test_checkpoint_resume.py`) — crash at writer → resume same
  thread → report completes; planner/search counters == 1.
- **Vector store roundtrip** — deterministic fake embeddings (3 orthogonal topic
  vectors), tmp-dir Chroma; nearest-neighbor + similarity assertions.
- **Episodic** — store → recall related (present) / unrelated (absent, threshold).
- **Semantic** — cache → search returns Source with score; re-caching same URL is
  an update not a duplicate.
- **Flow/routing/graph tests updated** — memory muted via a `_mute_memory` helper
  (unit tests must stay offline even on machines WITH a real key in .env — a
  subtle CI-vs-laptop difference worth naming).
- 83 unit tests total, all offline.

## 5. Things added/changed beyond the plan

1. **Chroma embedded replaces Docker-Qdrant** (rationale above; swap path kept).
2. **Own embeddings + ANN-only Chroma** rather than Chroma's bundled embedder.
3. **Best-effort memory nodes** — the plan didn't specify failure behavior.
4. **Cheap tier moved to flash-lite** after quota reality: lite models have their
   own free-tier pool AND are the honest "cheap" assignment. Fallbacks updated to
   cross model families for more independent failure domains.
5. **Budget-stop message now includes the resume command** — checkpointing turned
   the budget cap from "run killed" into "run paused".

## 6. Definition of Done — checklist

- [x] SQLite checkpointer; resume by thread id (CLI `--thread`)
- [x] Crash-resume proven by test (planner/researchers not re-run)
- [x] Semantic memory: sources cached; `semantic_search` as 4th registry tool
- [x] Episodic memory: session write-back + similar-session recall seeding planner
- [x] Live DoD: related topic reused memory (recall printed; agent chose the cache)
- [x] All gates green: ruff, mypy --strict, 83 unit tests
- [x] Sprint log + RUNBOOK updated

## 7. Next sprint (Phase 6 — Guardrails hardening)

PII scrubbing on input, URL allow/deny policy layered on the SSRF guard, budget-
exhaustion behavior test coverage, injection/PII corpora as regression suites.
