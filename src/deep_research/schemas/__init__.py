"""Pydantic contracts for every LLM boundary.

Every LLM call in the system goes through `with_structured_output` against a
model defined here. No free-text parsing anywhere.
Modules arrive per phase: planner (P1), research (P1), analysis (P2),
review (P2), routing (P3).
"""
