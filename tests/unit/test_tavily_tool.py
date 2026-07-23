"""Tavily wrapper: response mapping and fail-fast behavior (no network)."""

from typing import Any

import pytest

from deep_research.config import Settings
from deep_research.schemas.research import Source
from deep_research.tools import tavily_search


class _FakeTavilyClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int) -> dict[str, Any]:
        return {
            "results": [
                {"url": "https://a.example/1", "title": "A", "content": "aaa", "score": 0.9},
                {"url": "https://b.example/2", "title": None, "content": None},
                {"title": "no url -> dropped"},
            ]
        }


def _settings_with(tavily_key: str | None) -> Settings:
    kwargs: dict[str, Any] = {"tavily_api_key": tavily_key}
    return Settings(_env_file=None, **kwargs)


def test_search_maps_results_and_drops_urlless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tavily_search, "get_settings", lambda: _settings_with("test-key"))
    monkeypatch.setattr(tavily_search, "TavilyClient", _FakeTavilyClient)
    sources = tavily_search.search_web("anything")
    assert len(sources) == 2
    assert sources[0] == Source(url="https://a.example/1", title="A", snippet="aaa", score=0.9)
    # None title/content fall back to safe defaults instead of crashing
    assert sources[1].title == "(untitled)"
    assert sources[1].snippet == ""


def test_missing_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tavily_search, "get_settings", lambda: _settings_with(None))
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        tavily_search.search_web("anything")
