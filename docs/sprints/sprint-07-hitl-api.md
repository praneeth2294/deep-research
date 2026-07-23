# Sprint 07 — Human-in-the-Loop + API

> **Phase:** 7 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** steerability + serving — pause the graph for plan approval before researcher cost, and expose the whole system over HTTP with progress streaming and feedback.
> **Status:** ✅ Complete — 124 unit tests green; DoD proven end-to-end over HTTP (submit → see plan → edit a sub-topic → approve → stream → report → feedback); live CLI run with the approval gate.

---

## 1. What we built

```
planner -> [ hitl: interrupt() ] --approve--------> researcher fan-out
                 |                --edit(plan')---> researcher fan-out (edited!)
                 |                --cancel--------> END (explained, $0 researchers)
                 v
        (graph checkpointed & parked: "awaiting_approval")

HTTP:  POST /research {topic}            -> {thread_id}
       GET  /research/{id}               -> status | plan | result | error
       GET  /research/{id}/stream        -> SSE: node_completed events ... [DONE]
       POST /research/{id}/approve       -> {decision, sub_topics?}
       POST /feedback                    -> {thread_id, rating: up|down, comment}

CLI:   interactive a/e/c prompt at the pause; --auto-approve for scripts/demos;
       non-TTY runs auto-approve automatically.
```

| Artifact | Role |
|---|---|
| `graph/nodes/hitl.py` | `interrupt()` with the plan payload; resume decisions: approve / edit (PlannerOutput-validated) / cancel |
| `builder.py` | planner → hitl → fan-out-or-END; `build_graph(hitl=True)` default, `hitl=False` for pipeline-focused tests |
| `api/manager.py` | SessionManager: background-thread graph driving, per-session status/events/plan/result, per-session CostTracker |
| `api/app.py` | FastAPI app factory + the five endpoints; SSE via polling generator; feedback → `data/feedback.jsonl` |
| `cli.py` | interrupt loop: show plan → prompt (or auto) → `Command(resume=...)` |
| `tests/unit/fakes.py` | Shared `wire_deep_pipeline()` — one place that fakes the whole pipeline for graph-level tests |

## 2. Why — every decision, interview-depth

### Why the interrupt is exactly after the planner
The plan is the **last cheap artifact**: everything after it multiplies cost by the
number of researchers (LLM decisions × tool calls × analysis of the results). It is
also the **most human-correctable** artifact — a person instantly sees "that
sub-topic misreads my question" — whereas approving individual tool calls would be
noise. Approval gates go where human judgment is high-leverage and cost is about
to jump. That's the deck's HITL principle made concrete.

### interrupt() is checkpointing wearing a different hat
The pause is not a sleeping process. `interrupt()` persists the graph state via the
Phase-5 checkpointer and **returns**; nothing is running while a human thinks. The
resume — minutes or days later, from any process — is `invoke(Command(resume=
decision))` on the same thread id. This is why Phase 5 said HITL was "already paid
for": pause/resume and crash/resume are the same mechanism, deliberately.
**Interview terms:** interrupt/resume, Command channel, durable pause vs blocking
wait.

### Edits re-enter through the planner's contract
An edited plan is validated with `PlannerOutput.model_validate(...)` — the same
schema the planner's own output obeys (1–3 sub-topics, non-empty queries). The
human is a *peer of the planner*, not a superuser: no path into the graph bypasses
the contract. The API layer additionally validates before resuming (422 on bad
edits), so garbage can't even reach the graph.

### The API drives the graph in background threads (and why that's OK here)
`POST /research` returns a thread id immediately; a daemon thread drives
`graph.stream(...)`, appending each node completion to the session's event list.
The SSE endpooint is a **polling generator** over that list — no queues, no pubsub.
Honest scaling note (documented, and the kind interviewers probe): in-process
sessions + threads are correct for a single-instance service; multi-instance
deployment needs sticky routing or externalized session state (the graph state
itself is *already* external in SQLite — only the ephemeral event feed is not).

### Per-session cost tracking (a v0 limitation retired)
Sprint 03 flagged the process-global cost tracker as CLI-only. The API now gives
each session its own `CostTracker` wired through per-invoke callbacks —
`result.cost_usd` is per-run truth. (The *budget guard* still reads the global
tracker — retired in Phase 8 when cost moves to tracing.)

### One fakes module instead of copy-pasted patch blocks
`wire_deep_pipeline()` centralizes the "fake every LLM and tool" setup that three
test files were about to duplicate; `searched_queries` recording lets tests assert
*consequences* ("the edited query actually ran; the replaced one never did")
rather than just outcomes. Test infrastructure is architecture too.

## 3. What the tests + live run showed (DoD)

- **HTTP flow test** (real graph, faked models, real background threads, real
  polling): submit → `awaiting_approval` with visible plan → edit one query →
  `done` with report + review score + cost → SSE replay ends with `[DONE]` →
  feedback recorded. The edit assertions prove **the human's query ran and the
  planner's original did not**.
- **Cancel** ends the run with an explained refusal and **zero researcher calls**
  (recorded-queries list empty).
- **409/404/422 semantics**: approving a non-waiting session → 409; unknown
  thread → 404; edit without sub_topics → 422.
- **Live CLI**: plan paused → auto-approved → full pipeline; researchers showed
  multi-tool choice (`semantic_search` + `fetch_url` + `tavily_search`), 10/10
  review, ~$0.0029.

## 4. Things added beyond the plan

1. **Non-TTY auto-approve** — piped/scripted CLI runs don't hang on `input()`.
2. **Session state machine with explicit conflict semantics** (409 on
   approve-in-wrong-state) — the plan just said "approve endpoint".
3. **Per-session cost in the API result** — retired a documented v0 limitation.
4. **`hitl` build flag** — pattern tests stay focused; the gate has dedicated
   tests. Also the honest note that interrupt requires a checkpointer.
5. **SSE `[DONE]` sentinel + reconnect-friendly replay** (events list re-served
   from index 0 on each connect).

## 5. Definition of Done — checklist

- [x] interrupt() after planner; approve / edit / cancel all implemented
- [x] Full run driven over HTTP: submit → see plan → edit → approve → stream → report
- [x] Edited plans provably drive the research (query-recording assertions)
- [x] Cancel = explained end, zero researcher cost
- [x] Feedback endpoint persists {thread_id, rating, comment, timestamp}
- [x] CLI `--auto-approve` + interactive a/e/c prompt
- [x] All gates green: ruff, mypy --strict, 124 unit tests
- [x] Sprint log + RUNBOOK updated

## 6. Next sprint (Phase 8 — Observability + Evals)

Langfuse tracing (spans per node/tool, session cost rollups), feedback tied to
trace ids, golden dataset + LLM-as-judge evals wired into CI.
