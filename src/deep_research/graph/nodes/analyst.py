"""Analyst node — first step of the analysis chain (Prompt Chaining).

Deduplicates the evidence across all researcher results into one numbered
source list, then extracts structured claims (statement + confidence +
supporting source numbers) with the strong model.
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import strong_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.analysis import ClaimSet
from deep_research.schemas.research import Source

# Bound the prompt size: keep the best-scored sources when there are too many.
_MAX_SOURCES = 20


def dedupe_sources(state: ResearchState) -> list[Source]:
    """Merge all researchers' sources, dropping duplicate URLs (keep first seen)."""
    seen: set[str] = set()
    merged: list[Source] = []
    for result in state.get("research_results", []):
        for source in result.sources:
            if source.url not in seen:
                seen.add(source.url)
                merged.append(source)
    merged.sort(key=lambda s: s.score or 0.0, reverse=True)
    return merged[:_MAX_SOURCES]


def format_numbered(sources: list[Source]) -> str:
    """Render sources as the numbered evidence block used by all later nodes."""
    return "\n\n".join(
        f"[{i}] {s.title}\nURL: {s.url}\nContent: {s.snippet}"
        for i, s in enumerate(sources, start=1)
    )


def analyst_node(state: ResearchState) -> ResearchState:
    sources = dedupe_sources(state)
    if not sources:
        return {"sources": [], "claims": []}
    llm = strong_llm().with_structured_output(ClaimSet)
    claim_set = cast(
        ClaimSet,
        llm.invoke(
            [
                ("system", load_prompt("analyst")),
                (
                    "human",
                    f"Topic: {state['topic']}\n\nNumbered sources:\n\n{format_numbered(sources)}",
                ),
            ]
        ),
    )
    # Drop claims citing source numbers that don't exist (hallucinated ids).
    valid = [c for c in claim_set.claims if all(1 <= i <= len(sources) for i in c.source_ids)]
    return {"sources": sources, "claims": valid}
