"""Spre Google pleacă un cod, nu un nume — plicul 138.

Hotărârea lui Andrei, 23 septembrie: la Cody fiecare om are un **cod** (`Fox 34`), iar numele lui
nu pleacă niciodată spre model. Regula lui de la începutul campaniei: „sub nicio formă nu intră
nume de participanți… Nu menționezi niciodată numele lor, dar păstrezi conținutul."

Lacătul e pe singurul punct de trecere — furnizorul de generare: se prinde TOT textul care pleacă
(promptul de sistem și mesajele) la role-play (cu unul și cu două apeluri), strategie, quiz și
închidere (rezumatul și evaluatorul structural), plus memoria din ședințele de dinainte. Niciun
fragment din nume — prenume, nume, fără diacritice, cu litere mici — nu are voie să apară.

Numele e inventat și ușor de căutat; niciun om adevărat.
"""

from __future__ import annotations

import re
import unicodedata

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.alias import ANIMALE, ascunde_numele, cod_nou
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import ParticipantMemory, SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

NUMELE = "Ionela Zăvoianu-Testescu"
# Plicul 142, hotărârea lui Andrei: nici funcția omului nu mai pleacă — numai
# „conduce oameni: da/nu".
FUNCTIA = "Director Regional Mărgineanu Sud"
FRAGMENTE = ("ionela", "zăvoianu", "zavoianu", "testescu", "mărgineanu", "margineanu",
             "director regional")
FORMAT = re.compile(r"^[A-Z][a-z]+ [1-9][0-9]$")

REPLICI = (
    "Da, hai.",
    "Înțeleg ce spui, dar raportul a întârziat a treia oară și echipa a rămas blocată o zi.",
    "Aș vrea să stabilim împreună un termen clar, pe care să-l putem ține amândoi de acum.",
    "Când se întâmplă asta, eu rămân fără timp pentru restul echipei și lucrez seara.",
    "Bine, atunci hai să ne vedem vineri și să verificăm împreună cum a mers săptămâna.",
)


def _fara_diacritice(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _fragmente_gasite(provider: LocalGenerationProvider) -> list[str]:
    gasite = []
    for cerere in provider.recorded_requests:
        bucati = [cerere.system_instruction or "", *(m.text for m in cerere.messages)]
        for text in bucati:
            jos = text.lower()
            for f in FRAGMENTE:
                if f in jos or f in _fara_diacritice(jos):
                    gasite.append(f"{cerere.purpose.value}: …{f}…")
    return gasite


# --------------------------------------------------------------------------- codul


def test_lista_are_40_de_animale_fara_cele_care_jignesc() -> None:
    assert len(ANIMALE) == 40
    assert len(set(ANIMALE)) == 40
    for interzis in ("Pig", "Donkey", "Snake", "Rat", "Weasel", "Cow"):
        assert interzis not in ANIMALE


def test_formatul_codului() -> None:
    for _ in range(200):
        cod = cod_nou()
        assert FORMAT.match(cod), cod
        animal, numar = cod.split(" ")
        assert animal in ANIMALE
        assert 10 <= int(numar) <= 99


def test_numele_se_ascunde_si_fara_diacritice() -> None:
    text = "Ionela a spus clar. zavoianu-testescu a întârziat, IONELA știe. Zăvoianu tace."
    curat = ascunde_numele(text, NUMELE, "Fox 34")
    for f in FRAGMENTE:
        assert f not in _fara_diacritice(curat.lower()), curat
    assert "Fox 34 a spus clar." in curat


def test_un_cuvant_care_doar_incepe_ca_numele_ramane() -> None:
    """Numai cuvinte întregi: „Ionelaș” nu e numele ei, „Testescuul” nici."""
    assert ascunde_numele("Ionelaș și Testescuul", NUMELE, "Fox 34") == "Ionelaș și Testescuul"


# --------------------------------------------------------------------------- lacătul


async def _sedinta(service, ctx, fel: SessionKind, replici: tuple[str, ...]) -> None:
    sedinta, _ = await service.start_session(
        principal=ctx["principal"], project_id=ctx["project"].id, kind=fel
    )
    for replica in replici:
        await service.add_participant_turn(
            principal=ctx["principal"], session_id=sedinta.id, text=replica
        )
    await service.end_session(principal=ctx["principal"], session_id=sedinta.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("doua_apeluri", [False, True])
async def test_niciun_fragment_din_nume_nu_pleaca_spre_model(doua_apeluri: bool) -> None:
    settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri)
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        ctx["profile"].full_name = NUMELE
        ctx["profile"].position = FUNCTIA
        ctx["profile"].role_group = "leadership"
        ctx["program_settings"].quiz_enabled = True
        # Memoria de dinainte: scrisă de model pe vremea când numele pleca, deci îl conține.
        cont = User(
            id=ctx["principal"].user_id,
            email=ctx["principal"].email,
            password_hash="x",  # noqa: S106
            role=UserRole.participant,
        )
        session.add(cont)
        await session.flush()
        session.add(ParticipantMemory(
            user_id=cont.id,
            session_id="sedinta-veche",
            summary="Ionela Zăvoianu-Testescu a cerut un termen clar. Zavoianu a ezitat.",
            key_quotes=["Eu, Ionela, nu mai pot așa."],
            evolution_signals={},
            personal_context={"current_situation": "Ionela conduce o echipă de 6"},
            relevant_competencies=[],
            source_type="roleplay",
            relevance_score=90,
        ))
        await session.flush()

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )
        await _sedinta(service, ctx, SessionKind.roleplay, REPLICI)
        await _sedinta(service, ctx, SessionKind.coaching, REPLICI[1:])
        await _sedinta(service, ctx, SessionKind.knowledge, ("Da, hai.", "B", "C"))

        scopuri = {c.purpose.value for c in provider.recorded_requests}
        assert "summary" in scopuri or "evaluator" in scopuri, scopuri
        assert len(provider.recorded_requests) >= 12
        assert _fragmente_gasite(provider) == []

        # codul, în schimb, pleacă: e numele pe care Cody îl folosește
        cod = ctx["profile"].cody_alias
        assert cod and FORMAT.match(cod)
        assert any(cod in (c.system_instruction or "") for c in provider.recorded_requests)

        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_codul_se_da_o_singura_data_si_ramane() -> None:
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )
        assert ctx["profile"].cody_alias is None
        await _sedinta(service, ctx, SessionKind.roleplay, ("Da, hai.",))
        primul = ctx["profile"].cody_alias
        assert primul and FORMAT.match(primul)
        await _sedinta(service, ctx, SessionKind.coaching, ("Salut.",))
        assert ctx["profile"].cody_alias == primul

        from codrut.modules.companies.models import ParticipantProfile

        la_fel = (await session.execute(
            select(ParticipantProfile).where(ParticipantProfile.cody_alias == primul)
        )).scalars().all()
        assert len(la_fel) == 1

        await session.rollback()
        await redis.aclose()


