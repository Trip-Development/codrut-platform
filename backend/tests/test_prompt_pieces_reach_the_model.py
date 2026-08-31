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
    assert CODY_PROMPT_VERSION == "v2.2"


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


# ---- plicul 38 ----


def test_cursul_lui_andrei_intra_in_prompt():
    """Sloturile incarcau doar „cine e Codrut", nu si ce preda.

    Teoria statea in acelasi dosar si nu ajungea niciodata la model.
    """
    from codrut.modules.practice.prompts import CORE_SLOTS

    etichete = [eticheta for eticheta, _ in CORE_SLOTS]
    assert "TEORIA-TEMEI" in etichete
    # ultimul dinadins: prefixul constant ramane neschimbat, ca memoria de context sa
    # se prinda pe el
    assert etichete[-1] == "TEORIA-TEMEI"

    fisiere = dict(CORE_SLOTS)["TEORIA-TEMEI"]
    assert fisiere == [
        "codrut-comunicare-asertiva-v1-0.md",
        "feedback-theory-partea-1.md",
        "feedback-theory-part-2.md",
        "cum-spui-nu.md",
    ]

    # ce NU are voie sa intre: restul teoriei si cele 41 de reel-uri
    toate = [f for _, fs in CORE_SLOTS for f in fs]
    for nedorit in (
        "cum-primesti-feedback.md",
        "cum-imi-controlez-reactiile.md",
        "cum-gestionam-teama-in-comunicare.md",
        "cum-transmit-informatia.md",
    ):
        assert nedorit not in toate
    assert not any(f.startswith("reel-") for f in toate)


def test_cody_vorbeste_primul():
    """Slotul `first_turn` exista de la inceput si era mereu null.

    Aici se apara legatura, nu doar slotul: pornirea trebuie sa ceara replica, iar
    esecul modelului nu are voie sa coste sesiunea.
    """
    import inspect

    from codrut.modules.practice.service import PracticeSessionService

    for pornire in (
        PracticeSessionService.start_session,
        PracticeSessionService.start_trainer_session,
    ):
        sursa = inspect.getsource(pornire)
        assert "_prima_replica" in sursa, pornire.__name__
        assert "return practice_session, prima" in sursa, pornire.__name__

    prima = inspect.getsource(PracticeSessionService._prima_replica)
    # la esec: bugetul se elibereaza si se intoarce None, sesiunea NU se inchide
    assert "return None" in prima
    assert "await release(" in prima
    assert "SessionState.closed" not in prima
    # replica se salveaza ca prima din transcript
    assert "ordinal=1" in prima
    assert "role=TurnRole.actor" in prima


def test_deschiderea_nu_pune_vorbe_in_gura_participantului():
    """Aplicatia veche trimitea in ascuns o replica falsa DIN PARTEA participantului.

    Aici textul e o instructiune si nu se salveaza niciodata ca `PracticeTurn`, deci
    transcriptul incepe curat, cu replica lui Codrut.
    """
    import inspect

    from codrut.modules.practice.service import DESCHIDE_SESIUNEA, PracticeSessionService

    prima = inspect.getsource(PracticeSessionService._prima_replica)
    assert "DESCHIDE_SESIUNEA" in prima
    # instructiunea nu ajunge niciodata intr-un rand de transcript
    assert "text=DESCHIDE_SESIUNEA" not in prima.split("PracticeTurn(")[-1]
    # si nu e o replica pusa in gura omului
    assert "Salut" not in DESCHIDE_SESIUNEA
    assert "sesiunea" in DESCHIDE_SESIUNEA.lower()


# ---- plicul 39 ----


def test_blocul_json_nu_pleaca_spre_ecran():
    """`rezumat.md` cere modelului proza PLUS un bloc JSON, din care se scriu scorurile.

    Pana la plicul 39 spre ecran pleca textul intreg, deci participantul vedea acolade,
    ghilimele si nume de campuri in engleza.
    """
    from codrut.modules.practice.service import doar_proza

    intreg = (
        "##Concluzie\n"
        "Ai condus discutia calm si ai propus un pas concret.\n\n"
        "##Recomandari\n"
        "Pune mai multe intrebari deschise.\n\n"
        "```json\n"
        '{ "topic": "Sef agresiv", "characters": ["Vali"],\n'
        '  "scores": { "questionsRatio": 1, "assertiveness": 6 } }\n'
        "```"
    )
    proza = doar_proza(intreg)

    # proza ramane intreaga, si Concluzie SI Recomandari
    assert "Ai condus discutia calm" in proza
    assert "Pune mai multe intrebari deschise" in proza
    # blocul tehnic nu mai pleaca
    assert "```json" not in proza
    assert "questionsRatio" not in proza
    assert "{" not in proza


def test_doar_proza_nu_strica_o_sinteza_fara_bloc():
    from codrut.modules.practice.service import doar_proza

    assert doar_proza("Doar proza, fara bloc.") == "Doar proza, fara bloc."
    assert doar_proza(None) is None
    assert doar_proza("") == ""


def test_sinteza_care_iese_din_end_session_e_curata():
    """Aici se apara legatura, nu doar functia: `end_session` trebuie sa o cheme."""
    import inspect

    from codrut.modules.practice.service import PracticeSessionService

    sursa = inspect.getsource(PracticeSessionService.end_session)
    assert "return session_obj, doar_proza(summary_text)" in sursa
    assert "return session_obj, summary_text" not in sursa
