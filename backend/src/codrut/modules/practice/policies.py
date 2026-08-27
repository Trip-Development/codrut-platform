from __future__ import annotations

from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION


def require_current_terms(principal: SessionPrincipal) -> None:
    """Ensure principal has accepted the current privacy and confidentiality terms."""
    if not principal.can_access_workspace(UserRole.participant):
        return
    if (
        principal.terms_accepted_at is None
        or principal.terms_version != CURRENT_TERMS_VERSION
    ):
        raise DomainError(
            "Privacy and confidentiality terms must be accepted.",
            code="terms_required",
        )


def ensure_participant_may_practice(
    principal: SessionPrincipal,
    program_enabled: bool,
    membership_active: bool,
) -> None:
    """Pure authorization check for practice participation.

    Raises DomainError with specific error codes:
    - participant_required: wrong role / workspace
    - secure_link_practice_forbidden: accessed via questionnaire invite link
    - guest_practice_forbidden: guest account, unregistered
    - practice_not_enabled: practice disabled for this project
    - not_project_member: participant is not an active member of this project
    - terms_required: current terms not accepted
    """
    if not principal.can_access_workspace(UserRole.participant):
        raise DomainError(
            "Participant access required",
            code="participant_required",
        )
    if principal.access_mode == "secure_link":
        raise DomainError(
            "Practice is forbidden via secure link access",
            code="secure_link_practice_forbidden",
        )
    if principal.account_type == UserAccountType.guest:
        raise DomainError(
            "Registered participant account required for practice",
            code="guest_practice_forbidden",
        )
    if not program_enabled:
        raise DomainError(
            "Practice is not enabled for this project",
            code="practice_not_enabled",
        )
    if not membership_active:
        raise DomainError(
            "Active project membership required for practice",
            code="not_project_member",
        )
    require_current_terms(principal)


def ensure_trainer_may_read_feedback(
    principal: SessionPrincipal,
    is_project_trainer: bool,
) -> None:
    """Ensure trainer is authorized to read qualitative practice feedback for their project."""
    if not principal.can_access_workspace(UserRole.trainer):
        raise DomainError(
            "Trainer access required",
            code="trainer_required",
        )
    if not is_project_trainer:
        raise DomainError(
            "Trainer is not authorized for this project",
            code="not_project_trainer",
        )
