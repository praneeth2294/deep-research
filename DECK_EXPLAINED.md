# The Agentic AI Deck, Explained Simply

> A complete, plain-English walkthrough of `Agenticai-1.pdf` (SwirlAI — "Sprint 2 Info Review",
> 115 slides). Every diagram in the deck is covered here, in the deck's own order.
> Where useful, each section ends with **"In our project"** — where the concept lives in the
> Deep Research Agent we're building (see PROJECT_PLAN.md).

---

## Table of Contents

0. [Before the patterns: RAG (slides 2–3)](#0-before-the-patterns-rag)
1. [Part 1 — Patterns for Building Agentic Systems (slides 4–44)](#part-1--patterns-for-building-agentic-systems)
   - 1.1 Augmented LLM
   - 1.2 Prompt Chaining
   - 1.3 Routing
   - 1.4 Parallelisation
   - 1.5 Orchestrator-Workers
   - 1.6 Evaluator-Optimiser Loop
   - 1.7 Agent
2. [Part 2 — AI Agents in Depth (slides 45–114)](#part-2--ai-agents-in-depth)
   - 2.1 RAG pipeline anatomy
   - 2.2 Agent anatomy (Core, Memory, Planning, Tools)
   - 2.3 Tool Use
   - 2.4 Memory (working, context management, episodic, semantic, procedural)
   - 2.5 Planning (Chain of Thought, reasoning paths)
   - 2.6 Reflection
   - 2.7 ReAct Agents
   - 2.8 Observability
3. [The big picture — how it all fits together](#3-the-big-picture)

---

## 0. Before the patterns: RAG

*(slides 2–3 — shown before the patterns section as background knowledge)*

### 0.1 What RAG is (slide 2)

**The problem:** an LLM only knows what it was trained on. Ask it about *your* company's
documents, or anything recent, and it will either not know — or worse, confidently make
something up (hallucinate).

**The fix — RAG (Retrieval Augmented Generation):** before asking the LLM, go *fetch* the
relevant information and paste it into the prompt. The LLM then answers **using the
provided context** instead of its memory.

The slide shows the flow:

1. User types a question in a chat interface → a **Query**.
2. The query is used to search external sources (documents, databases, websites).
3. The **retrieved context** is placed into the LLM's **context window** (its "desk space"),
   together with the **system prompt** and the **user query**.
4. The LLM reads all of it and produces the **answer**.

> **Analogy:** RAG is an open-book exam. Instead of forcing the student (LLM) to memorize
> everything, you hand them the right pages of the textbook and say "answer using these."

### 0.2 How retrieval actually works — hybrid search (slide 3)

The deck splits retrieval into two stages:

**Preprocessing (done once, ahead of time):**
- Take all your documents.
- Path A (semantic): run each piece through an **embedding model** → store the vectors in a
  **vector database**. This captures *meaning* — "car" and "automobile" land close together.
- Path B (keyword): index the same documents using **TF-IDF / BM25 / exact match** —
  classic keyword search. This captures *exact terms* — product codes, names, IDs.

**Retrieval (at question time):**
- The query hits **both** indexes.
- Results from both are merged by **Rank Fusion** (combine the two ranked lists into one,
  keep the top N).
- A **Reranker** (a more careful, more expensive model) reorders those N and keeps the
  **top K** best chunks, which go to the LLM.

> **Why both?** Semantic search understands paraphrasing but can miss exact keywords;
> keyword search nails exact terms but doesn't understand meaning. Production systems use
> **hybrid search** because each covers the other's blind spot. The rerank step exists
> because the first pass is fast-but-rough; reranking is slow-but-accurate, so you only
> apply it to the shortlist.

**In our project:** the semantic-memory tool (`tools/semantic_search.py`) is a RAG
retriever over previously scraped sources; hybrid + rerank is a documented upgrade path.

---

# Part 1 — Patterns for Building Agentic Systems

*(slides 4–44. These are the 7 building-block patterns — the same taxonomy Anthropic uses
in "Building Effective Agents." Diagram legend used throughout: a brain icon = one LLM
call; a purple "Text" box = plain application logic, i.e. normal code, no LLM.)*

A key idea runs through this whole part: **a "workflow" is a fixed path you programmed; an
"agent" chooses its own path.** Patterns 1–6 are workflows (predictable, testable, cheaper).
Pattern 7 is the true agent (flexible, but harder to control). Production systems use the
simplest pattern that solves the problem — usually a workflow, not a free-running agent.

---

## 1.1 Augmented LLM (slides 5–10)

**The diagram:** `In → [LLM] → Out`, where the LLM is connected to three attachments:
**Retrieval**, **Tools**, **Memory**.

**In simple words:** the basic unit of every agentic system is not a bare LLM — it's an
LLM **augmented** with:
- **Retrieval** — can look things up (RAG, above).
- **Tools** — can *do* things (call APIs, search the web, run code, query a database).
- **Memory** — can remember (past conversation turns, stored knowledge).

Every other pattern in the deck is built by connecting these augmented blocks together.

> **Analogy:** a bare LLM is a very smart person locked in an empty room. The augmented LLM
> is the same person with a phone (tools), a library card (retrieval), and a notebook (memory).

**In our project:** every node is an augmented LLM; the purest example is the
`simple_answer` short path (one LLM + retrieval + a search tool).

---

## 1.2 Prompt Chaining (slides 11–15)

**The diagram:** `In → LLM 1 → Output 1 → Gate → (pass) → LLM 2 → Output 2 → LLM 3 → Out`,
and the Gate's fail branch: `→ Exit`.

**In simple words:** break a big task into **fixed steps in a fixed order**, one LLM call
per step, where each step's output feeds the next. Between steps you can insert a **gate**
— plain code (not an LLM) that checks "is this output good enough to continue?" If the
check fails, exit early instead of wasting money on the remaining steps.

**When to use:** the task decomposes cleanly into sequential subtasks, and you'd rather
make three small, reliable calls than one big, unreliable one. Each small call is easier
to prompt, easier to test, and easier to debug.

> **Example:** write an outline (LLM 1) → check the outline has 3–5 sections (gate, plain
> Python) → write the article from the outline (LLM 2) → translate it (LLM 3).

**In our project:** Analyst → Synthesizer → Writer is a chain; the Quality Gate is
exactly the deck's gate (pure Python, fails → replan instead of continuing).

---

## 1.3 Routing (slides 16–20)

**The diagram:** `In → Router (LLM) →` one of three different LLMs `→ Out`. Solid arrow =
the path taken; dashed arrows = the paths not taken this time.

**In simple words:** first **classify** the input, then send it to the handler that is
*specialized* for that category. The router is usually a small, cheap LLM call; each
handler has its own prompt, its own tools, and can even be a different model.

**Why it matters (two reasons):**
1. **Quality** — a prompt tuned for one job beats one mega-prompt trying to handle
   everything ("separation of concerns").
2. **Cost** — easy questions go to a cheap model/path; only hard questions get the
   expensive treatment.

> **Example:** customer message arrives → router decides: refund request / technical bug /
> general question → each goes to a different specialized handler.

**In our project:** the Router node triages every topic into `simple_lookup`
(one cheap call, done) vs `deep_research` / `comparison` (full pipeline). This is the
single biggest cost lever in the system.

---

## 1.4 Parallelisation (slides 21–26)

**The diagram:** `In →` three LLMs *at the same time* `→ Aggregator → Out`. The
aggregator is application logic (code), not an LLM.

**In simple words:** when subtasks **don't depend on each other**, don't run them one by
one — run them **simultaneously** and then combine the results. Two flavors:
- **Sectioning:** split the work ("research topic A, B, C"), each worker does a part.
- **Voting:** give the *same* task to several workers and compare/majority-vote the answers
  (useful for reliability: "three reviewers must agree this code is safe").

**What you gain:** wall-clock speed (3 tasks in the time of 1) and/or confidence (voting).
**What it costs:** more tokens — you're making N calls instead of 1.

**In our project:** the Send() fan-out that runs one researcher per sub-topic in
parallel; results are merged by a state reducer (`operator.add`) and later synthesized.

---

## 1.5 Orchestrator-Workers (slides 27–32)

**The diagram:** `In → Orchestrator (LLM) → ` several worker LLMs (dashed arrows — chosen
at runtime) ` → Synthesizer (LLM) → Out`.

**In simple words:** like Parallelisation, but the split is **not known in advance**. An
**orchestrator** LLM looks at the task and *decides on the fly* how many workers to spawn
and what each should do. A **synthesizer** LLM merges the workers' outputs into one
coherent result.

**Difference from 1.4 in one line:** Parallelisation = *you* hard-code the split;
Orchestrator-Workers = *the LLM* decides the split at runtime.

> **Example:** "Fix this bug" → orchestrator reads the codebase and decides which files
> need changes (you can't know this in advance) → one worker per file → synthesizer
> combines the edits into a single patch.

**In our project:** the Planner reads the topic and *decides* the 1–3 sub-topics
(orchestrator); researchers are the workers; the Synthesizer node merges and
cross-references their findings.

---

## 1.6 Evaluator-Optimiser Loop (slides 33–38)

**The diagram:** `In → Generator (LLM) → Solution → Evaluator (LLM)` — then either
`Accepted → Out`, or `Rejected + Feedback →` back to the Generator, which tries again.

**In simple words:** one LLM **produces**, another LLM **judges**. If the judge rejects,
it sends *specific feedback* back, and the producer revises. Loop until accepted (or until
a maximum number of rounds — always cap it, or a picky evaluator can loop forever).

**Why two separate roles?** The same trick as human writing: it's much easier to *critique*
a draft than to write it perfectly on the first try. Splitting "write" and "judge" into
two calls with two prompts measurably improves quality.

**When it works best:** when you can state clear evaluation criteria ("has citations,
under 500 words, no unsupported claims") — then the evaluator has something concrete to
check against.

**In our project:** Writer ↔ Reviewer (score 0–10, structured issue list, max 2
revisions). The Quality-Gate → Replanner loop is a second, cheaper instance: a *code*
evaluator driving an *LLM* optimiser.

---

## 1.7 Agent (slides 39–44)

**The diagram:** `Intent ↔ Agent (LLM)`; the agent takes an **Action** on the
**Environment**; the environment returns **Feedback** to the agent; this loops; when the
goal is reached → **Stop**.

**In simple words:** the real "agent" pattern. There is **no pre-programmed path**. The
LLM is given a *goal* (intent), a set of tools, and a loop:

1. Look at the goal and everything observed so far.
2. **Decide** the next action itself.
3. Do it (call a tool) — this touches the **environment** (web, files, APIs, databases).
4. **Observe** what came back (results, errors).
5. Repeat until it judges the goal is met (or a step/cost limit is hit) → stop.

**The trade-off, honestly:** maximum flexibility, but you give up predictability — the
agent may take a bad path, loop, or burn tokens. That's why production agents always ship
with **guardrails**: iteration caps, budget caps, restricted toolsets, and checkpoints
where a human can intervene. And that's why the deck's ordering matters: *use patterns
1–6 when you can; use 7 when you must.*

**In our project:** each Researcher is exactly this loop (bounded at N iterations),
choosing among Tavily / scraper / Wikipedia / semantic-memory per step.

---

# Part 2 — AI Agents in Depth

*(slides 45–114 — inside the components that make agents work)*

## 2.1 RAG pipeline anatomy (slide 46)

Before diving into agents, the deck shows the complete RAG pipeline with every moving part
labeled. Two halves:

**Retrieval side:**
- **F) Chunking** — split documents (Notion, Confluence, PDFs, internal docs) into
  bite-size pieces. Chunk size matters: too big = noisy, too small = context-less.
- **C) Embedding** — turn each chunk into a vector (list of numbers) capturing its meaning.
- **D) Vector Database** — store vectors + build a **vector index** for fast lookup.
- **E) Search** — embed the user's query the same way, find nearest stored vectors using
  **ANN (Approximate Nearest Neighbour)** search — "approximate" because exact search over
  millions of vectors is too slow, and near-enough is fine.
- **G) Heuristics** — practical filters applied to results (recency, source trust,
  deduplication, access rights).

**Generation side:**
- **B) Prompt Engineering** — the retrieved chunks are placed into a prompt that
  *constrains* the model: *"Answer the Query. Only use Context to construct the answer."*
  That one sentence is the anti-hallucination mechanism.
