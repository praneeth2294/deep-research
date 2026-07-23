"""Contracts for research artifacts flowing between nodes."""

from typing import Literal

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
    `history` is the ReAct action trail (thought/action/observation lines) —
    the researcher's working memory during the run and our audit trail after.
    """

    sub_topic: SubTopic
    sources: list[Source] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)
    history: list[str] = Field(default_factory=list)


class ReactStep(BaseModel):
    """One decision of the researcher's ReAct loop (structured output).

    The action names are a Literal so the model physically cannot emit a tool
    that does not exist — schema as guardrail. Kept in sync with the registry.
    """

    reasoning: str = Field(min_length=5, description="Why this action is the right next step.")
    action: Literal["tavily_search", "wikipedia", "fetch_url", "finish"] = Field(
        description="The tool to call next, or 'finish' when evidence is sufficient."
    )
    action_input: str = Field(
        default="",
        description="The tool's input (search query or URL). Empty for 'finish'.",
    )
