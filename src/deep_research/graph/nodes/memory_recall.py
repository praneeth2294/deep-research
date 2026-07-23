"""Memory-recall node — "have we researched something like this before?"

Runs before planning on the deep path. Failures (no key, empty store, network)
degrade gracefully to an empty context: memory must never break research.
"""

from deep_research.graph.state import ResearchState
from deep_research.memory.episodic import recall_similar


def memory_recall_node(state: ResearchState) -> ResearchState:
    try:
        prior = recall_similar(state["topic"])
    except Exception:
        prior = ""
    return {"prior_context": prior}
