"""Un rând pe fiecare cerere care NU reușește — plicul 140.

Backendul pornește cu `--no-access-log` și rămâne așa: jurnalul complet al fiecărei cereri ar scrie
adrese cu identificatori și ar crește mult. Dar fără nimic, o cerere care pica nu lăsa nicio urmă
pe server — pe 28, în fața oamenilor, n-am fi avut ce citi.

Ce se scrie, numai la 4xx și 5xx: metoda, RUTA (șablonul, `/practice/sessions/{session_id}/turns`,
nu calea cu identificatorii), codul de răspuns, durata, codul erorii din domeniu și identificatorul
cererii (`X-Request-ID`, același din răspuns). O cale fără rută se scrie `(fara ruta)`: ea poate
conține orice a scris cineva în adresă.

Ce NU se scrie, niciodată: parametri (`?...`), corpul cererii, anteturi, cookie-uri, adrese de
email, nume, text scris de om.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import unquote

from fastapi import FastAPI, Request, Response

from codrut.core.request_id import request_id_from_request

logger = logging.getLogger("codrut.cereri")

# pus de `error_response` (core/errors.py): codul erorii din domeniu, fără mesaj și fără detalii
COD_EROARE_STATE_KEY = "cod_eroare"


def _ruta(request: Request) -> str:
    """Calea cererii, cu fiecare parametru înlocuit de numele lui: `/sessions/{session_id}/turns`.

    Nu șablonul rutei: de la FastAPI 0.139 ruterele incluse nu se mai aplatizează, iar ruta din
    `scope` își păstrează calea relativă („/dashboard"). Calea reală nu conține niciodată `?...`.
    """
    if request.scope.get("route") is None:
        return "(fara ruta)"
    # bucată cu bucată, după decodare: un parametru scris codat în adresă („a%40b") tot se prinde
    dupa_valoare = {str(v): f"{{{k}}}" for k, v in request.path_params.items()}
    bucati = request.url.path.split("/")
    return "/".join(dupa_valoare.get(unquote(b), b) for b in bucati)


def install_failed_request_log(app: FastAPI) -> None:
    @app.middleware("http")
    async def urma_erorilor(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        inceput = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            _scrie(request, 500, inceput)
            raise
        if response.status_code >= 400:
            _scrie(request, response.status_code, inceput)
        return response


def _scrie(request: Request, cod: int, inceput: float) -> None:
    logger.warning(
        "cerere_esuata metoda=%s ruta=%s cod=%d ms=%d eroare=%s ref=%s",
        request.method,
        _ruta(request),
        cod,
        int((time.monotonic() - inceput) * 1000),
        getattr(request.state, COD_EROARE_STATE_KEY, None) or "-",
        request_id_from_request(request) or "-",
    )
