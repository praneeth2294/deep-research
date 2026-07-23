# RUNBOOK — deep-research

Every command needed to set up, verify, and run this project — phase by phase.
A new section is appended at the end of each sprint. The final section ("Run the
whole application") always reflects the *current* way to run the app end-to-end.

> **Shell note:** commands work in both PowerShell and Git Bash on Windows
> (and unchanged on macOS/Linux). Differences are called out where they exist.

---

## Prerequisites (one-time, any machine)

| Tool | Install | Verify |
|---|---|---|
| git | https://git-scm.com | `git --version` |
| uv | https://docs.astral.sh/uv (or `winget install astral-sh.uv`) | `uv --version` |

Python itself is **not** a prerequisite — uv reads `.python-version` and installs
Python 3.12 automatically on first `uv sync`.

---

## Phase 0 — Foundations

### First-time setup after cloning

```bash
uv sync
```

```bash
uv run pre-commit install
```

```bash
cp .env.example .env
```

(PowerShell: `Copy-Item .env.example .env`) — then edit `.env` and fill keys.
Not required until Phase 1; Phase 0 runs without any keys.

### Verify everything (the same gates CI runs)

```bash
uv run ruff format --check .
```

```bash
uv run ruff check .
```

```bash
uv run mypy
```

```bash
uv run pytest
```

### Smoke-test the CLI

```bash
uv run research
```

Expected output: `deep-research v0.1.0 — scaffolding OK (environment: dev)`

### Useful during development

```bash
uv run ruff format .
```

```bash
uv run ruff check --fix .
```

```bash
uv run pre-commit run --all-files
```

```bash
uv add <package>
```

(adds a dependency and updates `uv.lock`; use `uv add --group dev <package>` for dev tools)

---

## Phase 1 — Walking Skeleton

Requires `GOOGLE_API_KEY` and `TAVILY_API_KEY` in `.env` (see Phase 0 setup).

### Run a research topic (full pipeline: plan → search → cited report)

```bash
uv run research "impact of the EU AI Act on startups"
```

### Config smoke check (shows whether keys are detected)

```bash
uv run research
```

### Tests

```bash
uv run pytest tests/unit
```

(offline, free, runs in CI)

```bash
uv run pytest tests/integration -s
```

(real Gemini + Tavily calls — costs a few API requests; auto-skips if keys missing)

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` | Corporate TLS proxy (Zscaler etc.) | Already handled by `setup_tls()`; if it recurs in new entry points, call `deep_research.net.setup_tls()` first |
| `404 model ... not available` | Google retired the model name | List available models: see command below; update `CHEAP_MODEL` in `.env` |
| `503 high demand` | Model overloaded | Transient — retry; or switch `CHEAP_MODEL` to another flash model |
| `429 RESOURCE_EXHAUSTED` on pro models | Free-tier keys have no pro quota | Keep a flash model in `STRONG_MODEL`, or upgrade to a paid key |
| Garbled characters in console | Legacy Windows codepage | Already handled (CLI forces UTF-8) |

List models your key can use:

```bash
uv run python -c "from deep_research.net import setup_tls; setup_tls(); from deep_research.config import get_settings; from google import genai; [print(m.name) for m in genai.Client(api_key=get_settings().google_api_key.get_secret_value()).models.list() if 'generateContent' in (m.supported_actions or [])]"
```

## Phase 2 — Core Patterns

Same entry point as Phase 1 — the pipeline underneath got the full pattern set
(parallel researchers, quality gate, replanner, analyst → synthesizer, reviewer loop):

```bash
uv run research "Compare Qdrant and Chroma for production vector search"
```

The CLI now also prints: which sub-topics were **replanned** after the quality
gate, and the **review score** with the number of revisions.

### Run the offline full-graph flow test (no API keys, no cost)

```bash
uv run pytest tests/unit/test_graph_flow.py -v
```

This forces the gate-failure path (junk sources → replanner → attempt-2 research)
and the revision path (reviewer rejects → writer revises) with faked LLMs/tools.

### Tune the quality knobs (optional, via .env)

| Variable | Default | Effect |
|---|---|---|
| `GATE_QUALITY_THRESHOLD` | `0.4` | Raise → more replanning, higher evidence bar |
| `REVIEWER_PASS_SCORE` | `7` | Raise → stricter reviewer, more revisions |
| `MAX_WRITER_REVISIONS` | `2` | Hard cap on the evaluator-optimiser loop |

## Phase 3 — Router + Model Tiering *(arrives with sprint 03)*

## Phase 4 — ReAct Researchers + Tool Registry *(arrives with sprint 04)*

## Phase 5 — Memory *(arrives with sprint 05)*

Will add: `docker compose up qdrant` and checkpoint/resume commands.

## Phase 6 — Guardrails *(arrives with sprint 06)*

## Phase 7 — HITL + API *(arrives with sprint 07)*

Will add: `uv run uvicorn deep_research.api.app:app` and the HTTP flow
(submit → approve plan → stream → report).

## Phase 8 — Observability + Evals *(arrives with sprint 08)*

Will add: `docker compose up langfuse` and `uv run pytest tests/evals`.

## Phase 9 — Packaging *(arrives with sprint 09)*

Will add: `docker compose up` (full stack) and the one-command demo.

---

## Run the whole application (current state: Phase 2)

1. One-time setup (if not done): `uv sync`, copy `.env.example` → `.env`, fill
   `GOOGLE_API_KEY` + `TAVILY_API_KEY`.
2. Run:

```bash
uv run research "your research topic here"
```

What happens: **planner** decomposes the topic into 1–3 sub-topics → **researchers
run in parallel** (one per sub-topic, Send() fan-out) → **quality gate** (pure
Python) scores each result's evidence; failing sub-topics go to the **replanner**
for a revised query and one bounded re-research → **analyst** dedupes sources and
extracts claims (with confidence + source numbers) → **synthesizer** cross-references
claims and detects conflicts → **writer** drafts the cited report → **reviewer**
scores it 0–10; below 7 it goes back to the writer with concrete issues (max 2
revisions) → final report + sources printed.

This section is **updated every sprint**; by Phase 9 it will contain the full
`docker compose up` → submit topic → approve plan → stream progress → read report
walkthrough.
