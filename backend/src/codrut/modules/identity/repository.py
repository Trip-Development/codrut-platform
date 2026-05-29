import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.identity.models import Session, User


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
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
