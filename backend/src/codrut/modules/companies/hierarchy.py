from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from codrut.modules.companies.manager_matching import (
    clean_manager_reference,
    manager_reference_key,
)


@dataclass(frozen=True)
class HierarchyParticipant:
    id: UUID
    full_name: str
    reports_to_name: str | None
    role_group: str | None = None
    user_id: UUID | None = None


@dataclass(frozen=True)
class HierarchyIssue:
    code: str
    message: str
    participant_id: UUID | None = None
    participant_name: str | None = None
    reports_to_name: str | None = None


@dataclass(frozen=True)
class OrganizationHierarchy:
    participants: list[HierarchyParticipant]
    participant_by_id: dict[UUID, HierarchyParticipant]
    top_level_ids: set[UUID]
    manager_ids: set[UUID]
    leadership_ids: set[UUID]
    direct_reports_by_manager_id: dict[UUID, list[HierarchyParticipant]]
    issues: list[HierarchyIssue]
    ambiguous_name: str | None = None


def build_organization_hierarchy(
    participants: Sequence[HierarchyParticipant],
) -> OrganizationHierarchy:
    participant_list = list(participants)
    participant_by_id = {participant.id: participant for participant in participant_list}
    participant_by_name, duplicate_name_keys, labels_by_key = _participants_by_name_key(
        participant_list
    )
    referenced_manager_keys = {
        manager_reference_key(manager_name)
        for participant in participant_list
        for manager_name in (clean_manager_reference(participant.reports_to_name),)
        if manager_name
    }

    ambiguous_name_keys = duplicate_name_keys & referenced_manager_keys
    if ambiguous_name_keys:
        ambiguous_key = sorted(ambiguous_name_keys)[0]
        ambiguous_name = labels_by_key.get(ambiguous_key, "manager")
        return OrganizationHierarchy(
            participants=participant_list,
            participant_by_id=participant_by_id,
            top_level_ids=set(),
            manager_ids=set(),
            leadership_ids=set(),
            direct_reports_by_manager_id={},
            issues=[
                HierarchyIssue(
                    code="manager_ambiguous",
                    message=(
                        f'Manager name "{ambiguous_name}" is ambiguous in this company roster.'
                    ),
                )
            ],
            ambiguous_name=ambiguous_name,
        )

    top_level_ids: set[UUID] = set()
    manager_ids: set[UUID] = set()
    direct_reports_by_manager_id: dict[UUID, list[HierarchyParticipant]] = {}
    issues: list[HierarchyIssue] = []

    for participant in participant_list:
        reports_to_name = clean_manager_reference(participant.reports_to_name)
        if reports_to_name is None:
            top_level_ids.add(participant.id)
            continue

        manager = participant_by_name.get(manager_reference_key(reports_to_name))
        if manager is None:
            issues.append(
                HierarchyIssue(
                    code="manager_unresolved",
                    participant_id=participant.id,
                    participant_name=participant.full_name,
                    reports_to_name=reports_to_name,
                    message=(
                        f'Manager "{reports_to_name}" was not found in the company roster '
                        f"for {participant.full_name}."
                    ),
                )
            )
            continue

        if manager.id == participant.id:
            issues.append(
                HierarchyIssue(
                    code="manager_self_reference",
                    participant_id=participant.id,
                    participant_name=participant.full_name,
                    reports_to_name=reports_to_name,
                    message=f"{participant.full_name} cannot report to themselves.",
                )
            )
            continue

        manager_ids.add(manager.id)
        direct_reports_by_manager_id.setdefault(manager.id, []).append(participant)

    explicit_leadership_ids = {
        participant.id
        for participant in participant_list
        if _is_leadership_role(participant.role_group)
    }
    manager_ids.update(explicit_leadership_ids)
    leadership_ids = set(top_level_ids) | explicit_leadership_ids
    for top_level_id in top_level_ids:
        leadership_ids.update(
            direct_report.id for direct_report in direct_reports_by_manager_id.get(top_level_id, [])
        )

    return OrganizationHierarchy(
        participants=participant_list,
        participant_by_id=participant_by_id,
        top_level_ids=top_level_ids,
        manager_ids=manager_ids,
        leadership_ids=leadership_ids,
        direct_reports_by_manager_id=direct_reports_by_manager_id,
        issues=issues,
    )


def _participants_by_name_key(
    participants: Sequence[HierarchyParticipant],
) -> tuple[dict[str, HierarchyParticipant], set[str], dict[str, str]]:
    participants_by_key: dict[str, HierarchyParticipant] = {}
    duplicate_keys: set[str] = set()
    labels_by_key: dict[str, str] = {}

    for participant in participants:
        label = participant.full_name.strip()
        key = manager_reference_key(label)
        if not key:
            continue
        labels_by_key.setdefault(key, label)
        if key in participants_by_key:
            duplicate_keys.add(key)
        else:
            participants_by_key[key] = participant

    return participants_by_key, duplicate_keys, labels_by_key


def _is_leadership_role(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"leadership", "manager"}
