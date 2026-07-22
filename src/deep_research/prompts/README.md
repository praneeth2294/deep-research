# Prompt Registry (procedural memory)

Every prompt in the system lives here as a versioned, code-reviewed Markdown
file — never as an inline string in Python. This directory *is* the deck's
"procedural memory": the system's knowledge of *how* to do its job.

Files arrive per phase: planner.md + researcher.md + writer.md (P1),
analyst.md + synthesizer.md + reviewer.md (P2), router.md (P3).

Convention: one file per node, loaded via `deep_research.prompts.load()`
(helper arrives in Phase 1).
