"""O instalare care nu-și spune modelul nu pornește — plicul 114, pasul 3.

Până azi, `vertex_actor_model` și `vertex_evaluator_model` aveau valoare implicită în cod:
`gemini-2.5-flash`, modelul care se retrage pe 16 octombrie 2026 și care nu răspunde la
destinația europeană. `compose.prod.yaml` nu trece nicio setare Vertex, deci în ziua în care
producția ar fi chemat modelul ar fi pornit tăcut pe unul mort — **nu la pornire, ci la prima
replică a unui om adevărat.**

Lacătul de aici apără exact asta. Niciun apel la rețea.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codrut.core.config import Settings


def _fara_model(**peste: object) -> dict[str, object]:
    """Setările minime, fără cele două modele."""
    return {"generation_provider": "vertex", **peste}


@pytest.fixture
def mediu_curat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fără modelul din mediu — altfel testul măsoară `conftest`, nu codul.

    `conftest.py` pune cele două variabile pentru toată suita (plicul 114, pasul 2), tocmai ca
    testele să poată porni. Aici ne trebuie opusul: cazul omului care n-a spus nimic.
    """
    monkeypatch.delenv("CODRUT_VERTEX_ACTOR_MODEL", raising=False)
    monkeypatch.delenv("CODRUT_VERTEX_EVALUATOR_MODEL", raising=False)


def test_fara_model_aplicatia_nu_porneste(mediu_curat: None) -> None:
    with pytest.raises(ValidationError) as caz:
        Settings(_env_file=None, **_fara_model())  # type: ignore[arg-type]

    mesaj = str(caz.value)
    assert "vertex_actor_model" in mesaj
    assert "vertex_evaluator_model" in mesaj
    assert "Field required" in mesaj


def test_fara_evaluator_tot_nu_porneste(mediu_curat: None) -> None:
    """Amândouă sunt obligatorii, nu doar prima."""
    with pytest.raises(ValidationError) as caz:
        Settings(_env_file=None, **_fara_model(vertex_actor_model="gemini-3.8-flash"))  # type: ignore[arg-type]

    assert "vertex_evaluator_model" in str(caz.value)


def test_cu_modelul_spus_porneste() -> None:
    setari = Settings(
        _env_file=None,
        **_fara_model(
            vertex_actor_model="gemini-3.8-flash",
            vertex_evaluator_model="gemini-3.8-flash",
        ),  # type: ignore[arg-type]
    )
    assert setari.vertex_actor_model == "gemini-3.8-flash"
    assert setari.vertex_evaluator_model == "gemini-3.8-flash"


def test_niciun_model_mort_in_valorile_implicite() -> None:
    """Nimeni nu pune la loc, din reflex, un model care se retrage."""
    campuri = Settings.model_fields
    for nume in ("vertex_actor_model", "vertex_evaluator_model"):
        assert campuri[nume].is_required(), f"{nume} a primit iar o valoare implicită"
