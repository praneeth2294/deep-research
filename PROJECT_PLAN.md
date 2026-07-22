# Deep Research Agent — Production-Grade Agentic AI Project Plan

> A portfolio-grade project that implements **every agentic pattern** from the SwirlAI deck
> (Agenticai-1.pdf) plus the patterns production systems actually use, built the way a
> 5–7 year AI engineer would build it.

---

## 1. Problem Statement

**Business problem.** Knowledge workers (analysts, PMs, consultants, founders) spend
4–8 hours producing a well-sourced research brief on a topic: finding sources, judging
their credibility, cross-referencing claims, resolving conflicts, and writing a cited
summary. LLM chatbots answer fast but hallucinate, don't cite, don't verify against
multiple sources, and can't be audited.

**Technical problem.** Build a system that takes a research topic and autonomously
produces a **cited, conflict-checked, reviewed research report**, while being:

- **Trustworthy** — every claim traceable to a source; conflicting sources surfaced, not hidden.
- **Bounded** — hard caps on cost, time, retries, and iterations. No runaway loops.
- **Resumable** — a crash at minute 9 of a 10-minute run must not lose (or re-bill) the work.
- **Auditable** — every LLM call, tool call, token, and dollar visible in traces.
- **Steerable** — a human can approve/edit the research plan before money is spent.
- **Testable** — quality measured by automated evals in CI, not vibes.

Those six adjectives are the difference between a demo and a production system —
and each one maps to a specific pattern in this plan.

---

## 2. Solution Overview

A LangGraph-based multi-agent pipeline:

```
Research Topic (user input)
    |
    v
+--------------------------------------------------------------+
|  Guardrails Layer (pure Python, no LLM)                      |
|  PII Scrub | URL Validate | Prompt-Injection Heuristics      |
|  Budget Cap (per-session $) | Rate Limiter (RPM per provider)|
+--------------------------------------------------------------+
    |
    v
+-------------------+
| Episodic Memory   |  "Have we researched something similar?"
| Lookup (vector DB)|  Seeds planner with prior findings (or skips work)
+-------------------+
    |
    v
+-----------+   NEW (industry pattern #1)
|  Router   |   LLM triage: simple_lookup | deep_research | comparison
| (cheap    |   simple_lookup -> single Augmented-LLM answer -> END
|  model)   |   deep_research/comparison -> full pipeline below
+-----------+
    |
    v
+-----------+
|  Planner  |  Decompose topic into 1-3 sub-topics
| (cheap    |  with_structured_output(PlannerOutput)
|  model)   |
+-----------+
    |
    v   NEW (industry pattern #2)
+--------------------------+
| HUMAN-IN-THE-LOOP GATE   |  LangGraph interrupt(): user approves/edits
| approve / edit / cancel  |  sub-topics BEFORE researcher cost is incurred
+--------------------------+  (resumes from checkpoint on approval)
    |
    | Send() fan-out (parallel)
    v
+-----------+  +-----------+  +-----------+
| Researcher|  | Researcher|  | Researcher|   Each = bounded ReAct agent:
| (topic 1) |  | (topic 2) |  | (topic 3) |   reason -> pick tool -> observe -> repeat (<= N)
+-----------+  +-----------+  +-----------+   Tools from registry: Tavily, scraper,
    |               |               |          Wikipedia, semantic-memory RAG
    +-------+-------+-------+-------+          operator.add merges sources
            |
            v
    +---------------+
    | Quality Gate  |   Pure Python: domain trust + snippet scoring
    +---------------+   No LLM call (cost engineering)
            |
     +------+---------+
     |                |
  score < 0.4      score >= 0.4
     |                |
     v                v
+------------+   +-----------+
| REPLANNER  |   |  Analyst  |   Extract claims + confidence + evidence
| revise sub |   | (strong   |   with_structured_output(ClaimSet)
| topic (<=1)|   |  model)   |
+------------+   +-----------+
     |                |
     v                v
 (back to        +-----------+
  researcher)    |Synthesizer|   Cross-reference claims, detect conflicts,
                 | (strong)  |   rank sources by trust
                 +-----------+
                      |
                      v
                 +-----------+
                 |  Writer   |   Versioned drafts with inline citations
                 | (strong)  |
                 +-----------+
                      |
                      v
                 +-----------+
                 | Reviewer  |   Score 0-10 + structured issue list
                 | (cheap)   |
                 +-----------+
                      |
               +------+----------+
               |                 |
            score < 7         score >= 7
            & rev < 2            |
               |                 v
               v          +---------------+
          Writer          | Memory        |  episodic: session summary + verdicts
          (revision,      | Write-back    |  semantic: cache sources + embeddings
           gets issues    +---------------+
           as feedback)          |
                                 v
                              +-----+
                              | END |--> report + trace URL + feedback API (thumbs up/down)
                              +-----+
```

