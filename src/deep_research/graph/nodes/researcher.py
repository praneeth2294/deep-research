"""Researcher node v2 — a bounded ReAct agent (deck 2.7).

The loop: reason -> choose a tool -> act -> observe -> repeat, with the
accumulated action history in the prompt each step (the agent's working
memory). Hard-capped at `max_react_iterations` LLM decisions — an agent
without a cap is an outage waiting to happen.

Cost engineering: step 0 executes the planner's search query directly (no LLM
call) — the plan already contains a good first move, so the LLM only decides
what to do *beyond* the baseline.
"""

from typing import cast

from deep_research.config import get_settings
from deep_research.graph.state import ResearcherInput, ResearchState
from deep_research.llm.tiering import structured_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.research import ReactStep, ResearchResult, Source
from deep_research.tools.registry import catalog, get_tool


def _observation(new: list[Source], added: int) -> str:
    titles = "; ".join(source.title[:70] for source in new[:3])
    return f"{len(new)} sources ({added} new): {titles}" if new else "no results"


def researcher_node(state: ResearcherInput) -> ResearchState:
    settings = get_settings()
    sub_topic = state["sub_topic"]
    sources: list[Source] = []
    seen_urls: set[str] = set()
    history: list[str] = []

    def run_tool(tool_name: str, action_input: str) -> None:
        try:
            found = get_tool(tool_name).run(action_input)
        except Exception as exc:
            history.append(f"Action: {tool_name}({action_input!r}) -> ERROR: {exc}")
            return
        added = 0
        for source in found:
            if source.url not in seen_urls:
                seen_urls.add(source.url)
                sources.append(source)
                added += 1
        history.append(f"Action: {tool_name}({action_input!r}) -> {_observation(found, added)}")

    # Step 0 - seeded baseline search from the plan (no LLM decision needed).
    run_tool("tavily_search", sub_topic.search_query)

    for iteration in range(settings.max_react_iterations):
        step = cast(
            ReactStep,
            structured_llm(ReactStep, tier="cheap").invoke(
                [
                    ("system", load_prompt("researcher")),
                    (
                        "human",
                        f"Sub-topic: {sub_topic.title}\n"
                        f"Why it matters: {sub_topic.rationale}\n\n"
                        f"Available tools:\n{catalog()}\n\n"
                        f"Action history so far:\n" + "\n".join(history) + "\n\n"
                        f"Sources collected: {len(sources)}. "
                        f"Decision {iteration + 1} of {settings.max_react_iterations}: "
                        "choose the next action or finish.",
                    ),
                ]
            ),
        )
        if step.action == "finish":
            history.append(f"Finish: {step.reasoning}")
            break
        history.append(f"Thought: {step.reasoning}")
        run_tool(step.action, step.action_input)

    return {
        "research_results": [
            ResearchResult(
                sub_topic=sub_topic,
                sources=sources,
                attempt=state["attempt"],
                history=history,
            )
        ]
    }
