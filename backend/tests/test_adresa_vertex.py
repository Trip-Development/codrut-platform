"""Plicul 86: adresa Vertex se construieste dupa felul destinatiei. Fara retea.

Regiunile punctuale au gazda `<regiune>-aiplatform.googleapis.com`; multi-regiunile (`eu`, `us`)
au `aiplatform.<loc>.rep.googleapis.com`. Pana la plicul 86 exista doar prima forma, iar cu `eu`
Google raspundea 400, „Invalid hostname".
"""

from unittest.mock import MagicMock

from codrut.core.config import Settings
from codrut.modules.practice.generation_provider import VertexGenerationProvider

CALEA = (
    "/v1/projects/codrut-cody/locations/{loc}"
    "/publishers/google/models/gemini-3.8-flash:generateContent"
)


def _adresa(destinatie: str) -> str:
    setari = Settings(
        generation_provider="vertex",
        vertex_project_id="codrut-cody",
        vertex_region=destinatie,
        vertex_actor_model="gemini-3.8-flash",
    )
    cheie = MagicMock()
    cheie.valid = True
    cheie.token = "jeton-de-test"  # noqa: S105
    furnizor = VertexGenerationProvider(settings=setari, credentials=cheie)
    return furnizor._build_url("gemini-3.8-flash")


def test_regiunea_punctuala_pastreaza_forma_ei() -> None:
    assert _adresa("europe-west4") == (
        "https://europe-west4-aiplatform.googleapis.com" + CALEA.format(loc="europe-west4")
    )


def test_multi_regiunea_eu_are_gazda_rep() -> None:
    assert _adresa("eu") == "https://aiplatform.eu.rep.googleapis.com" + CALEA.format(loc="eu")


def test_multi_regiunea_us_are_gazda_rep() -> None:
    assert _adresa("us") == "https://aiplatform.us.rep.googleapis.com" + CALEA.format(loc="us")


def test_o_destinatie_necunoscuta_pastreaza_forma_veche_si_cade_zgomotos() -> None:
    assert _adresa("nicaieri-1") == (
        "https://nicaieri-1-aiplatform.googleapis.com" + CALEA.format(loc="nicaieri-1")
    )
