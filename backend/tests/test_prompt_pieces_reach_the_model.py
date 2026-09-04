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
    assert CODY_PROMPT_VERSION == "v3.1"


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


# ---- plicul 40 ----


def test_biblioteca_de_tranzitii_nu_ajunge_in_roleplay():
    """`actor.md` cere „nu ceri permisiunea… treci DIRECT la SETUP".

    Biblioteca de tranzitii cere exact opusul: sa-l intrebe pe om ce vrea sa discute.
    Pana la plicul 37 nu ajungea in role-play, fiindca `reguli_generale` nu se trimitea
    acolo deloc; a venit odata cu evaluarea, si de atunci in acelasi prompt stateau doua
    instructiuni opuse.
    """
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "BIBLIOTECA DE TRANZIȚII" not in prompt
    assert "Ce ai zice să trecem la subiectul principal" not in prompt
    assert "SENZORUL ANTI-PAPAGAL" not in prompt
    # regula anti-salut de la a doua replica ramane
    assert "REGULA ANTI-SALUT" in prompt


def test_la_coaching_biblioteca_ramane():
    """Singurul mod in care Codrut chiar intreaba ce vrea omul.

    Pana la plicul 41 testul asta cerea biblioteca si la quiz — gresit: acolo tranzitia
    e chiar prima intrebare.
    """
    prompt = get_system_prompt_for_kind("coaching", name="Andrei", history_length=3)
    assert "BIBLIOTECA DE TRANZIȚII" in prompt
    assert "SENZORUL ANTI-PAPAGAL" in prompt


def test_prima_replica_nu_are_tranzitii_in_niciun_mod():
    """La primul mesaj regula e alta si e aceeasi peste tot: doar salut."""
    for mod in ("roleplay", "coaching", "knowledge"):
        prompt = get_system_prompt_for_kind(mod, name="Andrei", history_length=0)
        assert "REGULA PRIMULUI MESAJ" in prompt, mod
        assert "BIBLIOTECA DE TRANZIȚII" not in prompt, mod


# ---- plicul 41 ----


def test_regulile_de_coaching_ajung_doar_la_coaching():
    """REGULA CONTEXTULUI si REGULA DE AUR lucreaza impotriva celorlalte doua moduri.

    La role-play, „bine, hai" e un mesaj vag, deci regula contextului se aprinde si
    Codrut intreaba ce situatie vrea — desi `actor.md` interzice exact asta. La quiz,
    regula de aur ii interzice sa dea solutia, adica exact ce trebuie sa faca acolo.
    """
    from codrut.modules.practice.prompts import REGULI_COACHING_PROMPT

    coaching = get_system_prompt_for_kind("coaching", name="Andrei", history_length=3)
    assert REGULI_COACHING_PROMPT in coaching

    # Se verifica FISIERUL, nu fraza: „REGULA CONTEXTULUI" si „REGULA DE AUR" apar si in
    # `reguli-comportament.md` din Biblioteca, care intra in toate modurile. Textul acela
    # e al lui Andrei si nu se atinge — vezi `gasite-plic-41.md`.
    for mod in ("roleplay", "knowledge"):
        prompt = get_system_prompt_for_kind(mod, name="Andrei", history_length=3)
        assert REGULI_COACHING_PROMPT not in prompt, mod
        # Antetul exista DOAR in reguli-coaching.md; regulile in sine sunt scrise si in
        # `reguli-comportament.md` din Biblioteca, care intra oricum peste tot.
        assert "REGULI DE COACHING" not in prompt, mod


def test_biblioteca_de_tranzitii_ramane_doar_la_coaching():
    """Plicul 40 a scos-o din role-play si a lasat-o la quiz.

    La quiz tranzitia e chiar prima intrebare, deci nu are ce cauta nici acolo.
    """
    assert "BIBLIOTECA DE TRANZIȚII" in get_system_prompt_for_kind(
        "coaching", name="Andrei", history_length=3
    )
    for mod in ("roleplay", "knowledge"):
        prompt = get_system_prompt_for_kind(mod, name="Andrei", history_length=3)
        assert "BIBLIOTECA DE TRANZIȚII" not in prompt, mod
        assert "SENZORUL ANTI-PAPAGAL" not in prompt, mod
        # regula anti-salut ramane peste tot
        assert "REGULA ANTI-SALUT" in prompt, mod


