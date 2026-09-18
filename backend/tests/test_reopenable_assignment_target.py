"""Fereastra de redeschidere trebuie sa spuna DESPRE CINE e fiecare chestionar.

Fara tinta, un lider care a evaluat 18 colegi vede 18 randuri identice si nu
poate alege corect decat din noroc. Interogarea intoarce tipul tintei si numele
ei; compunerea etichetei sta in frontend, unde e harta de denumiri.

Probam toate trei formele pe care le permite constrangerea din baza:
  self   -> fara tinta
  person -> numele omului evaluat
  team   -> numele echipei
"""

from uuid import uuid4

import pytest

from codrut.core.database import SessionLocal, engine
from codrut.modules.assignments.models import (
    AssignmentStatus,
    QuestionnaireAssignment,
    Team,
    TeamType,
)
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
)
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


async def _seed(db_session):
    """Un respondent cu trei chestionare trimise, cate unul din fiecare forma."""
    company = Company(id=uuid4(), name=f"Company {uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.flush()

    project = CompanyProject(
        id=uuid4(),
        company_id=company.id,
        name=f"Project {uuid4().hex[:8]}",
        status=CompanyProjectStatus.active,
    )
    db_session.add(project)

    respondent = ParticipantProfile(
        id=uuid4(),
        company_id=company.id,
        full_name="Dana Muresan",
        email=f"dana_{uuid4().hex[:8]}@example.com",
    )
    evaluated = ParticipantProfile(
        id=uuid4(),
        company_id=company.id,
        full_name="Zaharia Olteanu",
        email=f"zaharia_{uuid4().hex[:8]}@example.com",
    )
    evaluated_2 = ParticipantProfile(
        id=uuid4(),
        company_id=company.id,
        full_name="Barbu Craciun",
        email=f"barbu_{uuid4().hex[:8]}@example.com",
    )
    db_session.add_all([respondent, evaluated, evaluated_2])

    team = Team(
        id=uuid4(),
        company_id=company.id,
        name="Echipa Florilor",
        type=TeamType.functional,
    )
    db_session.add(team)

    key = "boss_360"
    version = 10_000 + int.from_bytes(uuid4().bytes[:4], "big") % 1_000_000_000
    definition = QuestionnaireDefinition(
        id=uuid4(),
        key=key,
        version=version,
        title=f"Synthetic {key}",
        description="Synthetic test definition.",
        schema={
            "key": key,
            "version": version,
            "title": f"Synthetic {key}",
            "audience": "participant",
            "sections": [],
        },
        feedback_policy={},
        trainer_visibility_policy={"raw_responses": "hidden"},
        content_checksum=uuid4().hex * 2,
        active=True,
    )
    db_session.add(definition)
    await db_session.flush()

    # DOUA tinte-persoana: distinctia dintre ele NU poate veni din target_type,
    # ci doar din nume. Exact cazul real al celor 18 evaluari boss_360.
    #
    # Numele la inserare sunt ANUME amestecate (Zaharia inaintea lui Barbu), ca
    # testul de sortare sa nu treaca din intamplare. In plus, dam id-uri crescatoare
    # in ordinea INVERSA fata de cea alfabetica: fara sortarea dupa nume, ordinea
    # iese deterministic gresita, nu doar probabil gresita.
    forms = [
        ("self", None, None),
        ("person", evaluated.id, None),
        ("person", evaluated_2.id, None),
        ("team", None, team.id),
    ]
    ids_crescator = sorted(uuid4() for _ in forms)
    ordine_alfabetica = [None, "Barbu Craciun", "Echipa Florilor", "Zaharia Olteanu"]
    nume_la_forma = {
        ("self", None, None): None,
        ("person", evaluated.id, None): "Zaharia Olteanu",
        ("person", evaluated_2.id, None): "Barbu Craciun",
        ("team", None, team.id): "Echipa Florilor",
    }
    id_pentru_forma = {
        forma: ids_crescator[len(forms) - 1 - ordine_alfabetica.index(nume_la_forma[forma])]
        for forma in forms
    }

    for forma in forms:
        target_type, person_id, team_id = forma
        assignment = QuestionnaireAssignment(
            id=id_pentru_forma[forma],
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=respondent.id,
            questionnaire_key=key,
            questionnaire_definition_id=definition.id,
            target_type=target_type,
            target_person_id=person_id,
            target_team_id=team_id,
            status=AssignmentStatus.submitted,
        )
        db_session.add(assignment)
        await db_session.flush()
        db_session.add(
            QuestionnaireResponse(
                id=uuid4(),
                assignment_id=assignment.id,
                questionnaire_key=key,
                questionnaire_version=version,
                status=QuestionnaireResponseStatus.submitted,
                answers={},
            )
        )
    await db_session.flush()
    return company, project, respondent


async def test_interogarea_intoarce_tinta_pentru_toate_trei_formele():
    async with SessionLocal() as db_session:
        company, project, respondent = await _seed(db_session)

        repository = CompanyRepository(db_session)
        reopenable = await repository.list_project_reopenable_assignments(
            company.id,
            project.id,
        )

        randuri = reopenable[respondent.id]
        assert len(randuri) == 4

        nume_dupa_tip: dict[str, set[str | None]] = {}
        for _id, _key, _n, target_type, target_name in randuri:
            nume_dupa_tip.setdefault(target_type, set()).add(target_name)

        assert nume_dupa_tip["self"] == {None}, "autoevaluarea nu are tinta"
        assert nume_dupa_tip["person"] == {
            "Zaharia Olteanu",
            "Barbu Craciun",
        }, "fiecare tinta-persoana vine cu numele ei"
        assert nume_dupa_tip["team"] == {
            "Echipa Florilor"
        }, "tinta-echipa vine cu numele echipei"

        await db_session.rollback()


async def test_randurile_cu_aceeasi_denumire_se_deosebesc_prin_tinta():
    """Proba care conteaza: acelasi questionnaire_key, randuri distincte."""
    async with SessionLocal() as db_session:
        company, project, respondent = await _seed(db_session)

        repository = CompanyRepository(db_session)
        reopenable = await repository.list_project_reopenable_assignments(
            company.id,
            project.id,
        )
        randuri = reopenable[respondent.id]

        assert {key for _id, key, _n, _t, _name in randuri} == {"boss_360"}

        # cele doua randuri "person" au acelasi tip: se pot deosebi DOAR prin nume
        persoane = [name for _id, _key, _n, t, name in randuri if t == "person"]
        assert len(persoane) == 2
        assert (
            len(set(persoane)) == 2
        ), "doua evaluari despre oameni diferiti nu au voie sa iasa la fel"

        semnaturi = {
            (target_type, target_name)
            for _id, _key, _n, target_type, target_name in randuri
        }
        assert len(semnaturi) == 4, "toate randurile cu aceeasi denumire trebuie sa iasa distincte"

        await db_session.rollback()


async def test_randurile_ies_sortate_dupa_numele_tintei():
    """Sortarea e scopul: gasesti un coleg anume fara sa citesti toata lista.

    Datele sunt asezate impotriva testului: la inserare, Zaharia vine inaintea
    lui Barbu, iar id-urile cresc exact invers fata de ordinea alfabetica. Daca
    sortarea dupa nume dispare, ordinea iese deterministic gresita.
    """
    async with SessionLocal() as db_session:
        company, project, respondent = await _seed(db_session)

        repository = CompanyRepository(db_session)
        reopenable = await repository.list_project_reopenable_assignments(
            company.id,
            project.id,
        )
        nume_in_ordine = [name for _id, _key, _n, _t, name in reopenable[respondent.id]]

        assert nume_in_ordine == [
            None,
            "Barbu Craciun",
            "Echipa Florilor",
            "Zaharia Olteanu",
        ], "autoevaluarea prima, apoi tintele alfabetic"

        await db_session.rollback()
