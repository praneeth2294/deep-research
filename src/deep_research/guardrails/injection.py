"""Prompt-injection heuristics for scraped/untrusted text.

Web pages and search snippets are UNTRUSTED INPUT that gets pasted into our
prompts. A malicious page can embed instructions ("ignore previous
instructions and ...") hoping the LLM treats them as commands. This module
neutralizes the obvious attempts at the tool boundary — every tool's output
passes through `sanitize_text` before any LLM ever sees it.

Heuristics catch the common patterns, not everything — defense in depth, not
a proof. The grounding rules in our prompts ("only use sources as evidence")
are the second layer.
"""

import re

_REDACTED = "[removed: suspected prompt injection]"

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+|any\s+)?(previous|prior|above|your)\s+instructions",
        r"forget\s+(all\s+|any\s+)?(previous|prior|your)\s+instructions",
        r"you\s+are\s+now\s+(a|an|in)\b",
        r"new\s+system\s+prompt",
        r"reveal\s+(your\s+)?(system\s+prompt|instructions)",
        r"do\s+not\s+(cite|mention|summarize)\s+this",
        r"instead[,]?\s+(output|respond|reply|say)\b",
        r"\bBEGIN\s+(SYSTEM|ADMIN|OVERRIDE)\b",
    ]
]


def contains_injection(text: str) -> bool:
    """True if any known injection pattern appears in the text."""
    return any(pattern.search(text) for pattern in _PATTERNS)


def sanitize_text(text: str) -> str:
    """Replace lines containing injection patterns; leave clean lines untouched."""
    if not contains_injection(text):
        return text
    lines = [
        _REDACTED if contains_injection(line) else line for line in text.splitlines() or [text]
    ]
    return "\n".join(lines)
