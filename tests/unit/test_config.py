"""Unit tests for configuration loading (no .env file, no network)."""

import pytest

from deep_research.config import Settings


def _fresh_settings(**overrides: object) -> Settings:
    # _env_file=None isolates tests from any local .env on the dev machine.
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_defaults_are_safe() -> None:
    s = _fresh_settings()
    assert s.environment == "dev"
    assert s.max_session_budget_usd == 1.0
    assert s.max_react_iterations == 5
    assert s.max_writer_revisions == 2
    assert s.google_api_key is None


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEAP_MODEL", "test-model")
    monkeypatch.setenv("MAX_REACT_ITERATIONS", "3")
    s = _fresh_settings()
    assert s.cheap_model == "test-model"
    assert s.max_react_iterations == 3


def test_secrets_never_leak_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "super-secret-value")
    s = _fresh_settings()
    assert "super-secret-value" not in repr(s)
    assert s.tavily_api_key is not None
    assert s.tavily_api_key.get_secret_value() == "super-secret-value"


def test_invalid_budget_rejected() -> None:
    with pytest.raises(ValueError):
        _fresh_settings(max_session_budget_usd=0)


def test_empty_string_keys_are_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI sets undefined secrets to '' - must read as 'no key', not a key."""
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "   ")
    s = _fresh_settings()
    assert s.google_api_key is None
    assert s.tavily_api_key is None
