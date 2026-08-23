from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleQuestionnaire,
    AssessmentCycleStatus,
    AssessmentCycleTeamMembership,
    AssignmentStatus,
    AssignmentTargetType,
    IcareCohort,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientMembership,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
)
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ParticipantReportingRelationship,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.protected_content.package import canonical_checksum
from codrut.modules.scoring.publication import ResultPublicationService
from codrut.modules.scoring.service import ScoringService
from codrut.tools.local_preview import (
    PREVIEW_DEFINITION_VERSION,
    PREVIEW_PARTICIPANT_EMAIL_DOMAIN,
    PREVIEW_SOURCE,
    assert_local_preview_allowed,
    build_preview_email_templates,
    build_preview_questionnaire_definitions,
    build_sample_answers,
)

PREVIEW_COMPANY_NAMES = (
    "Atelier Meridian",
    "Atlas Mobility Lab",
    "Nova Retail Demo",
)
LEGACY_PREVIEW_COMPANY_NAMES = (
    "E2E Test Company",
    "Pilot Codrut",
    "Pilot Codruț",
)
LEGACY_PREVIEW_COMPANY_PREFIX = "E2E Pilot UI Company "
PREVIEW_CAMPAIGN_NAMES = (
    "Reactivare clienți · iulie",
    "Invitație webinar · draft",
    "Follow-up program · trimis",
)
PREVIEW_EMAIL_TEMPLATES = build_preview_email_templates()
LEGACY_PREVIEW_CAMPAIGN_PREFIX = "Local QA campaign "
PREVIEW_ID_NAMESPACE = uuid.UUID("6f7488d7-4bc4-4a46-97cd-2f8bb7f623da")


def _preview_uuid(*parts: object) -> uuid.UUID:
    """Return a stable UUID for one semantic local-preview record."""
    return uuid.uuid5(PREVIEW_ID_NAMESPACE, ":".join(str(part) for part in parts))


@dataclass(frozen=True)
class PreviewSeedResult:
    trainer_email: str
    participant_email: str
    company_count: int
    project_count: int
    participant_count: int
    assignment_count: int
    campaign_count: int
    contact_count: int


@dataclass(frozen=True)
class CompanyContext:
    company: Company
    project: CompanyProject
    projects: tuple[CompanyProject, ...]
    participants: list[ParticipantProfile]
    team: Team
    cycles: tuple[AssessmentCycle, ...]


async def seed_local_preview(company_name: str | None = None) -> PreviewSeedResult:
    settings = get_settings()
    assert_local_preview_allowed(settings)

    trainer_email = os.getenv("CODRUT_SEED_TRAINER_EMAIL", "trainer@example.com").strip().lower()
    trainer_password = os.getenv(
        "CODRUT_SEED_TRAINER_PASSWORD",
        "replace-with-a-long-test-password",
    )
    participant_email = (
        os.getenv(
            "CODRUT_SEED_PARTICIPANT_EMAIL",
            "participant@example.com",
        )
        .strip()
        .lower()
    )
    participant_password = os.getenv(
        "CODRUT_SEED_PARTICIPANT_PASSWORD",
        "replace-with-a-long-test-password",
    )
    if trainer_email == participant_email:
        raise RuntimeError("Trainer and participant preview accounts require different emails.")

    async with SessionLocal() as session:
        trainer = await _upsert_user(
            session,
            email=trainer_email,
            password=trainer_password,
            role=UserRole.trainer,
        )
        participant_user = await _upsert_user(
            session,
            email=participant_email,
            password=participant_password,
            role=UserRole.participant,
            accept_terms=True,
        )
        await session.flush()

        await _clear_preview_data(session, trainer, participant_user, company_name=company_name)
        definitions = await _replace_preview_definitions(session)
        contexts = await _seed_company_contexts(
            session,
            trainer,
            participant_user,
            definitions,
            target_company_name=company_name,
        )
        assignments = await _seed_assignments(session, contexts, definitions)
        await ResultPublicationService(session).reconcile_all()
        await _seed_invites_and_delivery(session, trainer, contexts, assignments)
        campaign_count, contact_count = await _seed_communications(session, trainer)
        await session.commit()

    project_count = sum(len(context.projects) for context in contexts)
    return PreviewSeedResult(
        trainer_email=trainer_email,
        participant_email=participant_email,
        company_count=len(contexts),
        project_count=project_count,
        participant_count=sum(len(context.participants) for context in contexts),
        assignment_count=len(assignments),
        campaign_count=campaign_count,
        contact_count=contact_count,
    )


async def _upsert_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: UserRole,
    accept_terms: bool = False,
) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            id=_preview_uuid("user", email),
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
    else:
        user.password_hash = hash_password(password)
        user.role = role

    if accept_terms:
        user.terms_accepted_at = datetime.now(UTC)
        user.terms_version = CURRENT_TERMS_VERSION
    return user


