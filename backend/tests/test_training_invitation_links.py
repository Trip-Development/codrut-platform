"""Lacatul plicului 31.

Ce s-a stricat: pe un proiect de training, „Trimite invitatii" nu scria nimic —
nici invitatie, nici email — pentru ca toata masinaria de invitatii cere ca omul
sa aiba deja o asignare de chestionar activa. Un proiect de training n-are
chestionare, deci n-avea cum sa aiba asignari.

Testele astea apara cele doua jumatati ale reparatiei:

  1. poarta ramane INCHISA implicit — un link de chestionar tot trebuie sa poarte
     cel putin o sarcina, deci coaching-ul si evaluarile de pe productie nu se
     schimba cu nimic;
  2. poarta se poate deschide explicit, si atunci linkul de training exista.

Plus gardul de destinatari, care e cel care opreste un email trimis din greseala
catre adresa adevarata a unui om, in mediul de proba.
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


def _setari() -> Settings:
    return Settings(task_link_secret="secret-de-test-pentru-linkuri-0123456789")


def _pretentii(assignment_ids: tuple[uuid.UUID, ...]) -> TaskLinkClaims:
    return TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=assignment_ids,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        project_id=uuid.uuid4(),
    )


def test_linkul_de_chestionar_tot_cere_o_sarcina():
    """Implicit, poarta e inchisa. Asta e purtarea de pe productie, neschimbata."""
    with pytest.raises(DomainError) as exc:
        create_task_token(_pretentii(()), _setari())
    assert exc.value.code == "task_link_invalid"


def test_linkul_de_training_se_face_fara_nicio_sarcina():
    """Doar cu poarta deschisa explicit — si linkul rezultat se poate citi inapoi."""
    setari = _setari()
    pretentii = _pretentii(())
    token = create_task_token(pretentii, setari, allow_without_assignments=True)
    citite = parse_task_token(token, setari)
    assert citite.assignment_ids == ()
    assert citite.respondent_profile_id == pretentii.respondent_profile_id
    assert citite.project_id == pretentii.project_id


def test_linkul_obisnuit_cu_sarcini_merge_ca_pana_acum():
    setari = _setari()
    pretentii = _pretentii((uuid.uuid4(),))
    citite = parse_task_token(create_task_token(pretentii, setari), setari)
    assert citite.assignment_ids == pretentii.assignment_ids


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
