"""Lacatul plicului 37: cele trei piese chiar ajung la model.

Toate trei existau scrise pe disc si portate in cod, dar nu erau trimise. Nu se vedea
in nicio suita, pentru ca fiecare piesa avea ramura ei si ramura nu se atingea.
"""

import inspect

import pytest

from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    CODY_PROMPT_VERSION,
    EVALUARE_PROMPT,
    get_system_prompt_for_kind,
    resolve_biblioteca_dir,
)


def _fara_material_sari() -> None:
    """Testul cere materialul pe disc. Fara el, sare — cu motivul scris, nu picat si nu ascuns."""
    if resolve_biblioteca_dir() is None:
        pytest.skip(
            "BIBLIOTECA (materialul lui Cody) nu e pe disc: in CI nu exista, nu e in depozit. "
        "Pe productie o verifica verifica-cody-dupa-urcare.sh (miezul, 1812 fisiere). Plicul 155."
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
    # regula pedagogica cea mai valoroasa, din evaluare.md — plicul 66: replica se SCRIE
    assert "REPLICA SE SCRIE, NU SE DESCRIE" in prompt
    assert "PUNCTAJUL E OBLIGATORIU LA FIECARE REPLICĂ" in prompt
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
    assert CODY_PROMPT_VERSION == "v3.11"


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
    # Plicul 68: blocul de distributie se termina acum cu numele personajului, ales in
    # cod. Coada promptului e tot comanda + distributia, in ordinea asta — s-a mutat
    # doar ultima propozitie a distributiei.
    assert rp.rstrip().endswith("Nu-i da alt nume și nu inventa altul.")
    assert "se schimbă doar cu cine." in coada


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


def test_functia_omului_nu_mai_intra_in_scena():
    """Plicul 142, hotărârea lui Andrei, 23 septembrie: spre Google pleacă numai dacă omul conduce
    oameni sau nu. Funcția scrisă întreg („Director regional vânzări Sud") poate spune cine e omul,
    la 19 oameni. Până la 142 intra aici, la pornirea scenei (plicul 47)."""
    from codrut.modules.practice.prompts import bloc_de_distributie

    cu = bloc_de_distributie({"conduce_oameni": True, "functie": "inginer de producție"})
    assert "inginer de producție" not in cu
    assert "Funcția lui în firmă" not in cu
    # „conduce oameni: da/nu" rămâne: omul care nu conduce nu e pus șef în scenă
    nu_conduce = bloc_de_distributie({"conduce_oameni": False, "functie": "inginer"})
    assert "INTERZIS să-l pui pe participant în poziție de manager" in nu_conduce


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


# ---- plicul 49 ----


def test_omul_are_nume_nu_santinela():
    """La intrarea directa a trainerului, profilul se crea cu numele literal „Trainer".

    Modelului i se spunea ca omul din fata lui se cheama asa — si, fiindca nu e un nume,
    si-l inventa singur: cand „Mihai", cand un „Andrei" ghicit, cand „[Trainer]" cu
    paranteze, ca un loc necompletat. Masurat de Andrei in opt sesiuni la rand.
    """
    import inspect

    from codrut.modules.practice.service import PracticeSessionService, _nume_din_email

    assert _nume_din_email("andrei.vacaru@tripdevelopment.ro") == "Andrei Vacaru"
    assert _nume_din_email("ion_popescu@firma.ro") == "Ion Popescu"
    assert _nume_din_email("maria-ionescu2@x.ro") == "Maria Ionescu"
    # cazurile in care nu se poate scoate nimic cad pe un cuvant care macar e o categorie
    for gol in ("123@x.ro", "", None):
        assert _nume_din_email(gol) == "Participant"

    # si legatura: pornirea trainerului nu mai scrie santinela
    sursa = inspect.getsource(PracticeSessionService.start_trainer_session)
    assert 'full_name="Trainer"' not in sursa
    assert "_nume_din_email(principal.email)" in sursa
    # profilul vechi, scris cu santinela, se corecteaza la prima atingere
    assert 'profile.full_name == "Trainer"' in sursa


# ---- plicul 50 ----


def test_salutul_nu_mai_cheama_pe_nimeni_pe_nume():
    """RASTURNAT la plicul 128, partea A. Ce apara testul asta acum e opusul a ce apara la 50.

    La plicul 50 salutul trebuia sa-l cheme pe om pe prenume, fiindca numele era in prompt dar
    salutul nu-l folosea. Regula a tinut doi ani de plicuri si a picat la prima intalnire cu un
    profil adevarat: pe contul de proba al lui Andrei profilul se cheama „user 1", deci Cody i-a
    zis „Salut, user." (22 septembrie). Numele nu era gresit CITIT, era gresit ARATAT.

    Ce ramane din plicul 50, si de asta testul nu se sterge: salutul e cerut intr-un SINGUR loc
    (`formula_de_salut`), nu de doua sabloane deodata — aia era cauza formularului de atunci.
    """
    for mod in ("roleplay", "knowledge", "coaching"):
        p = get_system_prompt_for_kind(
            mod, name="Ion Popescu", history_length=0,
            profil_rol={"nr_sesiuni_anterioare": 0},
        )
        # niciun nume in salut, nici prenume, nici intreg
        assert "Salut, Ion" not in p, mod
        assert "Salut." in p, mod
        # tot un singur sablon, nu doua — asta e ce ramane din plicul 50
        assert p.count("- SALUTUL:") == 1, mod
        assert "îl saluți OBLIGATORIU pe prenume" not in p, mod

    # nici cand numele e dintr-un singur cuvant
    p = get_system_prompt_for_kind(
        "roleplay", name="Andrei", history_length=0, profil_rol={"nr_sesiuni_anterioare": 0}
    )
    assert "Salut, Andrei" not in p

    # regula se aplica DOAR la prima replica
    tarziu = get_system_prompt_for_kind("roleplay", name="Ion Popescu", history_length=4)
    assert "SALUTUL:" not in tarziu
    assert "REGULA ANTI-SALUT" in tarziu


# ---- plicul 53 ----


def test_salutul_nu_mai_are_ce_sa_aleaga():
    """RASTURNAT la plicul 128, partea A. Rotatia salutului nu mai exista.

    Plicul 53 a mutat alegerea vorbei de salut din mana modelului in cod, cu o lista de sapte
    si un numarator, fiindca modelul lasat sa aleaga incepea sase din opt sesiuni identic.
    Plicul 128 scoate si vorba, si numele: salutul e „Salut." si atat, la toate trei modurile,
    la orice numar de sedinte in urma.

    Ce ramane din plicul 53: alegerea NU se lasa modelului. Doar ca acum nu mai e nimic de ales
    — si ce nu se poate trimite nu se poate gresi, de asta functia nici nu mai are parametri.
    """
    from codrut.modules.practice.prompts import formula_de_salut

    assert formula_de_salut() == formula_de_salut()
    assert "Salut." in formula_de_salut()
    assert "INTERZIS să pui vreun nume în salut" in formula_de_salut()
    assert "INTERZIS să lași un loc gol" in formula_de_salut()

    # acelasi salut, oricate sedinte ar avea omul in urma si oricare ar fi modul
    for mod in ("roleplay", "knowledge", "coaching"):
        for n in (0, 1, 2, 5, 6, 7, 13):
            p = get_system_prompt_for_kind(
                mod, name="Ion Popescu", history_length=0,
                profil_rol={"nr_sesiuni_anterioare": n},
            )
            assert "- SALUTUL:" in p, (mod, n)
            assert "Salut, Ion" not in p, (mod, n)

    # vorbele vechi nu mai ajung nicaieri
    p = get_system_prompt_for_kind(
        "roleplay", name="Ion Popescu", history_length=0,
        profil_rol={"nr_sesiuni_anterioare": 2},
    )
    for vorba in ("mă bucur că te-ai apucat", "bine că ai prins un moment", "ne apucăm de treabă"):
        assert vorba not in p

    tarziu = get_system_prompt_for_kind("roleplay", name="Ion Popescu", history_length=4)
    assert "- SALUTUL:" not in tarziu
    assert "REGULA ANTI-SALUT" in tarziu


def test_evaluarea_cere_replica_scrisa_nu_o_mai_interzice():
    """Plicul 66: ce cautam doua saptamani era interzis chiar in prompt.

    Masurat de Andrei pe sase sesiuni reale, pe 12 septembrie: punctajul a aparut singur
    in 2 din 6, iar replica refacuta, scrisa cu cuvinte, in zero dintr-o sesiune de zece
    replici. Cand a aparut, a functionat — omul a folosit-o si punctajul a urcat de la 7
    la 8. Cauza nu era o regula lipsa, ci una care o interzicea.
    """
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "REPLICA SE SCRIE, NU SE DESCRIE" in prompt
    assert "PUNCTAJUL E OBLIGATORIU LA FIECARE REPLICĂ" in prompt
    # interdictia veche nu mai are voie sa fie nicaieri in promptul trimis
    assert "fraza gata formulată" not in prompt


# --- plicul 67: cursul ajunge la quiz, si numai la quiz ---
#
# Andrei a probat quizul pe 12 septembrie: „Intrebarile sunt despre Cody, nu despre situatii
# sau comunicare." Prima intrebare primita: „Care este scopul principal al deconstructiei
# fricii in comunicarea asertiva, conform filozofiei lui Andrei?"
#
# Doua cauze: blocul de quiz nu spunea DESPRE CE sunt intrebarile, si Cody nu avea cursul —
# 34.585 de octeti de teorie fata de 112.460 despre el insusi. Daca nu-i spui de unde sa
# intrebe, intreaba din ce are mai mult.

CURS_UNU = "CURS COMUNICARE ASERTIVA TRIP DEVELOPMENT"
CURS_DOI = "FEEDBACK LIKE A PRO"


def test_cursurile_ajung_la_quiz():
    """Cele doua suporturi de curs si regula care spune de unde se iau intrebarile."""
    _fara_material_sari()
    prompt = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=3, quiz_competency="mix"
    )

    assert CURS_UNU in prompt
    assert CURS_DOI in prompt
    assert "ÎNTREBĂRILE IES EXCLUSIV DIN CELE DOUĂ CURSURI" in prompt


