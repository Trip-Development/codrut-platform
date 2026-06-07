import asyncio
import pytest
from sqlalchemy import select
from redis.asyncio import Redis

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import Company
from codrut.modules.identity.models import User

@pytest.mark.asyncio
async def test_postgres_db_connection() -> None:
    """Verifies that we can connect to the database and perform basic operations."""
    settings = get_settings()
    # Ensure we are not using a fake database URL
    assert "postgresql" in settings.database_url

    async with SessionLocal() as session:
        # 1. Create a test company
        test_company = Company(
            name="Integration Test Company Co."
        )
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
