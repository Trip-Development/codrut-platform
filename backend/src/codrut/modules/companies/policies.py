from fastapi import HTTPException, status

from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def require_trainer_principal(principal: SessionPrincipal) -> None:
    if principal.role != UserRole.trainer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trainer access required",
        )
