"""Contracts for research artifacts flowing between nodes."""

from pydantic import BaseModel, Field

from deep_research.schemas.planner import SubTopic


class Source(BaseModel):
    """One retrieved piece of evidence (search result / scraped page)."""

    url: str = Field(min_length=10)
    title: str = Field(default="(untitled)")
    snippet: str = Field(default="", description="Relevant text content from the source.")
    score: float | None = Field(
        default=None, description="Relevance score reported by the search tool, if any."
    )


class ResearchResult(BaseModel):
    """Everything one researcher run produced for one sub-topic.

    `attempt` tracks replanning: 1 = original plan, 2 = re-researched after the
    quality gate rejected attempt 1. The sub-topic title is the join key across
    attempts (the replanner revises the query but keeps the title).
    """

    sub_topic: SubTopic
    sources: list[Source] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)
