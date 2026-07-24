"""Cost accounting v0 (Phase 3).

Token usage is collected by a LangChain `UsageMetadataCallbackHandler` attached
to the graph invocation; dollar cost is estimated from a per-model price table.

v0 limitation (fixed in Phase 7/8): `session_cost` is process-global, which is
correct for the single-run CLI but must become per-request state when the API
server arrives.
"""

from langchain_core.callbacks import UsageMetadataCallbackHandler

# Approximate USD per 1M tokens (input, output). Prices drift - these are for
# budget *guarding*, not billing. Matched by substring, first hit wins.
_PRICE_TABLE: list[tuple[str, float, float]] = [
    ("flash-lite", 0.10, 0.40),
    ("flash", 0.30, 2.50),
    ("pro", 1.25, 10.00),
]
_DEFAULT_PRICE = (0.30, 2.50)  # assume flash-class when unknown


def price_for(model_name: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a model name (substring match)."""
    name = model_name.lower()
    for needle, in_price, out_price in _PRICE_TABLE:
        if needle in name:
            return (in_price, out_price)
    return _DEFAULT_PRICE


_price_for = price_for  # backwards-compatible alias


class CostTracker:
    """Aggregates token usage and estimated cost for one session."""

    def __init__(self) -> None:
        self.callback = UsageMetadataCallbackHandler()

    def reset(self) -> None:
        self.callback = UsageMetadataCallbackHandler()

    def total_tokens(self) -> tuple[int, int]:
        """(input_tokens, output_tokens) across all models."""
        input_tokens = 0
        output_tokens = 0
        for usage in self.callback.usage_metadata.values():
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)
        return input_tokens, output_tokens

    def total_cost_usd(self) -> float:
        cost = 0.0
        for model_name, usage in self.callback.usage_metadata.items():
            in_price, out_price = _price_for(model_name)
            cost += usage.get("input_tokens", 0) / 1_000_000 * in_price
            cost += usage.get("output_tokens", 0) / 1_000_000 * out_price
        return cost

    def summary(self) -> str:
        input_tokens, output_tokens = self.total_tokens()
        lines = [
            f"Cost: ~${self.total_cost_usd():.4f} "
            f"({input_tokens:,} in / {output_tokens:,} out tokens)"
        ]
        for model_name, usage in sorted(self.callback.usage_metadata.items()):
            lines.append(
                f"  {model_name}: {usage.get('input_tokens', 0):,} in / "
                f"{usage.get('output_tokens', 0):,} out"
            )
        return "\n".join(lines)


# Process-global session tracker (CLI = one session). See module docstring.
session_cost = CostTracker()
