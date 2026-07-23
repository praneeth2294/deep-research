"""Human-in-the-loop node — plan approval before money is spent (deck HITL).

Placed between the planner and the researcher fan-out: the graph *pauses*
(LangGraph `interrupt()`), surfaces the plan to whoever drives the graph
(CLI prompt, API client), and resumes with their decision:

    {"decision": "approve"}                          -> run the plan as-is
    {"decision": "edit", "sub_topics": [...]}        -> run the edited plan
    {"decision": "cancel"}                           -> end the run, explained

The interrupt lands BEFORE the fan-out on purpose: the plan is the last cheap
artifact — everything after it multiplies cost by the number of researchers.
Requires a checkpointer (interrupt state must survive the pause).
"""

from langgraph.types import interrupt

from deep_research.graph.state import ResearchState
from deep_research.schemas.planner import PlannerOutput


def hitl_node(state: ResearchState) -> ResearchState:
    decision_raw = interrupt(
        {
            "type": "plan_approval",
            "topic": state.get("topic", ""),
            "sub_topics": [st.model_dump() for st in state.get("sub_topics", [])],
            "options": ["approve", "edit", "cancel"],
        }
    )
    decision = decision_raw if isinstance(decision_raw, dict) else {"decision": str(decision_raw)}
    choice = str(decision.get("decision", "approve")).lower()

    if choice == "cancel":
        message = "Research cancelled by the user at plan approval. No researchers were run."
        return {"refusal": message, "report": message}

    if choice == "edit" and decision.get("sub_topics"):
        # Same contract as the planner: edits must satisfy PlannerOutput (1-3
        # sub-topics, non-empty queries) or the resume is rejected upstream.
        validated = PlannerOutput.model_validate({"sub_topics": decision["sub_topics"]})
        return {"sub_topics": validated.sub_topics}

    return {}
