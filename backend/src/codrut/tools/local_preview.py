from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codrut.core.config import Settings

PREVIEW_DEFINITION_VERSION = 9001
PREVIEW_SOURCE = "local_preview"
PREVIEW_PARTICIPANT_EMAIL_DOMAIN = "preview.example.com"


@dataclass(frozen=True)
class PreviewQuestionnaireDefinition:
    key: str
    title: str
    description: str
    schema: dict[str, Any]
    feedback_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewEmailTemplate:
    key: str
    version: int
    subject: str
    html_body: str
    text_body: str
    required_context: frozenset[str]
    audience: str


def assert_local_preview_allowed(settings: Settings) -> None:
    if settings.is_production:
        raise RuntimeError("Local preview data cannot be seeded in production.")
    if settings.env != "development":
        raise RuntimeError("Local preview data can only be seeded in development.")


def build_preview_questionnaire_definitions() -> list[PreviewQuestionnaireDefinition]:
    return [
        _pcm_preview(),
        _team_preview(),
        _work_style_preview(),
        _feedback_preview(),
    ]


def build_preview_email_templates() -> dict[str, PreviewEmailTemplate]:
    variables = frozenset({"first_name", "action_url"})
    templates = (
        PreviewEmailTemplate(
            key="preview_evaluation_invite",
            version=PREVIEW_DEFINITION_VERSION,
            subject="Ai activități noi în Cody",
            html_body=(
                "<p>Bună, ${first_name}.</p><p>Activitățile tale sunt pregătite.</p>"
                '<p><a href="${action_url}">Deschide</a></p>'
            ),
            text_body="Bună, ${first_name}. Activitățile tale sunt pregătite: ${action_url}",
            required_context=variables,
            audience="preview:participant",
        ),
        PreviewEmailTemplate(
            key="preview_evaluation_reminder",
            version=PREVIEW_DEFINITION_VERSION,
            subject="Reamintire pentru activitățile tale",
            html_body=(
                "<p>Bună, ${first_name}.</p><p>Poți continua activitatea începută.</p>"
                '<p><a href="${action_url}">Continuă</a></p>'
            ),
            text_body="Bună, ${first_name}. Continuă activitatea: ${action_url}",
            required_context=variables,
            audience="preview:participant",
        ),
        PreviewEmailTemplate(
            key="preview_campaign_reactivation",
            version=PREVIEW_DEFINITION_VERSION,
            subject="Reluăm conversația despre dezvoltarea echipei",
            html_body=(
                "<p>Bună, ${first_name}.</p><p>Avem o resursă nouă pentru echipe.</p>"
                '<p><a href="${action_url}">Vezi detaliile</a></p>'
            ),
            text_body="Bună, ${first_name}. Vezi resursa nouă: ${action_url}",
            required_context=variables,
            audience="campaign:past_customer",
        ),
        PreviewEmailTemplate(
            key="preview_campaign_report",
            version=PREVIEW_DEFINITION_VERSION,
            subject="O actualizare scurtă din program",
            html_body=(
                "<p>Bună, ${first_name}.</p><p>Am publicat o actualizare de program.</p>"
                '<p><a href="${action_url}">Citește</a></p>'
            ),
            text_body="Bună, ${first_name}. Citește actualizarea: ${action_url}",
            required_context=variables,
            audience="campaign:past_customer",
        ),
    )
    return {template.key: template for template in templates}


