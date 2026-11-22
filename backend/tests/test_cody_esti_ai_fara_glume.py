"""Plicul 249 — după «ești AI?», personajul nu se mai întoarce la subiect.

Hotărârea lui Andrei [esti-ai-fara-glume] (21 nov, 19:27): „Aprob propoziția” — textul de mai jos,
cuvânt cu cuvânt. Sursa unică: `SPEC-CODY/FISE/esti-ai-fara-glume-aprobat.txt` (sha256
8933af73…ea6e); constanta a fost scrisă de un script din octeții fișierului, nu tastată.
Paragraful nou e ultimul din `actor.md`, imediat după paragraful 228, deci ajunge pe ambele
drumuri (un apel / două apeluri) și pe obiectiv, dar nu la profesor, quiz sau coaching.
"""

from __future__ import annotations

import hashlib

import pytest

from test_cody_recunoaste_ca_e_ai import PARAGRAF_AI

PROPOZITIE = (
    'După ce ai răspuns, personajul nu se mai întoarce la subiect: nu glumește pe '
    'seama faptului că vorbește cu un AI și nu-i spune omului că discută cu o mașină; '
    'scena merge mai departe exact de unde a rămas.'
)

AMPRENTA_PROPOZITIE = "8933af73ef83ccdf34495e29af0ac43eeccdc52142840c6df26927c150d5ea6e"


def _obiectivul_1() -> dict[str, str]:
    from test_cody_pe_obiectiv_prompturi import _obiectivul_1 as obiectivul

    return obiectivul()


def test_propozitia_e_cea_aprobata() -> None:
    assert hashlib.sha256(PROPOZITIE.encode("utf-8")).hexdigest() == AMPRENTA_PROPOZITIE


def test_e_in_actorul_de_la_un_apel() -> None:
    from codrut.modules.practice.prompts import ACTOR_PROMPT

    assert PROPOZITIE in ACTOR_PROMPT


def test_e_in_actorul_de_la_doua_apeluri() -> None:
    from codrut.modules.practice.prompts import ACTOR_PROMPT_DOUA_APELURI

    assert PROPOZITIE in ACTOR_PROMPT_DOUA_APELURI


@pytest.mark.parametrize("h", [0, 1, 3])
@pytest.mark.parametrize("cu_obiectiv", [False, True])
def test_e_in_promptul_de_role_play(h: int, cu_obiectiv: bool) -> None:
    from codrut.modules.practice.prompts import get_system_prompt_for_kind

    extra = {"obiectiv": _obiectivul_1()} if cu_obiectiv else {}
    prompt = get_system_prompt_for_kind("roleplay", name="Ion", history_length=h, **extra)
    assert PROPOZITIE in prompt


@pytest.mark.parametrize("h", [0, 3])
@pytest.mark.parametrize("tinta", [None, "Ascultare activă"])
@pytest.mark.parametrize("cu_obiectiv", [False, True])
def test_e_in_actorul_pe_meserii(h: int, tinta: str | None, cu_obiectiv: bool) -> None:
    from codrut.modules.practice.prompts import get_prompts_pe_meserii

    extra = {"obiectiv": _obiectivul_1()} if cu_obiectiv else {}
    actor, profesor = get_prompts_pe_meserii(
        name="Ion", history_length=h, memories=[], competenta_tinta=tinta, **extra
    )
    assert PROPOZITIE in actor
    assert PROPOZITIE not in profesor


def test_nu_e_la_quiz_si_la_coaching() -> None:
    from codrut.modules.practice.prompts import REPLICA_DE_CONFIRMARE, get_system_prompt_for_kind

    quiz = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=REPLICA_DE_CONFIRMARE,
        quiz_competency="mix", project_competencies=["A"],
    )
    assert PROPOZITIE not in quiz
    for kind in ("coaching", "research"):
        for h in (0, 3):
            prompt = get_system_prompt_for_kind(kind, name="Ion", history_length=h)
            assert PROPOZITIE not in prompt


def test_vine_imediat_dupa_paragraful_ai() -> None:
    from codrut.modules.practice.prompts import ACTOR_PROMPT, ACTOR_PROMPT_DOUA_APELURI

    for prompt in (ACTOR_PROMPT, ACTOR_PROMPT_DOUA_APELURI):
        assert prompt.rstrip().endswith(PARAGRAF_AI + "\n\n" + PROPOZITIE)


async def _cererile(doua_apeluri: bool, in_fundal: bool, pe_obiectiv: bool) -> list:
    from redis.asyncio import Redis

    from codrut.core.config import Settings
    from codrut.core.database import SessionLocal
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import PracticeProgramSettings, SessionKind
    from codrut.modules.practice.service import PracticeSessionService, asteapta_notele
    from test_cody_pe_obiectiv_pornire import CATALOG, _obiectivele
    from test_practice_session_flow import create_test_context

    settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri,
                        practice_nota_in_fundal=in_fundal)
    furnizor = LocalGenerationProvider(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        extra = {}
        if pe_obiectiv:
            from codrut.modules.practice.objective_service import alege

            setari = await s.get(PracticeProgramSettings, ctx["program_settings"].id)
            setari.objective_catalog = CATALOG
            await s.flush()
            obiective = await _obiectivele(s)
            await alege(s, ctx["principal"], ctx["project"].id, obiective[0].id)
            extra = {"pe_obiectiv": True}
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay, **extra)
        for text in ("Da, hai.", "Înțeleg. Azi nu mai pot, ți-l dau luni la prânz."):
            await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                           text=text)
        await asteapta_notele()
        cereri = list(furnizor.recorded_requests)
        await s.rollback()
        await redis.aclose()
    return cereri


# Combinațiile admise de `config.py`: nota în fundal are efect numai la două apeluri; la un apel
# setarea e citită, dar nu schimbă drumul — se rulează și ea, ca să nu rămână nevăzută.
@pytest.mark.asyncio
@pytest.mark.parametrize("doua_apeluri", [True, False])
@pytest.mark.parametrize("in_fundal", [True, False])
@pytest.mark.parametrize("pe_obiectiv", [False, True])
async def test_ajunge_la_model_pe_toate_drumurile(
    doua_apeluri: bool, in_fundal: bool, pe_obiectiv: bool
) -> None:
    from codrut.contracts.generation import GenerationPurpose

    cereri = await _cererile(doua_apeluri, in_fundal, pe_obiectiv)
    actor = [c for c in cereri if PARAGRAF_AI in (c.system_instruction or "")]
    assert actor, "nicio cerere de actor — testul ar trece în gol"
    for c in actor:
        assert PROPOZITIE in c.system_instruction
    profesor = [c for c in cereri if c.purpose == GenerationPurpose.evaluator]
    if doua_apeluri:
        assert profesor
    for c in profesor:
        assert PROPOZITIE not in (c.system_instruction or "")
