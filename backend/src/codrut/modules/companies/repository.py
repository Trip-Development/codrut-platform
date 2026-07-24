from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    CompanyProject,
    ParticipantAccountLinkAudit,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectMembership,
)


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
            .group_by(QuestionnaireAssignment.company_id)
            .subquery()
        )
        project_counts = (
            select(
                CompanyProject.company_id.label("company_id"),
                func.count(CompanyProject.id).label("project_count"),
            )
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

    async def list_projects(self, company_id: UUID) -> list[CompanyProject]:
        result = await self.session.execute(
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .order_by(CompanyProject.created_at.desc(), CompanyProject.name)
        )
        return list(result.scalars().all())

    async def list_projects_with_company(
        self,
        *,
        user_id: UUID | None = None,
    ) -> list[tuple[CompanyProject, str]]:
        stmt = (
            select(CompanyProject, Company.name)
            .join(Company, Company.id == CompanyProject.company_id)
            .order_by(CompanyProject.created_at.desc(), CompanyProject.name)
        )
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
    ) -> CompanyProject | None:
        result = await self.session.execute(
            select(CompanyProject)
            .where(CompanyProject.company_id == company_id)
            .where(CompanyProject.id == project_id)
        )
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

    async def add_project_membership(
        self,
        membership: ProjectMembership,
    ) -> ProjectMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

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
