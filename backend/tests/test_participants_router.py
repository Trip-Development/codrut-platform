import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from codrut.core.errors import DomainError
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.participants.router import get_my_workspace


@pytest.mark.asyncio
async def test_secure_invite_session_cannot_open_participant_workspace() -> None:
    principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email="temporary@example.com",
        role=UserRole.participant,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token="secure-session",  # noqa: S106
        assignment_invite_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(),),
        access_mode="secure_link",
    )

    with pytest.raises(DomainError) as exc_info:
        await get_my_workspace(principal=principal, session=AsyncMock())

    assert exc_info.value.code == "secure_invite_dashboard_forbidden"
