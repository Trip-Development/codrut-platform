import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from codrut.core.config import get_settings
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User


@pytest.mark.asyncio
async def test_postgres_db_connection() -> None:
    """Verifies that we can connect to the database and perform basic operations."""
    settings = get_settings()
    # Ensure we are not using a fake database URL
    assert "postgresql" in settings.database_url
    assert User.__name__ == "User"

    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            # 1. Create a test company
            test_company = Company(name="Integration Test Company Co.")
            session.add(test_company)
            await session.flush()
            company_id = test_company.id

            # 2. Query it back
            stmt = select(Company).where(Company.id == company_id)
            result = await session.execute(stmt)
            queried_company = result.scalar_one_or_none()

            assert queried_company is not None
            assert queried_company.name == "Integration Test Company Co."

            # 3. Clean up (rollback or delete)
            await session.delete(queried_company)
            await session.commit()

            # 4. Verify deletion
            result_after_delete = await session.execute(stmt)
            assert result_after_delete.scalar_one_or_none() is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_project_membership_insert_sets_timestamps() -> None:
    """Verifies project roster membership inserts do not depend on DB defaults alone."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            company = Company(name=f"Integration Timestamp Company {uuid.uuid4()}")
            session.add(company)
            await session.flush()

            project = CompanyProject(company_id=company.id, name="Leadership Cohort")
            participant = ParticipantProfile(
                company_id=company.id,
                full_name="Maria Popescu",
                email=f"maria-{uuid.uuid4()}@example.com",
            )
            session.add_all([project, participant])
            await session.flush()

            membership = ProjectMembership(
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=participant.id,
                position="Manager",
                location="Bucharest",
                role_group="leadership",
            )
            session.add(membership)
            await session.flush()

            assert membership.created_at is not None
            assert membership.updated_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_redis_cache_connection() -> None:
    """Verifies that the Redis cache/queue server is accessible and functional."""
    settings = get_settings()
    # Connect using the configured Redis URL
    client = Redis.from_url(settings.redis_url, socket_timeout=5.0)

    try:
        # Ping the server
        pong = await client.ping()
        assert pong is True

        # Test set and get
        test_key = "integration_test_key"
        test_value = "working_fine"
        await client.set(test_key, test_value, ex=10)

        value = await client.get(test_key)
        assert value is not None
        assert value.decode("utf-8") == test_value

        # Clean up
        await client.delete(test_key)
    finally:
        await client.aclose()
