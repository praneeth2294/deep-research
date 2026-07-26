# Code Tour — every file explained simply

> Written for someone with 0–1 years of experience. We start at
> [`builder.py`](../src/deep_research/graph/builder.py) — the file where the whole
> system is assembled — and follow its imports outward. Every file gets a plain
> explanation and an analogy. Read this top to bottom once, then read the real
> files in the order suggested at the end.

---

## 0. The big picture in three sentences

This project is a **team of small AI workers** that together research a topic and
write a cited report. The team is organized as a **flowchart that executes**
(a LangGraph "graph"): each box is a Python function, each arrow is a rule about
who works next. `builder.py` is the file that **draws that flowchart in code** —
so if you understand builder.py and what each imported file does, you understand
the entire system.

## 1. builder.py — the assembly plan (start here)

Open [`graph/builder.py`](../src/deep_research/graph/builder.py). It does only
three kinds of things:

1. **Registers workers:** `graph.add_node("planner", planner_node)` — "there is a
   worker called *planner*, and this function is what it does."
2. **Draws arrows:** `graph.add_edge("analyst", "synthesizer")` — "after the
   analyst, always the synthesizer." And `add_conditional_edges(...)` — "after the
   reviewer, *look at the data and decide*: revise again, or finish."
3. **Compiles:** `graph.compile(checkpointer=...)` — turn the drawing into a
   runnable program that saves its progress after every step.

Everything builder.py imports is either a **worker** (`nodes/`), the **shared
whiteboard** they write on (`state.py`), or a **setting** (`config.py`). So the
imports of builder.py are literally a map of the system. Let's walk through the
map, folder by folder.

---

## 2. The whiteboard: `graph/state.py`

**What it is:** one big dictionary shape (`ResearchState`) that lists every field
the workers share — the topic, the plan, the sources found, the report, the
review score.

**Analogy:** a whiteboard in a meeting room. Workers never talk to each other;
each one reads the board, does its one job, and writes its result on the board.

**The one tricky line:**
`research_results: Annotated[list[...], operator.add]` — this is a rule pinned to
the board that says *"if several workers write to this field at the same time,
APPEND their lists — don't overwrite each other."* We need it because 3
researchers run **in parallel** and all report results at once.

