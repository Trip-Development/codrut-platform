from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import get_settings
from codrut.modules.identity.schemas import (
    AuthResponse,
    ConsentRequest,
    InviteVerifyResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RegisterRequest,
    SessionPrincipal,
)
from codrut.modules.identity.service import IdentityService

router = APIRouter()


@router.get("/invite/verify", response_model=InviteVerifyResponse)
async def verify_invite(
    token: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> InviteVerifyResponse:
    result = await IdentityService(session).verify_invite_token_and_create_session(token)
    await session.commit()
    if result.session_token:
        _set_session_cookie(response, result.session_token)
    return result.response


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AuthResponse:
    result = await IdentityService(session).register(payload)
    await session.commit()
    _set_session_cookie(response, result.session_token)
    return result.response


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AuthResponse:
    result = await IdentityService(session).login(payload)
    await session.commit()
    _set_session_cookie(response, result.session_token)
    return result.response


@router.post("/reset-password", response_model=PasswordResetResponse)
async def request_password_reset(
    payload: PasswordResetRequest,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PasswordResetResponse:
    await IdentityService(session).request_password_reset(payload)
    await session.commit()
    return PasswordResetResponse()


@router.post("/reset-password/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PasswordResetResponse:
    await IdentityService(session).confirm_password_reset(payload)
    await session.commit()
    return PasswordResetResponse()


@router.post("/consent", response_model=AuthResponse)
async def consent(
    payload: ConsentRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AuthResponse:
    result = await IdentityService(session).accept_terms(principal.user_id, payload)
    await session.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    await IdentityService(session).logout(principal.session_token)
    await session.commit()
    response.delete_cookie("codrut_session", path="/")
    return response


@router.get("/me", response_model=SessionPrincipal)
async def me(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
) -> SessionPrincipal:
    return principal


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "codrut_session",
        token,
        max_age=int(timedelta(days=14).total_seconds()),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
