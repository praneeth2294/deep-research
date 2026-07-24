# ADR 003 — Two model tiers with fallback chains, composed as layered runnables

**Status:** accepted (Sprint 03, revised Sprint 05) · **Context:** ~10 LLM calls per
deep run with wildly different difficulty; free-tier quotas and model retirements
are routine failures, not edge cases.

## Decision
Every model access goes through `structured_llm(schema, tier=...)` / `text_llm(tier=...)`,
which compose (outside-in): **budget gate → fallback chain → per-model retries +
shared rate limiter**. Tiers: `cheap` (flash-lite class — router, planner,
replanner, reviewer, ReAct steps) and `strong` (flash class — analyst, synthesizer,
writer). Fallback chains are env-configured and cross model families.

## Rationale
- **Ordering is load-bearing.** Budget must gate before any provider (including
  fallbacks) can spend; retries handle transient blips *inside* a model; fallbacks
  handle persistent failure (429/5xx/404 retirement) *across* models.
- **One shared token bucket** across all clients — parallel researchers collectively
  respect the provider RPM instead of multiplying it.
- **Measured effect:** trivial queries cost 7.6% of a deep run; the tier split is
  visible in per-model token breakdowns.

## Consequences
- Learned live (Sprint 04): fallbacks only help across **independent failure
  domains** — two models sharing one free-tier pool exhaust together. Hence
  cross-family fallbacks and the lite/flash split (Sprint 05).
- The price table for budget guarding is approximate by design (guarding ≠ billing).
