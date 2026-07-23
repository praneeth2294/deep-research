"""URL policy — allow/deny rules applied to every URL the system touches.

Layered on top of the scraper's SSRF guard (which blocks private/reserved IP
classes): this layer handles the *policy* dimension — credentials smuggled in
URLs, odd ports, operator-configured blocked domains, and degenerate URLs.

Applied at two choke points:
- the tool registry drops disallowed URLs from every tool's results,
- the scraper refuses to fetch a disallowed URL outright.
"""

from urllib.parse import urlparse

from deep_research.config import get_settings

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_PORTS = {None, 80, 443, 8080, 8443}
_MAX_URL_LENGTH = 2000


class PolicyViolationError(ValueError):
    """Raised when a URL is refused by policy (reason in the message)."""


def evaluate(url: str) -> tuple[bool, str]:
    """Return (allowed, reason). Reason is '' when allowed."""
    if len(url) > _MAX_URL_LENGTH:
        return False, f"URL longer than {_MAX_URL_LENGTH} chars"
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "unparseable URL"
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, f"scheme '{parsed.scheme}' not allowed"
    if parsed.username or parsed.password:
        return False, "credentials embedded in URL"
    try:
        port = parsed.port
    except ValueError:
        return False, "invalid port"
    if port not in _ALLOWED_PORTS:
        return False, f"port {port} not allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing host"
    for blocked in _blocked_domains():
        if host == blocked or host.endswith("." + blocked):
            return False, f"domain '{blocked}' is blocked by policy"
    return True, ""


def check(url: str) -> None:
    """Raise PolicyViolationError when the URL is refused."""
    allowed, reason = evaluate(url)
    if not allowed:
        raise PolicyViolationError(f"URL refused by policy: {reason} ({url[:120]})")


def _blocked_domains() -> list[str]:
    raw = get_settings().blocked_domains
    return [domain.strip().lower() for domain in raw.split(",") if domain.strip()]
