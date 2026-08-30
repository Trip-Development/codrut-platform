from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings


def estimate_cost(usage: TokenUsage, settings: Settings, model: str | None = None) -> Decimal:
    """Calculate the exact USD cost of a model generation call from usageMetadata tokens.

    Formula:
    intrare_simpla = (prompt_tokens - cached_tokens) / 1_000_000 * price_input_per_million_usd
    intrare_cache  = cached_tokens / 1_000_000 * price_cached_per_million_usd
    iesire         = output_tokens / 1_000_000 * price_output_per_million_usd
    gandire        = thought_tokens / 1_000_000 * price_thought_per_million_usd
    total          = (intrare_simpla + intrare_cache + iesire + gandire)
    """
    price_input = settings.price_input_per_million_usd
    price_cached = settings.price_cached_per_million_usd
    price_output = settings.price_output_per_million_usd
    price_thought = settings.price_thought_per_million_usd

    if model and "pro" in model.lower():
        price_input = Decimal("1.25")
        price_cached = Decimal("0.3125")
        price_output = Decimal("5.00")
        price_thought = Decimal("5.00")

    non_cached_prompt = max(0, usage.prompt_tokens - usage.cached_tokens)
    intrare_simpla = (Decimal(non_cached_prompt) / Decimal(1_000_000)) * price_input
    intrare_cache = (Decimal(usage.cached_tokens) / Decimal(1_000_000)) * price_cached
    iesire = (Decimal(usage.output_tokens) / Decimal(1_000_000)) * price_output
    gandire = (Decimal(usage.thought_tokens) / Decimal(1_000_000)) * price_thought

    total = intrare_simpla + intrare_cache + iesire + gandire
    return total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def estimate_pessimistic_cost(
    prompt_tokens: int,
    max_output_tokens: int,
    thinking_budget: int,
    settings: Settings,
    model: str | None = None,
) -> Decimal:
    """Calculate pessimistic pre-call estimated USD cost based on maximum allowed limits."""
    usage = TokenUsage(
        prompt_tokens=prompt_tokens,
        output_tokens=max_output_tokens,
        thought_tokens=thinking_budget,
        cached_tokens=0,
    )
    return estimate_cost(usage, settings, model)
