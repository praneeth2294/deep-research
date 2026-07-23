"""Tavily web-search tool.

Thin, typed wrapper around the Tavily API: takes a query string, returns
validated `Source` objects. The LLM never sees raw API responses — everything
crossing a node boundary is a Pydantic model.
"""

from typing import Any

from tavily import TavilyClient

from deep_research.config import get_settings
from deep_research.schemas.research import Source

_MAX_RESULTS = 5


def search_web(query: str, max_results: int = _MAX_RESULTS) -> list[Source]:
    """Run a Tavily web search and return validated sources.

    Raises RuntimeError with a setup hint if the API key is missing.
    """
    settings = get_settings()
    if settings.tavily_api_key is None:
        raise RuntimeError(
            "TAVILY_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://app.tavily.com)."
        )
    client = TavilyClient(api_key=settings.tavily_api_key.get_secret_value())
    response: dict[str, Any] = client.search(query=query, max_results=max_results)
    sources = [
        Source(
            url=result.get("url", ""),
            title=result.get("title") or "(untitled)",
            snippet=result.get("content") or "",
            score=result.get("score"),
        )
        for result in response.get("results", [])
        if result.get("url")
    ]
    return sources
