from __future__ import annotations

from decimal import Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings
from codrut.modules.practice.pricing import estimate_cost


def test_pricing_values_locked():
    """Preturile modelului pe care rulam: gemini-3.8-flash, pret public verificat 20 sept 2026.

    Au fost ale lui gemini-2.5-flash (0.30 / 0.03 / 2.50 / 2.50), verificate 29-30 august 2026, si
    au ramas asa si dupa comutarea pe modelul nou, din 19 septembrie: aplicatia socotea de ~2,4 ori
    mai putin decat adevarul, inclusiv la plafonul care opreste generarea (plicul 101).
    Daca se schimba modelul, se schimba si astea — vezi LISTA-LA-SCHIMBAREA-MODELULUI.md.
    """
    settings = Settings()
    assert settings.price_input_per_million_usd == Decimal("0.75")
    assert settings.price_cached_per_million_usd == Decimal("0.075")
    assert settings.price_output_per_million_usd == Decimal("3.75")
    assert settings.price_thought_per_million_usd == Decimal("3.75")


def test_preturile_se_pot_da_din_mediu(monkeypatch) -> None:
    """Un pret schimbat de furnizor nu mai cere o comitere — plicul 101."""
    monkeypatch.setenv("CODRUT_PRICE_INPUT_PER_MILLION_USD", "1.10")

    assert Settings().price_input_per_million_usd == Decimal("1.10")


def test_pricing_pro_model_values():
    # Ramura „pro" din pricing.py scrie patru preturi direct in cod, ale lui gemini-2.5-pro.
    # Masurat la plicul 101: azi nu se atinge de nimic — niciun model folosit nu contine „pro".
    # Nereparata dinadins: plicul cere s-o spun, nu s-o schimb.
    settings = Settings()
    # 1M input + 1M output on gemini-2.5-pro = 1.25 + 5.00 = 6.25 USD
    usage = TokenUsage(
        prompt_tokens=1_000_000, cached_tokens=0, output_tokens=1_000_000, thought_tokens=0
    )
    cost_pro = estimate_cost(usage, settings, model="gemini-2.5-pro")
    assert cost_pro == Decimal("6.250000")

    # Cached input on gemini-2.5-pro: 1M cached tokens = 0.3125 USD
    usage_cached = TokenUsage(
        prompt_tokens=1_000_000, cached_tokens=1_000_000, output_tokens=0, thought_tokens=0
    )
    cost_cached = estimate_cost(usage_cached, settings, model="gemini-2.5-pro")
    assert cost_cached == Decimal("0.312500")
