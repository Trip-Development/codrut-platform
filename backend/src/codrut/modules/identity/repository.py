import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.identity.models import (
    AssignmentInvite,
    ConsentAcceptance,
    PasswordResetToken,
    Session,
    User,
    UserAccountType,
)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_by_id(
        self,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def has_participant_profile(self, user_id: UUID) -> bool:
        from codrut.modules.companies.models import ParticipantProfile

        result = await self.session.execute(
            select(
                exists(
                    select(ParticipantProfile.id).where(
                        ParticipantProfile.user_id == user_id
                    )
                )
            )
        )
        return bool(result.scalar())

    async def list_participant_profiles_by_email_for_update(self, email: str):
        from codrut.modules.companies.models import ParticipantProfile

        result = await self.session.execute(
            select(ParticipantProfile)
            .where(func.lower(ParticipantProfile.email) == email.strip().lower())
            .order_by(ParticipantProfile.created_at, ParticipantProfile.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def anonymous_name_exists(self, anonymous_name: str) -> bool:
        from codrut.modules.companies.models import ParticipantProfile

        result = await self.session.execute(
            select(
                exists().where(
                    ParticipantProfile.anonymous_name == anonymous_name
                )
            )
        )
        return bool(result.scalar())

    async def get_user_by_session_token(self, token: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .join(Session)
            .where(Session.token_hash == hash_session_token(token))
            .where(Session.expires_at > datetime.now(UTC))
        )
        return result.scalar_one_or_none()

    async def add_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def add_session(self, session: Session) -> Session:
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session_by_token(self, token: str) -> Session | None:
        result = await self.session.execute(
            select(Session)
            .where(Session.token_hash == hash_session_token(token))
            .where(Session.expires_at > datetime.now(UTC))
        )
        return result.scalar_one_or_none()

    async def get_consent_acceptance(
        self,
        *,
        user_id: UUID,
        terms_version: str,
        session_id: UUID | None,
    ) -> ConsentAcceptance | None:
        statement = select(ConsentAcceptance).where(
            ConsentAcceptance.user_id == user_id,
            ConsentAcceptance.terms_version == terms_version,
        )
        if session_id is None:
            statement = statement.where(ConsentAcceptance.session_id.is_(None))
        else:
            statement = statement.where(ConsentAcceptance.session_id == session_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_consent_acceptance(
        self,
        *,
        user_id: UUID,
        terms_version: str,
    ) -> ConsentAcceptance | None:
        result = await self.session.execute(
            select(ConsentAcceptance)
            .where(
                ConsentAcceptance.user_id == user_id,
                ConsentAcceptance.terms_version == terms_version,
            )
            .order_by(ConsentAcceptance.accepted_at.desc(), ConsentAcceptance.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_consent_acceptance(
        self,
        acceptance: ConsentAcceptance,
    ) -> ConsentAcceptance:
        self.session.add(acceptance)
        await self.session.flush()
        return acceptance

    async def get_invite_by_id(self, invite_id: UUID) -> AssignmentInvite | None:
        result = await self.session.execute(
            select(AssignmentInvite).where(AssignmentInvite.id == invite_id)
        )
        return result.scalar_one_or_none()

    async def delete_session_by_token(self, token: str) -> None:
        result = await self.session.execute(
            select(Session).where(Session.token_hash == hash_session_token(token))
        )
        session = result.scalar_one_or_none()
        if session is not None:
            await self.session.delete(session)

    async def delete_sessions_for_user(self, user_id: UUID) -> None:
        result = await self.session.execute(select(Session).where(Session.user_id == user_id))
        for session in result.scalars().all():
            await self.session.delete(session)

    async def delete_sessions_for_invites(self, invite_ids: list[UUID]) -> None:
        if not invite_ids:
            return
        await self.session.execute(
            delete(Session).where(Session.assignment_invite_id.in_(invite_ids))
        )

    async def delete_sessions_for_shadow_user(self, user_id: UUID) -> None:
        is_shadow_user = exists(
            select(User.id).where(
                User.id == user_id,
                User.account_type == UserAccountType.guest,
            )
        )
        await self.session.execute(
            delete(Session).where(
                Session.user_id == user_id,
                is_shadow_user,
            )
        )

    async def add_password_reset_token(self, token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_active_password_reset_token(self, token: str) -> PasswordResetToken | None:
        result = await self.session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == hash_session_token(token))
            .where(PasswordResetToken.expires_at > datetime.now(UTC))
            .where(PasswordResetToken.used_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def revoke_password_reset_tokens_for_user(self, user_id: UUID) -> None:
        result = await self.session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .where(PasswordResetToken.used_at.is_(None))
        )
        now = datetime.now(UTC)
        for token in result.scalars().all():
            token.used_at = now
        await self.session.flush()

    async def add_invite(self, invite: AssignmentInvite) -> AssignmentInvite:
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def get_active_invite_by_respondent(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
        project_id: UUID | None,
    ) -> AssignmentInvite | None:
        statement = (
            select(AssignmentInvite)
            .where(AssignmentInvite.company_id == company_id)
            .where(AssignmentInvite.respondent_profile_id == respondent_profile_id)
            .where(AssignmentInvite.status == "active")
            .where(AssignmentInvite.expires_at > datetime.now(UTC))
            .order_by(AssignmentInvite.created_at.desc())
        )
        statement = (
            statement.where(AssignmentInvite.project_id == project_id)
            if project_id is not None
            else statement.where(AssignmentInvite.project_id.is_(None))
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def list_invites_for_respondent(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
    ) -> list[AssignmentInvite]:
        result = await self.session.execute(
            select(AssignmentInvite).where(
                AssignmentInvite.company_id == company_id,
                AssignmentInvite.respondent_profile_id == respondent_profile_id,
            )
        )
        return list(result.scalars().all())

    async def get_invite_by_token(
        self,
        token: str,
        *,
        for_update: bool = False,
    ) -> AssignmentInvite | None:
        statement = select(AssignmentInvite).where(AssignmentInvite.token == token)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def invalidate_invites_for_respondent(
        self,
        company_id: UUID,
        respondent_profile_id: UUID,
        *,
        project_id: UUID | None = None,
        all_scopes: bool = False,
    ) -> list[AssignmentInvite]:
        statement = (
            select(AssignmentInvite)
            .where(AssignmentInvite.company_id == company_id)
            .where(AssignmentInvite.respondent_profile_id == respondent_profile_id)
            .where(AssignmentInvite.status == "active")
            .with_for_update()
        )
        if not all_scopes:
            statement = (
                statement.where(AssignmentInvite.project_id == project_id)
                if project_id is not None
                else statement.where(AssignmentInvite.project_id.is_(None))
            )
        result = await self.session.execute(statement)
        invites = result.scalars().all()
        for invite in invites:
            invite.status = "revoked"
        await self.session.flush()
        return invites
