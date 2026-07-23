"""PII scrubbing for user input.

The research topic is forwarded to third parties (LLM provider, search APIs) —
personal data has no business being in it. Detected PII is replaced with typed
placeholders; the caller learns *what kinds* were removed, never the values.

Detectors favor precision over recall (a false positive mangles a legitimate
topic): credit cards require a Luhn-valid number, phone patterns are shaped to
avoid year ranges and version numbers.
"""

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_PATTERNS = [
    re.compile(r"\+\d[\d\s.-]{7,14}\d"),  # +14155550123 / +91 98765 43210
    re.compile(r"\(\d{3}\)\s?\d{3}[-.\s]?\d{4}"),  # (415) 555-0123
    re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),  # 415-555-0123
    re.compile(r"\b\d{10}\b"),  # 4155550123
]
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_API_KEY_PATTERNS = [
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),  # Google
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),  # OpenAI-style
    re.compile(r"\btvly-[A-Za-z0-9_-]{10,}\b"),  # Tavily
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),  # GitHub PAT
]


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, char in enumerate(reversed(digits)):
        d = int(char)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Return (scrubbed_text, sorted list of PII kinds that were removed)."""
    found: set[str] = set()

    def _replace(pattern: re.Pattern[str], placeholder: str, kind: str, value: str) -> str:
        nonlocal found
        if pattern.search(value):
            found.add(kind)
            return pattern.sub(placeholder, value)
        return value

    for pattern in _API_KEY_PATTERNS:
        text = _replace(pattern, "[api-key removed]", "api key", text)
    text = _replace(_EMAIL, "[email removed]", "email address", text)
    text = _replace(_SSN, "[ssn removed]", "SSN", text)

    # Credit cards: candidates must pass Luhn, else they're just long numbers.
    def _card_sub(match: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.add("payment card number")
            return "[card removed]"
        return match.group()

    text = _CARD_CANDIDATE.sub(_card_sub, text)

    for pattern in _PHONE_PATTERNS:
        text = _replace(pattern, "[phone removed]", "phone number", text)

    return text, sorted(found)
