from dataclasses import dataclass
from datetime import UTC, datetime

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailSendResult
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.email_provider import EmailProvider
from codrut.modules.communications.templates import (
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import ParticipantProfile


@dataclass(frozen=True)
class AssignmentInvitationContext:
    company_name: str
    trainer_name: str
    action_url: str
    task_count: int = 1


class TransactionalEmailService:
    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    async def send_assignment_invitation(
        self,
        assignment: QuestionnaireAssignment,
        respondent: ParticipantProfile,
        context: AssignmentInvitationContext,
    ) -> EmailSendResult:
        template_key = _select_invitation_template(respondent)
        template = get_transactional_template(template_key)
        message = template.render(
            to=EmailAddress(respondent.email),
            context={
                "participant_name": respondent.full_name,
                "trainer_name": context.trainer_name,
                "company_name": context.company_name,
                "task_count": str(context.task_count),
                "action_url": context.action_url,
            },
        )
        result = await self.provider.send(message)
        if (
            result.status == EmailDeliveryStatus.accepted
            and assignment.status == AssignmentStatus.assigned
        ):
            assignment.status = AssignmentStatus.invited
            assignment.invited_at = datetime.now(UTC)
        return result


def _select_invitation_template(respondent: ParticipantProfile) -> TransactionalTemplateKey:
    if respondent.user_id is None:
        return TransactionalTemplateKey.account_setup
    return TransactionalTemplateKey.assignment_bundle
