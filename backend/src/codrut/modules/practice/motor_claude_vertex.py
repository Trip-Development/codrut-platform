"""Al doilea motor: modelele Claude prin Vertex, în UE — plicul 234 (fișa L5, L5-P2).

Primește același `GenerationRequest` și întoarce același `GenerationResult` ca motorul Gemini,
cu aceleași coduri de eroare, ca lanțul din plicul 233 să-l folosească fără să știe că e alt
furnizor. Același cont Google (`vertex_project_id`, `vertex_credentials_path`).

FORMA API-ULUI (adresa, corpul, câmpurile răspunsului, codurile de eroare) e după documentația
publică, NEVERIFICATĂ pe contul nostru. Se probează la L5-P3 (citirea gratuită) și L5-P4 (banca).

Numele modelului, regiunea și prețul NU au valoare implicită: până nu le completează cineva,
cu „da”-ul lui Andrei, motorul nu se poate porni, nici din greșeală (`construieste`).
"""

from __future__ import annotations

import asyncio
import json
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from codrut.contracts.generation import (
    GenerationError,
    GenerationProviderKey,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.practice.generation_provider import HttpxAuthRequest, _urma_apelului
from codrut.modules.practice.pricing import estimate_cost

# După documentația publică, neverificat pe contul nostru.
ANTHROPIC_VERSION = "vertex-2023-10-16"

# Ca la motorul Gemini (plicul 63): pauze scurte, omul așteaptă în fața ecranului.
PAUZE = (2.0, 5.0)
# 529 = „supraîncărcat” la Anthropic; pe Vertex poate veni și ca 429/503 (neverificat).
_REINCERCATE = (429, 503, 529)

# Lista închisă a regiunilor din UE (corecția 2 a controlorului): NU „orice începe cu
# europe-”, fiindcă europe-west2 e Londra și europe-west6 e Zürich, în afara UE.
REGIUNI_UE = (
    "eu",
    "europe-west1",
    "europe-west3",
    "europe-west4",
    "europe-west8",
    "europe-west9",
    "europe-west10",
    "europe-west12",
    "europe-north1",
    "europe-central2",
    "europe-southwest1",
)

# Aceeași regulă a gazdei ca la Gemini (plicul 86); pentru Claude: neverificat.
_MULTI_REGIUNI = ("eu", "us")

_ROLURI = {"user": "user", "model": "assistant"}
_OPRIRI = {"end_turn": "STOP", "stop_sequence": "STOP", "max_tokens": "MAX_TOKENS"}


def _neconfigurat(motiv: str) -> DomainError:
    return DomainError(f"Motorul claude_vertex nu e configurat: {motiv}",
                       code="claude_vertex_neconfigurat")


def _pret_valid(settings: Settings, model: str) -> bool:
    """Rândul modelului în `prices_by_model`: exact 4 valori numerice, finite, nenegative."""
    try:
        tabel = json.loads((settings.prices_by_model or "").strip() or "null")
    except ValueError:
        return False
    if not isinstance(tabel, dict):
        return False
    rand = tabel.get(model)
    if not isinstance(rand, list) or len(rand) != 4:
        return False
    for valoare in rand:
        if isinstance(valoare, bool) or not isinstance(valoare, (int, float, str)):
            return False
        try:
            d = Decimal(str(valoare))
        except InvalidOperation:
            return False
        if not d.is_finite() or d < 0:
            return False
    return True


def construieste(settings: Settings, credentials: Any, client: Any = None
                 ) -> ClaudeVertexGenerationProvider:
    """Verifică setarea înainte de orice cerere; fără model, regiune UE și preț nu pornește.

    Mesajele numesc numai câmpul lipsă sau motivul, nicio valoare din setări.
    """
    lipsa = [camp for camp in ("claude_vertex_model", "claude_vertex_region")
             if not getattr(settings, camp).strip()]
    if lipsa:
        raise _neconfigurat("lipsește " + ", ".join(lipsa))
    if settings.claude_vertex_region not in REGIUNI_UE:
        raise _neconfigurat("regiunea nu e în UE")
    if not _pret_valid(settings, settings.claude_vertex_model):
        raise _neconfigurat("fără preț pentru model în prices_by_model")
    return ClaudeVertexGenerationProvider(settings, credentials, client)


class ClaudeVertexGenerationProvider:
    key = GenerationProviderKey.claude_vertex
    suporta_audio = False

    def __init__(self, settings: Settings, credentials: Any,
                 client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.credentials = credentials
        self._client = client
        self._auth_request = HttpxAuthRequest()

    def _get_access_token_sync(self) -> str:
        if not self.credentials.valid:
            self.credentials.refresh(self._auth_request)
        token = self.credentials.token
        if not token:
            raise GenerationError(
                "Unable to obtain valid Vertex AI access token",
                code="token_acquisition_failed",
            )
        return token

    async def _get_access_token(self) -> str:
        return await asyncio.to_thread(self._get_access_token_sync)

    def _build_url(self) -> str:
        region = self.settings.claude_vertex_region
        gazda = (
            f"https://aiplatform.{region}.rep.googleapis.com"
            if region in _MULTI_REGIUNI
            else f"https://{region}-aiplatform.googleapis.com"
        )
        # `rawPredict` (un singur răspuns), nu `streamRawPredict`: nici Gemini nu e cerut azi
        # pe bucăți, iar rezultatul trebuie să aibă aceeași formă.
        return (
            f"{gazda}/v1/projects/{self.settings.vertex_project_id}/locations/{region}"
            f"/publishers/anthropic/models/{self.settings.claude_vertex_model}:rawPredict"
        )

    @staticmethod
    def _build_payload(request: GenerationRequest) -> dict[str, Any]:
        # `thinking_budget` și `response_mime_type` NU se trimit în acest plic: se hotărăsc
        # la L5-P4, cu banca. Nimic nu se adaugă la mesaje sau la instrucțiune.
        payload: dict[str, Any] = {
            "anthropic_version": ANTHROPIC_VERSION,
            "messages": [
                {"role": _ROLURI[m.role], "content": m.text} for m in request.messages
            ],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.system_instruction is not None:
            payload["system"] = request.system_instruction
        return payload

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        token = await self._get_access_token()
        model = self.settings.claude_vertex_model
        url = self._build_url()
        payload = self._build_payload(request)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        client = self._client
        owns_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=float(self.settings.vertex_timeout_seconds))
            owns_client = True

        response = None
        inceput = time.monotonic()
        scop = request.purpose.value
        incercare = 0
        try:
            for incercare in range(len(PAUZE) + 1):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except Exception as exc:
                    _urma_apelului("vertex_network_error", type(exc).__name__, incercare + 1,
                                   inceput, model, scop)
                    raise GenerationError(
                        f"Claude on Vertex network request failed: {type(exc).__name__}",
                        code="vertex_network_error",
                    ) from exc
                if response.status_code not in _REINCERCATE:
                    break
                if incercare < len(PAUZE):
                    await asyncio.sleep(PAUZE[incercare])
        finally:
            if owns_client:
                await client.aclose()

        assert response is not None
        # Corpul unui răspuns de eroare nu se citește în mesaje și nu se scrie în jurnal.
        if response.status_code in _REINCERCATE:
            _urma_apelului("vertex_rate_limited", response.status_code, len(PAUZE) + 1,
                           inceput, model, scop)
            raise GenerationError(
                f"Claude on Vertex is busy (HTTP {response.status_code}) after "
                f"{len(PAUZE) + 1} tries",
                code="vertex_rate_limited",
                http_status=response.status_code,
            )
        if response.status_code != 200:
            _urma_apelului("vertex_http_error", response.status_code, incercare + 1,
                           inceput, model, scop)
            raise GenerationError(
                f"Claude on Vertex returned HTTP {response.status_code}",
                code="vertex_http_error",
                http_status=response.status_code,
            )

        try:
            data = response.json()
        except Exception as exc:
            _urma_apelului("vertex_invalid_json", 200, incercare + 1, inceput, model, scop)
            raise GenerationError(
                "Invalid JSON response from Claude on Vertex",
                code="vertex_invalid_json",
            ) from exc

        continut = data.get("content") if isinstance(data, dict) else None
        if not isinstance(continut, list):
            _urma_apelului("vertex_no_candidates", 200, incercare + 1, inceput, model, scop)
            raise GenerationError(
                "No content returned from Claude on Vertex",
                code="vertex_no_candidates",
            )

        oprire = data.get("stop_reason")
        finish_reason = _OPRIRI.get(oprire) if isinstance(oprire, str) else None
        if finish_reason is None:
            _urma_apelului("vertex_finish_reason_error", 200, incercare + 1, inceput, model,
                           scop)
            raise GenerationError(
                f"Generation did not finish normally: {oprire or ''}",
                code="vertex_finish_reason_error",
            )

        text = "".join(
            bloc["text"] for bloc in continut
            if isinstance(bloc, dict) and bloc.get("type") == "text"
            and isinstance(bloc.get("text"), str)
        )

        folosit = data.get("usage") if isinstance(data.get("usage"), dict) else {}

        def _numar(camp: str) -> int:
            valoare = folosit.get(camp, 0)
            return valoare if isinstance(valoare, int) and not isinstance(valoare, bool) else 0

        # La Gemini `promptTokenCount` cuprinde și partea din cache (iar `estimate_cost` o
        # scade); la Claude, după documentația publică, `input_tokens` NU le cuprinde.
        cache_citit = _numar("cache_read_input_tokens")
        usage = TokenUsage(
            prompt_tokens=_numar("input_tokens") + cache_citit
            + _numar("cache_creation_input_tokens"),
            output_tokens=_numar("output_tokens"),
            thought_tokens=0,
            cached_tokens=cache_citit,
        )
        return GenerationResult(
            text=text,
            usage=usage,
            provider=self.key,
            model=model,
            region=self.settings.claude_vertex_region,
            finish_reason=finish_reason,
            estimated_usd=estimate_cost(usage, self.settings, model=model),
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
    ) -> tuple[str, TokenUsage, Decimal]:
        raise GenerationError("Motorul Claude pe Vertex nu transcrie audio",
                              code="transcription_unsupported")
