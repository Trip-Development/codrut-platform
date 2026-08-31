"""Lacatul plicului 37: cele trei piese chiar ajung la model.

Toate trei existau scrise pe disc si portate in cod, dar nu erau trimise. Nu se vedea
in nicio suita, pentru ca fiecare piesa avea ramura ei si ramura nu se atingea.
"""

import inspect

from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    CODY_PROMPT_VERSION,
    EVALUARE_PROMPT,
    get_system_prompt_for_kind,
)


def test_la_roleplay_evaluarea_merge_impreuna_cu_actorul():
    """Plicul 22: „peste el vine coach.md SAU PERECHEA actor.md + evaluare.md".

    Comutatorul `is_actor_role` era la role-play intotdeauna adevarat, deci ramura cu
    evaluarea nu se atingea niciodata in folosire reala. Asa s-a pierdut feedbackul
    imediat de dupa fiecare replica.
    """
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert ACTOR_PROMPT in prompt
    assert EVALUARE_PROMPT in prompt
    # regula pedagogica cea mai valoroasa, din evaluare.md
    assert "INTERZIS ABSOLUT" in prompt
    # si lista de jargon interzis, din reguli-generale.md
    assert "SENZORUL ANTI-PAPAGAL" in prompt or "ANTI-SALUT" in prompt


def test_comutatorul_care_rupea_perechea_nu_mai_exista():
    """Un parametru care nu mai comuta nimic e fix felul in care a aparut abaterea."""
    semnatura = inspect.signature(get_system_prompt_for_kind)
    assert "is_actor_role" not in semnatura.parameters


def test_la_quiz_blocul_la_care_trimite_promptul_chiar_exista():
    """`quiz.md` cere modelului sa urmeze EXCLUSIV blocul „MOD QUIZ ACTIV".

    Blocul se construia doar daca primea o competenta, si nu primea niciodata.
    """
    prompt = get_system_prompt_for_kind(
        "knowledge",
        name="Andrei",
        history_length=1,
        quiz_competency="mix",
        project_competencies=["Ascultare activă", "Feedback constructiv"],
    )

    assert "MOD QUIZ ACTIV" in prompt
    assert "NUMĂR FIX" in prompt
    # competentele proiectului ajung in tema quizului, nu un text generic
    assert "Ascultare activă" in prompt
    assert "Feedback constructiv" in prompt
    assert "toate competentele de comunicare" not in prompt


def test_memoria_ajunge_in_prompt_la_inceputul_sesiunii():
    """Se scria la fiecare final de sesiune si nu se citea niciodata inapoi."""
    memorii = [
        {
            "created_at": "2026-08-20T10:00:00+00:00",
            "summary": "A exersat o discutie despre un raport intarziat.",
            "key_quotes": [],
            "evolution_signals": {},
            "personal_context": {"role": "team lead"},
            "relevant_competencies": ["Ascultare activă"],
            "relevance_score": 80,
        }
    ]
    prompt = get_system_prompt_for_kind(
        "roleplay", name="Andrei", history_length=1, memories=memorii
    )

    assert "CE STIE CODRUT DESPRE ACEST PARTICIPANT" in prompt
    assert "raport intarziat" in prompt
    assert "team lead" in prompt


def test_versiunea_promptului_a_urcat():
    """Compozitia s-a schimbat; fara urcare, sesiunile nu se mai pot compara."""
    assert CODY_PROMPT_VERSION == "v2.1"


def test_serviciul_chiar_trimite_cele_trei_piese():
    """Legaturile lipsa erau in apel, nu in prompt. Aici se apara apelul.

    Fara asta, cineva poate repara `prompts/__init__.py` si tot sa nu ajunga nimic,
    exact cum s-a intamplat pana la plicul 37.
    """
    from codrut.modules.practice.service import PracticeSessionService

    sursa = inspect.getsource(PracticeSessionService.add_participant_turn)
    assert "quiz_competency=" in sursa
    assert "project_competencies=" in sursa
    assert "memories=" in sursa
    assert "is_actor_role" not in sursa