Also here: `ResearcherInput` — a tiny private note ("your sub-topic, your attempt
number") handed to each parallel researcher so they know which slice is theirs.

## 3. The workers: `graph/nodes/` (one file = one worker = one job)

Every file has the same shape: **read the state → do one job → return only what
changed.** A node never calls the next node — builder.py decides that.

| File | Its one job (plain words) |
|---|---|
| `input_guard.py` | The security guard at the door. Pure Python, no AI. Rejects empty/too-long topics and topics that try to give the AI orders ("ignore your instructions…"), and erases personal data (emails, card numbers) before anything is sent to the internet. Refusals cost $0 because nothing else runs. |
| `router.py` | The receptionist. Asks a cheap AI one question: "is this a quick question, a comparison, or real research?" Quick questions skip the whole expensive pipeline. |
| `simple_answer.py` | The quick-answer desk. For easy questions: one web search + one short cited answer. Done. |
| `memory_recall.py` | The archivist. Checks "have we researched something like this before?" and, if yes, puts a summary of the old findings on the whiteboard for the planner to see. |
| `planner.py` | The team lead. Splits the topic into 1–3 sub-topics, each with a ready-to-run search query. |
| `hitl.py` | The approval pause. The graph literally **stops** here (`interrupt()`) and shows you the plan. You approve, edit the queries, or cancel. Only after your answer does work (and cost) continue. HITL = human-in-the-loop. |
| `researcher.py` | The field investigators (one **copy** per sub-topic, running at the same time). Each is a mini-agent in a loop: think → pick a tool → look at results → repeat, at most 5 rounds. Everything it did is written down in a `history` list — its diary. |
| `quality_gate.py` | The quality inspector. Pure Python, no AI: scores each researcher's evidence (are the websites trustworthy? are the snippets substantial? enough sources?). Below the bar → send that sub-topic for a retry with a better query. Only one retry, ever — the loop cannot run forever. |
| `replanner.py` | The strategy fixer. When the gate rejects something, this asks a cheap AI: "that search query found junk — write a better one." Retry with a *different* approach, not the same one. |
| `analyst.py` | The fact extractor. Merges all sources (removing duplicates), numbers them [1], [2], …, and pulls out individual factual claims, each tagged with which sources support it. |
| `synthesizer.py` | The cross-checker. Looks at all claims together: what do independent sources agree on? **where do they contradict each other?** Contradictions are listed, not hidden. |
| `writer.py` | The author. Writes the report using ONLY the numbered sources, citing every claim like [3]. If the reviewer rejected a draft, it rewrites, fixing the listed issues. |
| `reviewer.py` | The editor. Scores the draft 0–10 against a checklist (everything cited? on-topic? conflicts mentioned?). Below 7 → back to the writer with concrete fixes. Maximum 2 rewrites. |
| `memory_store.py` | The librarian. Files away what this run learned (summary + all sources) so future runs can reuse it. If filing fails, the report is still delivered — memory is a bonus, never a blocker. |

**How the arrows connect them** (the diagram at the top of builder.py):

```
guard → router → (easy? quick answer, done)
                 (hard?) archivist → planner → YOUR APPROVAL
                     → researchers (parallel) → inspector → (fail? fixer → retry once)
                     → fact extractor → cross-checker → writer ⇄ editor → librarian → done
```

## 4. The shared services the workers use

Workers don't do everything themselves — they call helper modules. These are the
other folders.

### `schemas/` — the forms everyone must fill in
Pydantic classes like `SubTopic`, `Source`, `Claim`, `ReviewVerdict`. When we ask
the AI for a plan, we don't accept free text — we force it to fill in this exact
form (right fields, right types, 1–3 sub-topics). If the AI fills it wrong, it's
automatically rejected and retried. **Analogy:** a government office that only
accepts properly filled forms — no forms, no scribbled notes.

### `prompts/` — the instruction sheets
One `.md` file per worker (planner.md, writer.md, …) containing its instructions
("You are the planner. Split the topic…"). Kept as files — not buried in code —
so changing an instruction is a reviewed, tracked edit like any code change.
`load_prompt("planner")` just reads the file.

### `llm/tiering.py` — the one door to the AI models
No worker creates an AI client itself. They all call `structured_llm(...)` or
`text_llm(...)` from here. Behind that one door we've stacked the safety layers:
**budget check** (stop if we've spent too much) → **backup models** (if the main
model is down/out of quota, try the next) → **speed limit** (all workers share
one requests-per-minute budget). **Analogy:** one reception desk in front of the
AI — everyone goes through it, so the rules apply to everyone automatically.
`llm/content.py` is a small cleaner that extracts plain text from the different
response formats models return.

### `tools/` — the workers' equipment
- `registry.py` — the **toolbox catalog**: each tool's name + description + how to
  run it. The researcher picks tools *by name* from this catalog. Crucially, every
  tool's output passes through a **checkpoint** here that (a) drops links our URL
  policy forbids and (b) erases "ignore your instructions"-style text hidden in
  web pages. One checkpoint, so no tool can forget it.
- `tavily_search.py` — web search. `wikipedia.py` — encyclopedia search.
- `scraper.py` — fetches one full web page. Has real armor: refuses internal/
  private addresses (a classic attack called SSRF), times out slow sites, and has
  a **circuit breaker** — after 3 failures on a domain it stops trying that
  domain for 5 minutes instead of wasting the agent's turns on a dead site.
- `semantic_search.py` — searches our **own** memory of past sources. Free and
  instant; the researcher often tries it first.

### `guardrails/` — the safety rules (all plain Python, no AI)
`pii.py` finds emails/phones/cards (cards verified with the Luhn checksum so
random numbers aren't flagged). `injection.py` detects "ignore your
instructions" attacks. `url_policy.py` decides which URLs are acceptable.
`budget.py` raises an alarm when the session cost cap is reached. `rate_limit.py`
is the shared speed limit. **Why no AI here:** a rule written in code cannot be
sweet-talked; an AI asked to police itself sometimes can.

### `memory/` — how the system remembers
- `checkpointing.py` — the **photographer**: saves the whiteboard to a SQLite file
  after *every* step. Crash at step 9? Resume from step 9 — nothing already paid
  for is redone. This same mechanism powers the approval pause.
- `vector_store.py` + `embeddings.py` — the memory engine. Text is converted to
  number-lists ("embeddings") so that *similar meaning = nearby numbers*, letting
  us search by meaning, not keywords.
- `episodic.py` — memory of past **sessions** ("we researched Qdrant last week").
- `semantic.py` — memory of past **sources** (the cache `semantic_search` reads).

### `observability/` — the flight recorder
`tracing.py` records every step and AI call with timings, token counts, and cost
into one file per run — view it with `research --show-trace <id>`. `cost.py` adds
up tokens × price. `feedback.py` attaches your 👍/👎 to that same run's file.
**Analogy:** an airplane's black box — when something goes wrong, you replay
exactly what happened instead of guessing.

### `config.py`, `net.py` — the settings and the plumbing
`config.py` reads all settings from the `.env` file into one typed object
(model names, caps, paths) and validates them at startup — a bad setting crashes
immediately with a clear message, not silently at 2 a.m. `net.py` fixes one
corporate-laptop problem: making Python trust the company proxy's certificates.

## 5. The two front doors: `cli.py` and `api/`

- `cli.py` — the terminal door. Parses `research "topic"`, builds the graph
  (calling **builder.py**!), runs it, shows you the plan for approval, prints the
  report + cost + trace id.
- `api/manager.py` + `api/app.py` — the web door. Same graph, driven over HTTP:
  submit a topic → get a `thread_id` → watch progress stream in → approve the plan
  with a POST → fetch the report. The manager babysits each running session in a
  background thread.

Both doors call the **same** `build_graph()` — the business logic lives once, in
the graph, never in the doors.

## 6. Follow one request through the files (connect everything)

You type: `uv run research "Qdrant vs Chroma" `

1. **cli.py** reads your command → calls **builder.py**'s `build_graph()` with the
   checkpointer from **memory/checkpointing.py**.
2. **input_guard.py** checks your topic using **guardrails/pii.py** and
   **guardrails/injection.py**. Clean → continue.
3. **router.py** asks a cheap model — through **llm/tiering.py**, which first
   checks **guardrails/budget.py** — filling the `RouteDecision` form from
   **schemas/**. Verdict: "comparison" → deep path.
4. **memory_recall.py** asks **memory/episodic.py** about similar past work.
5. **planner.py** loads its instructions from **prompts/planner.md**, produces
   1–3 `SubTopic` forms.
6. **hitl.py** pauses the graph; **cli.py** shows you the plan; you press approve;
   the graph resumes from its checkpoint.
7. builder.py's fan-out sends one **researcher.py** per sub-topic, in parallel.
   Each picks tools from **tools/registry.py** (search, wikipedia, scraper,
   memory search) — every result sanitized at the registry checkpoint.
8. **quality_gate.py** scores the evidence; weak sub-topics detour through
   **replanner.py** once.
9. **analyst.py** → **synthesizer.py** → **writer.py** ⇄ **reviewer.py** produce
   the reviewed, cited report.
10. **memory_store.py** files the findings via **memory/semantic.py** and
    **memory/episodic.py**.
11. All along, **observability/tracing.py** was recording spans and
    **observability/cost.py** counting tokens — **cli.py** prints the report, the
    cost, and the trace id.

Every file in the project just appeared in one request. That's the whole system.

## 7. Suggested reading order (for a fresher)

1. `graph/state.py` — smallest file, defines the whiteboard.
2. `graph/nodes/planner.py` — the simplest "real" worker (prompt → form → state).
3. `graph/builder.py` — now the wiring will read like the diagram in its docstring.
4. `graph/nodes/researcher.py` — the agent loop (the most interesting file).
5. `llm/tiering.py` and `tools/registry.py` — the two "single doors."
6. Then anything else, in any order — and for each file, its **test** in
   `tests/unit/` shows exactly how it behaves (`test_routing.py` reads like
   documentation for builder.py's decisions).

> Deeper companions: [LLD.md](LLD.md) (exact contracts and algorithms),
> [patterns.md](patterns.md) (which industry pattern each file implements),
> [DECK_EXPLAINED.md](../DECK_EXPLAINED.md) (the concepts behind it all).
