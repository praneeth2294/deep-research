"""Writer node — produce the cited report from collected sources.

Prompt-chaining step: consumes the researcher's sources, emits prose whose
every claim carries an inline [n] citation resolvable against the source list.
"""

from langchain_core.messages import BaseMessage

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import cheap_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.research import Source


def extract_text(message: BaseMessage) -> str:
    """Return only the text of a model response.

    Gemini 3 returns `content` as a list of typed parts (text blocks plus
    reasoning-signature blobs); older models return a plain string. Never
    `str()` the raw content — normalize here.
    """
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") == "text":
            parts.append(str(part.get("text", "")))
    return "\n".join(parts).strip()


def format_sources(sources: list[Source]) -> str:
    """Render sources as a numbered evidence block for the prompt ([1], [2], ...)."""
    lines = [
        f"[{i}] {source.title}\nURL: {source.url}\nContent: {source.snippet}"
        for i, source in enumerate(sources, start=1)
    ]
    return "\n\n".join(lines)


def writer_node(state: ResearchState) -> ResearchState:
    sources = state.get("sources", [])
    if not sources:
        return {"report": "No sources were found for this topic; cannot write a grounded report."}
    response = cheap_llm(temperature=0.3).invoke(
        [
            ("system", load_prompt("writer")),
            (
                "human",
                f"Topic: {state['topic']}\n\nNumbered sources:\n\n{format_sources(sources)}",
            ),
        ]
    )
    return {"report": extract_text(response)}
