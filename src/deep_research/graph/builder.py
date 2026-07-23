"""Graph assembly.

Phase 1 wiring (prompt chain):

    START -> planner -> researcher -> writer -> END

Phase 2 replaces the planner->researcher edge with a Send() fan-out and adds
the quality gate, analyst, synthesizer, and reviewer loop.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from deep_research.graph.nodes.planner import planner_node
from deep_research.graph.nodes.researcher import researcher_node
from deep_research.graph.nodes.writer import writer_node
from deep_research.graph.state import ResearchState


def build_graph() -> CompiledStateGraph[ResearchState]:
    """Build and compile the research graph (no I/O happens until invoke)."""
    graph: StateGraph[ResearchState] = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", END)
    return graph.compile()
