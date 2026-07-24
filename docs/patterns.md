# Pattern Map — deck concept → implementation → proof

Every concept from the source deck (`DECK_EXPLAINED.md`), where it lives in this
codebase, and the test that pins its behavior. This is the learning artifact: pick
any row and you can read the pattern, the code, and its proof side by side.

## Part 1 — Workflow patterns

| Deck pattern (slides) | Implementation | Proof (tests) |
|---|---|---|
| Augmented LLM (5–10) | `graph/nodes/simple_answer.py` (purest form); every node is one | `test_graph_flow.py::test_simple_lookup_short_path` |
| Prompt Chaining + Gate (11–15) | `analyst.py` → `synthesizer.py` → `writer.py`; gate = `quality_gate.py` | `test_graph_flow.py::test_full_flow_with_replan_and_revision` |
| Routing (16–20) | `router.py` (LLM triage) + routing functions in `builder.py` | `test_routing.py`, short-path flow test with booby-trapped planner |
| Parallelisation (21–26) | `Send()` fan-out in `builder.py`; `operator.add` reducer in `state.py` | `test_routing.py::test_fan_out_one_send_per_sub_topic`; flow test asserts 3 parallel results |
| Orchestrator-Workers (27–32) | `planner.py` (dynamic decomposition) → researchers → `synthesizer.py` | flow test; `test_schemas.py` (1–3 sub-topics enforced) |
| Evaluator-Optimiser (33–38) | `reviewer.py` ↔ `writer.py` (bounded); gate → `replanner.py` (code-evaluator variant) | flow test (forced 5/10 → revision → 9/10); `test_routing.py` review routing |
| Agent loop (39–44) | `researcher.py` — bounded ReAct instance per sub-topic | `test_react_researcher.py` (tool choice, **hard cap**, error-as-observation) |

## Part 2 — Agent anatomy

| Deck concept (slides) | Implementation | Proof (tests) |
|---|---|---|
| RAG + hybrid retrieval (2–3, 46) | `memory/semantic.py` + `tools/semantic_search.py` (RAG over own corpus); hybrid = documented upgrade | `test_memory.py::test_semantic_cache_and_search` |
| Core: LLM + controller (47–51) | LLM calls via `llm/tiering.py`; controller = `builder.py` + node code | `test_graph.py` (wiring), `test_tiering.py` |
| Tool use + registry (52–59) | `tools/registry.py` (definitions, catalog, guarded choke point) | `test_registry.py` (incl. sanitization + URL filtering) |
| Working memory (61–66) | `graph/state.py` + ReAct history in prompts | `test_react_researcher.py` (history trail) |
| Context management (67–70) | Source cap (top-20) in `analyst.py`; snippet caps in memory | `test_graph_flow.py` (dedupe/cap assertions) |
| Episodic memory (71–74) | `memory/episodic.py` + `memory_recall.py` node | `test_memory.py` (recall related / ignore unrelated) |
| Semantic memory (75–78) | `memory/semantic.py` + `semantic_search` tool | `test_memory.py` (upsert = update not dupe) |
| Procedural memory (79–80) | `prompts/` registry + `tools/registry.py` | `test_prompts.py` |
| Planning / CoT (81–95) | `planner.py`; revised plans = `replanner.py` | `test_quality_gate.py::test_gate_never_replans_twice` (loop invariant) |
| Reflection (96–102) | replanner (reflect-on-evidence), reviewer loop (reflect-on-draft), ReAct observations | flow test revision path |
| ReAct (103–108) | `researcher.py`: reason → act → observe ≤ N, seeded step 0 | `test_react_researcher.py::test_hard_iteration_cap` |
| Observability (109–114) | `observability/tracing.py` (spans), `feedback.py` (👍/👎 → trace), `--show-trace` | `test_observability.py` (spans, resume-append, feedback tie) |

## Industry patterns beyond the deck

| Pattern | Implementation | Proof |
|---|---|---|
| Guardrails: input gate + refusals | `graph/nodes/input_guard.py` | `test_input_guard.py`; graph-level refusal test ($0 proof) |
| PII scrubbing (Luhn-gated) | `guardrails/pii.py` | `test_pii.py` (corpus + lookalike negatives) |
| Prompt-injection sanitization | `guardrails/injection.py` @ registry choke point | `test_injection.py`, `test_registry.py` |
| SSRF guard + URL policy | `tools/scraper.py` + `guardrails/url_policy.py` | `test_scraper.py` (payload table), `test_url_policy.py` |
| Circuit breaker | `tools/scraper.py` (per-domain, half-open probe) | `test_scraper.py` (full state machine) |
| Structured outputs everywhere | `schemas/` + `with_structured_output` | `test_schemas.py`; Literal action gate in `test_react_researcher.py` |
| Model tiering + fallbacks | `llm/tiering.py` (ADR 003) | `test_tiering.py` (fault injection, budget spy) |
| Budget cap (pre-call) | `guardrails/budget.py` | `test_tiering.py::test_budget_gate_blocks_before_the_call` |
| Rate limiting (shared bucket) | `guardrails/rate_limit.py` | wired via tiering; limits verified live |
| Durable execution / resume | `memory/checkpointing.py`; CLI `--thread` | `test_checkpoint_resume.py` (kill-9 semantics) |
| Human-in-the-loop | `graph/nodes/hitl.py` (interrupt/resume) | `test_hitl.py` (edit drives research; cancel = $0) |
| Serving: API + SSE | `api/manager.py`, `api/app.py` | `test_api.py` (full HTTP flow incl. stream) |
| Evals: deterministic + LLM-judge | `tests/evals/` (golden dataset, judges) | `test_observability.py` (citation gate), live `-m evals` |

## Deliberately deferred (known, named, not built)

Supervisor multi-agent (our orchestrator-workers is the structured variant) ·
MCP tool servers (registry is the in-process equivalent) · semantic caching ·
A/B prompt experiments · hybrid BM25+vector retrieval with reranking.
