"""Configuring practice on a training project.

Until plic 29 nothing in the application ever created ``practice_program_settings``:
the only two places that did were offline tools. A trainer could pick project type
``training`` and still not get a project anyone could practise on - the row had to be
placed by hand with a script. This module closes that gap.

It also owns the competency selection (``project_competencies``): the theme's
templates come pre-ticked, and the trainer removes or restores whichever they want,
at creation or any time afterwards.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import delete, select

from codrut.core.errors import DomainError
from codrut.modules.companies.models import CompanyProject
from codrut.modules.practice.models import (
    CompetencyTemplate,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeScenario,
    PracticeTheme,
    ProgramMode,
    ProjectCompetency,
)

TRAINING_PROJECT_TYPE = "training"


class PracticeSetupService:
    def __init__(self, session) -> None:
        self.session = session

    async def list_themes(self) -> list[dict]:
        """Themes a trainer can choose from, each with its competency templates.

        ``usable`` says whether a theme can actually host a session: a theme with no
        knowledge pack cannot, however many competencies it carries. The screen shows
        that instead of letting the trainer pick a theme that fails later.
        """
        themes = (await self.session.execute(
            select(PracticeTheme).order_by(PracticeTheme.name)
        )).scalars().all()

        out: list[dict] = []
        for theme in themes:
            competencies = (await self.session.execute(
                select(CompetencyTemplate)
                .where(CompetencyTemplate.theme_id == theme.id)
                .order_by(CompetencyTemplate.order_index, CompetencyTemplate.name)
            )).scalars().all()
            pack = (await self.session.execute(
                select(PracticeKnowledgePack)
                .where(PracticeKnowledgePack.theme_id == theme.id)
                .order_by(PracticeKnowledgePack.created_at.desc())
            )).scalars().first()
            scenario_count = len((await self.session.execute(
                select(PracticeScenario).where(PracticeScenario.theme_id == theme.id)
            )).scalars().all())

            out.append({
                "id": theme.id,
                "name": theme.name,
                "slug": theme.slug,
                "competencies": [
                    {"name": c.name, "description": c.description, "order_index": c.order_index}
                    for c in competencies
                ],
                "has_knowledge_pack": pack is not None,
                "scenario_count": scenario_count,
                "usable": pack is not None,
            })
        return out

    async def get_setup(self, project_id: uuid.UUID) -> dict:
        project = await self._require_project(project_id)
        settings = (await self.session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == project_id)
        )).scalar_one_or_none()
        selected = (await self.session.execute(
            select(ProjectCompetency)
            .where(ProjectCompetency.project_id == project_id)
            .order_by(ProjectCompetency.order_index, ProjectCompetency.name)
        )).scalars().all()

        theme_name = None
        if settings is not None:
            theme = (await self.session.execute(
                select(PracticeTheme).where(PracticeTheme.id == settings.theme_id)
            )).scalar_one_or_none()
            theme_name = theme.name if theme else None

        return {
            "project_id": project_id,
            "project_name": project.name,
            "project_type": project.project_type,
            "configured": settings is not None,
            "is_enabled": bool(settings.is_enabled) if settings else False,
            "theme_id": settings.theme_id if settings else None,
            "theme_name": theme_name,
            "competencies": [
                {"name": c.name, "description": c.description, "order_index": c.order_index}
                for c in selected
            ],
        }

    async def configure(
        self,
        project_id: uuid.UUID,
        theme_id: uuid.UUID,
        competency_names: list[str] | None,
        is_enabled: bool = True,
    ) -> dict:
        """Make a training project practisable, and record the chosen competencies.

        ``competency_names`` of ``None`` means "take the theme's templates" - that is
        the pre-ticked default. An explicit list replaces the selection, including an
        empty one, so a trainer can untick everything on purpose.
        """
        project = await self._require_project(project_id)
        if project.project_type != TRAINING_PROJECT_TYPE:
            raise DomainError(
                "Exersarea se configurează doar pe proiecte de tip training.",
                code="practice_setup_wrong_project_type",
            )

        theme = (await self.session.execute(
            select(PracticeTheme).where(PracticeTheme.id == theme_id)
        )).scalar_one_or_none()
        if theme is None:
            raise DomainError(f"Tema {theme_id} nu a fost găsită.", code="theme_not_found")

        pack = (await self.session.execute(
            select(PracticeKnowledgePack)
            .where(PracticeKnowledgePack.theme_id == theme_id)
            .order_by(PracticeKnowledgePack.created_at.desc())
        )).scalars().first()
        if pack is None:
            raise DomainError(
                f"Tema „{theme.name}” nu are niciun pachet de cunoștințe, "
                "deci nu poate găzdui o sesiune.",
                code="theme_has_no_knowledge_pack",
            )

        templates = (await self.session.execute(
            select(CompetencyTemplate)
            .where(CompetencyTemplate.theme_id == theme_id)
            .order_by(CompetencyTemplate.order_index, CompetencyTemplate.name)
        )).scalars().all()

        if competency_names is None:
            chosen = [(t.name, t.description, t.order_index) for t in templates]
        else:
            wanted = {n.strip() for n in competency_names if n and n.strip()}
            by_name = {t.name: t for t in templates}
            unknown = sorted(wanted - set(by_name))
            if unknown:
                raise DomainError(
                    "Aceste competențe nu aparțin temei alese: " + ", ".join(unknown),
                    code="competency_not_in_theme",
                )
            chosen = [
                (by_name[n].name, by_name[n].description, by_name[n].order_index)
                for n in sorted(wanted, key=lambda n: (by_name[n].order_index, n))
            ]

        settings = (await self.session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == project_id)
        )).scalar_one_or_none()
        if settings is None:
            settings = PracticeProgramSettings(
                id=uuid.uuid4(),
                project_id=project_id,
                mode=ProgramMode.training,
                theme_id=theme_id,
                active_pack_id=pack.id,
                is_enabled=is_enabled,
                max_turns_per_session=20,
                max_sessions_per_day=5,
                max_chars_per_turn=1200,
                turn_retention_days=30,
                usd_cap_per_participant=Decimal("3.00"),
            )
            self.session.add(settings)
        else:
            settings.mode = ProgramMode.training
            settings.theme_id = theme_id
            settings.active_pack_id = pack.id
            settings.is_enabled = is_enabled

        await self.session.execute(
            delete(ProjectCompetency).where(ProjectCompetency.project_id == project_id)
        )
        for name, description, order_index in chosen:
            self.session.add(ProjectCompetency(
                id=uuid.uuid4(),
                project_id=project_id,
                name=name,
                description=description,
                order_index=order_index,
            ))
        await self.session.flush()
        return await self.get_setup(project_id)

    async def _require_project(self, project_id: uuid.UUID) -> CompanyProject:
        project = (await self.session.execute(
            select(CompanyProject).where(CompanyProject.id == project_id)
        )).scalar_one_or_none()
        if project is None:
            raise DomainError(f"Proiectul {project_id} nu a fost găsit.", code="project_not_found")
        return project


async def competency_names_for_project(session, project_id: uuid.UUID) -> list[str]:
    """The competencies the evaluator scores against, for this project.

    Falls back to the theme's templates when nothing was ticked yet, so a project
    configured before the selection screen existed still gets evaluated.
    """
    selected = (await session.execute(
        select(ProjectCompetency)
        .where(ProjectCompetency.project_id == project_id)
        .order_by(ProjectCompetency.order_index, ProjectCompetency.name)
    )).scalars().all()
    if selected:
        return [c.name for c in selected]

    settings = (await session.execute(
        select(PracticeProgramSettings)
        .where(PracticeProgramSettings.project_id == project_id)
    )).scalar_one_or_none()
    if settings is None:
        return []
    templates = (await session.execute(
        select(CompetencyTemplate)
        .where(CompetencyTemplate.theme_id == settings.theme_id)
        .order_by(CompetencyTemplate.order_index, CompetencyTemplate.name)
    )).scalars().all()
    return [t.name for t in templates]
