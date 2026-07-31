from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from codrut.modules.forms.models import QuestionnaireDefinition


@dataclass(frozen=True)
class ScoreScale:
    score_unit: str
    scale_min: float
    scale_max: float


@dataclass(frozen=True)
class DefinitionScoreScale:
    scale: ScoreScale | None
    compatible: bool


def derive_definition_score_scale(
    definition: QuestionnaireDefinition | None,
    *,
    dimension_ids: Collection[str] | None = None,
) -> DefinitionScoreScale:
    if definition is None:
        return DefinitionScoreScale(scale=None, compatible=False)

    schemas = (
        _private_definition_schema(definition),
        getattr(definition, "schema", None),
    )
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        scoring = schema.get("scoring")
        if not isinstance(scoring, dict) or scoring.get("method") != "sum_by_group":
            continue
        group_scale = _sum_by_group_scale(
            schema,
            scoring,
            dimension_ids=dimension_ids,
            score_unit=_non_empty_string(scoring.get("score_unit")) or "score",
        )
        if group_scale is not None:
            return group_scale

    feedback_policy = getattr(definition, "feedback_policy", None)
    if isinstance(feedback_policy, dict):
        explicit = _explicit_scale(
            feedback_policy,
            default_unit=_inferred_output_unit(schemas) or "score",
        )
        if explicit is not None:
            return DefinitionScoreScale(scale=explicit, compatible=True)

    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        scoring = schema.get("scoring")
        if not isinstance(scoring, dict):
            continue
        method = scoring.get("method")
        score_unit = _non_empty_string(scoring.get("score_unit"))

        if method == "sum_by_group":
            explicit = _explicit_scale(scoring, default_unit=score_unit or "score")
            if explicit is not None:
                return DefinitionScoreScale(scale=explicit, compatible=True)

        if method == "average_statement_scores_by_section":
            if score_unit != "grade_1_to_5":
                return DefinitionScoreScale(
                    scale=ScoreScale(score_unit or "percent", 0.0, 100.0),
                    compatible=True,
                )
            minimum = _numeric(scoring.get("scale_min"))
            minimum = minimum if minimum is not None else 1.0
            maximum = _numeric(scoring.get("scale_max"))
            if minimum is not None and maximum is not None and maximum > minimum:
                return DefinitionScoreScale(
                    scale=ScoreScale(score_unit, minimum, maximum),
                    compatible=True,
                )

        explicit = _explicit_scale(scoring, default_unit=score_unit or "score")
        if explicit is not None:
            return DefinitionScoreScale(scale=explicit, compatible=True)

        normalize_to = _numeric(scoring.get("normalize_to"))
        if normalize_to is not None and normalize_to > 0:
            unit = score_unit or ("percent" if normalize_to == 100 else "score")
            return DefinitionScoreScale(
                scale=ScoreScale(unit, 0.0, normalize_to),
                compatible=True,
            )

        if method == "sum_statement_scores_by_driver":
            driver_scale = _sum_statement_scores_by_driver_scale(
                schema,
                scoring,
                dimension_ids=dimension_ids,
                score_unit=score_unit or "score",
            )
            if driver_scale is not None:
                return driver_scale

    return DefinitionScoreScale(scale=None, compatible=False)


def _inferred_output_unit(schemas: Collection[object]) -> str | None:
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        scoring = schema.get("scoring")
        if not isinstance(scoring, dict):
            continue
        explicit_unit = _non_empty_string(scoring.get("score_unit"))
        if explicit_unit is not None:
            return explicit_unit
        if scoring.get("method") == "average_statement_scores_by_section":
            return "percent"
        normalize_to = _numeric(scoring.get("normalize_to"))
        if normalize_to == 100:
            return "percent"
    return None


