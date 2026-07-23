"""Scraper: SSRF policy, text extraction, and the circuit breaker (no network)."""

import pytest

from deep_research.tools import scraper


@pytest.fixture(autouse=True)
def _reset_breaker() -> None:
    scraper._breaker.clear()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",  # caught by the policy layer (scheme)
        "file:///etc/passwd",  # caught by the policy layer (scheme)
        "http://localhost/admin",
        "http://127.0.0.1:8080/",
        "http://192.168.1.1/router",
        "http://10.0.0.5/internal",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata endpoint
        "http://printer.local/status",
    ],
)
def test_ssrf_policy_blocks(url: str) -> None:
    # Two guard layers run in sequence: URL policy (schemes/ports/credentials),
    # then the SSRF class check (private/reserved IPs). Either may refuse.
    from deep_research.guardrails.url_policy import PolicyViolationError

    with pytest.raises((scraper.BlockedUrlError, PolicyViolationError)):
        scraper.fetch_url(url)


def test_extracts_readable_text(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html><head><title>My Page</title><style>.x{color:red}</style></head>
    <body><nav>menu menu</nav><script>alert(1)</script>
    <p>Real content   here.</p><footer>footer junk</footer></body></html>
    """
    monkeypatch.setattr(scraper, "_fetch_html", lambda _url: html)
    [source] = scraper.fetch_url("https://example.com/article")
    assert source.title == "My Page"
    assert "Real content here." in source.snippet
    assert "alert(1)" not in source.snippet
    assert "menu menu" not in source.snippet
    assert "footer junk" not in source.snippet


def test_circuit_breaker_opens_after_three_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def boom(_url: str) -> str:
        calls["n"] += 1
        raise RuntimeError("connection refused")

    monkeypatch.setattr(scraper, "_fetch_html", boom)

    for _ in range(3):
        with pytest.raises(RuntimeError, match="connection refused"):
            scraper.fetch_url("https://dead.example/page")
    assert calls["n"] == 3

    # 4th call: circuit is open -> fetch never attempted
    with pytest.raises(scraper.CircuitOpenError):
        scraper.fetch_url("https://dead.example/other-page")
    assert calls["n"] == 3


def test_circuit_closes_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    scraper._breaker["slow.example"] = (3, 0.0)  # opened long ago
    monkeypatch.setattr(scraper, "_fetch_html", lambda _u: "<title>ok</title><body>fine</body>")
    [source] = scraper.fetch_url("https://slow.example/page")  # cooldown elapsed -> probe allowed
    assert source.title == "ok"
    assert "slow.example" not in scraper._breaker  # success resets the breaker