def test_quizul_are_zece_intrebari_in_ambele_cazuri():
    """Erau 7 la mix si 5 altfel, copiate din aplicatia veche.

    Zece ca sa se poata numara multiplu de zece puncte, deci scorul se citeste direct
    in procente.
    """
    from codrut.modules.practice.prompts import build_quiz_block

    for competenta in ("mix", "Ascultare activă"):
        for prima in (True, False):
            bloc = build_quiz_block(
                quiz_competency=competenta,
                is_first=prima,
                project_competencies=["Ascultare activă", "Feedback"],
            )
            assert "/10" in bloc, (competenta, prima)
            assert "/7" not in bloc, (competenta, prima)
            assert "/5" not in bloc, (competenta, prima)


def test_quizul_anunta_si_incepe_in_loc_sa_ceara_voie():
    """De la plicul 38 fiecare sesiune incepe cu un salut.

    Vechea regula 5 spunea „scrie direct «Întrebarea 1/N» fara salut", corecta in
    aplicatia veche unde la quiz nu exista salut deloc.
    """
    from codrut.modules.practice.prompts import build_quiz_block

    bloc = build_quiz_block(quiz_competency="mix", is_first=True, project_competencies=["A"])
    assert "DUPĂ PRIMUL SCHIMB DE REPLICI" in bloc
    assert "Hai să vedem ce-ai reținut" in bloc
    assert "Nu aștepți răspuns" in bloc
    assert "Întrebarea 1/10" in bloc
    assert "fără salut" not in bloc


def test_quizul_primeste_pornirea_cand_trebuie_sa_porneasca():
    """Eroare de o unitate, aparuta odata cu salutul de la plicul 38.

    Blocul de pornire se trimitea doar la `history_length <= 1`, adica exact la replica
    de salut. La a doua replica — momentul in care quizul trebuie sa inceapa — pleca deja
    blocul de continuare, care nu spune nicaieri sa inceapa.
    """
    # replica de salut: inca nu incepe
    salut = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=0,
        quiz_competency="mix", project_competencies=["A"],
    )
    assert "Întrebarea 1/10" in salut

    # a doua replica: AICI trebuie sa porneasca
    pornire = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=2,
        quiz_competency="mix", project_competencies=["A"],
    )
    assert "DUPĂ PRIMUL SCHIMB DE REPLICI" in pornire
    assert "Întrebarea 1/10" in pornire
    assert "NUMĂR FIX" in pornire

    # mai tarziu: blocul scurt, de continuare
    mai_tarziu = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=6,
        quiz_competency="mix", project_competencies=["A"],
    )
    assert "NUMĂR FIX" not in mai_tarziu
    assert "MOD QUIZ ACTIV" in mai_tarziu


# ---- plicul 45 ----


def test_comanda_de_pornire_e_ULTIMUL_lucru_din_prompt():
    """Ce e scris ultimul cantareste cel mai mult.

    Regula din `actor.md` sta la coada unui prompt de ~125.000 de octeti, dupa o suta de
    kiloocteti de material despre conversatii de coaching. Opt randuri nu bat o suta de
    kiloocteti — masurat, intrarea in rol reusea in 2 din 6 porniri.
    """
    from codrut.modules.practice.prompts import COMANDA_DE_PORNIRE, REPLICA_DE_CONFIRMARE

    # La quiz, comanda e chiar ultima. La role-play, plicul 47 lipeste dupa ea blocul de
    # distributie — acelasi moment, aceeasi pozitie — deci acolo cele doua impreuna sunt
    # coada promptului.
    quiz = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=REPLICA_DE_CONFIRMARE,
        quiz_competency="mix", project_competencies=["A"],
    )
    assert quiz.endswith(COMANDA_DE_PORNIRE["knowledge"])

    rp = get_system_prompt_for_kind(
        "roleplay", name="Andrei", history_length=REPLICA_DE_CONFIRMARE,
    )
    coada = rp[-1200:]
    assert COMANDA_DE_PORNIRE["roleplay"] in coada
    assert "DISTRIBUȚIA SCENEI" in coada
    # nimic altceva nu se strecoara intre ele
    assert coada.index(COMANDA_DE_PORNIRE["roleplay"]) < coada.index("DISTRIBUȚIA SCENEI")
    assert rp.rstrip().endswith("se schimbă doar cu cine.")