**NEW (industry pattern #3) — Model tiering & fallbacks (cross-cutting):**
cheap/fast model (e.g. Gemini Flash / Haiku) for Router, Planner, Reviewer, Gate-adjacent
tasks; strong model (e.g. Gemini Pro / Sonnet) for Analyst, Synthesizer, Writer.
Automatic provider fallback on 429/5xx with exponential backoff + jitter.

### Cross-cutting production concerns

| Concern | Mechanism |
|---|---|
| Durable execution | LangGraph checkpointer (SQLite dev → Postgres prod); resume by `thread_id` |
| Short-term memory | Graph state (TypedDict + reducers) + checkpointer |
| Episodic memory | Vector DB collection of past session summaries |
| Semantic memory | Vector DB cache of scraped sources (RAG for repeat topics) |
| Procedural memory | Versioned prompt files + tool registry (prompts are code-reviewed artifacts) |
| Observability | Langfuse (or LangSmith): traces, spans per node/tool, token + $ per session |
| User feedback | 👍/👎 endpoint attached to trace id (closes the observability loop) |
| Structured outputs | Pydantic schemas on every LLM boundary; retry-on-parse-failure |
| Resilience | tenacity retries w/ jitter, per-node timeouts, circuit-breaker on scraper |
| Config & secrets | pydantic-settings + `.env` (never in code), 12-factor style |
| Quality in CI | Golden dataset + LLM-as-judge / RAGAS evals, run on every PR |
| Serving | FastAPI + SSE streaming of node progress; Docker Compose stack |

---

## 3. Pattern Coverage Map (deck → project)

### Part 1 — the 7 workflow patterns

| # | Deck pattern | Where implemented |
|---|---|---|
| 1 | Augmented LLM | Every node; purest form = simple_lookup path (LLM + retrieval + tools) |
| 2 | Prompt Chaining + Gate | Analyst → Synthesizer → Writer; Quality Gate = deck's pass/fail gate |
| 3 | Routing | **Router node (LLM-based triage)** + rule-based gate routing |
| 4 | Parallelisation | Send() fan-out to researchers; `operator.add` + Synthesizer = aggregator |
| 5 | Orchestrator-Workers | Planner (dynamic decomposition) → workers → Synthesizer |
| 6 | Evaluator-Optimiser | Writer ↔ Reviewer loop (bounded); Gate → Replanner (cheap variant) |
| 7 | Agent (autonomous loop) | Researcher = bounded ReAct agent (intent → action → env → feedback → stop) |

### Part 2 — agent anatomy

| Deck concept | Where implemented |
|---|---|
| RAG + hybrid retrieval (slides 2–3, 46) | `memory/semantic.py` + `tools/semantic_search.py`; hybrid search (BM25 + vectors + rank fusion + rerank) documented as upgrade path |
| Tool use + registry + function definitions | `tools/registry.py`, per-tool schema modules |
| Short-term / working memory | Graph state + checkpointer |
| Long-term: episodic | `memory/episodic.py` (past sessions, vector DB) |
| Long-term: semantic | `memory/semantic.py` (source cache, RAG) |
| Long-term: procedural | `prompts/` registry + tool registry |
| Planning / revised plan | Planner + Replanner nodes |
| Reflection | Reviewer feedback loop; researcher observing tool results |
| ReAct | Researcher internals (history of thought/action/observation, ≤ N iters) |
| Observability: traces, spans, feedback | `observability/` + feedback endpoint |

### Industry patterns beyond the deck

| Pattern | Where |
|---|---|
| Guardrails (PII, injection, budget) | `guardrails/` |
| Structured output enforcement | `schemas/` + every LLM call |
| Human-in-the-loop | interrupt() after Planner |
| Model tiering + fallbacks | `llm/tiering.py` |
| Durable execution / checkpointing | `memory/checkpointing.py` |
| Cost engineering | no-LLM gate, caching, budget middleware, cheap-model routing |
| Evals as CI gate | `tests/evals/` + golden dataset |

**Known & named but deliberately deferred:** supervisor multi-agent, MCP tool servers,
semantic caching, A/B prompt experiments. (Mention in README as roadmap — shows judgment.)

---

## 4. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Industry default for agents |
| Orchestration | LangGraph | Graph model fits patterns 1:1; checkpointing + interrupt built in |
| LLMs | Gemini Flash + Pro (or Haiku + Sonnet) | Real tiering story; generous free tier for dev |
| Structured outputs | Pydantic v2 | `with_structured_output`, validation at every boundary |
| Search tools | Tavily, Wikipedia API, httpx + selectolax scraper | Free tiers; three genuinely different tools for ReAct |
| Vector DB | Qdrant (Docker) or Chroma (dev) | Episodic + semantic memory |
| Checkpointer | SQLite (dev) → Postgres (prod) | Durable execution |
| Observability | Langfuse (self-host, Docker) or LangSmith | Traces, spans, cost, feedback |
| API | FastAPI + SSE | Streaming progress; industry default |
| Config | pydantic-settings + .env | 12-factor |
| Resilience | tenacity | Retries w/ backoff + jitter |
| Testing | pytest, pytest-asyncio, respx (HTTP mocks) | Unit/integration |
| Evals | RAGAS or LLM-as-judge harness | Faithfulness, coverage, citation accuracy |
| Quality | ruff, mypy, pre-commit | Non-negotiable hygiene |
| Packaging | uv, Docker, docker-compose | Modern, fast, reproducible |
| CI | GitHub Actions | lint → type → unit → evals |

---

## 5. Repository Structure

```
agentic-research/
├── README.md                     # Problem, architecture diagram, demo GIF, pattern map
├── PROJECT_PLAN.md               # This file
├── pyproject.toml                # uv-managed; ruff + mypy config
├── .env.example                  # Every required secret, documented, no values
├── .pre-commit-config.yaml
├── docker-compose.yml            # app + postgres + qdrant + langfuse
├── Dockerfile
├── .github/
│   └── workflows/
│       └── ci.yml                # lint -> typecheck -> unit -> evals (on PR)
├── docs/
│   ├── adr/                      # Architecture Decision Records (1 page each)
│   │   ├── 001-langgraph-over-crewai.md
│   │   ├── 002-no-llm-quality-gate.md
│   │   └── 003-model-tiering.md
│   └── patterns.md               # Deck-pattern -> file map (the learning artifact)
├── src/
│   └── deep_research/
│       ├── __init__.py
│       ├── config.py             # pydantic-settings: models, budgets, limits, keys
│       ├── schemas/              # ALL Pydantic models (LLM I/O contracts)
│       │   ├── planner.py        #   PlannerOutput, SubTopic
│       │   ├── research.py       #   Source, ResearchResult
│       │   ├── analysis.py       #   Claim, ClaimSet, Conflict
│       │   ├── review.py         #   ReviewVerdict, Issue
│       │   └── routing.py        #   RouteDecision
│       ├── llm/
│       │   ├── tiering.py        # cheap/strong factories, fallback chain, retry policy
│       │   └── cache.py          # response cache (dev cost saver)
│       ├── graph/
│       │   ├── state.py          # ResearchState TypedDict + reducers (operator.add)
│       │   ├── builder.py        # assemble nodes/edges/interrupt/checkpointer
│       │   └── nodes/
│       │       ├── router.py     # PATTERN: Routing (LLM triage)
│       │       ├── simple_answer.py  # PATTERN: Augmented LLM (short path)
│       │       ├── planner.py    # PATTERN: Orchestrator (decompose)
│       │       ├── hitl.py       # PATTERN: Human-in-the-loop (interrupt)
│       │       ├── researcher.py # PATTERN: ReAct agent (bounded loop)
│       │       ├── quality_gate.py # PATTERN: Gate (pure Python, no LLM)
│       │       ├── replanner.py  # PATTERN: Planning w/ revision
│       │       ├── analyst.py    # PATTERN: Chaining step 1
│       │       ├── synthesizer.py# PATTERN: Aggregator / synthesis
│       │       ├── writer.py     # PATTERN: Chaining + revision target
│       │       └── reviewer.py   # PATTERN: Evaluator-Optimiser
│       ├── tools/
│       │   ├── registry.py       # tool definitions + registration (procedural memory)
│       │   ├── tavily_search.py
│       │   ├── wikipedia.py
│       │   ├── scraper.py        # httpx + selectolax, timeout + circuit breaker
│       │   └── semantic_search.py# RAG over cached sources
│       ├── memory/
│       │   ├── checkpointing.py  # SQLite/Postgres saver factory
│       │   ├── episodic.py       # session summaries: store + similarity lookup
│       │   ├── semantic.py       # source cache: embed, store, retrieve
│       │   └── embeddings.py
│       ├── guardrails/
│       │   ├── pii.py            # regex + heuristics scrub
│       │   ├── injection.py      # prompt-injection heuristics on scraped text
│       │   ├── url_policy.py     # allow/deny lists, scheme checks
│       │   ├── budget.py         # $ cap per session (raises BudgetExceeded)
│       │   └── rate_limit.py     # token-bucket per provider
│       ├── observability/
│       │   ├── tracing.py        # Langfuse init, span helpers
│       │   ├── cost.py           # token + $ accounting per node/session
│       │   └── feedback.py       # attach 👍/👎 to trace id
│       ├── prompts/              # PROCEDURAL MEMORY — versioned, reviewed
│       │   ├── router.md
│       │   ├── planner.md
│       │   ├── researcher.md
│       │   ├── analyst.md
│       │   ├── synthesizer.md
│       │   ├── writer.md
│       │   └── reviewer.md
│       ├── api/
│       │   ├── app.py            # FastAPI factory
│       │   ├── routes.py         # POST /research, GET /research/{id}/stream (SSE),
│       │   │                     # POST /research/{id}/approve (HITL), POST /feedback
│       │   └── sse.py
│       └── cli.py                # `research "topic"` for local runs/demos
├── tests/
│   ├── unit/                     # every node w/ mocked LLM; guardrails; gate scoring
│   ├── integration/              # graph wiring, checkpoint resume, HITL resume
│   └── evals/
│       ├── golden_dataset.jsonl  # ~15 topics w/ expected properties
│       ├── judges.py             # LLM-as-judge: faithfulness, coverage, citations
│       └── test_evals.py         # thresholds enforced in CI
└── scripts/
    ├── seed_memory.py
    └── run_demo.py
```

---

## 6. Phased Build Plan

Each phase ships something runnable, has a **Definition of Done**, and names the
**patterns you learn**. Order mirrors how a senior engineer de-risks: walking skeleton
first, then widen.

### Phase 0 — Foundations (½ day)
**Goal:** boring, correct scaffolding.
1. `git init`, `uv init`, Python 3.12, `pyproject.toml`.
2. ruff + mypy + pre-commit; GitHub Actions running them.
3. `config.py` with pydantic-settings; `.env.example`; secrets never in code.
4. Skeleton package layout (empty modules, no logic).

**DoD:** CI green on an empty-but-typed repo. **Learn:** production hygiene.

### Phase 1 — Walking Skeleton (1 day)
**Goal:** thinnest end-to-end slice: topic → 1 LLM plan → 1 Tavily search → written answer, via CLI.
1. `schemas/planner.py`, `research.py` — first Pydantic contracts.
2. `llm/tiering.py` v0: one cheap model, tenacity retry.
3. Minimal graph: planner → researcher (single tool call, not ReAct yet) → writer.
4. `cli.py` prints the report.

**DoD:** `uv run research "topic"` produces a cited paragraph. **Learn:** Augmented LLM, Prompt Chaining, structured outputs.

### Phase 2 — Core Patterns (2 days)
**Goal:** the deck's workflow patterns, end to end.
1. `state.py` with `operator.add` reducers; Send() fan-out to N researchers.
2. `quality_gate.py` — pure-Python domain-trust + snippet scoring.
3. `replanner.py` — gate failure revises the sub-topic (max 1 revision).
4. `analyst.py` → `synthesizer.py` (conflict detection) → `writer.py`.
5. `reviewer.py` + bounded Writer↔Reviewer loop (score < 7, rev < 2).

**DoD:** integration test: 3 parallel researchers, forced gate-failure path, forced revision path. **Learn:** Parallelisation, Orchestrator-Workers, Evaluator-Optimiser, Planning-with-revision.

### Phase 3 — Router + Model Tiering (1 day)
**Goal:** cost engineering.
1. `router.py` — cheap-model triage → simple_lookup | deep_research | comparison.
2. `simple_answer.py` — Augmented-LLM short path for trivial queries.
3. `tiering.py` v1: cheap/strong factories; provider fallback chain on 429/5xx.
4. `budget.py` + `rate_limit.py`; `cost.py` v0 (log tokens/$ per node).

**DoD:** trivial query costs <10% of a deep-research run; fallback proven by fault-injection test. **Learn:** Routing (LLM-based), tiering, budget control.

### Phase 4 — ReAct Researchers + Tool Registry (2 days)
**Goal:** turn researchers into real (bounded) agents.
1. `tools/registry.py` — definitions, schemas, registration.
2. `scraper.py` (timeouts, circuit breaker), `wikipedia.py`.
3. `researcher.py` v2: ReAct loop — reason → choose tool → observe → repeat (≤ N), action history in state.
4. Injection heuristics on scraped text (`guardrails/injection.py`).

**DoD:** trace shows researcher choosing different tools per sub-topic; hard iteration cap proven by test. **Learn:** Agent loop, ReAct, tool use + registry, Reflection.

### Phase 5 — Memory (2 days)
**Goal:** all four memory types from the deck.
1. `checkpointing.py` — SQLite saver; resume by `thread_id` (kill -9 test).
2. `embeddings.py` + Qdrant via docker-compose.
3. `semantic.py` — cache scraped sources; `semantic_search.py` as researcher tool.
4. `episodic.py` — session summary write-back + lookup before planning.
5. Prompts moved to `prompts/*.md` registry (procedural).

**DoD:** re-running a similar topic visibly reuses memory (fewer tool calls, cited cache hits); crash-resume test passes. **Learn:** short-term vs episodic/semantic/procedural memory, durable execution.

### Phase 6 — Guardrails Hardening (1 day)
**Goal:** the input/output safety layer.
1. `pii.py` scrub on input; `url_policy.py` allow/deny on every fetched URL.
2. Budget cap raises → graph ends gracefully with partial-results report.
3. Unit tests: injection corpus, PII corpus, budget-exceeded path.

**DoD:** malicious/degenerate inputs produce safe, explained refusals. **Learn:** guardrails as a first-class subsystem.

### Phase 7 — HITL + API (1–2 days)
**Goal:** steerability + serving.
1. `hitl.py` — `interrupt()` after planner; approve/edit/cancel.
2. FastAPI: `POST /research` (returns thread_id), SSE stream of node progress, `POST /research/{id}/approve`, `POST /feedback`.
3. CLI gains `--auto-approve` for demos.

**DoD:** full run driven over HTTP: submit → see plan → edit a sub-topic → approve → stream progress → get report. **Learn:** human-in-the-loop, interrupt/resume, SSE streaming.

### Phase 8 — Observability + Evals (2 days)
**Goal:** see everything; gate quality in CI.
1. Langfuse via docker-compose; spans for every node + tool; session cost rollup.
2. `feedback.py` ties 👍/👎 to trace id.
3. `golden_dataset.jsonl` (~15 topics); `judges.py` scoring faithfulness / citation accuracy / coverage; thresholds in `test_evals.py`, wired into CI (small subset on PR, full nightly).

**DoD:** one trace URL shows the whole run w/ costs; a deliberately-broken prompt fails CI evals. **Learn:** traces/spans/feedback, evals-as-CI.

### Phase 9 — Packaging & Story (1 day)
**Goal:** make it hirable.
1. Dockerfile + full docker-compose stack; `run_demo.py`.
2. README: problem, diagram, demo GIF, pattern map table, cost figures.
3. 3 ADRs; `docs/patterns.md` mapping every deck pattern → file → test.

**DoD:** `docker compose up` + one command demo works on a clean machine. **Learn:** communicating architecture — the actual senior-engineer skill.

**Total: ~12–14 focused days.**

---

## 7. Is This the Best Use Case? (honest assessment)

Scoring criteria: pattern coverage (does it *naturally* need all 7+ patterns), data
availability (no proprietary data needed), eval-ability (can quality be measured),
business resonance (does it read like a real job), novelty on a resume.

| Use case | Coverage | Data | Evals | Business | Novelty | Verdict |
|---|---|---|---|---|---|---|
| **Deep research agent (this plan)** | ★★★★★ | ★★★★★ | ★★★☆ | ★★★★ | ★★☆ | **Best learning vehicle** |
| Customer-support agent (triage + KB RAG + escalation) | ★★★★ | ★★☆ (need a KB) | ★★★★ | ★★★★★ | ★★★ | Best "business" story; weaker fan-out/parallelism |
| Text-to-SQL data analyst agent | ★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★ | Objective evals, hot market; narrow tool surface, little parallelism |
| Document/contract intelligence pipeline | ★★★ | ★★★ | ★★★★ | ★★★★★ | ★★★ | Enterprise-flavored; mostly chaining + extraction, weak agent loop |
| Incident-response / RCA copilot | ★★★★ | ★★☆ | ★★★ | ★★★★ | ★★★★★ | Very novel; needs synthetic infra data, harder to demo |

**Verdict:** for the goal of *learning every pattern in the deck and proving it in code*,
deep research is the strongest single choice — it is the only use case where
parallel fan-out, ReAct tool choice, evaluator loops, memory, and HITL are all
*naturally load-bearing* rather than bolted on. Its weaknesses: crowded space
(GPT-Researcher et al. exist) and fuzzier evals.

**Recommended upgrade (free differentiation):** keep the architecture, narrow the
domain — frame it as a **Competitive-Intelligence Research Agent** ("given a company,
produce a sourced competitive brief: products, pricing, recent moves, risks").
Same graph, but: episodic memory becomes genuinely useful (re-research the same
company monthly → memory shows deltas), evals get sharper (factual fields you can
check), and the README reads like a business tool instead of a tutorial. That is the
version I would put on a resume.

Optional stretch after Phase 9: add a second thin use case (e.g. support-ticket
triage) on the same infrastructure to prove the architecture is reusable — that is
what distinguishes "built a project" from "built a platform."
