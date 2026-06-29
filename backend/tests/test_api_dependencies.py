import uuid
from datetime import UTC, datetime

import pytest

from codrut.api.dependencies import CURRENT_TERMS_VERSION, require_current_terms
from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def principal(
    *,
    role: UserRole = UserRole.participant,
    terms_accepted_at: datetime | None = None,
    terms_version: str | None = None,
) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid.uuid4(),
        email="participant@example.com",
        role=role,
        terms_accepted_at=terms_accepted_at,
        terms_version=terms_version,
        session_token="test-session",  # noqa: S106
    )


def test_require_current_terms_allows_current_participant_consent() -> None:
    require_current_terms(
        principal(
            terms_accepted_at=datetime.now(UTC),
            terms_version=CURRENT_TERMS_VERSION,
        )
    )


def test_require_current_terms_blocks_unaccepted_participant_consent() -> None:
    with pytest.raises(DomainError) as exc_info:
        require_current_terms(principal())

    assert exc_info.value.code == "terms_required"


def test_require_current_terms_blocks_stale_participant_consent() -> None:
    with pytest.raises(DomainError) as exc_info:
        require_current_terms(
            principal(
                terms_accepted_at=datetime.now(UTC),
                terms_version="privacy-2025-01-01",
            )
        )

    assert exc_info.value.code == "terms_required"


def test_require_current_terms_does_not_apply_to_trainers() -> None:
    require_current_terms(principal(role=UserRole.trainer))
