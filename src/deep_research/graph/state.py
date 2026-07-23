"""Shared graph state.

The state is the single "working memory" all nodes read from and write to.
Each node returns a *partial* update (only the keys it changed); LangGraph
merges updates into the state.

`sources` uses an `operator.add` reducer already: in Phase 2, parallel
researchers write sources concurrently and the reducer merges them instead of
one overwriting the other.
"""

import operator
from typing import Annotated, TypedDict

from deep_research.schemas.planner import SubTopic
from deep_research.schemas.research import Source


class ResearchState(TypedDict, total=False):
    """State flowing through the research graph."""

    topic: str
    sub_topics: list[SubTopic]
    sources: Annotated[list[Source], operator.add]
    report: str
