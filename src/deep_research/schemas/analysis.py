"""Contracts for the analyst and synthesizer nodes."""

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One factual claim extracted from the sources."""

    statement: str = Field(min_length=10)
    confidence: Literal["high", "medium", "low"] = Field(
        description="high = multiple independent sources agree; low = single weak source."
    )
    source_ids: list[int] = Field(
        min_length=1,
        description="1-based numbers of the sources supporting this claim.",
    )


class ClaimSet(BaseModel):
    """All claims extracted by the analyst."""

    claims: list[Claim] = Field(min_length=1)


class SynthesisOutput(BaseModel):
    """The synthesizer's cross-referenced view of the evidence."""

    summary: str = Field(min_length=50, description="Coherent narrative of what the evidence says.")
    key_findings: list[str] = Field(min_length=1, description="The most important takeaways.")
    conflicts: list[str] = Field(
        default_factory=list,
        description="Points where sources disagree, each stating both positions.",
    )
