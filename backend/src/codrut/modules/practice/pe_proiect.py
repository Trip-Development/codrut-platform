"""Ce ține de un proiect — plicul 185 (Andrei, 30 sept: „pe proiect”).

O ședință nu ține proiectul direct: îl are prin setările programului
(`PracticeSession.program_settings_id` → `PracticeProgramSettings.project_id`, amândouă NOT NULL;
setările sunt unice pe proiect). Memoria lui Cody, momentele și mostrele țin ședința ca text
(`session_id` / `conversation_id` = `str(PracticeSession.id)`), deci legătura se face prin ea.
Aceeași definiție ca unealta de ștergere a plicului 149. Zero coloane noi.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, String, cast, select

from codrut.modules.practice.models import PracticeProgramSettings, PracticeSession


def sedintele_proiectului(project_id: uuid.UUID) -> Select:
    """Id-urile ședințelor proiectului, ca text — pentru `coloana.in_(...)`."""
    return (
        select(cast(PracticeSession.id, String))
        .join(
            PracticeProgramSettings,
            PracticeProgramSettings.id == PracticeSession.program_settings_id,
        )
        .where(PracticeProgramSettings.project_id == project_id)
    )


def toate_sedintele() -> Select:
    """Id-urile tuturor ședințelor, ca text.

    Orice ședință are proiect: ce nu e aici n-are proiect.
    """
    return select(cast(PracticeSession.id, String))
