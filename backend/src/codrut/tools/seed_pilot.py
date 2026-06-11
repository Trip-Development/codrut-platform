import asyncio
import os
import uuid

from sqlalchemy import select

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.companies.models import Company, CompanyMembership, CompanyMembershipRole
from codrut.modules.identity.models import User, UserRole


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


async def seed_pilot() -> None:
    settings = get_settings()
    if settings.is_production and os.getenv("CODRUT_SEED_ALLOW_PRODUCTION") != "true":
        raise RuntimeError("Refusing to seed production without CODRUT_SEED_ALLOW_PRODUCTION=true.")

    trainer_email = _required_env("CODRUT_SEED_TRAINER_EMAIL").lower()
    trainer_password = _required_env("CODRUT_SEED_TRAINER_PASSWORD")
    company_name = os.getenv("CODRUT_SEED_COMPANY_NAME", "Pilot Codruț").strip()

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == trainer_email))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=trainer_email,
                password_hash=hash_password(trainer_password),
                role=UserRole.trainer,
            )
            session.add(user)
        else:
            user.password_hash = hash_password(trainer_password)
            user.role = UserRole.trainer

        company = (
            await session.execute(select(Company).where(Company.name == company_name))
        ).scalar_one_or_none()
        if company is None:
            company = Company(id=uuid.uuid4(), name=company_name)
            session.add(company)

        await session.flush()

        membership = (
            await session.execute(
                select(CompanyMembership)
                .where(CompanyMembership.company_id == company.id)
                .where(CompanyMembership.user_id == user.id)
            )
        ).scalar_one_or_none()
        if membership is None:
            session.add(
                CompanyMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    user_id=user.id,
                    role=CompanyMembershipRole.owner,
                )
            )
        else:
            membership.role = CompanyMembershipRole.owner

        await session.commit()

    print(f"Seeded trainer account: {trainer_email}")
    print(f"Seeded company: {company_name}")


def main() -> None:
    asyncio.run(seed_pilot())


if __name__ == "__main__":
    main()
