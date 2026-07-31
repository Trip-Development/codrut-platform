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
class AssessmentCycleTeam:
    id: UUID
    name: str
    type: TeamType
    member_ids: frozenset[UUID]


@dataclass(frozen=True)
class AssessmentCycleTeamSnapshot:
    leadership_ids: frozenset[UUID]
    direct_report_ids_by_leader_id: dict[UUID, frozenset[UUID]]
    teams: tuple[AssessmentCycleTeam, ...] = ()


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
                Team.name,
            )
            .join(Team, Team.id == AssessmentCycleTeamMembership.team_id)
            .where(
                AssessmentCycleTeamMembership.assessment_cycle_id == assessment_cycle_id
            )
        )
    ).all()
    leadership_ids = frozenset(
        participant_id
        for _team_id, participant_id, _role, team_type, _team_name in rows
        if team_type == TeamType.leadership
    )
    team_details_by_id: dict[UUID, tuple[str, TeamType, set[UUID]]] = {}
    functional_members_by_team_id: dict[UUID, set[UUID]] = {}
    functional_leaders_by_team_id: dict[UUID, set[UUID]] = {}
    for team_id, participant_id, role, team_type, team_name in rows:
        details = team_details_by_id.setdefault(
            team_id,
            (team_name, team_type, set()),
        )
        details[2].add(participant_id)
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
        teams=tuple(
            AssessmentCycleTeam(
                id=team_id,
                name=name,
                type=team_type,
                member_ids=frozenset(member_ids),
            )
            for team_id, (name, team_type, member_ids) in sorted(
                team_details_by_id.items(),
                key=lambda item: (
                    0 if item[1][1] == TeamType.leadership else 1,
                    item[1][0].casefold(),
                    str(item[0]),
                ),
            )
        ),
    )