async def _clear_preview_data(
    session: AsyncSession,
    trainer: User,
    participant_user: User,
    *,
    company_name: str | None = None,
) -> None:
    if company_name is not None:
        company_ids = list(
            (
                await session.execute(select(Company.id).where(Company.name == company_name))
            ).scalars()
        )
    else:
        preview_company_names = (*PREVIEW_COMPANY_NAMES, *LEGACY_PREVIEW_COMPANY_NAMES)
        company_ids = list(
            (
                await session.execute(
                    select(Company.id).where(
                        or_(
                            Company.name.in_(preview_company_names),
                            Company.name.startswith(LEGACY_PREVIEW_COMPANY_PREFIX),
                            Company.id.in_(
                                select(ParticipantProfile.company_id).where(
                                    ParticipantProfile.user_id == participant_user.id
                                )
                            ),
                        )
                    )
                )
            ).scalars()
        )
    assignment_ids: list[uuid.UUID] = []
    if company_ids:
        assignment_ids = list(
            (
                await session.execute(
                    select(QuestionnaireAssignment.id).where(
                        QuestionnaireAssignment.company_id.in_(company_ids)
                    )
                )
            ).scalars()
        )

    campaigns = list(
        (
            await session.execute(
                select(Campaign).where(
                    Campaign.owner_id == trainer.id,
                    or_(
                        Campaign.name.in_(PREVIEW_CAMPAIGN_NAMES),
                        Campaign.name.startswith(LEGACY_PREVIEW_CAMPAIGN_PREFIX),
                    ),
                )
            )
        ).scalars()
    )
    campaign_ids = [campaign.id for campaign in campaigns]
    contacts = list(
        (
            await session.execute(
                select(CampaignRecipient).where(
                    CampaignRecipient.owner_id == trainer.id,
                    CampaignRecipient.source == PREVIEW_SOURCE,
                )
            )
        ).scalars()
    )
    contact_ids = [contact.id for contact in contacts]

    event_filters = []
    if campaign_ids:
        event_filters.append(CampaignRecipientEvent.campaign_id.in_(campaign_ids))
    if contact_ids:
        event_filters.append(CampaignRecipientEvent.recipient_id.in_(contact_ids))
    if event_filters:
        await session.execute(delete(CampaignRecipientEvent).where(or_(*event_filters)))

    send_filters = []
    if assignment_ids:
        send_filters.append(EmailSend.assignment_id.in_(assignment_ids))
    if campaign_ids:
        send_filters.append(EmailSend.campaign_id.in_(campaign_ids))
    if contact_ids:
        send_filters.append(EmailSend.campaign_recipient_id.in_(contact_ids))
    if send_filters:
        await session.execute(delete(EmailSend).where(or_(*send_filters)))

    if campaign_ids:
        await session.execute(delete(Campaign).where(Campaign.id.in_(campaign_ids)))
    if contact_ids:
        await session.execute(
            delete(CampaignRecipient).where(CampaignRecipient.id.in_(contact_ids))
        )
    await session.execute(
        delete(EmailTemplate).where(
            EmailTemplate.owner_id == trainer.id,
            EmailTemplate.key.in_((*PREVIEW_EMAIL_TEMPLATES, "local_preview_follow_up")),
        )
    )
    if company_ids:
        participant_ids = select(ParticipantProfile.id).where(
            ParticipantProfile.company_id.in_(company_ids)
        )
        await session.execute(
            delete(AssessmentCycleTeamMembership).where(
                AssessmentCycleTeamMembership.participant_profile_id.in_(participant_ids)
            )
        )
        await session.execute(delete(Company).where(Company.id.in_(company_ids)))
    await session.flush()

    known_preview_names = (*PREVIEW_COMPANY_NAMES, *LEGACY_PREVIEW_COMPANY_NAMES)
    if company_name is not None:
        known_preview_names = (*known_preview_names, company_name)
    linked_profile = (
        await session.execute(
            select(ParticipantProfile, Company.name)
            .join(Company, Company.id == ParticipantProfile.company_id)
            .where(
                ParticipantProfile.user_id == participant_user.id,
                Company.name.not_in(known_preview_names),
                ~Company.name.startswith(LEGACY_PREVIEW_COMPANY_PREFIX),
            )
        )
    ).first()
    if linked_profile is not None:
        raise RuntimeError(
            "The local preview participant email is already linked to a non-preview company: "
            f"{linked_profile[1]}. Set CODRUT_SEED_PARTICIPANT_EMAIL to a dedicated address."
        )


async def _replace_preview_definitions(
    session: AsyncSession,
) -> dict[str, QuestionnaireDefinition]:
    preview_definitions = build_preview_questionnaire_definitions()
    keys = [definition.key for definition in preview_definitions]
    active_system_keys = set(
        (
            await session.execute(
                select(QuestionnaireDefinition.key).where(
                    QuestionnaireDefinition.key.in_(keys),
                    QuestionnaireDefinition.system_managed.is_(True),
                    QuestionnaireDefinition.active.is_(True),
                )
            )
        ).scalars()
    )
    existing = list(
        (
            await session.execute(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key.in_(keys),
                    QuestionnaireDefinition.system_managed.is_(False),
                )
            )
        ).scalars()
    )
    for definition in existing:
        definition.active = False

    existing_preview = {d.key: d for d in existing if d.version == PREVIEW_DEFINITION_VERSION}
    persisted: dict[str, QuestionnaireDefinition] = {}
    for definition in preview_definitions:
        content_checksum = canonical_checksum(
            {
                "key": definition.key,
                "version": PREVIEW_DEFINITION_VERSION,
                "title": definition.title,
                "description": definition.description,
                "schema": definition.schema,
                "feedback_policy": definition.feedback_policy,
                "trainer_visibility_policy": {},
            }
        )
        if definition.key in existing_preview:
            model = existing_preview[definition.key]
            model.title = definition.title
            model.description = definition.description
            model.schema = definition.schema
            model.feedback_policy = definition.feedback_policy
            model.content_checksum = content_checksum
            model.active = definition.key not in active_system_keys
        else:
            model = QuestionnaireDefinition(
                id=_preview_uuid(
                    "questionnaire-definition",
                    definition.key,
                    PREVIEW_DEFINITION_VERSION,
                ),
                key=definition.key,
                version=PREVIEW_DEFINITION_VERSION,
                title=definition.title,
                description=definition.description,
                schema=definition.schema,
                feedback_policy=definition.feedback_policy,
                content_checksum=content_checksum,
                active=definition.key not in active_system_keys,
            )
            session.add(model)
        persisted[definition.key] = model
    await session.flush()
    return persisted


