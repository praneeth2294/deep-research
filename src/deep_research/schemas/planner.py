"""Contracts for the planner node (Orchestrator pattern).

The planner LLM is *forced* to return exactly this shape via
`with_structured_output(PlannerOutput)` — no free-text parsing anywhere.
"""

from pydantic import BaseModel, Field


class SubTopic(BaseModel):
    """One researchable slice of the user's topic."""

    title: str = Field(min_length=3, description="Short name of the sub-topic.")
    search_query: str = Field(
        min_length=3,
        description="The exact web-search query a researcher should run for this sub-topic.",
    )
    rationale: str = Field(
        min_length=3,
        description="Why this sub-topic is needed to answer the user's overall question.",
    )


class PlannerOutput(BaseModel):
    """The research plan: 1-3 sub-topics that together cover the topic."""

    sub_topics: list[SubTopic] = Field(min_length=1, max_length=3)