- **A) LLM** — generates the answer from that prompt.

> **Key takeaway:** RAG quality is mostly decided *before* the LLM — by chunking,
> embedding quality, search, and heuristics. If retrieval brings back garbage, no prompt
> can save the answer ("garbage in, garbage out").

---

## 2.2 Agent anatomy (slides 47–51)

**The diagram:** a **Core** box in the middle containing the **LLM** plus an
**Orchestrator/Controller**, connected to three satellites: **Memory** (short-term ↔
long-term), **Planning**, and **Tools**.

**In simple words:** every agent = four parts.

| Part | Human analogy | What it does |
|---|---|---|
| **Core (LLM + controller)** | Brain + nervous system | The LLM thinks; the controller is *code* around it that runs the loop, calls tools, enforces limits |
| **Memory** | Short-term + long-term memory | What's in the current conversation vs what's stored across sessions |
| **Planning** | Thinking before doing | Break the goal into steps, revise as reality pushes back |
| **Tools** | Hands | Act on the world: search, APIs, code, databases |

An important nuance the diagram encodes: the **controller is not the LLM**. The LLM
produces text/decisions; deterministic *code* around it executes tools, tracks state, and
enforces stop conditions. Production reliability lives in that code layer.

---

## 2.3 Tool Use (slides 52–59)

