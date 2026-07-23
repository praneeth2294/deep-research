"""Shared graph state.

The state is the single "working memory" all nodes read from and write to.
Each node returns a *partial* update (only the keys it changed); LangGraph
merges updates into the state.

`research_results` carries an `operator.add` reducer: parallel researchers
(Send() fan-out) append concurrently and LangGraph concatenates their updates
instead of letting one overwrite the other. All other keys are last-write-wins.
"""

import operator
from typing import Annotated, TypedDict

from deep_research.schemas.analysis import Claim, SynthesisOutput
from deep_research.schemas.planner import SubTopic
from deep_research.schemas.research import ResearchResult, Source
from deep_research.schemas.review import ReviewVerdict
from deep_research.schemas.routing import Route


class ResearchState(TypedDict, total=False):
    """State flowing through the research graph."""

    topic: str
    # set by the input guard when the run is refused (explanation for the user)
    refusal: str
    # what the input guard changed (e.g. PII kinds scrubbed from the topic)
    input_notes: list[str]
    # triage verdict: simple_lookup takes the short path, others the full pipeline
    route: Route
    # related past sessions from episodic memory (empty string when none)
    prior_context: str
    sub_topics: list[SubTopic]
    # fan-in point: every parallel researcher appends exactly one result
    research_results: Annotated[list[ResearchResult], operator.add]
    # sub-topics the quality gate rejected (consumed by the replanner)
    needs_replan: list[SubTopic]
    # revised sub-topics produced by the replanner (fanned out at attempt 2)
    revised_sub_topics: list[SubTopic]
    # deduplicated, numbered evidence set (built by the analyst)
    sources: list[Source]
    claims: list[Claim]
    synthesis: SynthesisOutput
    report: str
    review: ReviewVerdict
    # number of writer runs that were revisions (bounded by max_writer_revisions)
    revision_count: int


class ResearcherInput(TypedDict):
    """Private payload each Send() delivers to one researcher instance."""

    sub_topic: SubTopic
    attempt: int
