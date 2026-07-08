from pathlib import Path

from codrut.main import create_app
from codrut.tools.export_openapi import check_openapi_schema, write_openapi_schema


def operation_ids() -> list[str]:
    schema = create_app().openapi()
    return [
        operation["operationId"]
        for methods in schema["paths"].values()
        for operation in methods.values()
    ]


def test_openapi_operation_ids_are_unique() -> None:
    ids = operation_ids()

    assert len(ids) == len(set(ids))


def test_openapi_operation_ids_preserve_existing_shape() -> None:
    schema = create_app().openapi()

    assert schema["paths"]["/api/auth/login"]["post"]["operationId"] == (
        "login_api_auth_login_post"
    )
    assert schema["paths"]["/api/companies/{company_id}/participants"]["get"][
        "operationId"
    ] == "list_company_participants_api_companies__company_id__participants_get"


def test_openapi_validation_errors_use_standard_error_envelope() -> None:
    schema = create_app().openapi()

    validation_schema = schema["paths"]["/api/auth/login"]["post"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]

    assert validation_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_openapi_export_is_deterministic(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    write_openapi_schema(output)
    first_export = output.read_text()
    write_openapi_schema(output)

    assert output.read_text() == first_export
    assert check_openapi_schema(output)