**The diagram (6 numbered steps):**

1. **User query** arrives at the agent.
2. The agent holds **function definitions** (machine-readable descriptions of each tool:
   name, what it does, what parameters it takes) — kept in a **Tool Registry** (shown with
   a GitHub icon: tool definitions are *code artifacts*, versioned and reviewed).
3. Query + function definitions go to the **LLM**, which decides *which* tool to call and
   *with what arguments*. **The LLM does not execute anything** — it just outputs the
   intent, e.g. `search(query="EV market size 2025")`.
4. **The application code** actually executes that call against the real world — data
   stack, database, web. (This split is the safety boundary: your code can validate,
   sandbox, or refuse any call before running it.)
5. Results go back to the **LLM**, which either composes the final response or decides it
   needs another tool call.
6. The **answer** returns to the user.

> **Key takeaway:** "the LLM proposes, the runtime disposes." The model chooses; your
> code executes. Everything dangerous is controllable at step 4.

**In our project:** `tools/registry.py` + one module per tool; researchers do steps 2–5
in a loop.

---

## 2.4 Memory (slides 60–80)

The deck's longest section — four distinct diagrams.

### 2.4.1 Working memory = the prompt itself (slides 61–66)

**The diagram:** three snapshots of the same conversation growing over time. Each prompt
sent to the LLM contains: **system prompt** (identity: "You are a helpful assistant…",
available tools, external context) + **previous interactions** (the list of Human/Assistant
turns so far) + the **new human message** → model produces the next assistant reply.

