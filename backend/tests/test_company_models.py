from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.companies.models import CompanyMembershipRole


def test_company_participant_tables_are_registered() -> None:
    assert {
        "companies",
        "company_memberships",
        "participant_profiles",
        "participant_reporting_relationships",
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

    assert {"full_name", "email", "position", "location", "pcm_profile"}.issubset(
        columns.keys()
    )
    assert columns["pcm_profile"].nullable


def test_participant_profile_is_company_scoped() -> None:
    constraints = Base.metadata.tables["participant_profiles"].constraints
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("company_id", "email") in unique_columns
    assert ("user_id",) in unique_columns


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