def build_sample_answers(
    schema: dict[str, Any],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    answer_index = 0
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            question_scale = question.get("scale", [])
            if question.get("type") == "statement_score_set":
                for statement in question.get("statements", []):
                    scale = statement.get("scale") or question_scale
                    if not scale:
                        continue
                    answers[f"{question['id']}:{statement['id']}"] = scale[
                        (answer_index + offset) % len(scale)
                    ]["value"]
                    answer_index += 1
                    if limit is not None and len(answers) >= limit:
                        return answers
                continue
            if not question_scale:
                continue
            answers[question["id"]] = question_scale[(answer_index + offset) % len(question_scale)][
                "value"
            ]
            answer_index += 1
            if limit is not None and len(answers) >= limit:
                return answers
    return answers


def _scale(maximum: int = 5) -> list[dict[str, Any]]:
    return [{"value": value, "label": str(value)} for value in range(1, maximum + 1)]


def _pcm_preview() -> PreviewQuestionnaireDefinition:
    options = [
        {"value": "thinker", "label": "Gânditor"},
        {"value": "persister", "label": "Perseverent"},
        {"value": "harmonizer", "label": "Armonizator"},
    ]
    return PreviewQuestionnaireDefinition(
        key="pcm_base",
        title="Profil de comunicare, mostră",
        description="Două alegeri sintetice pentru verificarea fluxului local.",
        schema={
            "schema_version": "questionnaire.v1",
            "local_preview": {"sample": True},
            "sections": [
                {
                    "id": "profile",
                    "title": "Profil",
                    "questions": [
                        {
                            "id": "pcm_base",
                            "code": "BASE",
                            "type": "single_choice",
                            "label": "Alege stilul de bază pentru mostră",
                            "required": True,
                            "scale": options,
                        },
                        {
                            "id": "pcm_phase",
                            "code": "PHASE",
                            "type": "single_choice",
                            "label": "Alege faza pentru mostră",
                            "required": True,
                            "scale": options,
                        },
                    ],
                }
            ],
        },
    )


def _team_preview() -> PreviewQuestionnaireDefinition:
    groups = [
        ("team_signal_a", "Claritate"),
        ("team_signal_b", "Dialog"),
        ("team_signal_c", "Decizii"),
        ("team_signal_d", "Responsabilitate"),
        ("team_signal_e", "Rezultate"),
    ]
    questions = [
        {
            "id": f"team_sample_{index}",
            "code": f"T{index}",
            "type": "likert",
            "label": f"Afirmație sintetică pentru {label.lower()}",
            "required": True,
            "scale": _scale(3),
        }
        for index, (_group, label) in enumerate(groups, start=1)
    ]
    return PreviewQuestionnaireDefinition(
        key="lencioni",
        title="Evaluarea echipei, mostră",
        description="Conținut sintetic pentru stările de completare și raportare.",
        schema={
            "schema_version": "questionnaire.v1",
            "local_preview": {"sample": True},
            "sections": [{"id": "team", "title": "Echipă", "questions": questions}],
            "scoring": {
                "method": "sum_by_group",
                "groups": [
                    {"id": group, "label": label, "question_ids": [f"team_sample_{index}"]}
                    for index, (group, label) in enumerate(groups, start=1)
                ],
                "interpretation": [{"min": 1, "max": 3, "label": "Rezultat demonstrativ."}],
            },
        },
        feedback_policy={
            "participant_results": {
                "publication": "scores_and_interpretation",
                "target_types": ["team"],
                "dimension_ids": [group for group, _label in groups],
                "include_primary_result": True,
            }
        },
    )


def _work_style_preview() -> PreviewQuestionnaireDefinition:
    drivers = [
        ("work_signal_a", "Autonomie"),
        ("work_signal_b", "Rigoare"),
        ("work_signal_c", "Efort"),
        ("work_signal_d", "Ritm"),
        ("work_signal_e", "Cooperare"),
    ]
    statements = [
        {
            "id": f"style_{index}",
            "code": f"S{index}",
            "label": f"Afirmație sintetică despre {label.lower()}",
            "scoring": {"driver": driver},
        }
        for index, (driver, label) in enumerate(drivers, start=1)
    ]
    return PreviewQuestionnaireDefinition(
        key="distress_drivers",
        title="Preferințe de lucru, mostră",
        description="Set scurt și sintetic pentru previzualizarea scorurilor.",
        schema={
            "schema_version": "questionnaire.v1",
            "local_preview": {"sample": True},
            "sections": [
                {
                    "id": "style",
                    "title": "Stil",
                    "questions": [
                        {
                            "id": "style_set",
                            "code": "STYLE",
                            "type": "statement_score_set",
                            "label": "Preferințe",
                            "required": True,
                            "scale": _scale(5),
                            "statements": statements,
                        }
                    ],
                }
            ],
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "drivers": [{"id": driver, "label": label} for driver, label in drivers],
                "normalize_to": 100,
            },
        },
        feedback_policy={
            "participant_results": {
                "publication": "scores",
                "target_types": ["self"],
                "dimension_ids": [driver for driver, _label in drivers],
                "include_primary_result": True,
            }
        },
    )


def _participant_feedback_scale(behavior: str) -> list[dict[str, Any]]:
    behavior = behavior.rstrip(".").lower()
    return [
        {"value": 1, "label": f"Nu {behavior}"},
        {"value": 2, "label": f"{behavior.capitalize()} doar când i se cere"},
        {"value": 3, "label": f"{behavior.capitalize()} în majoritatea situațiilor"},
        {"value": 4, "label": f"{behavior.capitalize()} consecvent"},
    ]


def _feedback_preview() -> PreviewQuestionnaireDefinition:
    dimensions = [
        ("feedback_signal_a", "Dezvoltare"),
        ("feedback_signal_b", "Colaborare"),
        ("feedback_signal_c", "Claritate"),
        ("feedback_signal_d", "Adaptare"),
    ]
    sections = []
    for index, (dimension, label) in enumerate(dimensions, start=1):
        sections.append(
            {
                "id": f"feedback_section_{index}",
                "title": label,
                "questions": [
                    {
                        "id": dimension,
                        "code": f"F{index}",
                        "type": "statement_score_set",
                        "label": label,
                        "required": True,
                        "scale": _scale(4),
                        "statements": [
                            {
                                "id": f"feedback_{index}_a",
                                "code": "A",
                                "label": f"Comportament sintetic pentru {label.lower()}",
                                "scale": _participant_feedback_scale(
                                    f"clarifică un comportament legat de {label.lower()}"
                                ),
                            },
                            {
                                "id": f"feedback_{index}_b",
                                "code": "B",
                                "label": f"A doua observație sintetică pentru {label.lower()}",
                                "scale": _participant_feedback_scale(
                                    f"verifică efectul comportamentului de {label.lower()}"
                                ),
                            },
                        ],
                    }
                ],
            }
        )
    return PreviewQuestionnaireDefinition(
        key="boss_360",
        title="Feedback 360, mostră",
        description="Mostră sintetică pentru fluxul cu mai mulți evaluatori.",
        schema={
            "schema_version": "questionnaire.v1",
            "local_preview": {"sample": True},
            "sections": sections,
            "scoring": {
                "method": "average_statement_scores_by_section",
                "scale_min": 1,
                "scale_max": 4,
                "score_unit": "percent",
                "score_min": 1,
            },
        },
        feedback_policy={
            "publication": "aggregate",
            "minimum_completed": 2,
            "target_completed": 3,
            "dimension_ids": [dimension for dimension, _label in dimensions],
            "participant_results": {
                "publication": "scores",
                "target_types": ["person"],
                "require_self_target": True,
                "dimension_ids": [dimension for dimension, _label in dimensions],
                "include_primary_result": True,
            },
        },
    )
