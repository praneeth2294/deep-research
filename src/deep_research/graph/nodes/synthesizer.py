"""Synthesizer node — the aggregator of Orchestrator-Workers.

Cross-references the analyst's claims: what do independent sources agree on,
where do they conflict, and what actually matters for the topic. Produces the
structured brief the writer works from.
"""

from typing import cast

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import strong_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.analysis import SynthesisOutput


def _format_claims(state: ResearchState) -> str:
    return "\n".join(
        f"- ({c.confidence}) {c.statement}  [sources: {', '.join(map(str, c.source_ids))}]"
        for c in state.get("claims", [])
    )


def synthesizer_node(state: ResearchState) -> ResearchState:
    llm = strong_llm().with_structured_output(SynthesisOutput)
    synthesis = cast(
        SynthesisOutput,
        llm.invoke(
            [
                ("system", load_prompt("synthesizer")),
                (
                    "human",
                    f"Topic: {state['topic']}\n\nExtracted claims:\n{_format_claims(state)}",
                ),
            ]
        ),
    )
    return {"synthesis": synthesis}
