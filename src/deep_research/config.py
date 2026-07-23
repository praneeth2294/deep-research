"""Application configuration.

All runtime configuration comes from environment variables (or a local .env
file), validated once at startup through pydantic-settings. Secrets never
live in code — see .env.example for the full list of supported variables.

Usage:
    from deep_research.config import get_settings

    settings = get_settings()
    settings.cheap_model          # "gemini-2.5-flash"
    settings.tavily_api_key       # SecretStr | None — call .get_secret_value() at use site
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_models(raw: str) -> list[str]:
    return [name.strip() for name in raw.split(",") if name.strip()]


class Settings(BaseSettings):
    """Process-wide configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "staging", "prod"] = "dev"

    # --- Model tiering (Phase 3 wires these into real clients) -------------
    cheap_model: str = Field(
        default="gemini-flash-latest",
        description="Fast/cheap model: router, planner, reviewer, gate-adjacent tasks.",
    )
    strong_model: str = Field(
        default="gemini-3-flash-preview",
        description=(
            "Strong model: analyst, synthesizer, writer. Free-tier keys have no quota "
            "for the pro models (429), so default to a capable flash; override via "
            "STRONG_MODEL when using a paid key."
        ),
    )
    cheap_fallbacks: str = Field(
        default="gemini-3-flash-preview",
        description="Comma-separated fallback models tried when the cheap model fails.",
    )
    strong_fallbacks: str = Field(
        default="gemini-flash-latest",
        description="Comma-separated fallback models tried when the strong model fails.",
    )

    @property
    def cheap_model_chain(self) -> list[str]:
        """Primary cheap model followed by its fallbacks (order matters)."""
        return [self.cheap_model, *_split_models(self.cheap_fallbacks)]

    @property
    def strong_model_chain(self) -> list[str]:
        """Primary strong model followed by its fallbacks (order matters)."""
        return [self.strong_model, *_split_models(self.strong_fallbacks)]

    # --- API keys (optional at import time; call sites fail fast) ----------
    google_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None

    # --- Budgets & hard limits ---------------------------------------------
    max_session_budget_usd: float = Field(default=1.0, gt=0)
    max_react_iterations: int = Field(default=5, ge=1, le=20)
    max_writer_revisions: int = Field(default=2, ge=0, le=5)
    requests_per_minute: int = Field(default=30, ge=1)

    # --- Quality thresholds -------------------------------------------------
    gate_quality_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Research results scoring below this are sent back for replanning.",
    )
    reviewer_pass_score: int = Field(
        default=7, ge=0, le=10, description="Reports scoring >= this are accepted."
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton (one env read per process)."""
    return Settings()
