from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.database import get_session
from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.service import IdentityService

CURRENT_TERMS_VERSION = "privacy-2026-06-12"


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


async def current_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> SessionPrincipal:
    token = request.cookies.get("codrut_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    principal = await IdentityService(session).principal_from_session_token(token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return principal


def require_current_terms(principal: SessionPrincipal) -> None:
    if principal.role != UserRole.participant:
        return
    if (
        principal.terms_accepted_at is None
        or principal.terms_version != CURRENT_TERMS_VERSION
    ):
        raise DomainError(
            "Privacy and confidentiality terms must be accepted.",
            code="terms_required",
        )