# --------------------------------------------------------------------------- poarta din unealtă


class _Ecou:
    async def generate(self, cerere):
        return cerere


@pytest.mark.asyncio
async def test_poarta_din_unealta_numara_numele_si_nu_le_arata() -> None:
    from codrut.contracts.generation import GenerationMessage, GenerationRequest
    from codrut.tools.probe_automate import PaznicDeNume
    from codrut.tools.probe_scenarii import COD_PARTICIPANT, PARTICIPANT

    assert PARTICIPANT == NUMELE
    paznic = PaznicDeNume(_Ecou(), ["Andrei Probescu", "user 1"])
    curat = GenerationRequest(
        messages=(GenerationMessage(role="user", text=f"Salut, {COD_PARTICIPANT}."),),
        system_instruction="Andrei a scris materialul. Nu spui „user”.",
    )
    await paznic.generate(curat)
    assert paznic.gasite == 0, "un prenume de cont singur sau „user” nu sunt alarme"

    murdar = GenerationRequest(
        messages=(GenerationMessage(role="user", text="Pe om îl cheamă zavoianu."),),
        system_instruction="andrei probescu a întârziat",
    )
    await paznic.generate(murdar)
    assert paznic.gasite == 2

    # plicul 142: și funcția omului simulat e căutată
    from codrut.tools.probe_scenarii import FUNCTIE_PARTICIPANT

    functie = GenerationRequest(
        messages=(GenerationMessage(role="user", text="salut"),),
        system_instruction=f"Funcția lui în firmă e: {FUNCTIE_PARTICIPANT.lower()}.",
    )
    await paznic.generate(functie)
    assert paznic.gasite == 3


# ------------------------------------------------------------ comanda pentru producție


@pytest.mark.asyncio
async def test_comanda_pentru_productie_numara_zero_si_nu_lasa_nimic() -> None:
    """Rulează pe baza de test ce va rula chatul Aplicației pe copie: zero nume, nimic rămas."""
    from sqlalchemy import func

    from codrut.modules.companies.models import ParticipantProfile
    from codrut.modules.practice.models import PracticeConsent, PracticeSession
    from codrut.tools.numara_nume_spre_model import masoara

    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        ctx["profile"].full_name = NUMELE
        ctx["profile"].position = FUNCTIA
        ctx["profile"].role_group = "leadership"
        proiect = ctx["project"].id
        setari_id = ctx["program_settings"].id
        # ca pe proba si pe productie: omul nu si-a dat inca acordul (plicul 139)
        from sqlalchemy import delete as _delete

        from codrut.modules.practice.models import PracticeConsent

        await session.execute(_delete(PracticeConsent).where(
            PracticeConsent.participant_profile_id == ctx["profile"].id
        ))
        profil_id = ctx["profile"].id
        await session.commit()

    citite, cereri, bucati, intregi, functii = await masoara(proiect)
    assert citite == 1
    assert cereri >= 6
    assert (bucati, intregi, functii) == (0, 0, 0)

    async with SessionLocal() as session:
        ramase = (await session.execute(
            select(func.count(PracticeSession.id))
            .where(PracticeSession.program_settings_id == setari_id)
        )).scalar_one()
        cod = (await session.execute(
            select(ParticipantProfile.cody_alias).where(ParticipantProfile.id == profil_id)
        )).scalar_one()
        assert ramase == 0, "comanda trebuia să întoarcă tranzacția"
        assert cod is None, "nici codul dat în timpul măsurătorii nu rămâne"
        acorduri = (await session.execute(
            select(func.count(PracticeConsent.id))
            .where(PracticeConsent.participant_profile_id == profil_id)
        )).scalar_one()
        assert acorduri == 0, "nici acordul dat în timpul măsurătorii nu rămâne"


