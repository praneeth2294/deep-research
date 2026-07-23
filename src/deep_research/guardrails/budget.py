"""Session budget cap.

Checked *before every LLM call* (wired into the tiering layer): once the
estimated session cost reaches `MAX_SESSION_BUDGET_USD`, the next LLM call
raises instead of spending more. A hard ceiling by construction — no runaway
loop can outspend it by more than one call.
"""

from deep_research.config import get_settings
from deep_research.observability.cost import session_cost


class BudgetExceededError(RuntimeError):
    """Raised when the session's estimated spend reaches the configured cap."""


def check_budget() -> None:
    limit = get_settings().max_session_budget_usd
    spent = session_cost.total_cost_usd()
    if spent >= limit:
        raise BudgetExceededError(
            f"Session budget exhausted: ~${spent:.4f} spent of ${limit:.2f} cap. "
            "Raise MAX_SESSION_BUDGET_USD in .env to allow more."
        )