def test_la_pornirea_quizului_regulile_de_continut_sunt_acolo():
    """Blocul de pornire (history_length <= 2) poarta regulile 8-11, scrise intregi."""
    prompt = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=2, quiz_competency="mix"
    )

    assert "DE UNDE IEI ÎNTREBĂRILE" in prompt
    assert "INTERZIS SĂ ÎNTREBI DESPRE TINE, DESPRE ANDREI SAU DESPRE METODA TA" in prompt
    assert "LIMBAJUL E AL OMULUI, NU AL MANUALULUI DE CONSTRUCȚIE" in prompt
    assert "SITUAȚIE DE LA LOCUL DE MUNCĂ" in prompt


def test_cursul_NU_intra_la_role_play_si_nici_la_coaching():
    """Lacatul care conteaza cel mai mult: role-play-ul nu se atinge.

    Promptul de role-play e masurat si reglat pe sase sesiuni reale. 93 KB in plus la
    fiecare replica nu ajuta cu nimic si strica prefixul constant pe care se prinde
    memoria de context.
    """
    for mod in ("roleplay", "coaching"):
        prompt = get_system_prompt_for_kind(mod, name="Andrei", history_length=3)
        assert CURS_UNU not in prompt, f"cursul a ajuns la {mod}"
        assert CURS_DOI not in prompt, f"cursul a ajuns la {mod}"


