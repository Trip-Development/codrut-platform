import uuid

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.email_provider import LocalEmailProvider
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    TransactionalEmailService,
)
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity import models as identity_models  # noqa: F401


class FailingEmailProvider:
    async def send(self, message: EmailMessage) -> EmailSendResult:
        return EmailSendResult(
            provider=EmailProviderKey.test,
            status=EmailDeliveryStatus.failed,
            message_id="failed:test",
            recipient=message.to,
        )


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


def make_participant(*, user_id: uuid.UUID | None = None) -> ParticipantProfile:
    return ParticipantProfile(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=user_id,
        full_name="Ana Pop",
        email="ana@example.com",
    )


async def test_send_assignment_invitation_uses_account_setup_for_unlinked_participant() -> None:
    provider = LocalEmailProvider()
    service = TransactionalEmailService(provider)
    assignment = make_assignment()

    result = await service.send_assignment_invitation(
        assignment,
        make_participant(),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://app.codrut.ro/invite/token",
            task_count=2,
        ),
    )

    assert result.message_id.startswith("test:")
    assert assignment.status == AssignmentStatus.invited
    assert assignment.invited_at is not None
    assert provider.sent_messages[0].to.value == "ana@example.com"
    assert "Activeaza contul" in provider.sent_messages[0].html_body


async def test_send_assignment_invitation_uses_bundle_template_for_existing_account() -> None:
    provider = LocalEmailProvider()
    service = TransactionalEmailService(provider)

    await service.send_assignment_invitation(
        make_assignment(),
        make_participant(user_id=uuid.uuid4()),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://app.codrut.ro/tasks/token",
            task_count=3,
        ),
    )

    assert "3 sarcini" in provider.sent_messages[0].html_body


async def test_send_assignment_invitation_does_not_stamp_failed_send() -> None:
    service = TransactionalEmailService(FailingEmailProvider())
    assignment = make_assignment()

    await service.send_assignment_invitation(
        assignment,
        make_participant(user_id=uuid.uuid4()),
        AssignmentInvitationContext(
            company_name="Demo",
            trainer_name="Andrei",
            action_url="https://app.codrut.ro/tasks/token",
        ),
    )

    assert assignment.status == AssignmentStatus.assigned
    assert assignment.invited_at is None
