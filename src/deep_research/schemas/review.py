"""Contracts for the reviewer node (Evaluator-Optimiser pattern)."""

from pydantic import BaseModel, Field


class ReviewVerdict(BaseModel):
    """The evaluator's judgment of a report draft."""

    score: int = Field(ge=0, le=10, description="Overall quality, 10 = publishable.")
    issues: list[str] = Field(
        default_factory=list,
        description="Concrete, actionable problems the writer must fix (empty if none).",
    )
