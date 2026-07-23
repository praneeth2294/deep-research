"""Contracts for research artifacts flowing between nodes."""

from pydantic import BaseModel, Field


class Source(BaseModel):
    """One retrieved piece of evidence (search result / scraped page)."""

    url: str = Field(min_length=10)
    title: str = Field(default="(untitled)")
    snippet: str = Field(default="", description="Relevant text content from the source.")
    score: float | None = Field(
        default=None, description="Relevance score reported by the search tool, if any."
    )
