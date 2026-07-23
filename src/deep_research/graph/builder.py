"""Graph assembly — Phase 3 wiring.

    START -> router --simple_lookup--> simple_answer -> END
                |
                | deep_research / comparison
                v          Send() per sub-topic (parallel)
             planner ================================> researcher(s)
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

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from deep_research.config import get_settings
from deep_research.graph.nodes.analyst import analyst_node
from deep_research.graph.nodes.hitl import hitl_node
from deep_research.graph.nodes.input_guard import input_guard_node
from deep_research.graph.nodes.memory_recall import memory_recall_node
from deep_research.graph.nodes.memory_store import memory_store_node
from deep_research.graph.nodes.planner import planner_node
from deep_research.graph.nodes.quality_gate import quality_gate_node
from deep_research.graph.nodes.replanner import replanner_node
from deep_research.graph.nodes.researcher import researcher_node
from deep_research.graph.nodes.reviewer import reviewer_node
from deep_research.graph.nodes.router import router_node
from deep_research.graph.nodes.simple_answer import simple_answer_node
from deep_research.graph.nodes.synthesizer import synthesizer_node
from deep_research.graph.nodes.writer import writer_node
from deep_research.graph.state import ResearchState


def route_after_input_guard(state: ResearchState) -> str:
    """Refused input ends the run before any LLM call is made."""
    return END if state.get("refusal") else "router"


def route_after_router(state: ResearchState) -> str:
    """LLM-routing branch: trivial questions skip the whole pipeline."""
    return "simple_answer" if state.get("route") == "simple_lookup" else "memory_recall"


def fan_out_researchers(state: ResearchState) -> list[Send]:
    """Parallelisation: one researcher instance per planned sub-topic."""
    return [
        Send("researcher", {"sub_topic": sub_topic, "attempt": 1})
        for sub_topic in state.get("sub_topics", [])
    ]


def fan_out_after_hitl(state: ResearchState) -> list[Send] | str:
    """After plan approval: cancelled runs end; approved/edited plans fan out."""
    if state.get("refusal"):
        return END
    return fan_out_researchers(state)


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
    """Evaluator-Optimiser routing: accept (via memory write-back), or revise."""
    settings = get_settings()
    review = state.get("review")
    if review is None or review.score >= settings.reviewer_pass_score:
        return "memory_store"
    if state.get("revision_count", 0) >= settings.max_writer_revisions:
        return "memory_store"
    return "writer"


def build_graph(
    checkpointer: BaseCheckpointSaver[str] | None = None,
    *,
    hitl: bool = True,
) -> CompiledStateGraph[ResearchState]:
    """Build and compile the research graph (no I/O happens until invoke).

    Pass a checkpointer for durable execution: state persists after every
    superstep and a run can resume by thread_id after a crash.
    `hitl=True` (default) pauses after planning for human plan approval —
    requires a checkpointer at runtime. Tests of other paths pass hitl=False.
    """
    graph: StateGraph[ResearchState] = StateGraph(ResearchState)
    graph.add_node("input_guard", input_guard_node)
    graph.add_node("router", router_node)
    graph.add_node("simple_answer", simple_answer_node)
    graph.add_node("memory_recall", memory_recall_node)
    graph.add_node("memory_store", memory_store_node)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)  # Send() delivers ResearcherInput payloads
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("replanner", replanner_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges("input_guard", route_after_input_guard, ["router", END])
    graph.add_conditional_edges("router", route_after_router, ["simple_answer", "memory_recall"])
    graph.add_edge("simple_answer", END)
    graph.add_edge("memory_recall", "planner")
    if hitl:
        graph.add_node("hitl", hitl_node)
        graph.add_edge("planner", "hitl")
        graph.add_conditional_edges("hitl", fan_out_after_hitl, ["researcher", END])
    else:
        graph.add_conditional_edges("planner", fan_out_researchers, ["researcher"])
    graph.add_edge("researcher", "quality_gate")
    graph.add_conditional_edges("quality_gate", route_after_gate, ["replanner", "analyst"])
    graph.add_conditional_edges("replanner", fan_out_replanned, ["researcher"])
    graph.add_edge("analyst", "synthesizer")
    graph.add_edge("synthesizer", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges("reviewer", route_after_review, ["writer", "memory_store"])
    graph.add_edge("memory_store", END)
    return graph.compile(checkpointer=checkpointer)