**In simple words:** an LLM has **no memory between calls**. Zero. The illusion of a
conversation exists only because *your application* re-sends the entire history inside
every single prompt. "Short-term memory" is literally just text you place in the prompt.

> This is the most important demystifying fact in the whole deck: memory is not a model
> feature — it's an engineering feature *you* build.

### 2.4.2 Context-window management (slides 67–70)

**The problem:** the context window (max prompt size) is finite, and long prompts are
slow, expensive, and distracting for the model. A long conversation eventually won't fit.

**The diagram shows the standard recipe:**
- **Keep Top N** — the most recent turns stay verbatim (they matter most).
- **Compress the remaining** — older turns are summarized by an LLM into a short digest
  that stays in the prompt.
- **Offload** — the full, uncompressed history is written to a **database**, so nothing is
  truly lost — it can be retrieved later if needed.

> **Analogy:** desk (recent papers, as-is) + a one-page summary of everything filed +
> the filing cabinet (database) holding the originals.

### 2.4.3 Episodic memory (slides 71–74)

**What it is:** memory of **experiences** — past conversations/sessions.

**The diagram (3 steps):**
1. **Store** conversation history in a vector database (embed the turns).
2. When a new query arrives, **retrieve** relevant past conversations by similarity search.
3. **Inject** them into working memory (the prompt).

Result: "as we discussed last week…" actually works — across sessions.

### 2.4.4 Semantic memory (slides 75–78)

**What it is:** memory of **facts and knowledge** — not conversations. The private
knowledge base (Notion, Confluence, PDFs, documentation) plus **grounding context**,
embedded into the same vector-database machinery.

**The diagram (3 steps):** store private knowledge → store grounding context → inject
relevant knowledge into working memory at question time.

**Punchline the deck is making:** *RAG and agent memory are the same mechanism* — RAG is
semantic memory viewed from the agent's perspective.

### 2.4.5 The complete memory map (slides 79–80)

The final diagram assembles everything and adds the third long-term type:

- **Short-term (working) memory** — the prompt: prompt structure, available tools,
  additional context, and the **reasoning-and-action history** of the current task.
