"""Tool registry — the deck's "function definitions + tool registry" box.

One place where research tools are declared: name, LLM-facing description, and
implementation. The researcher's ReAct loop resolves tools from here by name —
no node imports a tool directly.

Every tool's output passes through the injection sanitizer at this choke
point, so no unsanitized web text can ever reach a prompt regardless of which
tool produced it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from deep_research.guardrails.injection import sanitize_text
from deep_research.schemas.research import Source
from deep_research.tools.scraper import fetch_url
from deep_research.tools.semantic_search import search_memory
from deep_research.tools.tavily_search import search_web
from deep_research.tools.wikipedia import search_wikipedia

ToolFn = Callable[[str], list[Source]]


@dataclass(frozen=True)
class ToolSpec:
    """Machine-readable definition of one research tool."""

    name: str
    description: str
    run: ToolFn


def _sanitized(run: ToolFn) -> ToolFn:
    def wrapper(argument: str) -> list[Source]:
        return [
            source.model_copy(
                update={
                    "title": sanitize_text(source.title),
                    "snippet": sanitize_text(source.snippet),
                }
            )
            for source in run(argument)
        ]

    return wrapper


_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name="tavily_search",
            description=(
                "Web search. Input: a search query. Returns titles, URLs and text "
                "snippets from across the web. Best first move for any sub-topic."
            ),
            run=_sanitized(search_web),
        ),
        ToolSpec(
            name="wikipedia",
            description=(
                "Wikipedia search. Input: a topic or entity name. Returns encyclopedic "
                "articles. Best for definitions, background and established facts."
            ),
            run=_sanitized(search_wikipedia),
        ),
        ToolSpec(
            name="fetch_url",
            description=(
                "Fetch one specific web page. Input: a full http(s) URL, typically one "
                "already seen in earlier results. Returns the page's readable text — "
                "use when a snippet looks promising but is too thin to cite."
            ),
            run=_sanitized(fetch_url),
        ),
        ToolSpec(
            name="semantic_search",
            description=(
                "Search this system's own memory of sources gathered in past research "
                "sessions. Instant and free — try it first when the sub-topic may "
                "overlap earlier work; fall back to web search if it returns little."
            ),
            run=_sanitized(search_memory),
        ),
    ]
}


def get_tool(name: str) -> ToolSpec:
    """Resolve a tool by name; raises KeyError with the valid names listed."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"Unknown tool '{name}'. Available: {sorted(_REGISTRY)}") from None


def catalog() -> str:
    """LLM-facing tool list, injected into the researcher prompt."""
    return "\n".join(f"- {spec.name}: {spec.description}" for spec in _REGISTRY.values())
