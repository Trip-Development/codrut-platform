import uuid
from typing import Any, cast

import pytest

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.models import EmailSend, EmailTemplate
from codrut.modules.communications.schemas import (
    EmailTemplateCreateRequest,
    EmailTemplateUpdateRequest,
)
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    CommunicationsService,
    TransactionalEmailService,
)
from codrut.modules.companies.models import ParticipantProfile


class FakeCommunicationsRepository:
    def __init__(self, templates: list[EmailTemplate] | None = None) -> None:
        self.templates = templates or []
        self.sends: list[EmailSend] = []
        self.sent_versions: set[tuple[str, int]] = set()

    async def has_sent_emails(self, key: str, version: int) -> bool:
        return (key, version) in self.sent_versions

    async def list_templates(
        self,
        *,
        active_only: bool = True,
    ) -> list[EmailTemplate]:
        templates = self.templates
        if active_only:
            templates = [t for t in templates if t.active]
        return sorted(templates, key=lambda t: (t.key, -t.version))

    async def get_template(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> EmailTemplate | None:
        templates = [t for t in self.templates if t.key == key]
        if version is None:
            templates = [t for t in templates if t.active]
            return max(templates, key=lambda t: t.version, default=None)
        return next(
            (t for t in templates if t.version == version),
            None,
        )

    async def get_latest_version(self, key: str) -> int:
        versions = [t.version for t in self.templates if t.key == key]
        return max(versions, default=0)

    async def add_template(
        self,
        template: EmailTemplate,
    ) -> EmailTemplate:
        template.id = uuid.uuid4()
        self.templates.append(template)
        return template

    async def deactivate_templates_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
    ) -> None:
        for t in self.templates:
            if t.key == key and t.version != except_version:
                t.active = False


class FakeEmailProvider:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent.append(message)
        return EmailSendResult(
            provider=EmailProviderKey.test,
            status=EmailDeliveryStatus.accepted,
            message_id=f"msg-{uuid.uuid4()}",
            recipient=message.to,
        )


def make_service(repository: FakeCommunicationsRepository) -> CommunicationsService:
    service = CommunicationsService()
    service.repository = cast(Any, repository)
    return service


def persisted_template(
    *,
    key: str = "account_setup",
    version: int = 1,
    active: bool = True,
) -> EmailTemplate:
    return EmailTemplate(
        id=uuid.uuid4(),
        key=key,
        version=version,
        subject="Setup account for ${company_name}",
        html_body=(
            "<p>Buna, ${participant_name}.</p>"
            "<p>Trainer: ${trainer_name}</p>"
            "<p><a href=\"${action_url}\">link</a></p>"
        ),
        text_body="Buna, ${participant_name}. Trainer: ${trainer_name}. link: ${action_url}",
        variables=["participant_name", "trainer_name", "company_name", "action_url"],
        audience="participant",
        active=active,
    )


@pytest.mark.asyncio
async def test_create_template_persists_versioned_structure() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    result = await service.create_template(
        EmailTemplateCreateRequest(
            key="account_setup",
            subject="Welcome, ${participant_name}",
            html_body=(
                "<p>Buna, ${participant_name}. "
                "${trainer_name} ${company_name} ${action_url}</p>"
            ),
            text_body="Buna, ${participant_name}. ${trainer_name} ${company_name} ${action_url}",
            variables=["participant_name", "trainer_name", "company_name", "action_url"],
        )
    )

    assert result.key == "account_setup"
    assert result.version == 1
    assert result.active is True
    assert "Welcome" in result.subject


@pytest.mark.asyncio
async def test_update_template_mutates_unused_version() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    service = make_service(repository)

    result = await service.update_template(
        "account_setup",
        EmailTemplateUpdateRequest(
            subject="New Setup for ${company_name}",
        ),
    )

    assert result.version == 1
    assert result.subject == "New Setup for ${company_name}"
    assert repository.templates[0].subject == "New Setup for ${company_name}"


@pytest.mark.asyncio
async def test_update_template_versions_used_template() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    repository.sent_versions.add(("account_setup", 1))

    service = make_service(repository)

    result = await service.update_template(
        "account_setup",
        EmailTemplateUpdateRequest(
            subject="New Setup for ${company_name}",
        ),
    )

    assert result.version == 2
    assert result.active is True
    assert template.active is False
    assert template.subject == "Setup account for ${company_name}"
    assert repository.templates[1].subject == "New Setup for ${company_name}"


@pytest.mark.asyncio
async def test_activate_template_deactivates_sibling_versions() -> None:
    t1 = persisted_template(version=1, active=False)
    t2 = persisted_template(version=2, active=True)
    repository = FakeCommunicationsRepository([t1, t2])
    service = make_service(repository)

    result = await service.activate_template("account_setup", 1)

    assert result.version == 1
    assert t1.active is True
    assert t2.active is False


@pytest.mark.asyncio
async def test_retire_template_marks_active_false() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    service = make_service(repository)

    result = await service.retire_template("account_setup")

    assert result.active is False
    assert repository.templates == [template]


@pytest.mark.asyncio
async def test_template_validation_missing_required() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    # Missing participant_name which is required for account_setup
    with pytest.raises(DomainError) as exc_info:
        await service.create_template(
            EmailTemplateCreateRequest(
                key="account_setup",
                subject="Test",
                html_body="No vars",
                text_body="No vars",
                variables=[],
            )
        )
    assert exc_info.value.code == "email_template_missing_required_variables"


@pytest.mark.asyncio
async def test_template_validation_undeclared_variables() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.create_template(
            EmailTemplateCreateRequest(
                key="custom_template",
                subject="Welcome ${missing_var}",
                html_body="Hello",
                text_body="Hello",
                variables=[],
            )
        )
    assert exc_info.value.code == "email_template_undeclared_variables"


@pytest.mark.asyncio
async def test_transactional_email_service_uses_db_template() -> None:
    # Set up provider and transactional service
    provider = FakeEmailProvider()
    trans_service = TransactionalEmailService(provider)

    # Inject fake session/service
    class FakeSession:
        def add(self, obj: Any) -> None:
            pass
        async def flush(self) -> None:
            pass
    session = cast(Any, FakeSession())
    trans_service.session = session
    
    # Mock communications service inside trans_service
    async def fake_get_template(key: str, *, version: int | None = None):
        # Return modified subject to verify it was read from database!
        t = persisted_template()
        t.subject = "Custom DB Subject for ${company_name}"
        return t
    
    # We will override the service constructor call
    class MockCommService:
        def __init__(self, s: Any) -> None:
            pass
        async def get_template(self, key: str, *, version: int | None = None):
            return await fake_get_template(key, version=version)
            
    import codrut.modules.communications.service as comm_svc_mod
    original_comm_service = comm_svc_mod.CommunicationsService
    comm_svc_mod.CommunicationsService = MockCommService

    try:
        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="icare",
            target_type="self",
            status=AssignmentStatus.assigned,
        )
        respondent = ParticipantProfile(
            id=uuid.uuid4(),
            full_name="Ana",
            email="ana@example.com",
            user_id=None,  # triggers account_setup
        )
        context = AssignmentInvitationContext(
            company_name="Demo Corp",
            trainer_name="Andrei",
            action_url="http://action",
            task_count=1,
        )

        result = await trans_service.send_assignment_invitation(
            assignment,
            respondent,
            context,
        )

        assert result.status == EmailDeliveryStatus.accepted
        assert len(provider.sent) == 1
        assert provider.sent[0].subject == "Custom DB Subject for Demo Corp"
    finally:
        comm_svc_mod.CommunicationsService = original_comm_service
