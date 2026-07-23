# Sprint 01 — Walking Skeleton

> **Phase:** 1 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** the thinnest possible end-to-end slice: `research "<topic>"` → plan → web search → cited report.
> **Status:** ✅ Complete — real run verified (2-sub-topic plan, 10 sources, report with inline [n] citations); 29 unit tests, ruff + mypy --strict green.

---

## 1. What we built

```
START → planner → researcher → writer → END        (LangGraph StateGraph)
         (LLM,      (Tavily       (LLM, cited
          structured  search        200-400 word
          output)     per sub-topic) report)
```

| Artifact | Role | Pattern it implements |
|---|---|---|
| `schemas/planner.py` | `SubTopic`, `PlannerOutput` (1–3 sub-topics enforced) | Structured-output contract |
| `schemas/research.py` | `Source` (url/title/snippet/score) | Typed boundary object |
| `prompts/__init__.py` + `planner.md`, `writer.md` | Prompt registry: versioned .md files, cached loader | Procedural memory |
| `llm/tiering.py` | `cheap_llm()` factory — the only place a model is constructed | Tiering v0 |
| `tools/tavily_search.py` | Typed Tavily wrapper → `list[Source]` | Tool use |
| `graph/state.py` | `ResearchState` TypedDict; `sources` already has an `operator.add` reducer | Shared working memory |
| `graph/nodes/{planner,researcher,writer}.py` | The three nodes | Orchestrator-lite → tool call → prompt chain |
| `graph/builder.py` | `build_graph()` — wiring only, no I/O at build time | Graph assembly |
| `net.py` | `setup_tls()` — OS trust store via truststore | Corporate-proxy fix |
| `cli.py` | `research "<topic>"` + no-arg smoke check | Entry point |
| `tests/` | 29 unit tests (all offline) + 1 integration test (auto-skips without keys) | Test pyramid |

## 2. Why — every decision, interview-depth

### Why a "walking skeleton" first (instead of building Phase 2's full graph)?
A walking skeleton is the smallest implementation that touches **every architectural
layer** (CLI → graph → LLM → tool → report). It de-risks integration early: we found
four real-world failures (TLS interception, retired model, provider content format,
console encoding — see §5) in the *simplest possible* pipeline, where each was trivial
to isolate. Had we built the full fan-out graph first, the same four failures would
have surfaced tangled together with parallelism bugs.
**Interview line:** *"I ship a walking skeleton first because integration risk is
front-loaded — pattern risk is not."*

### Why structured output (`with_structured_output`) instead of parsing LLM text?
The planner must return machine-usable sub-topics. Asking for JSON in the prompt and
`json.loads`-ing the reply breaks constantly (markdown fences, trailing commas,
schema drift). `with_structured_output(PlannerOutput)` uses the provider's
**function-calling / constrained decoding** mode: the model is *forced* to emit
arguments matching the Pydantic schema, and the SDK validates + retries on mismatch.
The schema also *constrains behavior*: `min_length=1, max_length=3` makes "1–3
sub-topics" a **validated invariant**, not a prompt suggestion the model may ignore.
**Technical terms to know:** function calling / tool calling, constrained decoding,
JSON Schema, Pydantic validation, retry-on-parse-failure.

### Why LangGraph's StateGraph (vs. plain function calls)?
For three nodes in a row, plain Python would be simpler. We pay the LangGraph tax now
because Phase 2+ needs exactly what it provides: **conditional edges** (quality gate
routing), **Send() fan-out** (parallel researchers), **checkpointing** (durable
execution + resume), and **interrupt()** (human-in-the-loop). The state is a
**TypedDict**; each node receives the state and returns a **partial update**; LangGraph
merges updates. `sources` is declared `Annotated[list[Source], operator.add]` *already*
— a **reducer** that concatenates instead of overwrites, so when Phase 2 runs three
researchers concurrently their results merge conflict-free. Declaring it now means the
Phase 2 diff is an edge change, not a state redesign.
**Technical terms:** state machine / graph orchestration, reducer, partial state
update, fan-out/fan-in.

