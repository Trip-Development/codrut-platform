from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from codrut.core.errors import DomainError

PackageKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
ContentKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9_]+$",
    ),
]


class ParticipantScaleOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value: int | float | str
    label: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class ParticipantStatement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: ContentKey
    code: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=2000)
    scale: list[ParticipantScaleOption] | None = None


class ParticipantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: ContentKey
    code: str = Field(min_length=1, max_length=120)
    type: Literal["likert", "statement_score_set", "single_choice"]
    label: str = Field(min_length=1, max_length=2000)
    required: bool = True
    instructions: str | None = Field(default=None, max_length=4000)
    scale: list[ParticipantScaleOption] = Field(min_length=1)
    statements: list[ParticipantStatement] | None = None

    @model_validator(mode="after")
    def validate_statement_shape(self) -> ParticipantQuestion:
        if self.type == "statement_score_set" and not self.statements:
            raise ValueError("statement_score_set questions require public statements")
        return self


class ParticipantSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: ContentKey
    title: str = Field(min_length=1, max_length=500)
    questions: list[ParticipantQuestion] = Field(min_length=1)


class ParticipantQuestionnaireSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["questionnaire.v1"]
    audience: Literal["leadership", "team", "participant"] | None = None
    instructions: str | None = Field(default=None, max_length=4000)
    sections: list[ParticipantSection] = Field(min_length=1)


class ProtectedQuestionnaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: ContentKey
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    participant_schema: dict[str, Any]
    private_config: dict[str, Any] = Field(default_factory=dict)
    feedback_policy: dict[str, Any] = Field(default_factory=dict)
    trainer_visibility_policy: dict[str, Any] = Field(default_factory=dict)
    activate: bool = True


class ProtectedEmailTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: ContentKey
    version: int = Field(ge=1)
    subject: str = Field(min_length=1, max_length=255)
    html_body: str = Field(min_length=1)
    text_body: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    audience: str | None = Field(default=None, max_length=100)
    activate: bool = True


class ProtectedContentPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_version: Literal["protected-content.v1"] = "protected-content.v1"
    package_id: PackageKey
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    questionnaires: list[ProtectedQuestionnaire] = Field(default_factory=list)
    email_templates: list[ProtectedEmailTemplate] = Field(default_factory=list)


