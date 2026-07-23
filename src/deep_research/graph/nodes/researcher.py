"""Researcher node — walking-skeleton version (Phase 1).

One Tavily search per sub-topic, run sequentially. No LLM call, no ReAct yet:
Phase 2 turns this into a parallel fan-out (one node instance per sub-topic)
and Phase 4 upgrades each instance to a bounded ReAct agent with tool choice.
"""

from deep_research.graph.state import ResearchState
from deep_research.schemas.research import Source
from deep_research.tools.tavily_search import search_web


def researcher_node(state: ResearchState) -> ResearchState:
    sources: list[Source] = []
    for sub_topic in state.get("sub_topics", []):
        sources.extend(search_web(sub_topic.search_query))
    return {"sources": sources}