async def _seed_company_contexts(
    session: AsyncSession,
    trainer: User,
    participant_user: User,
    definitions: dict[str, QuestionnaireDefinition],
    *,
    target_company_name: str | None = None,
) -> list[CompanyContext]:
    now = datetime.now(UTC)
    company_specs = (
        (
            PREVIEW_COMPANY_NAMES[0],
            "Leadership operațional Q3",
            [
                ("Andrei Radu", participant_user.email, participant_user, "Director operațional"),
                (
                    "Bianca Pavel",
                    f"bianca.pavel@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Director general",
                ),
                (
                    "Sorina Istrate",
                    f"sorina.istrate@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "People lead",
                ),
                (
                    "Darius Neagu",
                    f"darius.neagu@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Manager vânzări",
                ),
                (
                    "Elena Marin",
                    f"elena.marin@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Manager produs",
                ),
                (
                    "Mihai Enache",
                    f"mihai.enache@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Coordonator echipă",
                ),
            ],
        ),
        (
            PREVIEW_COMPANY_NAMES[1],
            "Leadership în mobilitate",
            [
                (
                    "Roxana Matei",
                    f"roxana.matei@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Director regional",
                ),
                (
                    "Tudor Stan",
                    f"tudor.stan@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Manager flotă",
                ),
            ],
        ),
        (
            PREVIEW_COMPANY_NAMES[2],
            "Cohortă management retail",
            [
                (
                    "Ioana Dobre",
                    f"ioana.dobre@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Director magazine",
                ),
                (
                    "Paul Munteanu",
                    f"paul.munteanu@{PREVIEW_PARTICIPANT_EMAIL_DOMAIN}",
                    None,
                    "Manager zonal",
                ),
            ],
        ),
    )

    if target_company_name is not None:
        matching_spec = next(
            (spec for spec in company_specs if spec[0] == target_company_name),
            None,
        )
        if matching_spec is not None:
            active_company_specs = [matching_spec]
        else:
            active_company_specs = [
                (
                    target_company_name,
                    "Leadership operațional Q3",
                    company_specs[0][2],
                )
            ]
    else:
        active_company_specs = list(company_specs)

    contexts: list[CompanyContext] = []
    for company_index, (
        company_name,
        project_name,
        participant_specs,
    ) in enumerate(active_company_specs):
        company = Company(id=_preview_uuid("company", company_name), name=company_name)
        session.add(company)
        await session.flush()
        session.add(
            CompanyMembership(
                id=_preview_uuid("company-membership", company.id, trainer.id),
                company_id=company.id,
                user_id=trainer.id,
                role=CompanyMembershipRole.owner,
            )
        )

        project = CompanyProject(
            id=_preview_uuid("project", company.id, project_name),
            company_id=company.id,
            name=project_name,
            description="Program de leadership pentru aliniere managerială și feedback aplicat.",
            project_type="leadership_program",
            status=CompanyProjectStatus.active,
            starts_at=now - timedelta(days=5 + company_index * 7),
            due_at=now + timedelta(days=21 + company_index * 7),
            form_opens_at=now - timedelta(days=14),
            form_closes_at=now + timedelta(days=21 + company_index * 7),
        )
        session.add(project)
        projects = [project]
        if company_index == 0:
            projects.extend(
                [
                    CompanyProject(
                        id=_preview_uuid("project", company.id, "Coaching managerial aplicat"),
                        company_id=company.id,
                        name="Coaching managerial aplicat",
                        description="Practică managerială și feedback între sesiuni.",
                        project_type="leadership_program",
                        status=CompanyProjectStatus.active,
                        starts_at=now - timedelta(days=30),
                        due_at=now + timedelta(days=10),
                        form_opens_at=now - timedelta(days=5),
                        form_closes_at=now + timedelta(days=10),
                    ),
                    CompanyProject(
                        id=_preview_uuid("project", company.id, "Pregătire cohortă retail"),
                        company_id=company.id,
                        name="Pregătire cohortă retail",
                        description="Cohortă în pregătire.",
                        project_type="cohort_program",
                        status=CompanyProjectStatus.draft,
                        starts_at=now + timedelta(days=35),
                    ),
                    CompanyProject(
                        id=_preview_uuid("project", company.id, "Pilot leadership 2025"),
                        company_id=company.id,
                        name="Pilot leadership 2025",
                        description="Program încheiat, păstrat pentru raportare.",
                        project_type="leadership_program",
                        status=CompanyProjectStatus.completed,
                        starts_at=now - timedelta(days=180),
                        due_at=now - timedelta(days=90),
                    ),
                ]
            )
            session.add_all(projects[1:])

        team = Team(
            id=_preview_uuid("team", company.id, "Echipa de leadership"),
            company_id=company.id,
            name="Echipa de leadership",
            type=TeamType.leadership,
        )
        session.add(team)
        await session.flush()

        participants: list[ParticipantProfile] = []
        for participant_index, (name, email, user, position) in enumerate(participant_specs):
            manager_name = None if participant_index == 0 else participant_specs[0][0]
            profile = ParticipantProfile(
                id=_preview_uuid("participant-profile", company.id, email or name),
                company_id=company.id,
                user_id=user.id if user is not None else None,
                full_name=name,
                email=email,
                reports_to_name=manager_name,
                position=position,
                location="București" if company_index != 1 else "Cluj-Napoca",
                role_group="leadership" if participant_index < 3 else "member",
                pcm_profile=("Gânditor" if participant_index % 2 == 0 else "Empatic"),
                pcm_base=("thinker" if participant_index % 2 == 0 else "harmonizer"),
                pcm_phase=("persister" if participant_index % 2 == 0 else "promoter"),
                anonymous_name=f"Preview-{company_index + 1}{participant_index + 1}",
            )
            session.add(profile)
            await session.flush()
            participants.append(profile)
            session.add_all(
                [
                    ProjectMembership(
                        id=_preview_uuid("project-membership", project.id, profile.id),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=profile.id,
                        reports_to_name=manager_name,
                        position=position,
                        location=profile.location,
                        role_group=profile.role_group,
                        active=True,
                    ),
                    TeamMembership(
                        id=_preview_uuid("team-membership", team.id, profile.id),
                        team_id=team.id,
                        participant_profile_id=profile.id,
                        role=(
                            TeamMembershipRole.leader
                            if participant_index == 0
                            else TeamMembershipRole.member
                        ),
                    ),
                ]
            )

            if company_index == 0 and participant_index < 3:
                session.add(
                    ProjectMembership(
                        id=_preview_uuid("project-membership", projects[1].id, profile.id),
                        company_id=company.id,
                        project_id=projects[1].id,
                        participant_profile_id=profile.id,
                        reports_to_name=manager_name,
                        position=position,
                        location=profile.location,
                        role_group=profile.role_group,
                        active=True,
                    )
                )

        for profile in participants[1:]:
            session.add(
                ParticipantReportingRelationship(
                    id=_preview_uuid(
                        "reporting-relationship",
                        company.id,
                        profile.id,
                        participants[0].id,
                    ),
                    company_id=company.id,
                    participant_profile_id=profile.id,
                    manager_profile_id=participants[0].id,
                )
            )

        cycle_specs = (
            (
                (
                    1,
                    "Evaluare inițială",
                    AssessmentCycleStatus.closed,
                    now - timedelta(days=75),
                    now - timedelta(days=45),
                ),
                (
                    2,
                    "Reevaluare",
                    AssessmentCycleStatus.active,
                    now - timedelta(days=14),
                    None,
                ),
            )
            if company_index == 0
            else (
                (
                    1,
                    "Evaluare curentă",
                    AssessmentCycleStatus.active,
                    now - timedelta(days=14),
                    None,
                ),
            )
        )
        cycles: list[AssessmentCycle] = []
        for sequence, name, status, starts_at, closed_at in cycle_specs:
            cycle = AssessmentCycle(
                id=_preview_uuid("assessment-cycle", project.id, sequence),
                company_id=company.id,
                project_id=project.id,
                sequence=sequence,
                name=name,
                status=status,
                source_cycle_id=cycles[-1].id if cycles else None,
                starts_at=starts_at,
                due_at=(closed_at or now + timedelta(days=21)),
                closed_at=closed_at,
                created_by_user_id=trainer.id,
            )
            session.add(cycle)
            cycles.append(cycle)
            await session.flush()
            for display_order, (key, definition) in enumerate(definitions.items(), start=1):
                session.add(
                    AssessmentCycleQuestionnaire(
                        id=_preview_uuid("cycle-questionnaire", cycle.id, key),
                        assessment_cycle_id=cycle.id,
                        questionnaire_definition_id=definition.id,
                        questionnaire_key=key,
                        display_order=display_order,
                    )
                )
            for participant_index, profile in enumerate(participants):
                session.add(
                    AssessmentCycleTeamMembership(
                        id=_preview_uuid("cycle-team-membership", cycle.id, team.id, profile.id),
                        assessment_cycle_id=cycle.id,
                        team_id=team.id,
                        participant_profile_id=profile.id,
                        role=(
                            TeamMembershipRole.leader
                            if participant_index == 0
                            else TeamMembershipRole.member
                        ),
                    )
                )
        contexts.append(
            CompanyContext(
                company=company,
                project=project,
                projects=tuple(projects),
                participants=participants,
                team=team,
                cycles=tuple(cycles),
            )
        )

    await session.flush()
    return contexts


