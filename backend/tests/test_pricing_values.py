from __future__ import annotations

from decimal import Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings
from codrut.modules.practice.pricing import estimate_cost


def test_pricing_values_locked():
    """preţuri gemini-2.5-flash Vertex AI, verificate 29–30 august 2026; dacă se schimbă modelul, se schimbă și astea, dar conştient."""
    settings = Settings()
    assert settings.price_input_per_million_usd == Decimal("0.30")
    assert settings.price_cached_per_million_usd == Decimal("0.03")
    assert settings.price_output_per_million_usd == Decimal("2.50")
    assert settings.price_thought_per_million_usd == Decimal("2.50")


def test_pricing_pro_model_values():
    settings = Settings()
    # 1M input + 1M output on gemini-2.5-pro = 1.25 + 5.00 = 6.25 USD
    usage = TokenUsage(prompt_tokens=1_000_000, cached_tokens=0, output_tokens=1_000_000, thought_tokens=0)
    cost_pro = estimate_cost(usage, settings, model="gemini-2.5-pro")
    assert cost_pro == Decimal("6.250000")

    # Cached input on gemini-2.5-pro: 1M cached tokens = 0.3125 USD
    usage_cached = TokenUsage(prompt_tokens=1_000_000, cached_tokens=1_000_000, output_tokens=0, thought_tokens=0)
    cost_cached = estimate_cost(usage_cached, settings, model="gemini-2.5-pro")
    assert cost_cached == Decimal("0.312500")
