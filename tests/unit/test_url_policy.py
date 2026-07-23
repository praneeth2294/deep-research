"""URL policy: deny rules, operator blocklist, and the registry choke point."""

import pytest

from deep_research.config import get_settings
from deep_research.guardrails.url_policy import PolicyViolationError, check, evaluate
from deep_research.schemas.research import Source
from deep_research.tools import registry


@pytest.mark.parametrize(
    ("url", "reason_fragment"),
    [
        ("ftp://example.com/x", "scheme"),
        ("https://user:pass@example.com/x", "credentials"),
        ("https://example.com:9200/_cat", "port"),
        ("https://" + "a" * 2100 + ".com", "longer"),
        ("https:///nopath", "host"),
    ],
)
def test_denied(url: str, reason_fragment: str) -> None:
    allowed, reason = evaluate(url)
    assert not allowed
    assert reason_fragment in reason
    with pytest.raises(PolicyViolationError):
        check(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/article",
        "http://example.com:8080/page",
        "https://docs.python.org:443/3/",
    ],
)
def test_allowed(url: str) -> None:
    assert evaluate(url) == (True, "")


def test_operator_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLOCKED_DOMAINS", "badsite.example, spam.example")
    get_settings.cache_clear()
    try:
        assert not evaluate("https://badsite.example/page")[0]
        assert not evaluate("https://sub.badsite.example/page")[0]  # suffix match
        assert not evaluate("https://spam.example/x")[0]
        assert evaluate("https://goodsite.example/page")[0]
        # must not over-match: notbadsite.example is a different domain
        assert evaluate("https://notbadsite.example/page")[0]
    finally:
        get_settings.cache_clear()


def test_registry_drops_disallowed_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry choke point silently filters policy-violating result URLs."""
    mixed = [
        Source(url="https://good.example/a", title="ok", snippet="fine content"),
        Source(url="https://user:pw@evil.example/b", title="creds", snippet="x"),
        Source(url="https://odd.example:9200/c", title="port", snippet="x"),
    ]
    spec = registry.ToolSpec("t", "fake", registry._guarded(lambda _q: mixed))
    results = spec.run("query")
    assert [s.url for s in results] == ["https://good.example/a"]
