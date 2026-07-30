import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.core.csrf import csrf_token_for_session, set_csrf_cookie
from codrut.core.errors import DomainError
from codrut.core.request_id import request_id_from_request
from codrut.modules.identity.schemas import (
    AuthResponse,
    ConsentRequest,
    CsrfTokenResponse,
    InviteExchangeRequest,
    InviteExchangeResponse,
    InviteVerifyResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RegisterRequest,
    SessionPrincipal,
)
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.session_cookie import (
    SESSION_COOKIE_NAME,
    delete_session_cookie,
    set_session_cookie,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/invite/verify", response_model=InviteVerifyResponse)
async def verify_invite(
    token: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> InviteVerifyResponse:
    response.headers["Cache-Control"] = "no-store"
    return await IdentityService(session).verify_invite_token(token)


@router.post("/invite/exchange", response_model=InviteExchangeResponse)
async def exchange_invite(
    payload: InviteExchangeRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> InviteExchangeResponse:
    try:
        result = await IdentityService(session).verify_invite_token_and_create_session(
            payload.token,
            existing_session_token=request.cookies.get(SESSION_COOKIE_NAME),
            replace_existing_session=payload.replace_existing_session,
        )
    except DomainError as exc:
        if exc.code != "invite_session_conflict":
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    await session.commit()
    response.headers["Cache-Control"] = "no-store"
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
    request: Request,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PasswordResetResponse:
    request_id = request_id_from_request(request)
    try:
        await IdentityService(session).request_password_reset(
            payload,
            request_id=request_id,
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            logger.exception(
                "Password reset transaction rollback failed.",
                extra={
                    "auth_event": "password_reset_rollback_failure",
                    "request_id": request_id,
                },
            )
        logger.exception(
            "Password reset request completed with an internal delivery failure.",
            extra={
                "auth_event": "password_reset_internal_failure",
                "request_id": request_id,
            },
        )
    return PasswordResetResponse()


@router.post("/reset-password/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PasswordResetResponse:
    await IdentityService(session).confirm_password_reset(payload)
    await session.commit()
    return PasswordResetResponse()


@router.post("/change-password", response_model=PasswordResetResponse)
async def change_password(
    payload: PasswordChangeRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PasswordResetResponse:
    await IdentityService(session).change_password(principal.user_id, payload)
    await session.commit()
    return PasswordResetResponse()


@router.post("/consent", response_model=AuthResponse)
async def consent(
    payload: ConsentRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AuthResponse:
    result = await IdentityService(session).accept_terms(
        principal.user_id,
        payload,
        session_token=principal.session_token,
    )
    await session.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> None:
    await IdentityService(session).logout(principal.session_token)
    await session.commit()
    delete_session_cookie(response)


@router.get("/csrf", response_model=CsrfTokenResponse)
async def csrf_token(request: Request, response: Response) -> CsrfTokenResponse:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    set_csrf_cookie(response, session_token)
    return CsrfTokenResponse(csrf_token=csrf_token_for_session(session_token))


@router.get("/me", response_model=SessionPrincipal)
async def me(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
) -> SessionPrincipal:
    return principal


def _set_session_cookie(response: Response, token: str) -> None:
    set_session_cookie(response, token)
