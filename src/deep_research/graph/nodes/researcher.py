"""Researcher node — one instance per sub-topic, run in parallel via Send().

Phase 2: each Send() delivers a private `ResearcherInput` payload; the node
runs the sub-topic's search query and appends a `ResearchResult` to the shared
state (merged by the `operator.add` reducer). Still a single tool call —
Phase 4 upgrades this into a bounded ReAct agent with tool choice.
"""

from deep_research.graph.state import ResearcherInput, ResearchState
from deep_research.schemas.research import ResearchResult
from deep_research.tools.tavily_search import search_web


def researcher_node(state: ResearcherInput) -> ResearchState:
    sub_topic = state["sub_topic"]
    sources = search_web(sub_topic.search_query)
    return {
        "research_results": [
            ResearchResult(sub_topic=sub_topic, sources=sources, attempt=state["attempt"])
        ]
    }
