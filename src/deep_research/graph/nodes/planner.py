"""Planner node — Orchestrator pattern (deck 1.5): decompose the topic.

One cheap-model call with structured output. The returned plan drives how
many researchers run (fan-out arrives in Phase 2).
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import structured_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.planner import PlannerOutput


def planner_node(state: ResearchState) -> ResearchState:
    plan = cast(
        PlannerOutput,
        structured_llm(PlannerOutput, tier="cheap").invoke(
            [
                ("system", load_prompt("planner")),
                (
                    "human",
                    f"Research topic: {state['topic']}\n"
                    f"Query type: {state.get('route', 'deep_research')}",
                ),
            ]
        ),
    )
    return {"sub_topics": plan.sub_topics}