- **Long-term, episodic** — past interactions (vector DB).
- **Long-term, semantic** — knowledge (vector DB + grounding context).
- **Long-term, procedural** — **how to do things**: the **Prompt Registry** and **Tool
  Registry**, shown with a GitHub icon. Your prompts and tool definitions *are* memory —
  stored as versioned code, not as text somebody retypes.
- The **Core (LLM + controller)** orchestrates: pull from long-term → assemble working
  memory → call the model → write new experience back.

| Memory type | Human analogy | In practice |
|---|---|---|
| Working | What's in your head right now | The assembled prompt |
| Episodic | "I remember doing this" | Past sessions, embedded + retrieved |
| Semantic | "I know this fact" | Knowledge base via RAG |
| Procedural | "I know how to ride a bike" | Versioned prompts + tool definitions |

**In our project:** checkpointer = working/durable; `memory/episodic.py`,
`memory/semantic.py`; `prompts/` + `tools/registry.py` = procedural.

---

## 2.5 Planning (slides 81–95)

### 2.5.1 Chain of Thought (slides 82–83)

**The diagram:** `LLM → thought → thought → thought → … → answer`.

**In simple words:** instead of jumping from question to answer in one hop, the model
produces **intermediate reasoning steps**. Asking a model to "think step by step"
measurably improves results on multi-step problems — each thought conditions the next,
like showing your work in math.

### 2.5.2 Reasoning paths + finetuning (slides 84–95)

**The diagram:** the LLM explores **multiple chains of thought in parallel** — several
dotted paths of thoughts, each ending in a (possibly different) answer. One answer is
circled green: the **desired answer**. A **"Finetune"** arrow loops from that desired
outcome back to the LLM.

**In simple words, two ideas:**
1. **Different reasoning paths → different answers.** Sampling several paths and comparing
   where they land (majority vote = "self-consistency") is more reliable than trusting a
   single chain.
2. **The good paths are training data.** Collect the reasoning paths that led to desired
   answers and **fine-tune** the model on them — teaching it to reason well by default.
   (This is essentially how modern "reasoning models" are trained.)

**In our project:** planning shows up as the Planner/Replanner nodes; CoT happens inside
every structured LLM call. Fine-tuning is out of scope (and worth saying so — knowing
what *not* to build is a senior skill).

---

## 2.6 Reflection (slides 96–102)

**The diagram:** user query → LLM produces a **Plan** → *another LLM pass revises it* →
**Revised Plan** → execute with **Tools** → results come back → more LLM passes reflect
again → … → **Improved Answer**. Dotted boxes mark each **Reflection Step**.

