"""Graph assembly — Phase 2 wiring.

                       Send() per sub-topic (parallel)
    START -> planner ================================> researcher(s)
                                                            |
                                                            v   (fan-in)
              +--------------------------------------- quality_gate
              | any sub-topic below threshold?              |
              v  yes (attempt 1 only)                       | no
          replanner ==Send() per revised sub-topic==> researcher(s)
                                                            |
              analyst  <------------------------------------+
                 |
                 v
            synthesizer -> writer -> reviewer --score >= pass, or
                              ^          |       revisions exhausted--> END
                              +--issues--+

Routing rules live here, next to the wiring, so the whole control flow is
readable in one file. Nodes stay pure (state in, partial state out).
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from deep_research.config import get_settings
from deep_research.graph.nodes.analyst import analyst_node
from deep_research.graph.nodes.planner import planner_node
from deep_research.graph.nodes.quality_gate import quality_gate_node
from deep_research.graph.nodes.replanner import replanner_node
from deep_research.graph.nodes.researcher import researcher_node
from deep_research.graph.nodes.reviewer import reviewer_node
from deep_research.graph.nodes.synthesizer import synthesizer_node
from deep_research.graph.nodes.writer import writer_node
from deep_research.graph.state import ResearchState


def fan_out_researchers(state: ResearchState) -> list[Send]:
    """Parallelisation: one researcher instance per planned sub-topic."""
    return [
        Send("researcher", {"sub_topic": sub_topic, "attempt": 1})
        for sub_topic in state.get("sub_topics", [])
    ]


def route_after_gate(state: ResearchState) -> str:
    """Gate routing: replan failed sub-topics (bounded), else proceed to analysis."""
    return "replanner" if state.get("needs_replan") else "analyst"


def fan_out_replanned(state: ResearchState) -> list[Send]:
    """Second (final) research wave for revised sub-topics."""
    return [
        Send("researcher", {"sub_topic": sub_topic, "attempt": 2})
        for sub_topic in state.get("revised_sub_topics", [])
    ]


def route_after_review(state: ResearchState) -> str:
    """Evaluator-Optimiser routing: accept, or revise while budget remains."""
    settings = get_settings()
    review = state.get("review")
    if review is None or review.score >= settings.reviewer_pass_score:
        return END
    if state.get("revision_count", 0) >= settings.max_writer_revisions:
        return END
    return "writer"


def build_graph() -> CompiledStateGraph[ResearchState]:
    """Build and compile the research graph (no I/O happens until invoke)."""
    graph: StateGraph[ResearchState] = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)  # Send() delivers ResearcherInput payloads
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("replanner", replanner_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", fan_out_researchers, ["researcher"])
    graph.add_edge("researcher", "quality_gate")
    graph.add_conditional_edges("quality_gate", route_after_gate, ["replanner", "analyst"])
    graph.add_conditional_edges("replanner", fan_out_replanned, ["researcher"])
    graph.add_edge("analyst", "synthesizer")
    graph.add_edge("synthesizer", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges("reviewer", route_after_review, ["writer", END])
    return graph.compile()