def test_prefixul_dinaintea_quizului_e_acelasi_ca_la_role_play():
    """`material` + `reguli_generale` sunt identice la quiz si la role-play.

    Verificat pe text, nu pe ochi: cursul se lipeste DUPA reguli_generale, tocmai ca
    partea dinainte sa ramana bit cu bit aceeasi si memoria de context sa se prinda pe ea.
    """
    _fara_material_sari()
    quiz = get_system_prompt_for_kind(
        "knowledge", name="Andrei", history_length=3, quiz_competency="mix"
    )
    roleplay = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    separator = "\n\n---\n\n"
    prefix_quiz = separator.join(quiz.split(separator)[:2])
    prefix_roleplay = separator.join(roleplay.split(separator)[:2])

    assert prefix_quiz == prefix_roleplay
    assert len(prefix_quiz) > 10000, "prefixul trebuie sa fie materialul intreg, nu o farama"


# --- plicul 68: personajul are un nume ales in cod, si pragul urca la 9 ---
#
# Masurat pe prima sesiune cu plicul 66 pus: punctajele au fost 8, 9, 10, 10, 8, 9, 9, 9,
# 10. Minimul a fost 8, deci regula „sub 8" nu s-a declansat niciodata si replica model a
# aparut de zero ori din noua. Lucrul cel mai valoros era legat de un prag care nu se
# atinge.
#
# In aceeasi sesiune, personajul a fost semnat „Andrei (eu, colega ta)" — numele
# participantului — desi setup-ul spunea ca o cheama Elena. Interdictia exista deja in
# reguli-generale.md si nu s-a tinut. Iar „domnul Popescu" a aparut de patru ori.


