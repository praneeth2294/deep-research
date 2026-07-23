"""Writer node — produce (and revise) the cited report.

The generator half of the Evaluator-Optimiser loop: the first run drafts the
report from the synthesis; when the reviewer rejects a draft, this node runs
again with the reviewer's issues as explicit revision instructions
(incrementing `revision_count`, which bounds the loop).
"""

from langchain_core.messages import BaseMessage

from deep_research.graph.state import ResearchState
from deep_research.llm.tiering import strong_llm
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


def _build_brief(state: ResearchState) -> str:
    synthesis = state.get("synthesis")
    sources = state.get("sources", [])
    parts = [f"Topic: {state['topic']}"]
    if synthesis is not None:
        parts.append(f"Synthesis:\n{synthesis.summary}")
        parts.append("Key findings:\n" + "\n".join(f"- {kf}" for kf in synthesis.key_findings))
        if synthesis.conflicts:
            parts.append(
                "Conflicts to surface explicitly:\n"
                + "\n".join(f"- {c}" for c in synthesis.conflicts)
            )
    parts.append(f"Numbered sources:\n\n{format_sources(sources)}")
    return "\n\n".join(parts)


def writer_node(state: ResearchState) -> ResearchState:
    sources = state.get("sources", [])
    if not sources:
        return {"report": "No sources were found for this topic; cannot write a grounded report."}

    messages: list[tuple[str, str]] = [("system", load_prompt("writer"))]
    review = state.get("review")
    is_revision = review is not None and bool(state.get("report"))
    if is_revision and review is not None:
        issues = "\n".join(f"- {issue}" for issue in review.issues) or "- (no specific issues)"
        messages.append(
            (
                "human",
                f"{_build_brief(state)}\n\n"
                f"Your previous draft:\n{state['report']}\n\n"
                f"A reviewer scored it {review.score}/10 and requires these fixes:\n{issues}\n\n"
                "Rewrite the report addressing every issue. Keep what was good.",
            )
        )
    else:
        messages.append(("human", _build_brief(state)))

    response = strong_llm(temperature=0.3).invoke(messages)
    update: ResearchState = {"report": extract_text(response)}
    if is_revision:
        update["revision_count"] = state.get("revision_count", 0) + 1
    return update