async def _seed_assignments(
    session: AsyncSession,
    contexts: list[CompanyContext],
    definitions: dict[str, QuestionnaireDefinition],
) -> list[QuestionnaireAssignment]:
    now = datetime.now(UTC)
    assignments: list[QuestionnaireAssignment] = []
    assignment_rounds: dict[uuid.UUID, uuid.UUID] = {}
    assignment_identity_counts: dict[str, int] = {}

    def add_assignment(
        context: CompanyContext,
        respondent: ParticipantProfile,
        key: str,
        *,
        status: AssignmentStatus,
        target_type: AssignmentTargetType = AssignmentTargetType.self_assessment,
        target_person: ParticipantProfile | None = None,
        target_team: Team | None = None,
        project: CompanyProject | None = None,
        cycle: AssessmentCycle | None = None,
        icare_cohort: IcareCohort | None = None,
    ) -> QuestionnaireAssignment:
        assignment_project = project or context.project
        round_key = cycle.id if cycle is not None else assignment_project.id
        identity = ":".join(
            str(part)
            for part in (
                assignment_project.id,
                cycle.id if cycle is not None else "legacy",
                respondent.id,
                key,
                target_type.value,
                target_person.id if target_person is not None else "no-person",
                target_team.id if target_team is not None else "no-team",
                icare_cohort.value if icare_cohort is not None else "no-cohort",
            )
        )
        occurrence = assignment_identity_counts.get(identity, 0)
        assignment_identity_counts[identity] = occurrence + 1
        assignment = QuestionnaireAssignment(
            id=_preview_uuid("assignment", identity, occurrence),
            company_id=context.company.id,
            project_id=assignment_project.id,
            assignment_round_id=assignment_rounds.setdefault(
                round_key,
                _preview_uuid("assignment-round", round_key),
            ),
            assessment_cycle_id=cycle.id if cycle is not None else None,
            cycle_shape_guard=cycle.id if cycle is not None else None,
            respondent_profile_id=respondent.id,
            questionnaire_key=key,
            questionnaire_definition_id=definitions[key].id,
            target_type=target_type,
            target_person_id=target_person.id if target_person is not None else None,
            target_team_id=target_team.id if target_team is not None else None,
            icare_cohort=icare_cohort,
            status=status,
            due_at=cycle.due_at if cycle is not None else now + timedelta(days=14),
            invited_at=now - timedelta(days=3) if status == AssignmentStatus.invited else None,
            started_at=now - timedelta(days=2) if status == AssignmentStatus.started else None,
        )
        session.add(assignment)
        assignments.append(assignment)
        return assignment

    def lencioni_answers(scores: tuple[int, int, int, int, int]) -> dict[str, int]:
        answer_sets = {
            3: (1, 1, 1),
            4: (1, 1, 2),
            5: (1, 2, 2),
            6: (2, 2, 2),
            7: (2, 2, 3),
            8: (2, 3, 3),
            9: (3, 3, 3),
        }
        return {
            f"team_sample_{group_index}_{item_index}": value
            for group_index, score in enumerate(scores, start=1)
            for item_index, value in enumerate(answer_sets[score], start=1)
        }

    def driver_answers(values: tuple[int, int, int, int, int]) -> dict[str, int]:
        return {
            f"style_set:style_{driver_index}_{item_index}": value
            for driver_index, value in enumerate(values, start=1)
            for item_index in range(1, 3)
        }

    completed: list[tuple[QuestionnaireAssignment, dict[str, object], int]] = []

    def queue_completed(
        assignment: QuestionnaireAssignment,
        answers: dict[str, object],
        *,
        age_days: int,
    ) -> None:
        completed.append((assignment, answers, age_days))

    main = contexts[0]
    demo, manager, people_lead, sales_lead, product_lead, coordinator = main.participants
    lencioni_cycle_scores = (
        ((5, 6, 4, 5, 6), (6, 5, 5, 4, 6), (5, 6, 5, 5, 7)),
        ((7, 7, 5, 6, 8), (6, 7, 6, 6, 7), (7, 6, 6, 7, 8)),
    )
    driver_cycle_values = (
        ((3, 5, 3, 2, 4), (2, 5, 4, 3, 3)),
        ((4, 4, 3, 3, 4), (3, 5, 3, 2, 4)),
    )
    for cycle_index, cycle in enumerate(main.cycles):
        age_days = 50 if cycle_index == 0 else 3
        for respondent, scores in zip(
            (demo, manager, people_lead),
            lencioni_cycle_scores[cycle_index],
            strict=True,
        ):
            queue_completed(
                add_assignment(
                    main,
                    respondent,
                    "lencioni",
                    status=AssignmentStatus.scored,
                    target_type=AssignmentTargetType.team,
                    target_team=main.team,
                    cycle=cycle,
                ),
                lencioni_answers(scores),
                age_days=age_days,
            )
        for respondent, values in zip(
            (demo, manager),
            driver_cycle_values[cycle_index],
            strict=True,
        ):
            queue_completed(
                add_assignment(
                    main,
                    respondent,
                    "distress_drivers",
                    status=AssignmentStatus.scored,
                    cycle=cycle,
                ),
                driver_answers(values),
                age_days=age_days,
            )
        pcm_assignment = add_assignment(
            main,
            demo,
            "pcm_base",
            status=AssignmentStatus.submitted,
            cycle=cycle,
        )
        queue_completed(
            pcm_assignment,
            {
                "pcm_base": "thinker",
                "pcm_phase": "persister" if cycle_index == 0 else "harmonizer",
            },
            age_days=age_days,
        )
        icare_specs = (
            (demo, IcareCohort.self),
            (manager, IcareCohort.leadership_peers),
            (people_lead, IcareCohort.leadership_peers),
            (sales_lead, IcareCohort.direct_team),
            (product_lead, IcareCohort.direct_team),
            (coordinator, IcareCohort.direct_team),
        )
        for response_index, (respondent, cohort) in enumerate(icare_specs):
            queue_completed(
                add_assignment(
                    main,
                    respondent,
                    "boss_360",
                    status=AssignmentStatus.scored,
                    target_type=AssignmentTargetType.person,
                    target_person=demo,
                    cycle=cycle,
                    icare_cohort=cohort,
                ),
                build_sample_answers(
                    definitions["boss_360"].schema,
                    offset=response_index + cycle_index + 1,
                ),
                age_days=age_days,
            )

    secondary_project = main.projects[1]
    draft_assignment = add_assignment(
        main,
        demo,
        "distress_drivers",
        status=AssignmentStatus.started,
        project=secondary_project,
    )
    add_assignment(
        main,
        demo,
        "boss_360",
        status=AssignmentStatus.assigned,
        target_type=AssignmentTargetType.person,
        target_person=manager,
        project=secondary_project,
    )
    for reviewer, offset in ((manager, 4), (people_lead, 5)):
        queue_completed(
            add_assignment(
                main,
                reviewer,
                "boss_360",
                status=AssignmentStatus.scored,
                target_type=AssignmentTargetType.person,
                target_person=demo,
                project=secondary_project,
            ),
            build_sample_answers(definitions["boss_360"].schema, offset=offset),
            age_days=offset + 4,
        )

    if len(contexts) > 2:
        atlas, nova = contexts[1], contexts[2]
        queue_completed(
            add_assignment(
                atlas,
                atlas.participants[0],
                "lencioni",
                status=AssignmentStatus.scored,
                target_type=AssignmentTargetType.team,
                target_team=atlas.team,
                cycle=atlas.cycles[0],
            ),
            lencioni_answers((6, 5, 7, 6, 6)),
            age_days=2,
        )
        add_assignment(
            atlas,
            atlas.participants[1],
            "boss_360",
            status=AssignmentStatus.invited,
            target_type=AssignmentTargetType.person,
            target_person=atlas.participants[0],
            cycle=atlas.cycles[0],
            icare_cohort=IcareCohort.direct_team,
        )
        queue_completed(
            add_assignment(
                nova,
                nova.participants[0],
                "distress_drivers",
                status=AssignmentStatus.scored,
                cycle=nova.cycles[0],
            ),
            driver_answers((5, 3, 2, 4, 3)),
            age_days=3,
        )
        add_assignment(
            nova,
            nova.participants[1],
            "lencioni",
            status=AssignmentStatus.invited,
            target_type=AssignmentTargetType.team,
            target_team=nova.team,
            cycle=nova.cycles[0],
        )
    await session.flush()

    session.add(
        QuestionnaireResponse(
            id=_preview_uuid("questionnaire-response", draft_assignment.id),
            assignment_id=draft_assignment.id,
            questionnaire_key=draft_assignment.questionnaire_key,
            questionnaire_version=PREVIEW_DEFINITION_VERSION,
            status=QuestionnaireResponseStatus.draft,
            answers=build_sample_answers(definitions["distress_drivers"].schema, limit=3),
        )
    )

    scoring_service = ScoringService(session)
    for assignment, answers, age_days in completed:
        submitted_at = now - timedelta(days=age_days)
        session.add(
            QuestionnaireResponse(
                id=_preview_uuid("questionnaire-response", assignment.id),
                assignment_id=assignment.id,
                questionnaire_key=assignment.questionnaire_key,
                questionnaire_version=PREVIEW_DEFINITION_VERSION,
                status=QuestionnaireResponseStatus.submitted,
                answers=answers,
                submitted_at=submitted_at,
            )
        )
        assignment.submitted_at = submitted_at
        if assignment.questionnaire_key == "pcm_base":
            assignment.status = AssignmentStatus.submitted
            continue
        assignment.scored_at = submitted_at
        await session.flush()
        await scoring_service.compute_and_save_score(
            assignment.id,
            assignment.questionnaire_key,
            answers,
            questionnaire_version=PREVIEW_DEFINITION_VERSION,
            definition_schema=definitions[assignment.questionnaire_key].schema,
        )

    await session.flush()
    return assignments


