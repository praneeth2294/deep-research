"""Replanner node — Planning-with-revision (deck: Plan -> Revised Plan).

When the quality gate rejects a sub-topic's evidence, this node revises the
*search query* (keeping the title — it is the join key across attempts) so the
second research attempt looks somewhere better, instead of blindly retrying
the identical query.
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import cheap_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.planner import PlannerOutput, SubTopic


def replanner_node(state: ResearchState) -> ResearchState:
    failed = state.get("needs_replan", [])
    failed_block = "\n".join(
        f"- title: {s.title}\n  failed query: {s.search_query}" for s in failed
    )
    llm = cheap_llm().with_structured_output(PlannerOutput)
    revised = cast(
        PlannerOutput,
        llm.invoke(
            [
                ("system", load_prompt("replanner")),
                (
                    "human",
                    f"Overall topic: {state['topic']}\n\n"
                    f"Sub-topics whose search results were low quality:\n{failed_block}",
                ),
            ]
        ),
    )
    # Preserve original titles positionally if the model drifted - the title is
    # the join key the gate uses to bound the loop.
    revised_sub_topics: list[SubTopic] = []
    for i, original in enumerate(failed):
        if i < len(revised.sub_topics):
            candidate = revised.sub_topics[i]
            revised_sub_topics.append(candidate.model_copy(update={"title": original.title}))
        else:
            revised_sub_topics.append(original)
    return {"revised_sub_topics": revised_sub_topics, "needs_replan": []}