def test_numaratoarea_vede_numele_cand_pleaca() -> None:
    """Instrumentul se verifică întâi pe un caz în care TREBUIE să găsească."""
    from codrut.tools.numara_nume_spre_model import numara

    texte = ["pe om il cheama ionela.", "ionela zavoianu-testescu a intarziat"]
    bucati, intregi = numara(texte, NUMELE, [NUMELE, "Radu Probescu"])
    # două apariții ale omului: prenumele singur, apoi numele întreg (numărat o dată, întreg)
    assert bucati == 2
    assert intregi == 1


def test_un_cuvant_generic_din_numele_contului_nu_e_alarma() -> None:
    """Pe probă, un cont se cheamă „user 1", iar regula lui Cody spune „INTERZIS «user»".

    Măsurat la plicul 138, pe serverul de probă: 18 alarme false, toate din cuvântul ăsta.
    """
    from codrut.tools.numara_nume_spre_model import numara

    texte = ["- numele omului: interzis „user”, „participant”."]
    assert numara(texte, "user 1", ["user 1"]) == (0, 0)
    assert ascunde_numele("INTERZIS user", "user 1", "Fox 34") == "INTERZIS user"


@pytest.mark.asyncio
async def test_memoria_scrisa_sub_alt_profil_al_aceluiasi_om_nu_scapa_numele() -> None:
    """Găsit pe probă, la plicul 138: memoria lui Cody e ținută pe CONT, nu pe profil.

    Același om poate avea mai multe profiluri (la companii diferite), cu nume scrise diferit.
    Memoria scrisă sub unul („Dragă <nume>, în acest joc de rol...") pleca spre model și când
    omul exersa sub celălalt. Se curăță de numele tuturor profilurilor lui.
    """
    from codrut.modules.companies.models import Company, ParticipantProfile

    settings = Settings(generation_provider="local", practice_two_calls=True)
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        ctx["profile"].full_name = "user 1"
        cont = User(
            id=ctx["principal"].user_id,
            email=ctx["principal"].email,
            password_hash="x",  # noqa: S106
            role=UserRole.participant,
        )
        alta_firma = Company(name=f"Alta firma {ctx['company'].name}")
        session.add_all([cont, alta_firma])
        await session.flush()
        ctx["profile"].user_id = cont.id
        session.add(ParticipantProfile(
            company_id=alta_firma.id, user_id=cont.id, full_name=NUMELE,
            email=ctx["principal"].email,
        ))
        session.add(ParticipantMemory(
            user_id=cont.id,
            session_id="sedinta-de-sub-celalalt-profil",
            summary="Dragă Ionela Zăvoianu-Testescu, în acest joc de rol ai exersat feedbackul.",
            key_quotes=[],
            evolution_signals={},
            personal_context={},
            relevant_competencies=[],
            source_type="roleplay",
            relevance_score=90,
        ))
        await session.flush()

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )
        await _sedinta(service, ctx, SessionKind.roleplay, REPLICI[:2])
        assert any("joc de rol ai exersat" in (c.system_instruction or "")
                   for c in provider.recorded_requests), "memoria trebuia să ajungă în prompt"
        assert _fragmente_gasite(provider) == []

        await session.rollback()
        await redis.aclose()


def test_un_nume_facut_numai_din_cuvinte_generice_se_ascunde_intreg() -> None:
    """Pe probă, contul folosit de comanda pentru producție se cheamă „Test …" — numai cuvinte
    generice. Memoria lui îl conținea întreg: „Dragă Test Participant, ...". Numele întreg al
    omului devine codul; cuvântul generic singur rămâne."""
    from codrut.tools.numara_nume_spre_model import numara

    text = "Dragă Test Participant, în acest joc de rol ai exersat. Un test simplu."
    curat = ascunde_numele(text, "Test Participant", "Fox 34")
    assert curat == "Dragă Fox 34, în acest joc de rol ai exersat. Un test simplu."
    assert numara([text.lower()], "Test Participant", ["Test Participant"]) == (1, 1)