### Why prompts as .md files (prompt registry)?
Prompts are behavior — they must be diffable, reviewable, and versioned like code
(the deck's *procedural memory*). Inline strings get edited ad hoc and never reviewed.
A cached loader (`@cache`) reads each file once per process.
**Interview line:** *"Prompt changes go through PR review exactly like code changes,
because a prompt regression is a production regression."*

### Why a factory for the LLM client (`cheap_llm()`)?
No node constructs a client or names a model. One factory = one place to change
models, add retries (`max_retries=3` → exponential backoff on 429/5xx), and later add
fallback chains and cost tracking (Phase 3). This is dependency inversion applied to
LLM clients.

### Why does the researcher make NO LLM call in this phase?
Phase 1's researcher just executes each sub-topic's `search_query` against Tavily.
The *planner* already produced good queries — an extra LLM hop would add cost and
latency for nothing yet. The ReAct upgrade (Phase 4) is justified only when the
researcher must *choose between tools* and *react to results*. Knowing when an LLM
call is NOT needed is the cost-engineering skill interviewers probe.

### Why is the search tool a typed wrapper?
`search_web()` maps raw Tavily JSON → `list[Source]` and drops malformed entries
(missing URL) at the boundary. Nothing downstream ever touches provider JSON. This is
the **anti-corruption layer** idea: external formats stop at the edge.

### Why fail-fast key checks at call time (not import time)?
`cheap_llm()`/`search_web()` raise a clear RuntimeError with a setup hint when keys
are missing. At *call* time, not import time — so tests, linting, and `build_graph()`
work on machines with no credentials (CI!). The graph compiles without I/O;
credentials are only touched when a node actually runs.

### Why the writer's grounding rules?
The writer prompt enforces: cite every claim `[n]`, surface conflicts explicitly,
say "sources do not cover X" instead of filling gaps from model knowledge. This is
**grounded generation** — the same anti-hallucination mechanism as RAG's "only use
context." The citations make the report *auditable*: every claim traces to a URL.

## 3. Usage

```bash
uv run research "impact of the EU AI Act on startups"   # full pipeline
uv run research                                          # config smoke check
uv run pytest tests/unit                                 # offline tests (free)
uv run pytest tests/integration -s                       # real API calls (few cents)
```

## 4. Test strategy (interview-relevant)

- **Unit (29, all offline):** schema invariants (1–3 sub-topics enforced, junk URLs
  rejected), prompt files load and are non-empty, Tavily wrapper maps/drops correctly
  (faked client), graph compiles **without credentials**, Gemini content-format
  normalization (plain string AND parts-list), citation numbering.
- **Integration (1, auto-skipped when keys absent):** real pipeline run asserting
  plan size, ≥1 source, report length, and at least one inline citation.
- CI stays green with zero secrets because integration tests *skip themselves* —
  the standard pattern for testing LLM apps in CI.

## 5. Real-world failures we hit and fixed (the best interview stories)

1. **Corporate TLS interception (Zscaler).** Every HTTPS call failed with
   `CERTIFICATE_VERIFY_FAILED`. Diagnosis: opened the TLS socket ourselves and read
   the certificate chain — issuer was `Zscaler Intermediate Root CA`, i.e. a
   **man-in-the-middle proxy** re-signing traffic with a CA that exists only in the
   *Windows* cert store, while Python's httpx trusts only the bundled **certifi** list.
   Fix: `truststore.inject_into_ssl()` (what pip itself uses) → Python validates
   against the OS store. No `verify=False` anywhere — that would disable TLS security
   instead of fixing trust. Wrapped in idempotent `setup_tls()` called at every entry
   point.
2. **Model retirement.** `gemini-2.5-flash` returned 404 "no longer available to new
   users". Instead of guessing names, we queried the **ListModels API** to see what
   the key can actually serve, then probed candidates with a 1-token call. Chose
   `gemini-flash-latest` — a **stable alias** that tracks a serving model, trading
   pinned reproducibility for availability (right trade-off in dev; pin exact
   versions when you need reproducible evals).
3. **Free-tier quota reality.** `gemini-pro-latest` 429s instantly on free keys (no
   pro quota at all). Documented in config; strong tier defaults to a capable flash
   until a paid key exists. Phase 3's tiering will make this a config concern, not a
   code concern.
4. **Provider content-format drift.** Gemini 3 returns message content as a **list of
   typed parts** (text blocks + opaque reasoning signatures), not a string.
   `str(content)` dumped the raw list — including a huge signature blob — into the
   report. Fix: `extract_text()` normalizes both formats and filters non-text parts,
   with a unit test proving reasoning blobs never leak into output.
5. **Windows console encoding.** Printing a source title containing `ł` crashed with
   `UnicodeEncodeError` because Windows consoles default to legacy **cp1252**.
   Fix: reconfigure stdout to UTF-8 at CLI startup.

## 6. Things added beyond the plan

1. `net.py` TLS module (plan never considered corporate proxies).
2. `extract_text()` content normalizer + tests (plan assumed string content).
3. UTF-8 console guard.
4. Model-availability probing workflow (documented in RUNBOOK troubleshooting).
5. The `operator.add` reducer declared one phase early (removes a Phase 2 landmine).

## 7. Definition of Done — checklist

- [x] `uv run research "<topic>"` produces a cited report from live web sources
- [x] Plan is structured output (1–3 sub-topics, schema-enforced)
- [x] All quality gates green: ruff format, ruff check, mypy --strict, 29 unit tests
- [x] Integration test exists and self-skips without keys (CI-safe)
- [x] Graph compiles with zero credentials (proven by unit test)
- [x] RUNBOOK.md updated (Phase 1 section + troubleshooting)
- [x] Sprint log (this file) written

## 8. Next sprint (Phase 2 — Core Patterns)

Send() fan-out to parallel researchers, pure-Python quality gate, replanner on gate
failure, analyst → synthesizer chain, and the writer ↔ reviewer evaluator-optimiser
loop (score < 7, max 2 revisions).