def test_personajul_primeste_un_nume_din_lista():
    """Numele nu se mai cere modelului, se alege in cod si i se da unul singur."""
    from codrut.modules.practice.prompts import NUME_PERSONAJ, bloc_de_distributie

    bloc = bloc_de_distributie({"nr_roleplay_anterioare": 0}, "Andrei")

    assert "PERSONAJUL SE NUMEȘTE" in bloc
    gasite = [nume for nume in NUME_PERSONAJ if nume in bloc]
    assert len(gasite) == 1, f"trebuie exact un nume, am gasit {gasite}"


def test_personajul_nu_poarta_niciodata_numele_participantului():
    """Lacatul care conteaza: regula tine pe TOATA lista, nu doar intr-un caz.

    Pentru fiecare sesiune, daca participantul se cheama fix cum s-ar fi chemat personajul,
    se alege altul. Asta e diferenta fata de o interdictie scrisa in prompt: aici nu are
    cum sa nu se tina.
    """
    from codrut.modules.practice.prompts import NUME_PERSONAJ, _numele_personajului

    for n in range(len(NUME_PERSONAJ)):
        ar_fi_iesit = NUME_PERSONAJ[n % len(NUME_PERSONAJ)].split(" ")[0]
        ales = _numele_personajului(n, ar_fi_iesit)
        assert ales.split(" ")[0].lower() != ar_fi_iesit.lower(), (
            f"la sesiunea {n}, personajul poarta numele participantului: {ales}"
        )
        assert ales in NUME_PERSONAJ


def test_zece_sesiuni_zece_nume_diferite():
    """„Domnul Popescu" de patru ori. Acum numaratorul tine varietatea, nu modelul."""
    from codrut.modules.practice.prompts import _numele_personajului

    nume = [_numele_personajului(n, "Andrei") for n in range(10)]

    assert len(set(nume)) == 10, f"se repeta: {nume}"
    assert not any("Popescu" in x for x in nume)


def test_pragul_replicii_model_e_sub_9():
    """Andrei, 12 septembrie: „muta punctajul la sub 9. Nici sa fim mai catolici decat papa."

    Pragul vechi nu s-a atins niciodata in noua replici, deci replica model n-a aparut deloc.
    """
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "ORI DE CÂTE ORI DAI SUB 9" in prompt
    assert "SUB 8" not in prompt
    assert "De la 9 în sus spui ce a mers" in prompt


# --- plicul 69: evaluarea se sprijina pe citat si nu se razgandeste la presiune ---
#
# Sesiunea a opta, 13 septembrie. La 6/10, Cody i-a reprosat lui Andrei ca „nu i-a adresat
# direct problema increderii". Replica lui o adresa, cuvant cu cuvant: „Vreau sa clarific ca
# nu este asta. Motivele, asa cum ti-am explicat, tin de mine si de planurile mele in
# aceasta perioada." A criticat o lipsa care nu exista — si cand Andrei i-a semnalat, nota a
# sarit de la 6 la 10, cu „Bravo!".
#
# Andrei: „daca se intampla asta in interactiuni live, participantii il vor contesta imediat."
# E primul defect care ataca increderea, nu experienta: cine-l prinde o data cu o nota
# gresita nu-i mai crede nicio nota.
#
# Al doilea caz, sesiunea a saptea: „Zi faina!" — doua cuvinte de despartire — a luat 10/10,
# cu cinci randuri de lauda. Zece puncte pe un mesaj din afara rolului.


def test_evaluarea_se_sprijina_pe_citat_si_nu_negociaza_nota():
    """Lacatul cerut rosu-inainte/verde-dupa: citatul si interdictia de a sari la 10."""
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "CITATUL ÎNAINTE DE VERDICT" in prompt
    assert "INTERZIS ABSOLUT să sari la 10" in prompt
    assert "CEL MULT UN PUNCT" in prompt


