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

## Phase 1 — Walking Skeleton *(arrives with sprint 01)*

Will add: `uv run research "your topic"` — first real end-to-end run
(requires `GOOGLE_API_KEY`, `TAVILY_API_KEY` in `.env`).

## Phase 2 — Core Patterns *(arrives with sprint 02)*

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

## Run the whole application (current state)

The pipeline does not exist yet — Phase 0 is scaffolding only. Today, "the app" is:

```bash
uv run research
```

This section is **updated every sprint**; by Phase 9 it will contain the full
`docker compose up` → submit topic → approve plan → stream progress → read report
walkthrough.
