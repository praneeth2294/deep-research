"""Memory write-back node — persist what this session learned.

Runs after the reviewer accepts (or the revision budget ends):
- episodic: the session summary (topic + key findings), for future recall
- semantic: the deduplicated sources, for the semantic_search tool

Best-effort by design: a memory failure must never lose the finished report.
"""

from langchain_core.runnables import RunnableConfig

from deep_research.graph.state import ResearchState
from deep_research.memory.episodic import store_session
from deep_research.memory.semantic import cache_sources


def memory_store_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    thread_id = str(config.get("configurable", {}).get("thread_id", "no-thread"))
    synthesis = state.get("synthesis")
    try:
        store_session(
            thread_id=thread_id,
            topic=state["topic"],
            report=state.get("report", ""),
            key_findings=synthesis.key_findings if synthesis else [],
        )
        cache_sources(state.get("sources", []))
    except Exception:
        pass
    return {}
