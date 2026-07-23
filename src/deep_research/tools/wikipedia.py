"""Wikipedia search tool — encyclopedic background, no API key needed."""

import re

import httpx

from deep_research.schemas.research import Source

_API = "https://en.wikipedia.org/w/api.php"
_TIMEOUT_S = 10.0
_MAX_RESULTS = 3
_TAG_RE = re.compile(r"<[^>]+>")


def search_wikipedia(query: str, max_results: int = _MAX_RESULTS) -> list[Source]:
    """Search Wikipedia and return the top articles as sources."""
    with httpx.Client(timeout=_TIMEOUT_S) as client:
        response = client.get(
            _API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    sources: list[Source] = []
    for item in payload.get("query", {}).get("search", []):
        title = str(item.get("title", ""))
        if not title:
            continue
        sources.append(
            Source(
                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                title=f"Wikipedia: {title}",
                snippet=_TAG_RE.sub("", str(item.get("snippet", ""))),
            )
        )
    return sources
