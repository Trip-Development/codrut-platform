import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import get_settings
from codrut.core.database import get_session
from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION

logger = logging.getLogger(__name__)
LOCAL_AUTH_ROLE_HEADER = "X-Codrut-Dev-Role"
LOCAL_AUTH_HOSTS = {"localhost", "127.0.0.1", "::1", "backend", "frontend", "testserver"}


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


async def current_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> SessionPrincipal:
    settings = get_settings()
    local_role_value = request.headers.get(LOCAL_AUTH_ROLE_HEADER)
    if local_role_value and settings.local_auth_bypass and request.url.hostname in LOCAL_AUTH_HOSTS:
        try:
            local_role = UserRole(local_role_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid local development role.",
            ) from exc

        local_email = (
            settings.local_auth_trainer_email
            if local_role == UserRole.trainer
            else settings.local_auth_participant_email
        )
        principal = await IdentityService(session).principal_for_local_user(
            email=local_email,
            role=local_role,
        )
        if principal is None:
            logger.error(
                "Local authentication user is missing or has the wrong role.",
                extra={"auth_event": "local_auth_user_missing", "local_role": local_role.value},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local preview user is unavailable. Run the local preview seed.",
            )
        return principal

    token = request.cookies.get("codrut_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        principal = await IdentityService(session).principal_from_session_token(token)
    except Exception:
        logger.exception(
            "Session validation failed while resolving current principal.",
            extra={"auth_event": "session_validation_failed"},
        )
        raise
    if principal is None:
        logger.info(
            "Rejected invalid or expired session cookie.",
            extra={"auth_event": "session_rejected"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return principal


async def secure_link_principal(
    token: str,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> SessionPrincipal:
    if not principal.can_access_workspace(UserRole.participant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Participant access is required.",
        )
    require_current_terms(principal)
    await IdentityService(session).require_secure_link_consent(principal, token)
    return principal


def require_current_terms(principal: SessionPrincipal) -> None:
    if not principal.can_access_workspace(UserRole.participant):
        return
    if principal.terms_accepted_at is None or principal.terms_version != CURRENT_TERMS_VERSION:
        raise DomainError(
            "Privacy and confidentiality terms must be accepted.",
            code="terms_required",
        )
