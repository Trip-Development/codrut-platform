from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.communications.models import EmailTemplate
from codrut.modules.communications.service import validate_template_placeholders
from codrut.modules.forms.models import ProtectedContentImport, QuestionnaireDefinition
from codrut.modules.forms.service import _validate_definition_schema
from codrut.modules.protected_content.package import (
    ProtectedContentPackage,
    content_checksum,
)


@dataclass(frozen=True)
class ProtectedContentResult:
    package_id: str
    checksum: str
    questionnaires: int
    email_templates: int
    status: str


class ProtectedContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_package(self, package: ProtectedContentPackage) -> ProtectedContentResult:
        existing_import = await self._get_import(package.package_id)
        if existing_import is not None:
            if existing_import.checksum != package.checksum:
                raise DomainError(
                    "Package ID was already imported with different content.",
                    code="protected_content_package_conflict",
                )
            return self._result(package, status="already_imported")

        for item in package.questionnaires:
            _validate_definition_schema(item.participant_schema, require_questions=True)
            await self._import_questionnaire(package, item)
        for item in package.email_templates:
            validate_template_placeholders(
                item.subject,
                item.html_body,
                item.text_body,
                item.variables,
                item.key,
            )
            await self._import_template(package, item)

        self.session.add(
            ProtectedContentImport(
                package_id=package.package_id,
                checksum=package.checksum,
                questionnaire_count=len(package.questionnaires),
                template_count=len(package.email_templates),
            )
        )
        await self.session.flush()
        return self._result(package, status="imported")

    async def activate_package(self, package: ProtectedContentPackage) -> ProtectedContentResult:
        imported = await self._get_import(package.package_id)
        if imported is None or imported.checksum != package.checksum:
            raise DomainError(
                "Import this exact protected content package before activation.",
                code="protected_content_not_imported",
            )

        for item in package.questionnaires:
            if not item.activate:
                continue
            result = await self.session.execute(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == item.key,
                    QuestionnaireDefinition.package_id == package.package_id,
                    QuestionnaireDefinition.version == item.version,
                )
            )
            definition = result.scalar_one_or_none()
            if definition is None:
                raise DomainError(
                    f"Imported questionnaire is missing: {item.key}@{item.version}.",
                    code="protected_content_missing_questionnaire",
                )
            siblings = await self.session.execute(
                select(QuestionnaireDefinition).where(QuestionnaireDefinition.key == item.key)
            )
            for sibling in siblings.scalars():
                sibling.active = sibling.id == definition.id

        for item in package.email_templates:
            if not item.activate:
                continue
            result = await self.session.execute(
                select(EmailTemplate).where(
                    EmailTemplate.key == item.key,
                    EmailTemplate.package_id == package.package_id,
                    EmailTemplate.version == item.version,
                )
            )
            template = result.scalar_one_or_none()
            if template is None:
                raise DomainError(
                    f"Imported email template is missing: {item.key}@{item.version}.",
                    code="protected_content_missing_template",
                )
            siblings = await self.session.execute(
                select(EmailTemplate).where(
                    EmailTemplate.key == item.key,
                    EmailTemplate.owner_id.is_(None),
                )
            )
            for sibling in siblings.scalars():
                sibling.active = sibling.id == template.id

        await self.session.flush()
        return self._result(package, status="activated")

    async def _import_questionnaire(self, package, item) -> None:
        checksum = content_checksum(item)
        result = await self.session.execute(
            select(QuestionnaireDefinition).where(
                QuestionnaireDefinition.key == item.key,
                QuestionnaireDefinition.version == item.version,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if (
                existing.system_managed
                and existing.content_checksum == checksum
                and existing.title == item.title
                and (existing.description or "") == item.description
                and existing.schema == item.participant_schema
                and (existing.private_config or {}) == item.private_config
                and existing.feedback_policy == item.feedback_policy
                and existing.trainer_visibility_policy == item.trainer_visibility_policy
            ):
                return
            raise DomainError(
                f"Questionnaire version already exists: {item.key}@{item.version}.",
                code="protected_content_questionnaire_conflict",
            )
        self.session.add(
            QuestionnaireDefinition(
                key=item.key,
                version=item.version,
                title=item.title,
                description=item.description,
                schema=item.participant_schema,
                private_config=item.private_config,
                feedback_policy=item.feedback_policy,
                trainer_visibility_policy=item.trainer_visibility_policy,
                package_id=package.package_id,
                content_checksum=checksum,
                system_managed=True,
                active=False,
            )
        )

    async def _import_template(self, package, item) -> None:
        checksum = content_checksum(item)
        result = await self.session.execute(
            select(EmailTemplate).where(
                EmailTemplate.key == item.key,
                EmailTemplate.version == item.version,
                EmailTemplate.owner_id.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.system_managed and existing.content_checksum == checksum:
                return
            if (
                existing.subject == item.subject
                and existing.html_body == item.html_body
                and existing.text_body == item.text_body
                and existing.variables == item.variables
                and existing.audience == item.audience
            ):
                existing.package_id = package.package_id
                existing.content_checksum = checksum
                existing.system_managed = True
                return
            raise DomainError(
                f"Email template version already exists: {item.key}@{item.version}.",
                code="protected_content_template_conflict",
            )
        self.session.add(
            EmailTemplate(
                key=item.key,
                version=item.version,
                subject=item.subject,
                html_body=item.html_body,
                text_body=item.text_body,
                variables=item.variables,
                audience=item.audience,
                package_id=package.package_id,
                content_checksum=checksum,
                system_managed=True,
                owner_id=None,
                active=False,
            )
        )

    async def _get_import(self, package_id: str) -> ProtectedContentImport | None:
        result = await self.session.execute(
            select(ProtectedContentImport).where(ProtectedContentImport.package_id == package_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _result(package: ProtectedContentPackage, *, status: str) -> ProtectedContentResult:
        return ProtectedContentResult(
            package_id=package.package_id,
            checksum=package.checksum,
            questionnaires=len(package.questionnaires),
            email_templates=len(package.email_templates),
            status=status,
        )
