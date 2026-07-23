"""Router node — LLM-based Routing (deck 1.3): triage before spending money.

One cheap structured call classifies the topic; trivial questions take the
simple_lookup short path (one search + one LLM call) instead of the full
multi-node pipeline. This is the system's biggest cost lever.
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import structured_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.routing import RouteDecision


def router_node(state: ResearchState) -> ResearchState:
    decision = cast(
        RouteDecision,
        structured_llm(RouteDecision, tier="cheap").invoke(
            [
                ("system", load_prompt("router")),
                ("human", f"Topic: {state['topic']}"),
            ]
        ),
    )
    return {"route": decision.route}