async def _seed_invites_and_delivery(
    session: AsyncSession,
    trainer: User,
    contexts: list[CompanyContext],
    assignments: list[QuestionnaireAssignment],
) -> None:
    now = datetime.now(UTC)
    identity = IdentityService(session)
    assignments_by_profile: dict[uuid.UUID, list[QuestionnaireAssignment]] = {}
    for assignment in assignments:
        assignments_by_profile.setdefault(assignment.respondent_profile_id, []).append(assignment)

    delivery_statuses = (
        EmailSendStatus.delivered,
        EmailSendStatus.accepted,
        EmailSendStatus.failed,
    )
    delivery_index = 0
    for context in contexts:
        for profile in context.participants:
            profile_assignments = assignments_by_profile.get(profile.id, [])
            active_by_project: dict[uuid.UUID, list[QuestionnaireAssignment]] = {}
            for assignment in profile_assignments:
                if assignment.status in {
                    AssignmentStatus.submitted,
                    AssignmentStatus.scored,
                    AssignmentStatus.validated,
                }:
                    continue
                active_by_project.setdefault(assignment.project_id, []).append(assignment)

            for project_id, active_assignments in active_by_project.items():
                await identity.create_invite(
                    company_id=context.company.id,
                    respondent_profile_id=profile.id,
                    assignment_ids=[assignment.id for assignment in active_assignments],
                    project_id=project_id,
                    expires_at=now + timedelta(days=30),
                    force_rotate=True,
                )
                if profile.email is None:
                    continue
                status = delivery_statuses[delivery_index % len(delivery_statuses)]
                delivery_index += 1
                assignment = active_assignments[0]
                idempotency_key = hashlib.sha256(
                    f"{PREVIEW_SOURCE}:assignment:{assignment.id}".encode()
                ).hexdigest()
                email_send = EmailSend(
                    id=_preview_uuid("assignment-email-send", assignment.id),
                    owner_id=trainer.id,
                    assignment_id=assignment.id,
                    recipient_email=profile.email,
                    template_key=PREVIEW_EMAIL_TEMPLATES["preview_evaluation_invite"].key,
                    template_version=PREVIEW_EMAIL_TEMPLATES["preview_evaluation_invite"].version,
                    provider="local_preview",
                    provider_message_id=f"preview-assignment-{assignment.id}",
                    idempotency_key=idempotency_key,
                    payload_fingerprint=idempotency_key,
                    status=status,
                    error_details=(
                        "Mesaj respins în mostra locală. Verifică adresa și reîncearcă."
                        if status == EmailSendStatus.failed
                        else None
                    ),
                    last_event_at=now - timedelta(hours=delivery_index),
                )
                session.add(email_send)
                await session.flush()
                if status == EmailSendStatus.delivered:
                    session.add(
                        EmailEvent(
                            id=_preview_uuid("assignment-email-event", email_send.id, "delivered"),
                            email_send_id=email_send.id,
                            event_type=EmailEventType.delivered,
                            provider_event_id=f"preview-delivered-{email_send.id}",
                            occurred_at=email_send.last_event_at or now,
                        )
                    )


