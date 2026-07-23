"""Reviewer node — the evaluator half of the Evaluator-Optimiser loop.

Scores the draft 0-10 against a concrete rubric and lists actionable issues.
The routing function (in builder.py) sends rejected drafts back to the writer,
bounded by `max_writer_revisions`.
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import structured_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.review import ReviewVerdict


def reviewer_node(state: ResearchState) -> ResearchState:
    verdict = cast(
        ReviewVerdict,
        structured_llm(ReviewVerdict, tier="cheap").invoke(
            [
                ("system", load_prompt("reviewer")),
                (
                    "human",
                    f"Topic: {state['topic']}\n\n"
                    f"Number of available sources: {len(state.get('sources', []))}\n\n"
                    f"Report draft:\n{state.get('report', '')}",
                ),
            ]
        ),
    )
    return {"review": verdict}