def _sum_by_group_scale(
    schema: dict[str, Any],
    scoring: dict[str, Any],
    *,
    dimension_ids: Collection[str] | None,
    score_unit: str,
) -> DefinitionScoreScale | None:
    requested_ids = set(dimension_ids) if dimension_ids is not None else None
    groups = [
        group
        for group in scoring.get("groups", [])
        if isinstance(group, dict)
        and isinstance(group.get("id"), str)
        and (requested_ids is None or group["id"] in requested_ids)
    ]
    if not groups:
        return None
    if requested_ids is not None and {group["id"] for group in groups} != requested_ids:
        return DefinitionScoreScale(scale=None, compatible=False)

    questions = {
        question["id"]: question
        for section in schema.get("sections", [])
        if isinstance(section, dict)
        for question in section.get("questions", [])
        if isinstance(question, dict) and isinstance(question.get("id"), str)
    }
    ranges: set[tuple[float, float]] = set()
    for group in groups:
        question_ids = group.get("question_ids")
        if not isinstance(question_ids, list) or not question_ids:
            return DefinitionScoreScale(scale=None, compatible=False)
        minimum = 0.0
        maximum = 0.0
        for question_id in question_ids:
            question = questions.get(question_id)
            if question is None:
                return DefinitionScoreScale(scale=None, compatible=False)
            values = [
                value
                for option in question.get("scale", [])
                if isinstance(option, dict) and (value := _numeric(option.get("value"))) is not None
            ]
            if not values:
                return DefinitionScoreScale(scale=None, compatible=False)
            minimum += min(values)
            maximum += max(values)
        if maximum <= minimum:
            return DefinitionScoreScale(scale=None, compatible=False)
        ranges.add((minimum, maximum))

    if len(ranges) != 1:
        return DefinitionScoreScale(scale=None, compatible=False)
    minimum, maximum = next(iter(ranges))
    return DefinitionScoreScale(
        scale=ScoreScale(score_unit, minimum, maximum),
        compatible=True,
    )


def _sum_statement_scores_by_driver_scale(
    schema: dict[str, Any],
    scoring: dict[str, Any],
    *,
    dimension_ids: Collection[str] | None,
    score_unit: str,
) -> DefinitionScoreScale | None:
    requested_ids = set(dimension_ids) if dimension_ids is not None else None
    configured_ids = {
        driver["id"]
        for driver in scoring.get("drivers", [])
        if isinstance(driver, dict) and isinstance(driver.get("id"), str)
    }
    target_ids = requested_ids if requested_ids is not None else configured_ids
    if not target_ids or (requested_ids is not None and not requested_ids <= configured_ids):
        return None

    totals = {driver_id: [0.0, 0.0] for driver_id in target_ids}
    seen_ids: set[str] = set()
    for section in schema.get("sections", []):
        if not isinstance(section, dict):
            continue
        for question in section.get("questions", []):
            if not isinstance(question, dict) or question.get("type") != "statement_score_set":
                continue
            question_scale = question.get("scale", [])
            for statement in question.get("statements", []):
                if not isinstance(statement, dict):
                    continue
                statement_scoring = statement.get("scoring")
                driver_id = (
                    statement_scoring.get("driver")
                    if isinstance(statement_scoring, dict)
                    else None
                )
                if driver_id not in target_ids:
                    continue
                scale = statement.get("scale") or question_scale
                values = [
                    value
                    for option in scale
                    if isinstance(option, dict)
                    and (value := _numeric(option.get("value"))) is not None
                ]
                if not values:
                    return DefinitionScoreScale(scale=None, compatible=False)
                totals[driver_id][0] += min(values)
                totals[driver_id][1] += max(values)
                seen_ids.add(driver_id)

    if seen_ids != target_ids:
        return DefinitionScoreScale(scale=None, compatible=False)
    ranges = {tuple(total) for total in totals.values()}
    if len(ranges) != 1:
        return DefinitionScoreScale(scale=None, compatible=False)
    minimum, maximum = next(iter(ranges))
    if maximum <= minimum:
        return DefinitionScoreScale(scale=None, compatible=False)
    return DefinitionScoreScale(
        scale=ScoreScale(score_unit, minimum, maximum),
        compatible=True,
    )


def _explicit_scale(
    source: dict[str, Any],
    *,
    default_unit: str = "score",
) -> ScoreScale | None:
    minimum = _numeric(source.get("scale_min"))
    minimum = minimum if minimum is not None else 0.0
    maximum = _numeric(source.get("scale_max"))
    if maximum is None or maximum <= minimum:
        return None
    return ScoreScale(
        _non_empty_string(source.get("score_unit")) or default_unit,
        minimum,
        maximum,
    )


def _private_definition_schema(definition: QuestionnaireDefinition) -> dict[str, Any]:
    if not definition.private_config:
        return {}
    schema = definition.private_config.get("schema")
    return schema if isinstance(schema, dict) else {}


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
