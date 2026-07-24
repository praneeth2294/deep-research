# ADR 002 — The quality gate is pure Python, not an LLM

**Status:** accepted (Sprint 02) · **Context:** after parallel research, something
must decide whether each sub-topic's evidence is good enough to analyze, or needs
replanning.

## Decision
The gate is deterministic code: 50% mean domain trust (curated weights, neutral 0.6
for unknown), 25% snippet substance, 25% source count; threshold configurable
(`GATE_QUALITY_THRESHOLD`, default 0.4). Zero LLM calls.

## Rationale
- **The decision is mechanical, not judgmental.** Domain reputation and snippet
  length don't need intelligence to evaluate.
- **Deterministic ⇒ testable and explainable.** We assert exact scores in unit tests
  and can decompose any verdict into its three components.
- **Cost.** The gate runs on every researcher result including replans — LLM-scoring
  it would add N calls per run for no accuracy gain.

The complementary rule: decisions that DO need judgment get the *cheapest capable*
LLM (the router, ADR 003). Heuristics for mechanical decisions, cheap models for
judgment calls, strong models for generation.

## Consequences
- The domain-trust table is curated and therefore incomplete — unknown domains score
  neutral rather than being judged. Acceptable: the gate's job is catching *junk*,
  not ranking excellence.
- Threshold tuning is an operator knob, with the failure mode being extra replans
  (bounded by construction), not runaway loops.