def canonical_checksum(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def package_checksum(package: ProtectedContentPackage) -> str:
    return canonical_checksum(package.model_dump(mode="json", exclude={"checksum"}))


def content_checksum(value: BaseModel) -> str:
    return canonical_checksum(value.model_dump(mode="json"))


def load_protected_content_package(raw: bytes | str) -> ProtectedContentPackage:
    try:
        payload = json.loads(raw)
        package = ProtectedContentPackage.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise DomainError(
            "Protected content package is invalid.",
            code="protected_content_invalid",
        ) from exc

    if not package.questionnaires and not package.email_templates:
        raise DomainError(
            "Protected content package is empty.",
            code="protected_content_empty",
        )
    if package_checksum(package) != package.checksum:
        raise DomainError(
            "Protected content checksum does not match the package payload.",
            code="protected_content_checksum_mismatch",
        )

    questionnaire_keys = [(item.key, item.version) for item in package.questionnaires]
    template_keys = [(item.key, item.version) for item in package.email_templates]
    if len(questionnaire_keys) != len(set(questionnaire_keys)):
        raise DomainError(
            "Protected content package repeats a questionnaire key and version.",
            code="protected_content_duplicate_questionnaire",
        )
    if len(template_keys) != len(set(template_keys)):
        raise DomainError(
            "Protected content package repeats an email template key and version.",
            code="protected_content_duplicate_template",
        )
    for questionnaire in package.questionnaires:
        questionnaire.participant_schema = _project_participant_schema(
            questionnaire.participant_schema
        )
        _validate_feedback_policy(questionnaire.feedback_policy)
        _validate_trainer_visibility_policy(questionnaire.trainer_visibility_policy)
    return package


def reversion_protected_content_package(
    raw: bytes | str,
    *,
    package_id: str,
) -> ProtectedContentPackage:
    try:
        payload = json.loads(raw)
        source = ProtectedContentPackage.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise DomainError(
            "Protected content source package is invalid.",
            code="protected_content_invalid",
        ) from exc
    if package_checksum(source) != source.checksum:
        raise DomainError(
            "Protected content checksum does not match the source package.",
            code="protected_content_checksum_mismatch",
        )
    if source.package_id == package_id:
        raise DomainError(
            "A re-versioned package requires a new package ID.",
            code="protected_content_package_id_unchanged",
        )

    transformed = source.model_dump(mode="json")
    transformed["package_id"] = package_id
    for questionnaire in transformed["questionnaires"]:
        questionnaire["version"] += 1
        questionnaire["participant_schema"].pop("response", None)
    for template in transformed["email_templates"]:
        template["version"] += 1
    transformed["checksum"] = canonical_checksum(
        {key: value for key, value in transformed.items() if key != "checksum"}
    )
    projected = load_protected_content_package(json.dumps(transformed, ensure_ascii=False))
    projected.checksum = package_checksum(projected)
    return load_protected_content_package(
        json.dumps(projected.model_dump(mode="json"), ensure_ascii=False)
    )


def _project_participant_schema(schema: dict[str, Any]) -> dict[str, Any]:
    try:
        projection = ParticipantQuestionnaireSchema.model_validate(schema)
    except ValidationError as exc:
        extra_field = next(
            (error for error in exc.errors() if error.get("type") == "extra_forbidden"),
            None,
        )
        if extra_field is not None:
            path = ".".join(str(segment) for segment in extra_field["loc"])
            raise DomainError(
                f"Participant questionnaire schema contains non-public metadata at {path}.",
                code="protected_content_participant_schema_private",
            ) from exc
        raise DomainError(
            "Participant questionnaire schema does not match the public contract.",
            code="protected_content_participant_schema_invalid",
        ) from exc
    return projection.model_dump(mode="json", exclude_none=True)


def _validate_feedback_policy(policy: dict[str, Any]) -> None:
    if not policy:
        return
    publication = policy.get("publication")
    if publication is not None and publication not in {"none", "aggregate"}:
        raise DomainError(
            "Feedback policy publication must be none or aggregate.",
            code="protected_content_feedback_policy_invalid",
        )
    if publication is not None:
        minimum = _policy_positive_int(policy.get("minimum_completed"), default=2)
        target = _policy_positive_int(policy.get("target_completed"), default=3)
        if minimum < 2 or target < minimum:
            raise DomainError(
                "Feedback policy requires a minimum of two and a target at least as large.",
                code="protected_content_feedback_policy_invalid",
            )
        dimension_ids = _policy_dimension_ids(policy.get("dimension_ids", []))
        if publication == "aggregate" and not dimension_ids:
            raise DomainError(
                "Aggregate feedback policy must declare participant-visible dimensions.",
                code="protected_content_feedback_policy_invalid",
            )

    participant_results = policy.get("participant_results")
    if participant_results is None:
        return
    if not isinstance(participant_results, dict):
        raise DomainError(
            "Participant result policy must be an object.",
            code="protected_content_feedback_policy_invalid",
        )
    result_publication = participant_results.get("publication")
    if result_publication not in {"none", "scores", "scores_and_interpretation"}:
        raise DomainError(
            "Participant result publication mode is invalid.",
            code="protected_content_feedback_policy_invalid",
        )
    result_dimensions = _policy_dimension_ids(participant_results.get("dimension_ids", []))
    if result_publication != "none" and not result_dimensions:
        raise DomainError(
            "Published participant results must declare visible dimensions.",
            code="protected_content_feedback_policy_invalid",
        )
    target_types = participant_results.get("target_types", ["self", "team"])
    if not isinstance(target_types, list) or any(
        value not in {"self", "person", "team"} for value in target_types
    ):
        raise DomainError(
            "Participant result target types are invalid.",
            code="protected_content_feedback_policy_invalid",
        )
    include_primary = participant_results.get("include_primary_result", True)
    if not isinstance(include_primary, bool):
        raise DomainError(
            "Participant result primary-result policy must be boolean.",
            code="protected_content_feedback_policy_invalid",
        )
    require_self_target = participant_results.get("require_self_target", False)
    if not isinstance(require_self_target, bool):
        raise DomainError(
            "Participant self-target policy must be boolean.",
            code="protected_content_feedback_policy_invalid",
        )


def _policy_dimension_ids(value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise DomainError(
            "Feedback policy dimension IDs must be non-empty strings.",
            code="protected_content_feedback_policy_invalid",
        )
    if len(value) != len(set(value)):
        raise DomainError(
            "Feedback policy repeats a dimension ID.",
            code="protected_content_feedback_policy_invalid",
        )
    return value


def _validate_trainer_visibility_policy(policy: dict[str, Any]) -> None:
    raw_responses = policy.get("raw_responses")
    if raw_responses is None:
        return
    if raw_responses not in {"hidden", "policy_controlled", "visible"}:
        raise DomainError(
            "Trainer visibility policy has an invalid raw-response mode.",
            code="protected_content_trainer_visibility_invalid",
        )


def _policy_positive_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DomainError(
            "Feedback policy thresholds must be positive integers.",
            code="protected_content_feedback_policy_invalid",
        )
    return value
