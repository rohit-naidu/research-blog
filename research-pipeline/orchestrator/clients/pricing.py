"""
Token pricing table. Updated whenever the labs adjust their rates.

All prices are in USD per million tokens. These are rough estimates that
get refined per-call once the API returns actual usage; the table lets us
estimate cost BEFORE we make a call (for cost-cap checks).

If a model isn't listed here, we use the `default` row, which is set
deliberately high so missing entries err on the side of caution.

NOTE: prices vary by model, deployment, and tier. Verify against the
provider's pricing page periodically. The pipeline still tracks the
actual billed cost via API response metadata where available.
"""

from __future__ import annotations

# Per 1,000,000 tokens. (input, output)
PRICING_USD: dict[str, tuple[float, float]] = {
    # OpenAI flagship reasoning + writing models. Approximate May 2026 pricing.
    "gpt-5": (10.0, 30.0),
    "gpt-5-mini": (0.5, 1.5),
    "o3-deep-research": (15.0, 60.0),
    "o3": (15.0, 60.0),
    # xAI Grok models with live search; the live search itself has a
    # per-source surcharge that we approximate in the call site.
    "grok-4": (5.0, 15.0),
    "grok-4-fast": (1.0, 3.0),
    # Defensive default for any model ID we don't recognize.
    "default": (20.0, 60.0),
}


def estimate_cost_usd(
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> float:
    """Return an estimated USD cost for a call. Defensive defaults."""
    rates = PRICING_USD.get(model, PRICING_USD["default"])
    return (tokens_in / 1_000_000) * rates[0] + (tokens_out / 1_000_000) * rates[1]
