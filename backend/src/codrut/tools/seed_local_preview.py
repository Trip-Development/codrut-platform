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
    AssignmentStatus,
    AssignmentTargetType,
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


async def seed_local_preview() -> PreviewSeedResult:
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

        await _clear_preview_data(session, trainer, participant_user)
        definitions = await _replace_preview_definitions(session)
        contexts = await _seed_company_contexts(session, trainer, participant_user)
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
            id=uuid.uuid4(),
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
) -> None:
    preview_company_names = (*PREVIEW_COMPANY_NAMES, *LEGACY_PREVIEW_COMPANY_NAMES)
    company_ids = list(
        (
            await session.execute(
                select(Company.id).where(
                    or_(
                        Company.name.in_(preview_company_names),
                        Company.name.startswith(LEGACY_PREVIEW_COMPANY_PREFIX),
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
        await session.execute(delete(Company).where(Company.id.in_(company_ids)))
    await session.flush()

    linked_profile = (
        await session.execute(
            select(ParticipantProfile, Company.name)
            .join(Company, Company.id == ParticipantProfile.company_id)
            .where(ParticipantProfile.user_id == participant_user.id)
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
    await session.execute(
        delete(QuestionnaireDefinition).where(
            QuestionnaireDefinition.key.in_(keys),
            QuestionnaireDefinition.version == PREVIEW_DEFINITION_VERSION,
            QuestionnaireDefinition.system_managed.is_(False),
        )
    )
    await session.flush()

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
        model = QuestionnaireDefinition(
            id=uuid.uuid4(),
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

    contexts: list[CompanyContext] = []
    for company_index, (company_name, project_name, participant_specs) in enumerate(company_specs):
        company = Company(id=uuid.uuid4(), name=company_name)
        session.add(company)
        await session.flush()
        session.add(
            CompanyMembership(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=trainer.id,
                role=CompanyMembershipRole.owner,
            )
        )

        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name=project_name,
            description="Program de leadership pentru aliniere managerială și feedback aplicat.",
            project_type="leadership_program",
            status=CompanyProjectStatus.active,
            starts_at=now - timedelta(days=14 + company_index * 7),
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
                        id=uuid.uuid4(),
                        company_id=company.id,
                        name="Coaching managerial aplicat",
                        description="Practică managerială și feedback între sesiuni.",
                        project_type="leadership_program",
                        status=CompanyProjectStatus.active,
                        starts_at=now - timedelta(days=5),
                        due_at=now + timedelta(days=35),
                        form_opens_at=now - timedelta(days=5),
                        form_closes_at=now + timedelta(days=35),
                    ),
                    CompanyProject(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        name="Pregătire cohortă retail",
                        description="Cohortă în pregătire.",
                        project_type="cohort_program",
                        status=CompanyProjectStatus.draft,
                        starts_at=now + timedelta(days=35),
                    ),
                    CompanyProject(
                        id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
                id=uuid.uuid4(),
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
                        id=uuid.uuid4(),
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
                        id=uuid.uuid4(),
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
                        id=uuid.uuid4(),
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
                    id=uuid.uuid4(),
                    company_id=company.id,
                    participant_profile_id=profile.id,
                    manager_profile_id=participants[0].id,
                )
            )
        contexts.append(
            CompanyContext(
                company=company,
                project=project,
                projects=tuple(projects),
                participants=participants,
                team=team,
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
    ) -> QuestionnaireAssignment:
        assignment_project = project or context.project
        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=context.company.id,
            project_id=assignment_project.id,
            assignment_round_id=assignment_rounds.setdefault(
                assignment_project.id,
                uuid.uuid4(),
            ),
            respondent_profile_id=respondent.id,
            questionnaire_key=key,
            questionnaire_definition_id=definitions[key].id,
            target_type=target_type,
            target_person_id=target_person.id if target_person is not None else None,
            target_team_id=target_team.id if target_team is not None else None,
            status=status,
            due_at=now + timedelta(days=14),
            invited_at=now - timedelta(days=3) if status == AssignmentStatus.invited else None,
            started_at=now - timedelta(days=2) if status == AssignmentStatus.started else None,
        )
        session.add(assignment)
        assignments.append(assignment)
        return assignment

    main = contexts[0]
    demo, manager, people_lead, sales_lead, product_lead, coordinator = main.participants
    draft_assignment = add_assignment(
        main,
        demo,
        "lencioni",
        status=AssignmentStatus.started,
        target_type=AssignmentTargetType.team,
        target_team=main.team,
    )
    completed_demo_assignment = add_assignment(
        main,
        demo,
        "distress_drivers",
        status=AssignmentStatus.scored,
    )
    add_assignment(
        main,
        demo,
        "boss_360",
        status=AssignmentStatus.assigned,
        target_type=AssignmentTargetType.person,
        target_person=manager,
    )
    add_assignment(
        main,
        demo,
        "boss_360",
        status=AssignmentStatus.invited,
        target_type=AssignmentTargetType.person,
        target_person=people_lead,
    )
    add_assignment(
        main,
        demo,
        "boss_360",
        status=AssignmentStatus.assigned,
        target_type=AssignmentTargetType.person,
        target_person=sales_lead,
    )
    icare_draft_assignment = add_assignment(
        main,
        demo,
        "boss_360",
        status=AssignmentStatus.started,
        target_type=AssignmentTargetType.person,
        target_person=product_lead,
    )
    completed_specs = (
        (manager, "lencioni", AssignmentTargetType.team, None, main.team, 1),
        (people_lead, "lencioni", AssignmentTargetType.team, None, main.team, 3),
        (sales_lead, "lencioni", AssignmentTargetType.team, None, main.team, 4),
        (people_lead, "distress_drivers", AssignmentTargetType.self_assessment, None, None, 2),
        (sales_lead, "boss_360", AssignmentTargetType.person, demo, None, 1),
        (product_lead, "boss_360", AssignmentTargetType.person, demo, None, 2),
    )
    completed_assignments: list[tuple[QuestionnaireAssignment, int]] = [
        (completed_demo_assignment, 0)
    ]
    for respondent, key, target_type, target_person, target_team, offset in completed_specs:
        assignment = add_assignment(
            main,
            respondent,
            key,
            status=AssignmentStatus.scored,
            target_type=target_type,
            target_person=target_person,
            target_team=target_team,
        )
        completed_assignments.append((assignment, offset))
    add_assignment(
        main,
        coordinator,
        "lencioni",
        status=AssignmentStatus.invited,
        target_type=AssignmentTargetType.team,
        target_team=main.team,
    )

    secondary_project = main.projects[1]
    add_assignment(
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
        assignment = add_assignment(
            main,
            reviewer,
            "boss_360",
            status=AssignmentStatus.scored,
            target_type=AssignmentTargetType.person,
            target_person=demo,
            project=secondary_project,
        )
        completed_assignments.append((assignment, offset))

    atlas, nova = contexts[1], contexts[2]
    atlas_completed = add_assignment(
        atlas,
        atlas.participants[0],
        "lencioni",
        status=AssignmentStatus.scored,
        target_type=AssignmentTargetType.team,
        target_team=atlas.team,
    )
    completed_assignments.append((atlas_completed, 2))
    add_assignment(
        atlas,
        atlas.participants[1],
        "boss_360",
        status=AssignmentStatus.invited,
        target_type=AssignmentTargetType.person,
        target_person=atlas.participants[0],
    )
    nova_completed = add_assignment(
        nova,
        nova.participants[0],
        "distress_drivers",
        status=AssignmentStatus.scored,
    )
    completed_assignments.append((nova_completed, 3))
    add_assignment(
        nova,
        nova.participants[1],
        "lencioni",
        status=AssignmentStatus.invited,
        target_type=AssignmentTargetType.team,
        target_team=nova.team,
    )
    await session.flush()

    session.add(
        QuestionnaireResponse(
            id=uuid.uuid4(),
            assignment_id=draft_assignment.id,
            questionnaire_key=draft_assignment.questionnaire_key,
            questionnaire_version=PREVIEW_DEFINITION_VERSION,
            status=QuestionnaireResponseStatus.draft,
            answers=build_sample_answers(definitions["lencioni"].schema, limit=3),
        )
    )
    session.add(
        QuestionnaireResponse(
            id=uuid.uuid4(),
            assignment_id=icare_draft_assignment.id,
            questionnaire_key=icare_draft_assignment.questionnaire_key,
            questionnaire_version=PREVIEW_DEFINITION_VERSION,
            status=QuestionnaireResponseStatus.draft,
            answers=build_sample_answers(definitions["boss_360"].schema, limit=2),
        )
    )

    scoring_service = ScoringService(session)
    for assignment, offset in completed_assignments:
        definition = definitions[assignment.questionnaire_key]
        answers = build_sample_answers(definition.schema, offset=offset)
        submitted_at = now - timedelta(days=offset + 1)
        session.add(
            QuestionnaireResponse(
                id=uuid.uuid4(),
                assignment_id=assignment.id,
                questionnaire_key=assignment.questionnaire_key,
                questionnaire_version=PREVIEW_DEFINITION_VERSION,
                status=QuestionnaireResponseStatus.submitted,
                answers=answers,
                submitted_at=submitted_at,
            )
        )
        assignment.submitted_at = submitted_at
        assignment.scored_at = submitted_at
        await session.flush()
        await scoring_service.compute_and_save_score(
            assignment.id,
            assignment.questionnaire_key,
            answers,
            questionnaire_version=PREVIEW_DEFINITION_VERSION,
            definition_schema=definition.schema,
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
                if assignment.status in {AssignmentStatus.scored, AssignmentStatus.validated}:
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
                    id=uuid.uuid4(),
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
                            id=uuid.uuid4(),
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
                id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
                    id=uuid.uuid4(),
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
            id=uuid.uuid4(),
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
                    id=uuid.uuid4(),
                    recipient_id=recipient.id,
                    event_type=event_type,
                    variant_key="preview-a",
                    occurred_at=now - timedelta(hours=event_index + 1),
                )
            )

    await session.flush()
    return len(campaigns), len(recipients)


def main() -> None:
    result = asyncio.run(seed_local_preview())
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
