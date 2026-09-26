from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings

logger = logging.getLogger(__name__)

# Preturile stiute, in dolari pe milion: intrare · din cache · iesire · gandire.
#
# Verificate la sursa pe 20 septembrie 2026. Se pot schimba din mediu, fara comitere
# (`CODRUT_PRICES_BY_MODEL`), tocmai ca sa nu imbatraneasca in cod — plicul 101.
TABEL_PRETURI: dict[str, tuple[str, str, str, str]] = {
    "gemini-3.8-flash": ("0.75", "0.075", "3.75", "3.75"),
    "gemini-3.1-flash-lite": ("0.25", "0.025", "1.50", "1.50"),
    "gemini-3.5-flash-lite": ("0.30", "0.03", "2.50", "2.50"),
    # Erau scrise direct in `estimate_cost`, pe o ramura „daca numele contine pro" — chiar
    # boala pe care a reparat-o plicul 101. Acum stau aici, cu celelalte.
    "gemini-2.5-pro": ("1.25", "0.3125", "5.00", "5.00"),
}


def _tabelul(settings: Settings) -> dict[str, tuple[Decimal, Decimal, Decimal, Decimal]]:
    tabel = {m: tuple(Decimal(x) for x in p) for m, p in TABEL_PRETURI.items()}
    brut = (getattr(settings, "prices_by_model", "") or "").strip()
    if brut:
        try:
            for model, preturi in json.loads(brut).items():
                tabel[model] = tuple(Decimal(str(x)) for x in preturi)
        except Exception:
            logger.warning("CODRUT_PRICES_BY_MODEL nu se poate citi; ramane tabelul din cod",
                           exc_info=True)
    return tabel  # type: ignore[return-value]


def _preturile(settings: Settings, model: str | None) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Preturile unui apel, in ordinea: mediu, setarile de azi, tabel, cel mai scump stiut.

    1. fara model (socoteli vechi, estimari) — cele patru setari de azi, neschimbate;
    2. modelul EVALUATORULUI — tot ele: setarile alea descriu modelul principal, si se dau din
       mediu de la plicul 101, deci trebuie sa ramana volanul;
    3. orice alt model cunoscut — randul lui din tabel;
    4. model necunoscut — CEL MAI SCUMP pret din tabel, si un rand in jurnal. Nu trece tacut:
       mai bine numaram mai mult decat adevarul decat mai putin (plicul 101).
    """
    ale_setarilor = (
        settings.price_input_per_million_usd,
        settings.price_cached_per_million_usd,
        settings.price_output_per_million_usd,
        settings.price_thought_per_million_usd,
    )
    if model is None or model == settings.vertex_evaluator_model:
        return ale_setarilor

    tabel = _tabelul(settings)
    if model in tabel:
        return tabel[model]

    cel_mai_scump = max(tabel.values(), key=lambda p: p[0] + p[2])
    logger.warning(
        "pret necunoscut pentru modelul %r; se socoteste la cel mai scump stiut (%s/%s)",
        model, cel_mai_scump[0], cel_mai_scump[2],
    )
    return cel_mai_scump


def estimate_cost(usage: TokenUsage, settings: Settings, model: str | None = None) -> Decimal:
    """Calculate the exact USD cost of a model generation call from usageMetadata tokens.

    Formula:
    intrare_simpla = (prompt_tokens - cached_tokens) / 1_000_000 * price_input_per_million_usd
    intrare_cache  = cached_tokens / 1_000_000 * price_cached_per_million_usd
    iesire         = output_tokens / 1_000_000 * price_output_per_million_usd
    gandire        = thought_tokens / 1_000_000 * price_thought_per_million_usd
    total          = (intrare_simpla + intrare_cache + iesire + gandire)
    """
    price_input, price_cached, price_output, price_thought = _preturile(settings, model)

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
