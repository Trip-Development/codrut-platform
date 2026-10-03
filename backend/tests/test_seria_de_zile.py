"""„Serie de zile" = zile consecutive cu note, în ora României — plicul 166, partea C.

Până acum seria era maximul dintre zilele calculate și `profile.streak`, un contor vechi care
crește la fiecare ședință închisă: la contul C arăta 19, la liderul complet 2 după două ședințe
în aceeași zi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.scoring import ZONA_ROMANIEI
from test_punctajul_in_tablou import _context_cu_cont, _nota, _sedinta


def _azi_ro_la(ora: int) -> datetime:
    """Azi, la ora dată, în ora României, întors în UTC."""
    azi = datetime.now(ZONA_ROMANIEI).replace(hour=ora, minute=0, second=0, microsecond=0)
    return azi.astimezone(UTC)


@pytest.mark.asyncio
async def test_doua_sedinte_in_aceeasi_zi_fac_o_zi_iar_contorul_vechi_nu_mai_conteaza() -> None:
    async with SessionLocal() as s:
        ctx = await _context_cu_cont(s, "leadership")
        ctx["profile"].streak = 19  # contorul vechi, crescut la fiecare ședință închisă
        await s.flush()
        for ora in (9, 11):
            sed = await _sedinta(s, ctx, SessionKind.roleplay, _azi_ro_la(ora))
            await _nota(s, ctx, sed, 80, _azi_ro_la(ora))
        date = await PracticeDashboardService(s).get_participant_dashboard_data(
            ctx["principal"], ctx["project"].id
        )
        assert date["streak_days"] == 1
        await s.rollback()


@pytest.mark.asyncio
async def test_zile_consecutive_in_ora_romaniei() -> None:
    async with SessionLocal() as s:
        ctx = await _context_cu_cont(s, "leadership")
        await s.flush()
        # ieri la 00:30 în București = alaltăieri seara UTC; plus azi → 2 zile românești la rând
        ieri = (datetime.now(ZONA_ROMANIEI) - timedelta(days=1)).replace(
            hour=0, minute=30, second=0, microsecond=0).astimezone(UTC)
        for cand in (ieri, _azi_ro_la(10)):
            sed = await _sedinta(s, ctx, SessionKind.roleplay, cand)
            await _nota(s, ctx, sed, 80, cand)
        date = await PracticeDashboardService(s).get_participant_dashboard_data(
            ctx["principal"], ctx["project"].id
        )
        assert date["streak_days"] == 2
        await s.rollback()
