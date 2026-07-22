import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import EmailDeliveryStatus, EmailMessage, EmailProviderKey
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import EmailSend, EmailSendStatus, EmailTemplate
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    TransactionalEmailService,
)
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity import models as identity_models  # noqa: F401

TEST_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class NeverCalledProvider:
    key = EmailProviderKey.test

    def __init__(self) -> None:
        self.called = False

    async def send(self, _message: EmailMessage) -> None:
        self.called = True
        raise AssertionError("request-time invitation delivery must not call the provider")


class MemoryRepository:
    def __init__(self) -> None:
        self.sends: list[EmailSend] = []

    async def get_template(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def enqueue_email_send(self, send: EmailSend) -> tuple[EmailSend, bool]:
        existing = next(
            (value for value in self.sends if value.idempotency_key == send.idempotency_key),
            None,
        )
        if existing is not None:
            return existing, False
        self.sends.append(send)
        return send, True


class OwnerTemplateRepository(MemoryRepository):
    def __init__(self, templates: dict[uuid.UUID, EmailTemplate]) -> None:
        super().__init__()
        self.templates = templates
        self.lookups: list[tuple[str, uuid.UUID | None]] = []

    async def get_template(
        self,
        key: str,
        *,
        owner_id: uuid.UUID | None = None,
        **_kwargs: Any,
    ) -> EmailTemplate | None:
        self.lookups.append((key, owner_id))
        template = self.templates.get(owner_id) if owner_id is not None else None
        return template if template is not None and template.key == key else None


def make_assignment() -> QuestionnaireAssignment:
    return QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.team,
        target_team_id=uuid.uuid4(),
        status=AssignmentStatus.assigned,
    )


def make_participant(*, role_group: str | None = None) -> ParticipantProfile:
    return ParticipantProfile(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        full_name="Ana Pop",
        email="ana@example.com",
        role_group=role_group,
    )


def make_service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TransactionalEmailService, MemoryRepository, NeverCalledProvider]:
    repository = MemoryRepository()
    provider = NeverCalledProvider()
    monkeypatch.setattr(
        "codrut.modules.communications.service.CommunicationsRepository",
        lambda _session: repository,
    )
    service = TransactionalEmailService(
        provider,
        cast(AsyncSession, object()),
        owner_id=TEST_OWNER_ID,
    )
    return service, repository, provider


async def test_assignment_invitation_enqueues_immutable_account_setup_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, provider = make_service(monkeypatch)
    assignment = make_assignment()
    related_assignment = make_assignment()

    result = await service.send_assignment_invitation(
        assignment,
        make_participant(role_group="leadership"),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://codrut.andreivacaru.ro/invite/token",
            task_count=2,
        ),
        assignment_ids=[assignment.id, related_assignment.id],
    )

    assert result.status == EmailDeliveryStatus.queued
    assert provider.called is False
    assert assignment.status == AssignmentStatus.assigned
    assert assignment.invited_at is None
    send = repository.sends[0]
    assert send.status == EmailSendStatus.queued
    assert send.message_payload is not None
    assert send.message_payload["to"] == "ana@example.com"
    assert "Activează contul" in str(send.message_payload["html_body"])
    assert send.message_payload["assignment_ids"] == [
        str(assignment.id),
        str(related_assignment.id),
    ]


async def test_assignment_invitation_enqueues_bundle_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, provider = make_service(monkeypatch)

    result = await service.send_assignment_invitation(
        make_assignment(),
        make_participant(role_group="member"),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://codrut.andreivacaru.ro/tasks/token",
            task_count=3,
        ),
    )

    assert result.status == EmailDeliveryStatus.queued
    assert provider.called is False
    assert "3 chestionare" in str(repository.sends[0].message_payload["html_body"])


async def test_assignment_invitation_duplicate_enqueue_returns_same_queued_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, provider = make_service(monkeypatch)
    assignment = make_assignment()
    participant = make_participant(role_group="member")
    context = AssignmentInvitationContext(
        company_name="Demo",
        trainer_name="Andrei",
        action_url="https://codrut.andreivacaru.ro/tasks/token",
    )

    first = await service.send_assignment_invitation(
        assignment,
        participant,
        context,
        idempotency_key="stable-invitation-request",
    )
    replay = await service.send_assignment_invitation(
        assignment,
        participant,
        context,
        idempotency_key="stable-invitation-request",
    )

    assert first.status == replay.status == EmailDeliveryStatus.queued
    assert len(repository.sends) == 1
    assert provider.called is False


async def test_assignment_reminder_uses_reminder_template_and_tracks_assignment_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, provider = make_service(monkeypatch)
    assignment = make_assignment()

    result = await service.send_assignment_invitation(
        assignment,
        make_participant(role_group="leadership"),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://codrut.andreivacaru.ro/tasks/token",
        ),
        assignment_ids=[assignment.id],
        reminder_assignment_ids=[assignment.id],
    )

    assert result.status == EmailDeliveryStatus.queued
    assert provider.called is False
    send = repository.sends[0]
    assert send.template_key == "assignment_reminder"
    assert send.message_payload is not None
    assert send.message_payload["delivery_kind"] == "reminder"
    assert send.message_payload["reminder_assignment_ids"] == [str(assignment.id)]
    assert "Continuă chestionarele" in str(send.message_payload["html_body"])


async def test_invitation_template_lookup_and_cache_are_owner_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()

    def template(owner_id: uuid.UUID, label: str) -> EmailTemplate:
        return EmailTemplate(
            id=uuid.uuid4(),
            owner_id=owner_id,
            key="account_setup",
            version=3,
            subject=f"{label}: ${{participant_name}}",
            html_body="<p>${company_name}: ${action_url}</p>",
            text_body="${trainer_name}: ${action_url}",
            variables=[
                "participant_name",
                "trainer_name",
                "company_name",
                "action_url",
            ],
            active=True,
        )

    repository = OwnerTemplateRepository(
        {
            owner_a: template(owner_a, "Trainer A"),
            owner_b: template(owner_b, "Trainer B"),
        }
    )
    monkeypatch.setattr(
        "codrut.modules.communications.service.CommunicationsRepository",
        lambda _session: repository,
    )
    service = TransactionalEmailService(
        NeverCalledProvider(),
        cast(AsyncSession, object()),
        owner_id=owner_a,
    )
    context = AssignmentInvitationContext(
        company_name="Demo",
        trainer_name="Andrei",
        action_url="https://codrut.local/invite",
    )

    await service.send_assignment_invitation(
        make_assignment(),
        make_participant(role_group="leadership"),
        context,
    )
    await service.send_assignment_invitation(
        make_assignment(),
        make_participant(role_group="leadership"),
        context,
    )
    service.owner_id = owner_b
    await service.send_assignment_invitation(
        make_assignment(),
        make_participant(role_group="leadership"),
        context,
    )

    assert repository.lookups == [
        ("account_setup", owner_a),
        ("account_setup", owner_b),
    ]
    assert [send.owner_id for send in repository.sends] == [owner_a, owner_a, owner_b]
    assert [send.message_payload["subject"] for send in repository.sends] == [
        "Trainer A: Ana Pop",
        "Trainer A: Ana Pop",
        "Trainer B: Ana Pop",
    ]
