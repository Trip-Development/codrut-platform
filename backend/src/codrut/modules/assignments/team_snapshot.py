from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.assignments.models import (
    AssessmentCycleTeamMembership,
    Team,
    TeamMembershipRole,
    TeamType,
)


@dataclass(frozen=True)
class AssessmentCycleTeamSnapshot:
    leadership_ids: frozenset[UUID]
    direct_report_ids_by_leader_id: dict[UUID, frozenset[UUID]]


async def load_assessment_cycle_team_snapshot(
    session: AsyncSession,
    assessment_cycle_id: UUID,
) -> AssessmentCycleTeamSnapshot:
    rows = (
        await session.execute(
            select(
                AssessmentCycleTeamMembership.team_id,
                AssessmentCycleTeamMembership.participant_profile_id,
                AssessmentCycleTeamMembership.role,
                Team.type,
            )
            .join(Team, Team.id == AssessmentCycleTeamMembership.team_id)
            .where(
                AssessmentCycleTeamMembership.assessment_cycle_id == assessment_cycle_id
            )
        )
    ).all()
    leadership_ids = frozenset(
        participant_id
        for _team_id, participant_id, _role, team_type in rows
        if team_type == TeamType.leadership
    )
    functional_members_by_team_id: dict[UUID, set[UUID]] = {}
    functional_leaders_by_team_id: dict[UUID, set[UUID]] = {}
    for team_id, participant_id, role, team_type in rows:
        if team_type != TeamType.functional:
            continue
        functional_members_by_team_id.setdefault(team_id, set()).add(participant_id)
        if role == TeamMembershipRole.leader:
            functional_leaders_by_team_id.setdefault(team_id, set()).add(participant_id)

    direct_report_ids_by_leader_id: dict[UUID, set[UUID]] = {}
    for team_id, leader_ids in functional_leaders_by_team_id.items():
        member_ids = functional_members_by_team_id.get(team_id, set())
        for leader_id in leader_ids:
            direct_report_ids_by_leader_id.setdefault(leader_id, set()).update(
                member_ids - {leader_id}
            )

    return AssessmentCycleTeamSnapshot(
        leadership_ids=leadership_ids,
        direct_report_ids_by_leader_id={
            leader_id: frozenset(direct_report_ids)
            for leader_id, direct_report_ids in direct_report_ids_by_leader_id.items()
        },
    )
