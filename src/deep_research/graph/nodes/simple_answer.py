"""Simple-answer node — the Augmented LLM short path (deck 1.1).

For simple_lookup topics: one web search + one cheap LLM call with citations.
No planning, no fan-out, no review loop — the cheapest sufficient machinery.
"""

from deep_research.graph.state import ResearchState
from deep_research.llm.content import extract_text
from deep_research.llm.tiering import text_llm
from deep_research.prompts import load_prompt
from deep_research.tools.tavily_search import search_web

_SIMPLE_MAX_RESULTS = 3


def simple_answer_node(state: ResearchState) -> ResearchState:
    sources = search_web(state["topic"], max_results=_SIMPLE_MAX_RESULTS)
    if not sources:
        return {
            "sources": [],
            "report": "No sources were found for this question; cannot give a grounded answer.",
        }
    numbered = "\n\n".join(
        f"[{i}] {s.title}\nURL: {s.url}\nContent: {s.snippet}"
        for i, s in enumerate(sources, start=1)
    )
    response = text_llm(tier="cheap", temperature=0.2).invoke(
        [
            ("system", load_prompt("simple_answer")),
            ("human", f"Question: {state['topic']}\n\nNumbered sources:\n\n{numbered}"),
        ]
    )
    return {"sources": sources, "report": extract_text(response)}