**In simple words:** after (or before) acting, the system pauses and asks itself:
*"Did that actually work? Is the plan still right? What should change?"* — and revises
accordingly. It's the Evaluator-Optimiser idea applied **inside** an agent's own loop:
- Reflect on the **plan** before spending money executing it.
- Reflect on **tool results** after each step ("did this search actually answer the
  sub-question, or do I need a different query?").

> **Why it matters:** the first plan is a guess made before touching reality. Reality
> pushes back (searches return junk, pages fail to load). Agents that never reflect
> execute a broken plan to the bitter end; agents that reflect course-correct.

**In our project:** the Replanner (reflect on gate failure), the Reviewer loop (reflect
on the draft), and the researcher's per-step observation of tool results.

---

## 2.7 ReAct Agents (slides 103–108)

**The name:** **Re**asoning + **Act**ing — the loop pattern that operationalizes
everything above. **The diagram (numbered):**

1. **The prompt** given to the LLM contains: the goal ("Solve the User Query intent"),
   **Available Tools: […]**, an instruction to output its next step in a fixed format —
   `{Next action and reasoning: "", Action inputs and result: ""}` — and the
   **reasoning-and-action history** so far: `[ … ]`.
2. **Analyse Reasoning** — an LLM pass asks: *"Is the user's intent solved yet?"*
   - **Yes** → produce the **Answer** → back to the chat interface. Done.
   - **No** → continue:
3. The agent LLM picks the next **tool** and calls it (data stack / database / web).
4. The result is **appended to the history** in the prompt.
5. **Repeat the loop, up to N times** — the hard cap is drawn on the slide itself;
   never ship an unbounded loop.

**In simple words:** the agent alternates *think → act → observe → think…*, accumulating a
visible trail of thoughts, actions, and observations, until it judges the goal met (or
runs out of allowed iterations).

> **Why the history matters twice:** (a) the model conditions on everything it has learned
> so far — that's what makes step 7 smarter than step 1; (b) humans can read the trail
> afterwards and see *why* the agent did what it did — built-in explainability.

**In our project:** `researcher.py` is a bounded ReAct loop, verbatim.

---

## 2.8 Observability (slides 109–114)

### 2.8.1 Tracing a RAG system (slides 110–111)

**The diagram:** the full RAG pipeline on the left; on the right, a **timeline**:
- **Trace** (dark bar) — one user request, end to end.
- **Spans** (small bars) — each individual step inside it: embedding call, vector search,
  prompt assembly, LLM call, answer building — each with its own duration.
- The user's **👍/👎 feedback** is linked *to the trace*.

**In simple words:** log every step of every request with timing, so any answer can be
opened up and inspected step by step later.

### 2.8.2 Tracing an agent (slides 112–114)

The same instrumentation applied to the full agent: every memory access, every planning
step, every tool call in the ReAct loop becomes a span; red **"?"** marks on the timeline
stand for the questions you can now answer: *Where did the time go? What did this run
cost? Which step failed?*

**Why the deck ends here (and why it's the most "production" section of all):** agents
are non-deterministic — the same question can take a different path tomorrow. You cannot
fully test that in advance; you **must** be able to inspect what actually happened.
- Traces let you **debug** ("why was this answer wrong?" → open the trace → see the bad
  retrieval or wrong tool choice).
- Spans expose **cost and latency** per step (LLM calls dominate both).
- **User feedback tied to traces** turns 👍/👎 into a dataset: collect the 👎 traces, find
  the failing step, fix the prompt/tool, and re-test — the improvement flywheel.

**In our project:** Langfuse tracing on every node and tool call, cost rollups per
session, and `POST /feedback` attaching 👍/👎 to the trace id.

---

# 3. The Big Picture

One paragraph to hold the whole deck:

> Start with **RAG** — an LLM that can look things up before answering. Make the LLM
> **augmented** (retrieval + tools + memory) — that's the basic building block. Compose
> blocks with the six **workflow patterns** — chain them, route between them, run them in
> parallel, let an orchestrator split work dynamically, and let an evaluator loop reject
> bad outputs. When a fixed path isn't enough, promote to a true **agent**: a goal-driven
> **ReAct loop** (think → act → observe → repeat, capped at N) with a **controller** in
> code around it. Give it **four memories** — working (the prompt you assemble), episodic
> (past sessions), semantic (knowledge/RAG), procedural (versioned prompts and tools).
> Let it **plan** with chains of thought and **reflect** to revise plans against reality.
> And because such a system is non-deterministic, wrap every request in **traces and
> spans**, tie **user feedback** to them, and use that data to debug and improve. That —
> composed patterns, engineered memory, bounded autonomy, full observability — is a
> production agentic system.

### Deck → project map (quick reference)

| Deck section | Slides | Our project component |
|---|---|---|
| RAG + hybrid retrieval | 2–3 | `tools/semantic_search.py` (+ documented hybrid upgrade path) |
| Augmented LLM | 5–10 | `simple_answer.py`; every node |
| Prompt Chaining + Gate | 11–15 | Analyst → Synthesizer → Writer; `quality_gate.py` |
| Routing | 16–20 | `router.py` (LLM triage) |
| Parallelisation | 21–26 | Send() fan-out + `operator.add` reducers |
| Orchestrator-Workers | 27–32 | `planner.py` → researchers → `synthesizer.py` |
| Evaluator-Optimiser | 33–38 | `reviewer.py` ↔ `writer.py`; gate → `replanner.py` |
| Agent loop | 39–44 | `researcher.py` (bounded) |
| RAG anatomy | 46 | chunking/embedding/ANN inside `memory/semantic.py` |
| Agent anatomy | 47–51 | Core = graph + nodes; satellites = `memory/`, `tools/`, planning nodes |
| Tool use + registry | 52–59 | `tools/registry.py` |
| Working memory / context mgmt | 61–70 | graph state + checkpointer; summarization on long histories |
| Episodic / semantic / procedural | 71–80 | `memory/episodic.py`, `memory/semantic.py`, `prompts/` + registry |
| Planning / CoT | 81–95 | `planner.py`, `replanner.py` |
| Reflection | 96–102 | replanner + reviewer loops, researcher observations |
| ReAct | 103–108 | `researcher.py` |
| Observability | 109–114 | `observability/` + feedback endpoint |
