"""Plicul 101: socoteala banilor e pe preturile modelului pe care rulam.

Pana azi, preturile erau ale lui gemini-2.5-flash, desi din 19 septembrie ruleaza gemini-3.8-flash.
Nu e doar raportare: aceeasi suma opreste generarea la plafonul pe participant, deci un plafon
socotit cu preturi mici lasa sa treaca de ~2,4 ori mai multi bani decat cere.
"""

from decimal import Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings
from codrut.modules.practice.pricing import estimate_cost, estimate_pessimistic_cost

PRETURI_VECHI = {
    "price_input_per_million_usd": Decimal("0.30"),
    "price_cached_per_million_usd": Decimal("0.03"),
    "price_output_per_million_usd": Decimal("2.50"),
    "price_thought_per_million_usd": Decimal("2.50"),
}


def test_costul_unei_folosiri_cunoscute() -> None:
    # 100.000 intrare din care 50.000 din cache, 1.000 iesire:
    # 0,05 M x 0,75 + 0,05 M x 0,075 + 0,001 M x 3,75 = 0,0375 + 0,00375 + 0,00375
    usage = TokenUsage(
        prompt_tokens=100_000, cached_tokens=50_000, output_tokens=1_000, thought_tokens=0
    )

    assert estimate_cost(usage, Settings()) == Decimal("0.045000")


def test_plafonul_opreste_mai_devreme_decat_inainte() -> None:
    """Acelasi plafon pe participant, dar replicile incap mai putine — asta e miezul."""
    def cate_replici(setari: Settings, plafon: Decimal = Decimal("1.00")) -> int:
        pe_replica = estimate_pessimistic_cost(
            prompt_tokens=40_000, max_output_tokens=1024, thinking_budget=0, settings=setari
        )
        return int(plafon / pe_replica)

    acum = cate_replici(Settings())
    inainte = cate_replici(Settings(**PRETURI_VECHI))

    assert acum < inainte
    assert (acum, inainte) == (29, 68)  # masurat, nu ghicit
