import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.identity.models import AssignmentInvite, PasswordResetToken, Session, User


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

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
        self, company_id: UUID, respondent_profile_id: UUID
    ) -> AssignmentInvite | None:
        result = await self.session.execute(
            select(AssignmentInvite)
            .where(AssignmentInvite.company_id == company_id)
            .where(AssignmentInvite.respondent_profile_id == respondent_profile_id)
            .where(AssignmentInvite.status == "active")
            .where(AssignmentInvite.expires_at > datetime.now(UTC))
            .order_by(AssignmentInvite.created_at.desc())
        )
        return result.scalars().first()

    async def get_invite_by_token(self, token: str) -> AssignmentInvite | None:
        result = await self.session.execute(
            select(AssignmentInvite).where(AssignmentInvite.token == token)
        )
        return result.scalar_one_or_none()

    async def invalidate_invites_for_respondent(
        self, company_id: UUID, respondent_profile_id: UUID
    ) -> None:
        result = await self.session.execute(
            select(AssignmentInvite)
            .where(AssignmentInvite.company_id == company_id)
            .where(AssignmentInvite.respondent_profile_id == respondent_profile_id)
            .where(AssignmentInvite.status == "active")
        )
        invites = result.scalars().all()
        for invite in invites:
            invite.status = "revoked"
        await self.session.flush()
