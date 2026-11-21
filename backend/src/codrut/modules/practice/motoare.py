"""Lista de motoare și comutarea automată — plicul 233 (fișa L5, L5-P1).

Aplicația ține o listă ORDONATĂ de motoare (setarea `generation_engines`) și trece singură la
următorul când primul chiar nu răspunde. Implicit lista are un singur motor (`vertex`), iar
atunci `build_generation_provider` întoarce exact obiectul de azi — lanțul de aici nu se
folosește deloc.

Ce comută: `vertex_rate_limited`, `vertex_network_error`, `vertex_http_error` cu 5xx și un
răspuns gol. Ce NU comută, dinadins: 4xx (cerere greșită: se repară, nu se ascunde), JSON
stricat, `vertex_no_candidates` (poate fi blocarea de siguranță a cererii — ce a oprit
siguranța nu se trimite la alt motor), oprire din alt motiv decât STOP/MAX_TOKENS, tokenul,
orice eroare de cod. Anularea (limita profesorului, plicul 210) nu e o cădere.

Ocolirea ține minte PE PROCES (serviciul se construiește la fiecare cerere): fiecare lucrător
al serverului învață singur pana.

Nu importă decât din `codrut.contracts` și `codrut.core`.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any, Protocol

from codrut.contracts.generation import (
    GenerationError,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError

logger = logging.getLogger("codrut.model")

MOTOARE_CUNOSCUTE = ("vertex",)

_CODURI_CARE_COMUTA = ("vertex_rate_limited", "vertex_network_error")


class _Motor(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def transcribe_audio(
        self, audio_bytes: bytes, mime_type: str = "audio/webm"
    ) -> tuple[str, TokenUsage, Decimal]: ...


def _vertex(settings: Settings, credentials: Any, client: Any) -> _Motor:
    from codrut.modules.practice.generation_provider import VertexGenerationProvider

    return VertexGenerationProvider(settings, credentials=credentials, client=client)


# nume → constructor(settings, credentials, client). Plicul 234 adaugă `claude_vertex`.
CONSTRUCTORI: dict[str, Callable[[Settings, Any, Any], _Motor]] = {"vertex": _vertex}


def citeste_lista(settings: Settings) -> tuple[str, ...]:
    """Lista de motoare din setare: fără spații, litere mici, fără goluri, dubluri, necunoscute.

    Mesajul de eroare numește numai elementul greșit, nimic altceva din setări.
    """
    lista: list[str] = []
    for bucata in settings.generation_engines.split(","):
        nume = bucata.strip().lower()
        if not nume:
            raise DomainError("Lista de motoare are un element gol", code="motoare_invalide")
        if nume in lista:
            raise DomainError(f"Motor repetat în listă: {nume}", code="motoare_invalide")
        if nume not in MOTOARE_CUNOSCUTE:
            raise DomainError(f"Motor necunoscut: {nume}", code="motoare_invalide")
        lista.append(nume)
    return tuple(lista)


@dataclasses.dataclass
class _Fisa:
    caderi: int = 0
    ocolit_pana_la: float = 0.0


class StareaMotoarelor:
    """Căderile la rând și ocolirea, pe nume de motor (ceas monoton)."""

    def __init__(self) -> None:
        self._fise: dict[str, _Fisa] = {}

    def _fisa(self, nume: str) -> _Fisa:
        return self._fise.setdefault(nume, _Fisa())

    def caderi(self, nume: str) -> int:
        return self._fise[nume].caderi if nume in self._fise else 0

    def e_ocolit(self, nume: str, acum: float) -> bool:
        return nume in self._fise and acum < self._fise[nume].ocolit_pana_la

    def cadere(self, nume: str, acum: float, n: int, s: int) -> bool:
        """Numără o cădere; adevărat când tocmai a început o ocolire.

        Contorul se golește numai la o reușită, deci după ce ocolirea expiră o singură
        cădere îl ocolește din nou.
        """
        fisa = self._fisa(nume)
        fisa.caderi += 1
        if fisa.caderi >= n:
            fisa.ocolit_pana_la = acum + s
            return True
        return False

    def reusita(self, nume: str) -> int:
        fisa = self._fisa(nume)
        erau = fisa.caderi
        fisa.caderi = 0
        fisa.ocolit_pana_la = 0.0
        return erau

    def goleste(self) -> None:
        self._fise.clear()


STAREA = StareaMotoarelor()


def se_comuta(exc: BaseException) -> bool:
    if not isinstance(exc, GenerationError):
        return False
    if exc.code in _CODURI_CARE_COMUTA:
        return True
    if exc.code == "vertex_http_error":
        http = getattr(exc, "http_status", None)
        return http is not None and 500 <= http <= 599
    return False


class ComutareMotoare:
    """Respectă `GenerationProvider`: încearcă motoarele în ordine, aceeași cerere, neschimbată."""

    def __init__(
        self,
        motoare: Sequence[tuple[str, _Motor]],
        settings: Settings,
        stare: StareaMotoarelor | None = None,
        ceas: Callable[[], float] = time.monotonic,
    ) -> None:
        self._motoare = list(motoare)
        self._settings = settings
        self._stare = STAREA if stare is None else stare
        self._ceas = ceas

    def _ordinea(self, acum: float) -> list[tuple[str, _Motor]]:
        neocolite = [m for m in self._motoare if not self._stare.e_ocolit(m[0], acum)]
        ocolite = [m for m in self._motoare if self._stare.e_ocolit(m[0], acum)]
        return neocolite + ocolite

    def _cadere(self, nume: str) -> None:
        if self._stare.cadere(
            nume,
            self._ceas(),
            self._settings.generation_engine_skip_after_failures,
            self._settings.generation_engine_skip_seconds,
        ):
            logger.warning(
                "model_ocolit motor=%s caderi=%d secunde_ocolire=%d",
                nume, self._stare.caderi(nume), self._settings.generation_engine_skip_seconds,
            )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        inceput = self._ceas()
        scop = request.purpose.value
        ordinea = self._ordinea(inceput)
        risipit = Decimal("0")
        ultimul_gol: GenerationResult | None = None
        ultima_eroare: GenerationError | None = None
        for i, (nume, motor) in enumerate(ordinea):
            urmatorul = ordinea[i + 1][0] if i + 1 < len(ordinea) else None
            try:
                rezultat = await motor.generate(request)
            except Exception as exc:
                if not se_comuta(exc):
                    raise
                assert isinstance(exc, GenerationError)
                ultima_eroare = exc
                self._cadere(nume)
                if urmatorul is not None:
                    self._jurnal_comutare(nume, urmatorul, exc.code,
                                          getattr(exc, "http_status", None), inceput, scop)
                continue

            if rezultat.text.strip() == "":
                risipit += rezultat.estimated_usd
                ultimul_gol = rezultat
                self._cadere(nume)
                if urmatorul is not None:
                    self._jurnal_comutare(nume, urmatorul, "raspuns_gol", None, inceput, scop)
                    continue
                return dataclasses.replace(rezultat, estimated_usd=risipit)

            erau = self._stare.reusita(nume)
            if erau:
                logger.warning("model_revenit motor=%s dupa_caderi=%d", nume, erau)
            if risipit:
                return dataclasses.replace(
                    rezultat, estimated_usd=rezultat.estimated_usd + risipit
                )
            return rezultat

        # Ultimul a căzut cu o eroare. Dacă un motor de dinainte a dat totuși un răspuns gol,
        # se întoarce acela, cu tot costul (cum se întoarce azi un text gol).
        if ultimul_gol is not None:
            return dataclasses.replace(ultimul_gol, estimated_usd=risipit)
        assert ultima_eroare is not None
        logger.warning(
            "model_toate_motoarele_au_cazut motoare=%s motiv=%s secunde=%.1f scop=%s",
            ",".join(n for n, _ in self._motoare), ultima_eroare.code,
            self._ceas() - inceput, scop,
        )
        raise ultima_eroare

    def _jurnal_comutare(self, de_la: str, la: str, motiv: str, http: int | None,
                         inceput: float, scop: str) -> None:
        logger.warning(
            "model_comutare de_la=%s la=%s motiv=%s http=%s secunde=%.1f scop=%s",
            de_la, la, motiv, "-" if http is None else http, self._ceas() - inceput, scop,
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
    ) -> tuple[str, TokenUsage, Decimal]:
        """Numai primul motor care știe audio; transcrierea nu comută în acest plic."""
        for _nume, motor in self._motoare:
            if getattr(motor, "suporta_audio", True):
                return await motor.transcribe_audio(audio_bytes, mime_type)
        raise GenerationError(
            "No engine in the list supports audio transcription",
            code="transcription_failed",
        )
