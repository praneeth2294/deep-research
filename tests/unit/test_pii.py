"""PII scrubbing: real PII removed, technical lookalikes untouched."""

import pytest

from deep_research.guardrails.pii import scrub_pii


@pytest.mark.parametrize(
    ("text", "expected_kind", "must_not_contain"),
    [
        ("Research market for john.doe@acme.com", "email address", "john.doe@acme.com"),
        ("Call +1 415 555 0123 about pricing", "phone number", "415 555 0123"),
        ("My number is (415) 555-0123", "phone number", "555-0123"),
        ("Reach me at 415-555-0123 today", "phone number", "415-555-0123"),
        ("SSN 078-05-1120 exposure risks", "SSN", "078-05-1120"),
        ("Card 4111 1111 1111 1111 fraud patterns", "payment card number", "4111 1111 1111 1111"),
        ("Why does AIzaSyA1234567890abcdefghijklmnopqrstu leak", "api key", "AIzaSy"),
        ("Found key sk-abcdefghij1234567890xyz in repo", "api key", "sk-abcdefghij"),
        ("AWS key AKIAIOSFODNN7EXAMPLE rotation", "api key", "AKIAIOSFODNN7EXAMPLE"),
    ],
)
def test_pii_is_scrubbed(text: str, expected_kind: str, must_not_contain: str) -> None:
    scrubbed, kinds = scrub_pii(text)
    assert expected_kind in kinds
    assert must_not_contain not in scrubbed


@pytest.mark.parametrize(
    "text",
    [
        "Python 3.12.4 vs 3.13 performance",  # version numbers
        "EU AI Act 2024-2026 implementation timeline",  # year range
        "Order 1234 5678 status handling",  # short digit groups, fails Luhn
        "RFC 9110 HTTP semantics",  # standards numbers
        "The 2010s startup landscape",
    ],
)
def test_technical_text_untouched(text: str) -> None:
    scrubbed, kinds = scrub_pii(text)
    assert scrubbed == text
    assert kinds == []


def test_luhn_gate_rejects_random_16_digits() -> None:
    # 16 digits that fail Luhn must NOT be treated as a card.
    scrubbed, kinds = scrub_pii("ID 1234 5678 9012 3455 in dataset")
    assert "payment card number" not in kinds
    assert "1234 5678 9012 3455" in scrubbed
