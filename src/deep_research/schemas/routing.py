"""Contract for the router node (LLM-based Routing pattern)."""

from typing import Literal

from pydantic import BaseModel, Field

Route = Literal["simple_lookup", "deep_research", "comparison"]


class RouteDecision(BaseModel):
    """Triage verdict for an incoming topic."""

    route: Route = Field(
        description=(
            "simple_lookup: single fact/definition answerable with one search. "
            "comparison: 'X vs Y' style question. "
            "deep_research: multi-faceted topic needing decomposition."
        )
    )
    reason: str = Field(min_length=5, description="One sentence justifying the route.")