def test_nu_se_puncteaza_ce_nu_e_o_replica_din_scena():
    """„Zi faina!" nu e o performanta si nu primeste nota."""
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "NU SE PUNCTEAZĂ CE NU E O REPLICĂ DIN SCENĂ" in prompt
    assert "Zi faină!" in prompt


def test_ce_era_deja_in_evaluare_nu_s_a_pierdut():
    """Fisierul s-a rescris intreg — aici se verifica ce trebuia sa ramana."""
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei", history_length=3)

    assert "REPLICA SE SCRIE, NU SE DESCRIE" in prompt
    assert "ORI DE CÂTE ORI DAI SUB 9" in prompt
    assert "PUNCTAJUL E OBLIGATORIU" in prompt
    assert "SUB 8" not in prompt


# --- plicul 76: omul are nume si la quiz, nu doar la salut ---
#
# Andrei, 18 septembrie: „la role play mi-a spus pe nume, dar la quiz mi-a zis «user»".
# Numele ajungea in prompt numai prin salut; la quiz si la coaching, dupa salut, nu mai era
# nicaieri. Acum intra o data, ca fapt, in `reguli_generale`, care merge la toate trei modurile.


def test_la_quiz_numele_e_in_prompt_si_in_mijlocul_conversatiei():
    prompt = get_system_prompt_for_kind(
        "knowledge", name="Andrei Vacaru", history_length=4, quiz_competency="mix"
    )
    # de la plicul 143: numele (codul) e o eticheta, nu o forma de adresare
    assert "sub codul „Andrei Vacaru”" in prompt
    assert "INTERZIS să i te adresezi pe cod" in prompt


def test_la_coaching_numele_e_in_prompt_si_in_mijlocul_conversatiei():
    prompt = get_system_prompt_for_kind("coaching", name="Andrei Vacaru", history_length=4)
    assert "sub codul „Andrei Vacaru”" in prompt


def test_la_role_play_numele_ramane_si_salutul_e_neschimbat():
    from codrut.modules.practice.prompts import formula_de_salut

    mijloc = get_system_prompt_for_kind("roleplay", name="Andrei Vacaru", history_length=4)
    assert "sub codul „Andrei Vacaru”" in mijloc

    # salutul: acelasi text, cuvant cu cuvant, ca inainte de plicul 76 — si acum fara nume,
    # de la plicul 128
    inceput = get_system_prompt_for_kind("roleplay", name="Andrei Vacaru", history_length=1)
    assert formula_de_salut() in inceput


def test_evaluarea_nu_mai_poarta_cifra_inventata():
    from codrut.modules.practice.prompts import EVALUARE_PROMPT

    assert "de trei ori din opt sesiuni" not in EVALUARE_PROMPT
    assert "s-a întâmplat, și o dată e destul" in EVALUARE_PROMPT


# --- plicul 91: o replica din scena ramane in scena ---
#
# Plicul 88 a pus regula de ordine singura: ordinea a prins (6 din 6), dar personajul a disparut la
# 3 pasi din 9, fiindca Cody a citit replici neutre drept contestarea notei sau intrebari catre el
# (regula de la plicul 69). Ideea lui Andrei: contestarea se face cu o comanda, /feedback — nu se
# mai ghiceste din cuvinte.

BUCATILE_91 = (
    "ORDINEA, LA FIECARE REPLICĂ DIN JOC: întâi răspunde personajul, în rol",
    "TOT CE SCRIE OMUL E REPLICĂ DIN SCENĂ",
    "SINGURA IEȘIRE DIN SCENĂ E COMANDA /feedback",
)


def test_cele_trei_reguli_de_scena_sunt_primele_din_evaluare():
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei Vacaru", history_length=4)

    for bucata in BUCATILE_91:
        assert bucata in prompt, bucata
        assert prompt.index(bucata) < prompt.index("EVALUAREA CA CODY"), bucata


def test_regula_contestarii_ramane_si_ce_era_deja_nu_s_a_pierdut():
    prompt = get_system_prompt_for_kind("roleplay", name="Andrei Vacaru", history_length=4)

    for bucata in (
        "CÂND OMUL CONTESTĂ NOTA SAU OBSERVAȚIA",
        "CITATUL ÎNAINTE DE VERDICT",
        "PUNCTAJUL E OBLIGATORIU",
        "REPLICA SE SCRIE, NU SE DESCRIE",
        "ORI DE CÂTE ORI DAI SUB 9",
    ):
        assert bucata in prompt, bucata
