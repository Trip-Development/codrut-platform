"""Plicul 89: transcrierea nu mai poate ajunge la un model pe care nu l-am pus noi.

Rezervele transcrierii erau "gemini-2.5-flash" si "gemini-2.5-pro", scrise in cod. Se retrag pe 16
octombrie si nu raspund la destinatia `eu`. Acum rezerva e o setare, goala implicit.
Fara retea: un raspuns fals da 404 la orice cerere, iar testul numara modelele incercate.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from codrut.contracts.generation import GenerationError
from codrut.core.config import Settings
from codrut.modules.practice.generation_provider import VertexGenerationProvider


async def _modele_incercate(rezerva: str) -> list[str]:
    setari = Settings(
        generation_provider="vertex",
        vertex_project_id="codrut-cody",
        vertex_region="eu",
        vertex_actor_model="gemini-3.8-flash",
        vertex_evaluator_model="gemini-3.8-flash",
        vertex_transcribe_fallback=rezerva,
    )
    cheie = MagicMock()
    cheie.valid = True
    cheie.token = "jeton-de-test"  # noqa: S105
    cereri: list[str] = []

    def raspunde(req: httpx.Request) -> httpx.Response:
        cereri.append(str(req.url).split("/models/")[1].split(":")[0])
        return httpx.Response(404, json={"error": "nu exista"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        furnizor = VertexGenerationProvider(settings=setari, credentials=cheie, client=client)
        with pytest.raises(GenerationError):
            await furnizor.transcribe_audio(b"sunet de proba", "audio/webm")
    return cereri


@pytest.mark.asyncio
async def test_fara_rezerva_se_incearca_doar_modelul_principal() -> None:
    assert await _modele_incercate("") == ["gemini-3.8-flash"]


@pytest.mark.asyncio
async def test_rezerva_vine_doar_din_setari() -> None:
    assert await _modele_incercate("gemini-3.6-flash") == ["gemini-3.8-flash", "gemini-3.6-flash"]
