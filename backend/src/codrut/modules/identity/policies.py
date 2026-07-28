from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def is_trainer(principal: SessionPrincipal) -> bool:
    return principal.can_access_workspace(UserRole.trainer)
