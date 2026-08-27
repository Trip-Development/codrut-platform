from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings


def estimate_cost(usage: TokenUsage, settings: Settings) -> Decimal:
    """Calculate the estimated USD cost of a model generation call.

    Formula:
    intrare  = prompt_tokens / 1_000_000 * price_input_per_million_usd
    iesire   = (output_tokens + thought_tokens) / 1_000_000 * price_output_per_million_usd
    total    = (intrare + iesire) rounded to 4 decimal places
    """
    intrare = (
        Decimal(usage.prompt_tokens) / Decimal(1_000_000)
    ) * settings.price_input_per_million_usd
    iesire = (
        Decimal(usage.output_tokens + usage.thought_tokens) / Decimal(1_000_000)
    ) * settings.price_output_per_million_usd
    total = intrare + iesire
    return total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def estimate_pessimistic_cost(
    prompt_tokens: int,
    max_output_tokens: int,
    thinking_budget: int,
    settings: Settings,
) -> Decimal:
    """Calculate pessimistic pre-call estimated USD cost based on maximum allowed limits."""
    usage = TokenUsage(
        prompt_tokens=prompt_tokens,
        output_tokens=max_output_tokens,
        thought_tokens=thinking_budget,
    )
    return estimate_cost(usage, settings)
