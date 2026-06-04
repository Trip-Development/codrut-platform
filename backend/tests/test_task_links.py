import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.task_links import (
    TaskLinkClaims,
    build_task_url,
    create_task_token,
    parse_task_token,
)


def make_claims(*, expires_at: datetime | None = None) -> TaskLinkClaims:
    return TaskLinkClaims(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        assignment_ids=(uuid.uuid4(), uuid.uuid4()),
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
    )


def test_task_token_round_trips_claims() -> None:
    settings = Settings()
    claims = make_claims()

    token = create_task_token(claims, settings)
    parsed = parse_task_token(token, settings)

    assert parsed.company_id == claims.company_id
    assert parsed.respondent_profile_id == claims.respondent_profile_id
    assert parsed.assignment_ids == claims.assignment_ids


def test_task_token_rejects_tampering() -> None:
    settings = Settings()
    token = create_task_token(make_claims(), settings)

    with pytest.raises(DomainError, match="Invalid task link"):
        parse_task_token(f"{token}x", settings)


def test_task_token_rejects_expired_claims() -> None:
    settings = Settings()
    token = create_task_token(
        make_claims(expires_at=datetime.now(UTC) - timedelta(minutes=1)),
        settings,
    )

    with pytest.raises(DomainError, match="expired"):
        parse_task_token(token, settings)


def test_build_task_url_points_to_participant_bundle() -> None:
    settings = Settings(public_app_url="https://app.codrut.ro")

    url = build_task_url("token.value", settings)

    assert url == "https://app.codrut.ro/invite/token.value"
