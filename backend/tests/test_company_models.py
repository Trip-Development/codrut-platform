import uuid

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.core.security import hash_password
from codrut.modules.companies.models import (
    CompanyMembershipRole,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.companies.schemas import ParticipantResponse
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    User,
    UserAccountType,
    UserRole,
)


def test_company_participant_tables_are_registered() -> None:
    assert {
        "companies",
        "company_memberships",
        "participant_profiles",
        "participant_reporting_relationships",
        "company_access_codes",
    }.issubset(Base.metadata.tables)


def test_company_relationship_mappers_configure() -> None:
    configure_mappers()


def test_membership_role_values_support_admin_and_participants() -> None:
    assert {role.value for role in CompanyMembershipRole} == {
        "owner",
        "trainer",
        "participant",
    }


def test_participant_profile_matches_roster_shape() -> None:
    columns = Base.metadata.tables["participant_profiles"].columns

    assert {
        "full_name",
        "email",
        "reports_to_name",
        "position",
        "location",
        "pcm_profile",
    }.issubset(columns.keys())
    assert columns["pcm_profile"].nullable
    assert columns["reports_to_name"].nullable


def test_participant_response_distinguishes_shadow_and_permanent_accounts() -> None:
    shadow_user = User(
        id=uuid.uuid4(),
        email="temporary@example.com",
        password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        role=UserRole.participant,
        account_type=UserAccountType.guest,
    )
    shadow_profile = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=shadow_user.id,
        full_name="Temporary Participant",
        email=shadow_user.email,
        user=shadow_user,
    )
    permanent_user = User(
        id=uuid.uuid4(),
        email="permanent@example.com",
        password_hash=hash_password("permanent-password-123"),
        role=UserRole.participant,
    )
    permanent_profile = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=permanent_user.id,
        full_name="Permanent Participant",
        email=permanent_user.email,
        user=permanent_user,
    )

    assert ParticipantResponse.model_validate(shadow_profile).is_shadow_account is True
    assert ParticipantResponse.model_validate(permanent_profile).is_shadow_account is False


def test_participant_profile_is_company_scoped() -> None:
    constraints = Base.metadata.tables["participant_profiles"].constraints
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("company_id", "email") in unique_columns
    assert ("user_id",) not in unique_columns


def test_reporting_relationship_supports_org_chart_without_self_reports() -> None:
    table = Base.metadata.tables["participant_reporting_relationships"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    foreign_key_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    checks = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert ("participant_profile_id",) in unique_columns
    assert ("company_id", "participant_profile_id") in foreign_key_columns
    assert ("company_id", "manager_profile_id") in foreign_key_columns
    assert "participant_profile_id <> manager_profile_id" in checks


def test_project_membership_timestamps_do_not_depend_only_on_database_defaults() -> None:
    table = Base.metadata.tables["project_memberships"]

    assert table.c.created_at.default is not None
    assert table.c.created_at.server_default is not None
    assert table.c.updated_at.default is not None
    assert table.c.updated_at.server_default is not None
    assert ProjectMembership.created_at.property.columns[0].default is not None
    assert ProjectMembership.updated_at.property.columns[0].onupdate is not None
