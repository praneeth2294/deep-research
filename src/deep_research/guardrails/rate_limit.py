"""Provider rate limiting.

One process-wide token-bucket limiter shared by every LLM client, so parallel
researchers cannot collectively exceed the provider's requests-per-minute cap
(free-tier Gemini enforces low RPM). LangChain's chat models accept the
limiter natively and block until a slot is free.
"""

from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter

from deep_research.config import get_settings


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    settings = get_settings()
    return InMemoryRateLimiter(
        requests_per_second=settings.requests_per_minute / 60.0,
        check_every_n_seconds=0.1,
        max_bucket_size=5,  # small burst allowance for the parallel fan-out
    )
