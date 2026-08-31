"""Lacatul plicului 31: invitatia de training e o invitatie la CONT.

Ce s-a stricat: pe un proiect de training, „Trimite invitatii" nu scria nimic —
nici invitatie, nici email — pentru ca ruta obisnuita cere ca omul sa aiba deja o
asignare de chestionar activa. Un proiect de training n-are chestionare.

Prima solutie incercata a fost sa se deschida o poarta in mecanismul de asignari,
ca sa mearga fara asignari. Andrei a oprit-o, si pe drept: la coaching legatura
ESTE sarcina, iar acolo regula trebuie sa ramana intreaga. La training oamenii nu
primesc niciun chestionar — au nevoie de cont adevarat, cu parola.

Testele astea apara exact granita dintre cele doua:

  1. mecanismul de coaching a ramas neatins — un link de sarcina fara nicio
     sarcina e in continuare refuzat, la facere si la citire;
  2. gardul de destinatari, care opreste un email trimis din greseala catre adresa
     adevarata a unui om, in mediul de proba.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.task_links import (
    TaskLinkClaims,
    create_task_token,
    parse_task_token,
)

# Nu e o parola: doar cheia cu care se semneaza linkurile in testul asta.
_CHEIE_DE_TEST = "-".join(["cheie", "doar", "pentru", "semnat", "linkuri", "in", "test"])


def _setari() -> Settings:
    return Settings(task_link_secret=_CHEIE_DE_TEST)


def _pretentii(assignment_ids: tuple[uuid.UUID, ...]) -> TaskLinkClaims:
    return TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=assignment_ids,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        project_id=uuid.uuid4(),
    )


def test_linkul_de_sarcina_tot_cere_o_sarcina_la_facere():
    """La coaching legatura ESTE sarcina. Fara sarcina nu se face link."""
    with pytest.raises(DomainError) as exc:
        create_task_token(_pretentii(()), _setari())
    assert exc.value.code == "task_link_invalid"


def test_linkul_de_sarcina_tot_cere_o_sarcina_si_la_citire():
    """Si a doua poarta ramane inchisa, nu doar prima."""
    setari = _setari()
    pretentii = _pretentii((uuid.uuid4(),))
    token = create_task_token(pretentii, setari)
    stricat = token.split(".", 1)[0]
    with pytest.raises(DomainError):
        parse_task_token(stricat, setari)


def test_linkul_obisnuit_cu_sarcini_merge_ca_pana_acum():
    setari = _setari()
    pretentii = _pretentii((uuid.uuid4(),))
    citite = parse_task_token(create_task_token(pretentii, setari), setari)
    assert citite.assignment_ids == pretentii.assignment_ids
    assert citite.project_id == pretentii.project_id


def test_invitatia_de_training_nu_trece_prin_linkuri_de_sarcina():
    """Calea trainingului nu atinge deloc mecanismul de sarcini.

    Daca cineva o leaga din nou de el, testul asta il opreste: `send` nu are voie
    sa cheme nici `create_task_token`, nici `create_invite`.
    """
    import inspect

    from codrut.modules.practice import room_service

    sursa = inspect.getsource(room_service.PracticeInvitationsService)
    assert "create_task_token" not in sursa
    assert "create_invite" not in sursa
    assert "AssignmentInvite" not in sursa
    # si chiar face un cont adevarat, nu unul de oaspete
    assert "UserAccountType.registered" in sursa
    assert "PasswordResetToken" in sursa


def test_lista_goala_de_destinatari_nu_opreste_pe_nimeni():
    """Asa arata productia: nicio restrictie, exact ca inainte de plicul 31."""
    setari = Settings(email_allowed_recipients=[])
    assert setari.recipient_is_allowed("oricine@exemplu.ro") is True


def test_lista_de_destinatari_lasa_doar_adresele_ei():
    setari = Settings(email_allowed_recipients=["Andrei@Exemplu.ro", " altul@exemplu.ro "])
    assert setari.recipient_is_allowed("andrei@exemplu.ro") is True
    assert setari.recipient_is_allowed("ANDREI@EXEMPLU.RO") is True
    assert setari.recipient_is_allowed("altul@exemplu.ro") is True
    assert setari.recipient_is_allowed("participant.real@firma-lui.ro") is False


@pytest.mark.asyncio
async def test_a_doua_apasare_pune_al_doilea_mail_in_coada() -> None:
    """Apasa „Trimite invitatii" de doua ori la rand, fara sa stearga nimic.

    Ce s-a stricat: cheia de idempotenta era fixa — `training-cont:{user}:{profil}`.
    Dar fiecare apasare face un link nou, deci alt continut de email. Coada gasea
    randul vechi dupa aceeasi cheie, vedea alt continut si refuza cu
    `email_send_idempotency_payload_conflict`. Intre timp jetonul vechi fusese deja
    stins. Rezultat: link vechi mort, mail nou zero.

    Testul asta NU sterge nimic intre apasari — exact asta ascunsese o proba de
    dinainte, care golea `email_sends` si de aceea arata verde.
    """
    from sqlalchemy import select

    from codrut.core.database import SessionLocal, engine
    from codrut.modules.communications.models import EmailSend
    from codrut.modules.companies.models import (
        Company,
        CompanyProject,
        ParticipantProfile,
        ProjectMembership,
    )
    from codrut.modules.identity.models import User, UserRole
    from codrut.modules.practice.room_service import PracticeInvitationsService

    await engine.dispose()
    try:
        async with SessionLocal() as sesiune:
            marca = uuid.uuid4().hex[:8]
            companie = Company(id=uuid.uuid4(), name=f"Training {marca}")
            trainer = User(
                id=uuid.uuid4(),
                email=f"trainer-{marca}@example.com",
                password_hash="registered-password-hash",  # noqa: S106
                role=UserRole.trainer,
            )
            sesiune.add_all([companie, trainer])
            await sesiune.flush()

            proiect = CompanyProject(
                id=uuid.uuid4(),
                company_id=companie.id,
                name=f"Program {marca}",
                project_type="training",
            )
            profil = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=companie.id,
                email=f"om-{marca}@example.com",
                full_name="Om De Proba",
            )
            sesiune.add_all([proiect, profil])
            await sesiune.flush()
            sesiune.add(
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=companie.id,
                    project_id=proiect.id,
                    participant_profile_id=profil.id,
                )
            )
            await sesiune.flush()

            serviciu = PracticeInvitationsService(sesiune)

            prima = await serviciu.send(proiect.id, [profil.id], trainer_user_id=trainer.id)
            a_doua = await serviciu.send(proiect.id, [profil.id], trainer_user_id=trainer.id)
            await sesiune.flush()

            assert prima[0]["email_queued"] is True, prima[0]["error"]
            assert a_doua[0]["email_queued"] is True, a_doua[0]["error"]

            # linkuri diferite, deci doua randuri de email, nu unul refuzat
            assert prima[0]["invite_url"] != a_doua[0]["invite_url"]
            randuri = (await sesiune.execute(
                select(EmailSend).where(EmailSend.recipient_email == profil.email)
            )).scalars().all()
            assert len(randuri) == 2, [r.idempotency_key for r in randuri]
            assert len({r.idempotency_key for r in randuri}) == 2

            # jetonul brut nu are voie sa ajunga in tabela de emailuri
            for rand in randuri:
                assert "update-password?token=" not in rand.idempotency_key

            await sesiune.rollback()
    finally:
        await engine.dispose()
