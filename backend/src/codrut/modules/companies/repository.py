from datetime import datetime
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import QuestionnaireAssignment
from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantAccountLinkAudit,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ParticipantViewAudit,
    ProjectLifecycleEvent,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireResponse,
    QuestionnaireResponseArchive,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity.models import User


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_companies_for_user(self, user_id: UUID) -> list[Company]:
        result = await self.session.execute(
            select(Company)
            .join(CompanyMembership)
            .where(CompanyMembership.user_id == user_id)
            .order_by(Company.name)
        )
        return list(result.scalars().all())

    async def list_all_companies(self) -> list[Company]:
        result = await self.session.execute(select(Company).order_by(Company.name))
        return list(result.scalars().all())

    async def list_company_summaries(
        self,
        user_id: UUID | None = None,
    ) -> list[tuple[Company, int, int, int, int, int]]:
        from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment

        completed_statuses = (
            AssignmentStatus.submitted,
            AssignmentStatus.validated,
            AssignmentStatus.scored,
        )
        participant_counts = (
            select(
                ParticipantProfile.company_id.label("company_id"),
                func.count(ParticipantProfile.id).label("participant_count"),
            )
            .group_by(ParticipantProfile.company_id)
            .subquery()
        )
        assignment_counts = (
            select(
                QuestionnaireAssignment.company_id.label("company_id"),
                func.count(QuestionnaireAssignment.id).label("assignment_count"),
                func.sum(
                    case(
                        (QuestionnaireAssignment.status.in_(completed_statuses), 1),
                        else_=0,
                    )
                ).label("completed_count"),
                func.sum(
                    case(
                        (QuestionnaireAssignment.status == AssignmentStatus.scored, 1),
                        else_=0,
                    )
                ).label("scored_count"),
            )
            .outerjoin(
                CompanyProject,
                CompanyProject.id == QuestionnaireAssignment.project_id,
            )
            .where(
                or_(
                    QuestionnaireAssignment.project_id.is_(None),
                    CompanyProject.status != CompanyProjectStatus.archived,
                )
            )
            .group_by(QuestionnaireAssignment.company_id)
            .subquery()
        )
        project_counts = (
            select(
                CompanyProject.company_id.label("company_id"),
                func.count(CompanyProject.id).label("project_count"),
            )
            .where(CompanyProject.status != CompanyProjectStatus.archived)
            .group_by(CompanyProject.company_id)
            .subquery()
        )
        stmt = (
            select(
                Company,
                func.coalesce(participant_counts.c.participant_count, 0),
                func.coalesce(project_counts.c.project_count, 0),
                func.coalesce(assignment_counts.c.assignment_count, 0),
                func.coalesce(assignment_counts.c.completed_count, 0),
                func.coalesce(assignment_counts.c.scored_count, 0),
            )
            .outerjoin(participant_counts, participant_counts.c.company_id == Company.id)
            .outerjoin(project_counts, project_counts.c.company_id == Company.id)
            .outerjoin(assignment_counts, assignment_counts.c.company_id == Company.id)
            .order_by(Company.name)
        )
        if user_id is not None:
            stmt = stmt.join(
                CompanyMembership,
                CompanyMembership.company_id == Company.id,
            ).where(CompanyMembership.user_id == user_id)
        result = await self.session.execute(stmt)
        return [
            (
                company,
                int(participant_count),
                int(project_count),
                int(assignment_count),
                int(completed_count),
                int(scored_count),
            )
            for (
                company,
                participant_count,
                project_count,
                assignment_count,
                completed_count,
                scored_count,
            ) in result.all()
        ]

    async def get_company(self, company_id: UUID) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def get_company_by_name(self, name: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.name == name))
        return result.scalar_one_or_none()

    async def add_company(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.flush()
        return company

    async def delete_company(self, company: Company) -> None:
        await self.session.delete(company)
        await self.session.flush()

    async def list_projects(
        self,
        company_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[CompanyProject]:
        stmt = select(CompanyProject).where(CompanyProject.company_id == company_id)
        if not include_archived:
            stmt = stmt.where(CompanyProject.status != CompanyProjectStatus.archived)
        result = await self.session.execute(
            stmt.order_by(CompanyProject.created_at.desc(), CompanyProject.name)
        )
        return list(result.scalars().all())

    async def list_projects_with_company(
        self,
        *,
        user_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list[tuple[CompanyProject, str]]:
        stmt = (
            select(CompanyProject, Company.name)
            .join(Company, Company.id == CompanyProject.company_id)
            .order_by(CompanyProject.created_at.desc(), CompanyProject.name)
        )
        if not include_archived:
            stmt = stmt.where(CompanyProject.status != CompanyProjectStatus.archived)
        if user_id is not None:
            stmt = stmt.join(
                CompanyMembership,
                CompanyMembership.company_id == Company.id,
            ).where(CompanyMembership.user_id == user_id)
        result = await self.session.execute(stmt)
        return [(project, company_name) for project, company_name in result.all()]

    async def get_project_by_id(
        self,
        project_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> tuple[CompanyProject, str] | None:
        stmt = (
            select(CompanyProject, Company.name)
            .join(Company, Company.id == CompanyProject.company_id)
            .where(CompanyProject.id == project_id)
        )
        if user_id is not None:
            stmt = stmt.join(
                CompanyMembership,
                CompanyMembership.company_id == Company.id,
            ).where(CompanyMembership.user_id == user_id)
        result = await self.session.execute(stmt.limit(1))
        return result.one_or_none()

    async def get_project(
        self,
        company_id: UUID,
        project_id: UUID,
        *,
        for_update: bool = False,
    ) -> CompanyProject | None:
        statement = (
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .where(CompanyProject.id == project_id)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_project_by_name(
        self,
        company_id: UUID,
        name: str,
    ) -> CompanyProject | None:
        result = await self.session.execute(
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .where(CompanyProject.name == name)
        )
        return result.scalar_one_or_none()

    async def add_project(self, project: CompanyProject) -> CompanyProject:
        self.session.add(project)
        await self.session.flush()
        return project

    async def delete_project(self, project: CompanyProject) -> None:
        await self.session.delete(project)
        await self.session.flush()

    async def add_project_lifecycle_event(
        self,
        event: ProjectLifecycleEvent,
    ) -> ProjectLifecycleEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_project_lifecycle_events(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> list[tuple[ProjectLifecycleEvent, str | None]]:
        result = await self.session.execute(
            select(ProjectLifecycleEvent, User.email)
            .outerjoin(User, User.id == ProjectLifecycleEvent.actor_user_id)
            .where(ProjectLifecycleEvent.company_id == company_id)
            .where(ProjectLifecycleEvent.project_id == project_id)
            .order_by(ProjectLifecycleEvent.created_at.desc())
        )
        return [(event, actor_email) for event, actor_email in result.all()]

    async def add_membership(self, membership: CompanyMembership) -> CompanyMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(self, company_id: UUID, user_id: UUID) -> CompanyMembership | None:
        result = await self.session.execute(
            select(CompanyMembership)
            .where(CompanyMembership.company_id == company_id)
            .where(CompanyMembership.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_participants(self, company_id: UUID) -> list[ParticipantProfile]:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .order_by(ParticipantProfile.full_name)
        )
        return list(result.scalars().all())

    async def get_participant(
        self,
        company_id: UUID,
        participant_id: UUID,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.id == participant_id)
        )
        return result.scalar_one_or_none()

    async def get_participant_for_update(
        self,
        company_id: UUID,
        participant_id: UUID,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.id == participant_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def add_participant_account_link_audit(
        self,
        audit: ParticipantAccountLinkAudit,
    ) -> ParticipantAccountLinkAudit:
        self.session.add(audit)
        await self.session.flush()
        return audit

    async def add_participant_view_audit(
        self,
        audit: ParticipantViewAudit,
    ) -> ParticipantViewAudit:
        self.session.add(audit)
        await self.session.flush()
        return audit

    async def list_participant_view_audits(
        self,
        company_id: UUID,
        *,
        trainer_user_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ParticipantViewAudit]:
        stmt = select(ParticipantViewAudit).where(ParticipantViewAudit.company_id == company_id)
        if trainer_user_id is not None:
            stmt = stmt.where(ParticipantViewAudit.trainer_user_id == trainer_user_id)
        stmt = stmt.order_by(ParticipantViewAudit.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_project_memberships(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> list[tuple[ProjectMembership, ParticipantProfile]]:
        result = await self.session.execute(
            select(ProjectMembership, ParticipantProfile)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == ProjectMembership.participant_profile_id,
            )
            .where(ProjectMembership.company_id == company_id)
            .where(ProjectMembership.project_id == project_id)
            .where(ProjectMembership.active.is_(True))
            .order_by(ParticipantProfile.full_name)
        )
        return [(membership, participant) for membership, participant in result.all()]

    async def list_project_reopen_counters(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> dict[UUID, tuple[int, datetime | None]]:
        """De cate ori a fost redeschis fiecare om din proiect, si cand ultima data.

        Numarul vine din contorul de pe asignari. Data vine dintr-un ``max()``
        peste arhiva, adus ca subinterogare agregata: daca s-ar face join direct
        pe randurile de arhiva, un om cu doua redeschideri ar aparea de doua ori
        si suma contoarelor ar iesi dubla.
        """
        archive_last = (
            select(
                QuestionnaireResponseArchive.assignment_id.label("assignment_id"),
                func.max(QuestionnaireResponseArchive.reopened_at).label("last_reopened_at"),
            )
            .group_by(QuestionnaireResponseArchive.assignment_id)
            .subquery()
        )
        result = await self.session.execute(
            select(
                QuestionnaireAssignment.respondent_profile_id,
                func.coalesce(func.sum(QuestionnaireAssignment.reopen_count), 0),
                func.max(archive_last.c.last_reopened_at),
            )
            .outerjoin(
                archive_last,
                archive_last.c.assignment_id == QuestionnaireAssignment.id,
            )
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.project_id == project_id)
            .group_by(QuestionnaireAssignment.respondent_profile_id)
        )
        return {
            profile_id: (int(total or 0), last_reopened_at)
            for profile_id, total, last_reopened_at in result.all()
        }

    async def list_project_reopenable_assignments(
        self,
        company_id: UUID,
        project_id: UUID,
    ) -> dict[UUID, list[tuple[UUID, str, int]]]:
        """Ce chestionare are fiecare om de redeschis.

        Redeschidem doar ce a fost trimis: fara raspuns trimis nu exista nimic de
        arhivat, iar butonul trebuie sa fie stins, nu sa dea eroare.
        """
        result = await self.session.execute(
            select(
                QuestionnaireAssignment.respondent_profile_id,
                QuestionnaireAssignment.id,
                QuestionnaireAssignment.questionnaire_key,
                QuestionnaireAssignment.reopen_count,
            )
            .join(
                QuestionnaireResponse,
                QuestionnaireResponse.assignment_id == QuestionnaireAssignment.id,
            )
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.project_id == project_id)
            .where(QuestionnaireResponse.status == QuestionnaireResponseStatus.submitted)
            .order_by(
                QuestionnaireAssignment.questionnaire_key,
                QuestionnaireAssignment.id,
            )
        )
        reopenable: dict[UUID, list[tuple[UUID, str, int]]] = {}
        for profile_id, assignment_id, questionnaire_key, reopen_count in result.all():
            reopenable.setdefault(profile_id, []).append(
                (assignment_id, questionnaire_key, int(reopen_count or 0))
            )
        return reopenable

    async def get_project_membership(
        self,
        project_id: UUID,
        participant_profile_id: UUID,
    ) -> ProjectMembership | None:
        result = await self.session.execute(
            select(ProjectMembership)
            .where(ProjectMembership.project_id == project_id)
            .where(ProjectMembership.participant_profile_id == participant_profile_id)
        )
        return result.scalar_one_or_none()

    async def list_project_memberships_for_participant(
        self,
        company_id: UUID,
        participant_profile_id: UUID,
    ) -> list[ProjectMembership]:
        result = await self.session.execute(
            select(ProjectMembership)
            .where(ProjectMembership.company_id == company_id)
            .where(ProjectMembership.participant_profile_id == participant_profile_id)
            .where(ProjectMembership.active.is_(True))
        )
        return list(result.scalars().all())

    async def list_all_project_memberships(
        self,
        company_id: UUID,
    ) -> list[tuple[ProjectMembership, ParticipantProfile]]:
        result = await self.session.execute(
            select(ProjectMembership, ParticipantProfile)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == ProjectMembership.participant_profile_id,
            )
            .where(ProjectMembership.company_id == company_id)
            .order_by(ParticipantProfile.full_name)
        )
        return [(membership, participant) for membership, participant in result.all()]

    async def add_project_membership(
        self,
        membership: ProjectMembership,
    ) -> ProjectMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def delete_project_membership(self, membership: ProjectMembership) -> None:
        await self.session.delete(membership)
        await self.session.flush()

    async def participant_deletion_blockers(self, participant_id: UUID) -> list[str]:
        from codrut.modules.assignments.models import (
            AssessmentCycleTeamMembership,
            QuestionnaireAssignment,
        )
        from codrut.modules.identity.models import AssignmentInvite, ConsentAcceptance
        from codrut.modules.scoring.models import ResultPublication

        result = await self.session.execute(
            select(
                exists()
                .where(
                    or_(
                        QuestionnaireAssignment.respondent_profile_id == participant_id,
                        QuestionnaireAssignment.target_person_id == participant_id,
                    )
                )
                .label("assignments"),
                exists()
                .where(AssessmentCycleTeamMembership.participant_profile_id == participant_id)
                .label("assessment_cycles"),
                exists()
                .where(AssignmentInvite.respondent_profile_id == participant_id)
                .label("invitations"),
                exists()
                .where(ParticipantAccountLinkAudit.participant_profile_id == participant_id)
                .label("account_link_audits"),
                exists()
                .where(ResultPublication.participant_profile_id == participant_id)
                .label("published_results"),
                exists()
                .where(ConsentAcceptance.respondent_profile_id == participant_id)
                .label("consent_history"),
            )
        )
        row = result.one()._mapping
        return [name for name, present in row.items() if present]

    async def delete_participant(self, participant: ParticipantProfile) -> None:
        await self.session.delete(participant)
        await self.session.flush()

    async def replace_reporting_relationships(
        self,
        company_id: UUID,
        relationships: list[ParticipantReportingRelationship],
    ) -> list[ParticipantReportingRelationship]:
        existing = await self.session.execute(
            select(ParticipantReportingRelationship).where(
                ParticipantReportingRelationship.company_id == company_id
            )
        )
        deleted_existing = False
        for relationship in existing.scalars():
            await self.session.delete(relationship)
            deleted_existing = True
        if deleted_existing:
            await self.session.flush()
        for relationship in relationships:
            self.session.add(relationship)
        await self.session.flush()
        return relationships

    async def list_reporting_relationships(
        self,
        company_id: UUID,
    ) -> list[ParticipantReportingRelationship]:
        result = await self.session.execute(
            select(ParticipantReportingRelationship).where(
                ParticipantReportingRelationship.company_id == company_id
            )
        )
        return list(result.scalars().all())

    async def get_participant_by_company_email(
        self,
        company_id: UUID,
        email: str,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_unemailed_participant_by_roster_identity(
        self,
        company_id: UUID,
        *,
        full_name: str,
        reports_to_name: str | None,
        position: str | None,
        location: str | None,
    ) -> ParticipantProfile | None:
        reports_to_filter = (
            ParticipantProfile.reports_to_name.is_(None)
            if reports_to_name is None
            else ParticipantProfile.reports_to_name == reports_to_name
        )
        position_filter = (
            ParticipantProfile.position.is_(None)
            if position is None
            else ParticipantProfile.position == position
        )
        location_filter = (
            ParticipantProfile.location.is_(None)
            if location is None
            else ParticipantProfile.location == location
        )
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.email.is_(None))
            .where(ParticipantProfile.full_name == full_name)
            .where(reports_to_filter)
            .where(position_filter)
            .where(location_filter)
        )
        return result.scalar_one_or_none()

    async def add_participant(self, participant: ParticipantProfile) -> ParticipantProfile:
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def anonymous_name_exists(self, anonymous_name: str) -> bool:
        result = await self.session.execute(
            select(exists().where(ParticipantProfile.anonymous_name == anonymous_name))
        )
        return bool(result.scalar())

    async def add_access_code(self, access_code: CompanyAccessCode) -> CompanyAccessCode:
        self.session.add(access_code)
        await self.session.flush()
        return access_code

    async def get_active_access_code(self, code_hash: str) -> CompanyAccessCode | None:
        result = await self.session.execute(
            select(CompanyAccessCode)
            .where(CompanyAccessCode.code_hash == code_hash)
            .where(CompanyAccessCode.active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_unclaimed_participant_by_company_email(
        self,
        company_id: UUID,
        email: str,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.email == email.lower())
            .where(ParticipantProfile.user_id.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_participant_by_id(self, participant_id: UUID) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id == participant_id)
        )
        return result.scalar_one_or_none()

    async def get_team_by_company_name(self, company_id: UUID, name: str):
        from codrut.modules.assignments.models import Team

        result = await self.session.execute(
            select(Team).where(Team.company_id == company_id).where(Team.name == name)
        )
        return result.scalar_one_or_none()

    async def list_team_memberships_by_team(self, team_id: UUID) -> list:
        from codrut.modules.assignments.models import TeamMembership

        result = await self.session.execute(
            select(TeamMembership).where(TeamMembership.team_id == team_id)
        )
        return list(result.scalars().all())

    async def list_assignments_for_participant(self, participant_id: UUID) -> list:
        from codrut.modules.assignments.models import QuestionnaireAssignment

        result = await self.session.execute(
            select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.respondent_profile_id == participant_id
            )
        )
        return list(result.scalars().all())

    async def list_assignments_for_participants(
        self,
        participant_ids: list[UUID],
    ) -> list:
        from codrut.modules.assignments.models import QuestionnaireAssignment

        if not participant_ids:
            return []

        result = await self.session.execute(
            select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.respondent_profile_id.in_(participant_ids)
            )
        )
        return list(result.scalars().all())