def test_comanda_apare_doar_la_replica_de_confirmare():
    """Nici mai devreme, nici mai tarziu: e un declansator, nu o regula permanenta."""
    from codrut.modules.practice.prompts import COMANDA_DE_PORNIRE

    for h in (0, 1, 3, 4, 8):
        prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=h)
        assert COMANDA_DE_PORNIRE["roleplay"] not in prompt, h


def test_comanda_nu_ajunge_la_coaching():
    """Acolo pornirea in doi pasi n-are ce cauta — decizia lui Andrei din 31 august."""
    from codrut.modules.practice.prompts import COMANDA_DE_PORNIRE

    prompt = get_system_prompt_for_kind("coaching", name="Andrei", history_length=2)
    for text in COMANDA_DE_PORNIRE.values():
        assert text not in prompt


def test_prima_replica_intreaba_daca_e_gata_doar_la_roleplay_si_quiz():
    """La coaching ramane salutul plus «Cum iti merge ziua», decizia lui Andrei."""
    # Se verifica REGULA, nu fraza: „Cum iti merge ziua pana acum" apare si in
    # `reguli-comportament.md` din Biblioteca, sectiunea 12A, unde e citata ca exemplu
    # INTERZIS. Textul acela e al lui Andrei si nu se atinge.
    rp = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=0)
    assert "dacă e gata să înceapă un joc de rol" in rp
    assert "REGULA PRIMULUI MESAJ: DOAR saluți" not in rp

    quiz = get_system_prompt_for_kind("knowledge", name="Andrei", history_length=0)
    assert "dacă e gata să-și verifice cunoștințele" in quiz
    assert "REGULA PRIMULUI MESAJ: DOAR saluți" not in quiz

    coaching = get_system_prompt_for_kind("coaching", name="Andrei", history_length=0)
    assert "REGULA PRIMULUI MESAJ: DOAR saluți" in coaching
    assert "dacă e gata să înceapă un joc de rol" not in coaching


# ---- plicul 47 ----


def test_scena_se_alege_dupa_pozitia_reala_a_omului():
    """Toate cele 15 scenarii de pana acum il puneau pe om manager care da feedback.

    Un om care nu conduce pe nimeni juca mereu un rol pe care nu-l are.
    """
    from codrut.modules.practice.prompts import bloc_de_distributie

    # cine nu conduce nu primeste NICIODATA o scena „in jos"
    for n in range(12):
        t = bloc_de_distributie({"conduce_oameni": False, "nr_roleplay_anterioare": n})
        assert "DIN ECHIPA participantului" not in t, n
        assert "INTERZIS să-l pui pe participant în poziție de manager" in t, n

    # cine conduce le primeste pe toate patru, si se rotesc
    directii = {
        bloc_de_distributie({"conduce_oameni": True, "nr_roleplay_anterioare": n})
        for n in range(4)
    }
    assert len(directii) == 4


def test_functia_omului_intra_in_scena_daca_o_stim():
    from codrut.modules.practice.prompts import bloc_de_distributie

    cu = bloc_de_distributie({"conduce_oameni": True, "functie": "inginer de producție"})
    assert "inginer de producție" in cu
    assert "plauzibil pentru funcția asta" in cu

    fara = bloc_de_distributie({"conduce_oameni": True, "functie": None})
    assert "Funcția lui în firmă" not in fara


def test_fara_profil_se_merge_pe_varianta_sigura():
    """Un om care conduce si primeste o scena cu un coleg pierde putin; unul care nu
    conduce si e pus «manager de echipa» joaca o minciuna."""
    from codrut.modules.practice.prompts import bloc_de_distributie

    for gol in (None, {}, {"conduce_oameni": None}):
        t = bloc_de_distributie(gol)
        assert "DIN ECHIPA participantului" not in t
        assert "INTERZIS să-l pui pe participant în poziție de manager" in t


def test_distributia_nu_ajunge_la_coaching_sau_quiz():
    profil = {"conduce_oameni": True, "nr_roleplay_anterioare": 0}
    for mod in ("coaching", "knowledge"):
        prompt = get_system_prompt_for_kind(
            mod, name="Andrei", history_length=2,
            quiz_competency="mix" if mod == "knowledge" else None,
            project_competencies=["A"], profil_rol=profil,
        )
        assert "DISTRIBUȚIA SCENEI" not in prompt, mod
