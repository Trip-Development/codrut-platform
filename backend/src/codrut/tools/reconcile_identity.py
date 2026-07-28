from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter

from sqlalchemy import func, select

from codrut.core.database import SessionLocal
from codrut.modules.assignments.models import QuestionnaireAssignment
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.forms.models import QuestionnaireResponse
from codrut.modules.identity.models import Session, User
from codrut.modules.scoring.models import ScoringResult


async def identity_report(email: str) -> dict:
    normalized_email = email.strip().lower()
    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        profiles = list(
            (
                await session.scalars(
                    select(ParticipantProfile)
                    .where(func.lower(ParticipantProfile.email) == normalized_email)
                    .order_by(ParticipantProfile.created_at, ParticipantProfile.id)
                )
            ).all()
        )
        profile_ids = [profile.id for profile in profiles]
        sessions = (
            list(
                (
                    await session.scalars(
                        select(Session)
                        .where(Session.user_id == user.id)
                        .order_by(Session.created_at.desc())
                    )
                ).all()
            )
            if user is not None
            else []
        )

        assignment_count = response_count = result_count = project_membership_count = 0
        if profile_ids:
            assignment_ids = list(
                (
                    await session.scalars(
                        select(QuestionnaireAssignment.id).where(
                            QuestionnaireAssignment.respondent_profile_id.in_(profile_ids)
                        )
                    )
                ).all()
            )
            assignment_count = len(assignment_ids)
            project_membership_count = int(
                await session.scalar(
                    select(func.count(ProjectMembership.id)).where(
                        ProjectMembership.participant_profile_id.in_(profile_ids)
                    )
                )
                or 0
            )
            if assignment_ids:
                response_count = int(
                    await session.scalar(
                        select(func.count(QuestionnaireResponse.id)).where(
                            QuestionnaireResponse.assignment_id.in_(assignment_ids)
                        )
                    )
                    or 0
                )
                result_count = int(
                    await session.scalar(
                        select(func.count(ScoringResult.id)).where(
                            ScoringResult.assignment_id.in_(assignment_ids)
                        )
                    )
                    or 0
                )

        linked_user_ids = Counter(
            str(profile.user_id) if profile.user_id is not None else "unlinked"
            for profile in profiles
        )
        conflicts = [
            str(profile.id)
            for profile in profiles
            if user is not None
            and profile.user_id is not None
            and profile.user_id != user.id
        ]
        return {
            "dry_run": True,
            "email": normalized_email,
            "account": (
                {
                    "id": str(user.id),
                    "account_type": user.account_type.value,
                    "default_workspace": user.role.value,
                }
                if user is not None
                else None
            ),
            "profiles": {
                "count": len(profiles),
                "by_linked_user": dict(linked_user_ids),
                "conflicting_profile_ids": conflicts,
            },
            "sessions": {
                "count": len(sessions),
                "account": sum(
                    session_row.assignment_invite_id is None for session_row in sessions
                ),
                "secure_link": sum(
                    session_row.assignment_invite_id is not None
                    for session_row in sessions
                ),
            },
            "preserved_data": {
                "project_memberships": project_membership_count,
                "assignments": assignment_count,
                "responses": response_count,
                "scoring_results": result_count,
            },
            "safe_to_auto_claim": user is not None and not conflicts,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a read-only identity and participant-link reconciliation report."
    )
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(identity_report(args.email)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
