"""URL scraper tool — fetch a specific page and extract its readable text.

Production defenses built in:
- SSRF guard: only http(s), never localhost or private/reserved IPs.
- Timeouts and a response-size cap.
- Per-domain circuit breaker: after 3 consecutive failures a domain is
  skipped for a cooldown window instead of hammering a dead site.
"""

import ipaddress
import time
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from deep_research.schemas.research import Source

_TIMEOUT_S = 10.0
_MAX_BYTES = 500_000
_MAX_TEXT_CHARS = 4_000
_FAILURE_THRESHOLD = 3
_COOLDOWN_S = 300.0

_BLOCKED_HOSTS = {"localhost", "0.0.0.0", "metadata.google.internal"}
_STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]


class CircuitOpenError(RuntimeError):
    """Raised when a domain's circuit is open (too many recent failures)."""


class BlockedUrlError(ValueError):
    """Raised for URLs the SSRF policy refuses to fetch."""


# domain -> (consecutive_failures, last_failure_monotonic)
_breaker: dict[str, tuple[int, float]] = {}


def _check_url_allowed(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedUrlError(f"Only http(s) URLs are allowed, got: {url}")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        raise BlockedUrlError(f"Host not allowed: {host or '(empty)'}")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host  # a hostname, not a literal IP
    if address.is_private or address.is_loopback or address.is_reserved or address.is_link_local:
        raise BlockedUrlError(f"Private/reserved IP not allowed: {host}")
    return host


def _check_breaker(domain: str) -> None:
    failures, last_failure = _breaker.get(domain, (0, 0.0))
    if failures >= _FAILURE_THRESHOLD:
        if time.monotonic() - last_failure < _COOLDOWN_S:
            raise CircuitOpenError(f"Circuit open for {domain} ({failures} recent failures)")
        _breaker.pop(domain, None)  # cooldown elapsed -> half-open, allow a probe


def _record(domain: str, *, ok: bool) -> None:
    if ok:
        _breaker.pop(domain, None)
    else:
        failures, _ = _breaker.get(domain, (0, 0.0))
        _breaker[domain] = (failures + 1, time.monotonic())


def _fetch_html(url: str) -> str:
    with httpx.Client(timeout=_TIMEOUT_S, follow_redirects=True) as client:
        response = client.get(url, headers={"User-Agent": "deep-research/0.1 (research agent)"})
        response.raise_for_status()
        return response.text[:_MAX_BYTES]


def _extract_text(html: str) -> tuple[str, str]:
    """Return (title, readable_text) from raw HTML."""
    tree = HTMLParser(html)
    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else ""
    for tag in _STRIP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    body = tree.body
    text = body.text(separator=" ", strip=True) if body else ""
    return title, " ".join(text.split())[:_MAX_TEXT_CHARS]


def fetch_url(url: str) -> list[Source]:
    """Fetch one page and return it as a single high-detail source."""
    url = url.strip()
    domain = _check_url_allowed(url)
    _check_breaker(domain)
    try:
        html = _fetch_html(url)
    except Exception:
        _record(domain, ok=False)
        raise
    _record(domain, ok=True)
    title, text = _extract_text(html)
    if not text:
        return []
    return [Source(url=url, title=title or url, snippet=text)]
