# Sprint 00 — Foundations

> **Phase:** 0 of 9 (see PROJECT_PLAN.md §6)
> **Goal:** boring, correct scaffolding — a repo where quality is enforced by machines, not discipline.
> **Status:** ✅ Complete — all checks green (ruff, mypy --strict, 16 unit tests, CLI smoke test).

---

## 1. What we built

| Artifact | What it is |
|---|---|
| Git repository (`main` branch) | Version control from commit #1 |
| `pyproject.toml` | Single source of truth: metadata, dependencies, ruff/mypy/pytest config |
| `.python-version` → 3.12 | Pinned interpreter, auto-installed by uv everywhere (laptop + CI) |
| `uv.lock` | Exact, hash-verified versions of every dependency |
| `src/deep_research/` package skeleton | 10 subpackages, each with a docstring stating its role + arrival phase |
| `config.py` | Typed settings via pydantic-settings; secrets as `SecretStr`; validated limits |
| `.env.example` | Every supported variable documented; the real `.env` is git-ignored |
| `cli.py` + `research` script | Placeholder entry point proving package + config wiring works |
| `tests/unit/` (16 tests) | Config defaults/overrides/secret-masking/validation + import smoke tests |
| `.github/workflows/ci.yml` | CI: format check → lint → type check → tests, on every push/PR |
| `.pre-commit-config.yaml` (installed) | Local gate: ruff + format + secrets detection + large-file block |
| `README.md` | Entry map to all project documents |
| `RUNBOOK.md` | Command reference (grows every sprint) |

## 2. Why each decision (the reasoning you should be able to defend)

**Why `uv` (not pip/poetry).** One tool does interpreter pinning, virtualenv, lockfile,
and script running — and it's what fast-moving Python teams adopted in 2024–25. The
lockfile (`uv.lock`) means CI and every future machine install *byte-identical*
dependencies: "works on my machine" is eliminated on day one.

**Why Python 3.12 (not 3.14 that's on your machine).** The LLM ecosystem
(LangGraph/LangChain, vector-DB clients) certifies against 3.12 today; the newest
interpreter is where you meet missing wheels and lagging support. Choosing the
*boring* version is the production-grade move. The pin travels with the repo, so uv
installs 3.12 automatically anywhere.

**Why `src/` layout (not a flat package).** With the package under `src/`, tests can
only import the *installed* package — you can't accidentally rely on files that
wouldn't ship. This is the standard packaging pitfall-avoider.

**Why ruff + mypy `--strict` from day 0.** Retrofitting types onto an untyped codebase
is miserable; starting strict costs nothing on an empty repo and pays forever. In an
LLM system especially, typed boundaries (Pydantic + mypy) are the difference between
"the model returned something weird and it propagated" and "the parse failed loudly at
the boundary." Ruff replaces flake8+isort+black with one fast tool.

**Why pydantic-settings for config.** Config is *validated at startup*: a typo'd
budget (`MAX_SESSION_BUDGET_USD=0`) crashes immediately with a clear error instead of
silently allowing unlimited spend. `SecretStr` means API keys can never leak via
`repr()`/logs — we have a test proving it.

**Why CI on an empty repo.** The Definition of Done for this phase is "CI green on an
empty-but-typed repo." Quality gates added *before* code exist enforce themselves on
every future line; gates added later meet resistance ("we'll fix CI next sprint").

**Why pre-commit locally too.** CI catches problems after push; pre-commit catches
them before commit (including `detect-private-key` — a last line of defense against
committing an API key). Fast feedback beats slow feedback.

**Why docstring-only skeleton packages (no empty `.py` node files).** Each subpackage
documents its role and *which phase fills it* — a map of the system. But we did NOT
create 20 empty module files: dead placeholder files rot, confuse imports, and give a
false sense of progress. Files appear in the phase that implements them.

## 3. Usage (what you can do right now)

```bash
uv sync            # create .venv with exact locked deps (auto-installs Python 3.12)
uv run research    # CLI smoke test -> "scaffolding OK"
uv run pytest      # 16 tests
uv run ruff check .
uv run mypy
uv run pre-commit run --all-files
```

Copy `.env.example` → `.env` and add keys when Phase 1 needs them (not required yet).

## 4. Things added beyond the plan (gaps I filled)

The plan's Phase 0 said "repo, tooling, config, skeleton, CI." While building, these
were missing and are now included:

1. **`uv.lock` committed** — the plan didn't call out committing the lockfile; without
   it, CI reproducibility is fiction. (`uv sync --locked` in CI fails if lock and
   `pyproject.toml` drift.)
2. **Secret-masking test** — proves `SecretStr` keys can't appear in `repr()`; this is
   the kind of test security reviews ask for.
3. **`detect-private-key` + large-file pre-commit hooks** — cheap insurance before any
   collaborator (or future you) commits a key or a model blob.
4. **`prompts/README.md`** — declares the prompt-registry convention (procedural
   memory) *before* the first prompt exists, so no prompt ever lands as an inline
   Python string.
5. **CLI entry point already wired** (`research` script) — proves packaging works
   end-to-end now, instead of debugging entry points in Phase 1 alongside real code.
6. **Placeholder-free discipline documented** — decision recorded here (see §2 last
   item) so future sprints follow it.

## 5. Definition of Done — checklist

- [x] `git init` on `main`; first commit contains working toolchain
- [x] `uv sync` reproduces the environment from lockfile
- [x] `ruff format --check`, `ruff check`, `mypy --strict` all pass
- [x] 16 unit tests pass (config + import smoke)
- [x] `uv run research` prints scaffold confirmation
- [x] Pre-commit hooks installed and passing
- [x] CI workflow ready (will run on first push to GitHub)
- [x] Sprint log (this file) + RUNBOOK.md written

## 6. Next sprint (Phase 1 — Walking Skeleton)

Thinnest end-to-end slice: `research "topic"` → planner (structured output) → one
researcher (single Tavily call) → writer → cited paragraph on stdout. First real LLM
calls, first prompt files, first schema contracts. Requires `GOOGLE_API_KEY` and
`TAVILY_API_KEY` in `.env`.
