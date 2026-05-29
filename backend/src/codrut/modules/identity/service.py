from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.core.security import hash_password, new_session_token, verify_password
from codrut.modules.identity.models import Session, User, UserRole
from codrut.modules.identity.repository import IdentityRepository, hash_session_token
from codrut.modules.identity.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    SessionPrincipal,
)


@dataclass(frozen=True)
class AuthResult:
    response: AuthResponse
    session_token: str


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = IdentityRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResult:
        existing = await self.repository.get_user_by_email(payload.email)
        if existing is not None:
            raise DomainError("An account with this email already exists.", code="email_taken")
        user = await self.repository.add_user(
            User(
                email=payload.email.lower(),
                password_hash=hash_password(payload.password),
                role=UserRole.participant,
            )
        )
        token = await self._create_session(user)
        return AuthResult(response=self._response(user), session_token=token)

    async def login(self, payload: LoginRequest) -> AuthResult:
        user = await self.repository.get_user_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise DomainError("Invalid email or password.", code="invalid_credentials")
        token = await self._create_session(user)
        return AuthResult(response=self._response(user), session_token=token)

    async def logout(self, token: str) -> None:
        await self.repository.delete_session_by_token(token)

    async def principal_from_session_token(self, token: str) -> SessionPrincipal | None:
        user = await self.repository.get_user_by_session_token(token)
        if user is None:
            return None
        return SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=user.role,
            session_token=token,
        )

    async def _create_session(self, user: User) -> str:
        token = new_session_token()
        await self.repository.add_session(
            Session(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=datetime.now(UTC) + timedelta(days=14),
            )
        )
        return token

    @staticmethod
    def _response(user: User) -> AuthResponse:
        return AuthResponse(user_id=user.id, email=user.email, role=user.role)