async def _seed_communications(session: AsyncSession, trainer: User) -> tuple[int, int]:
    for template in PREVIEW_EMAIL_TEMPLATES.values():
        session.add(
            EmailTemplate(
                id=_preview_uuid("email-template", trainer.id, template.key, template.version),
                key=template.key,
                version=template.version,
                subject=template.subject,
                html_body=template.html_body,
                text_body=template.text_body,
                variables=list(template.required_context),
                audience=template.audience,
                active=True,
                owner_id=trainer.id,
            )
        )

    contact_specs = (
        ("Ana Stoica", "ana.stoica@north-preview.test", "North Studio", "past", "active"),
        ("Radu Georgescu", "radu.georgescu@forge-preview.test", "Forge Lab", "past", "active"),
        ("Carmen Ilie", "carmen.ilie@vertex-preview.test", "Vertex", "potential", "active"),
        ("Matei Sandu", "matei.sandu@orbit-preview.test", "Orbit Works", "potential", "active"),
        ("Irina Pop", "irina.pop@civic-preview.test", "Civic Hub", "past", "unsubscribed"),
        ("Vlad Toma", "vlad.toma@axis-preview.test", "Axis Group", "potential", "suppressed"),
        ("Nicoleta Dan", None, "Atelier 42", "potential", "suppressed"),
        ("Alex Petrescu", "alex.petrescu@delta-preview.test", "Delta Office", "past", "active"),
    )
    recipients: list[CampaignRecipient] = []
    for name, email, organization, segment, status in contact_specs:
        recipient = CampaignRecipient(
            id=_preview_uuid("campaign-recipient", trainer.id, email or name),
            owner_id=trainer.id,
            email=email,
            contact_name=name,
            organization_name=organization,
            segment=(
                CampaignRecipientSegment.past_customer
                if segment == "past"
                else CampaignRecipientSegment.potential_customer
            ),
            source=PREVIEW_SOURCE,
            status=CampaignRecipientStatus(status),
        )
        recipients.append(recipient)
        session.add(recipient)
    await session.flush()

    now = datetime.now(UTC)
    promo_reactivation = PREVIEW_EMAIL_TEMPLATES["preview_campaign_reactivation"]
    promo_report = PREVIEW_EMAIL_TEMPLATES["preview_campaign_report"]
    campaigns = [
        Campaign(
            id=_preview_uuid("campaign", trainer.id, PREVIEW_CAMPAIGN_NAMES[0]),
            owner_id=trainer.id,
            name=PREVIEW_CAMPAIGN_NAMES[0],
            segment=CampaignRecipientSegment.past_customer,
            status=CampaignStatus.ready,
            subject=promo_reactivation.subject,
            html_body=promo_reactivation.html_body,
            text_body=promo_reactivation.text_body,
            landing_page_url="https://example.com/preview/reactivare",
            recipient_memberships_initialized=True,
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(hours=6),
        ),
        Campaign(
            id=_preview_uuid("campaign", trainer.id, PREVIEW_CAMPAIGN_NAMES[1]),
            owner_id=trainer.id,
            name=PREVIEW_CAMPAIGN_NAMES[1],
            segment=CampaignRecipientSegment.potential_customer,
            status=CampaignStatus.draft,
            subject="Un atelier practic pentru echipe care cresc",
            html_body=(
                "<p>Salut, ${first_name}.</p><p>Pregătim un atelier practic pentru echipe.</p>"
            ),
            text_body="Salut, ${first_name}. Pregătim un atelier practic pentru echipe.",
            recipient_memberships_initialized=True,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=2),
        ),
        Campaign(
            id=_preview_uuid("campaign", trainer.id, PREVIEW_CAMPAIGN_NAMES[2]),
            owner_id=trainer.id,
            name=PREVIEW_CAMPAIGN_NAMES[2],
            segment=CampaignRecipientSegment.past_customer,
            status=CampaignStatus.completed,
            subject=promo_report.subject,
            html_body=promo_report.html_body,
            text_body=promo_report.text_body,
            landing_page_url="https://example.com/preview/raport",
            recipient_memberships_initialized=True,
            created_at=now - timedelta(days=12),
            updated_at=now - timedelta(days=1),
        ),
    ]
    session.add_all(campaigns)
    await session.flush()

    active_recipients = [
        recipient for recipient in recipients if recipient.status == CampaignRecipientStatus.active
    ]
    for campaign in campaigns:
        matching_recipients = [
            recipient
            for recipient in active_recipients
            if campaign.segment is None or recipient.segment == campaign.segment
        ]
        for recipient in matching_recipients:
            session.add(
                CampaignRecipientMembership(
                    id=_preview_uuid("campaign-membership", campaign.id, recipient.id),
                    campaign_id=campaign.id,
                    recipient_id=recipient.id,
                    source=PREVIEW_SOURCE,
                )
            )

    completed_campaign = campaigns[2]
    completed_recipients = [
        recipient
        for recipient in active_recipients
        if recipient.segment == CampaignRecipientSegment.past_customer
    ]
    statuses = (EmailSendStatus.delivered, EmailSendStatus.accepted, EmailSendStatus.failed)
    for index, recipient in enumerate(completed_recipients):
        if recipient.email is None:
            continue
        status = statuses[index % len(statuses)]
        idempotency_key = hashlib.sha256(
            f"{PREVIEW_SOURCE}:campaign:{completed_campaign.id}:{recipient.id}".encode()
        ).hexdigest()
        send = EmailSend(
            id=_preview_uuid("campaign-email-send", completed_campaign.id, recipient.id),
            owner_id=trainer.id,
            campaign_id=completed_campaign.id,
            campaign_recipient_id=recipient.id,
            recipient_email=recipient.email,
            template_key=promo_report.key,
            template_version=promo_report.version,
            provider="local_preview",
            provider_message_id=f"preview-campaign-{recipient.id}",
            idempotency_key=idempotency_key,
            payload_fingerprint=idempotency_key,
            status=status,
            error_details=(
                "Livrare eșuată în mostra locală." if status == EmailSendStatus.failed else None
            ),
            last_event_at=now - timedelta(days=1, hours=index),
        )
        session.add(send)

    preview_events = {
        "ana.stoica@north-preview.test": (
            "opened",
            "opened",
            "clicked",
            "calendly_clicked",
        ),
        "radu.georgescu@forge-preview.test": (
            "opened",
            "video_viewed",
            "replied",
        ),
        "matei.sandu@orbit-preview.test": ("opened", "clicked"),
        "alex.petrescu@delta-preview.test": (
            "opened",
            "opened",
            "clicked",
            "video_viewed",
            "replied",
            "calendly_clicked",
        ),
    }
    for recipient in active_recipients:
        if recipient.email is None:
            continue
        for event_index, event_type in enumerate(preview_events.get(recipient.email, ())):
            session.add(
                CampaignRecipientEvent(
                    id=_preview_uuid(
                        "campaign-recipient-event",
                        completed_campaign.id,
                        recipient.id,
                        event_index,
                        event_type,
                    ),
                    owner_id=trainer.id,
                    campaign_id=completed_campaign.id,
                    recipient_id=recipient.id,
                    event_type=event_type,
                    variant_key="preview-a",
                    occurred_at=now - timedelta(hours=event_index + 1),
                )
            )

    await session.flush()
    return len(campaigns), len(recipients)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed local preview data.")
    parser.add_argument(
        "--company-name",
        type=str,
        default=None,
        help="Optional company name to seed/clear in isolation.",
    )
    args = parser.parse_args()
    result = asyncio.run(seed_local_preview(company_name=args.company_name))
    print("Local preview data is ready.")
    print(f"Trainer: {result.trainer_email}")
    print(f"Participant: {result.participant_email}")
    print(
        "Seeded "
        f"{result.company_count} companies, {result.project_count} projects, "
        f"{result.participant_count} participants, {result.assignment_count} assignments, "
        f"{result.campaign_count} campaigns, and {result.contact_count} contacts."
    )


if __name__ == "__main__":
    main()
