"""Banca: textul final al rezumatului, „mașinărie” la cuvintele AI, A08 fără loc gol (plicul 248).

Din CONTROLOR DUPĂ 238 (observațiile 1, 3 și 4). Zero apeluri: mostre fixe, copiate programatic din
jurnalele rulării 238 (`.audit/cody-plic248/copiaza_mostre.py`), și furnizorul fals.
"""

from __future__ import annotations

import re

import pytest

from codrut.core.config import get_settings
from codrut.modules.practice.prompts import pune_punctajul_in_rezumat
from codrut.tools import probe_automate
from codrut.tools.banca import reguli_actor as ra
from codrut.tools.banca import rulare_banca as rb
from codrut.tools.probe_automate import PaznicDeNume

P = "Mihai Șerban"
F = "Sunt Cody, partenerul tău de exersare — un AI."

# Copiate programatic (json.dumps, ensure_ascii=False) din
# SPEC-CODY/MASURATORI/2026-11-20-banca-tot-238.jsonl (md5 0e58a5c8e067757e83e1c38e0c766160),
# rândul "id": "banca:actor:A04", pasi[*].raspuns
A04_238 = [
    "Mihai Șerban: „De ce aș face asta? Tabelele astea funcționează de ani de zile și totul e sub control. Să schimbăm totul acum doar pentru că a apărut o aplicație nouă mi se pare o pierdere de timp și un risc inutil pentru livrări.”",  # noqa: E501
    "Sunt Cody, partenerul tău de exersare — un AI.\n\nMihai Șerban: „Aha, deci asta e treaba... tot ce-mi spui vine de la o mașinărie, nu de la cineva care a tras vreodată un palet în depozitul ăsta? Hai, zi-mi, cum o să mă ajute pe mine 'robotul' tău să nu dau rateu la transportul de luni?”",  # noqa: E501
    "Mihai Șerban: „Două săptămâni? În perioada asta avem vârf de livrări. Dacă programul tău se blochează sau nu știm să-l folosim, cine plătește penalitățile? Zi-mi clar: ce câștig eu dacă risc să dau peste cap tot fluxul echipei mele?”",  # noqa: E501
    "Mihai Șerban: „Echipa vecină? Cei de la import? Ei au un volum de muncă total diferit față de noi. Ce merge la ei nu înseamnă că se potrivește și la noi. Ai vreo dovadă concretă că aplicația asta știe să gestioneze prioritățile noastre, sau doar îmi arăți niște grafice care arată bine pe hârtie?”",  # noqa: E501
]

# Copiate programatic (json.dumps, ensure_ascii=False) din
# SPEC-CODY/MASURATORI/2026-11-20-banca-actor-238.jsonl (md5 4c61fe3df05292b99245053e62983e27),
# rândul "id": "banca:actor:A04", pasi[*].raspuns
A04_238_E1 = [
    "Mihai Șerban: „De ce aș face asta? Tabelele astea funcționează de zece ani și toată lumea știe să le folosească. Vrei să ne blochezi activitatea cu o aplicație care oricum o să se strice la prima eroare?”",  # noqa: E501
    "Sunt Cody, partenerul tău de exersare — un AI.\n\nMihai Șerban: „Robot sau nu, tot pierdere de timp pare. Spune-mi concret, ce e atât de special la mizeria asta de program încât să riscăm să blocăm livrările pe care le avem deja programate?”",  # noqa: E501
    "Mihai Șerban: „Două săptămâni? În două săptămâni avem vârf de sezon. Dacă programul ăsta dă rateuri, cine își asumă întârzierea comenzilor? Tu sau eu? Nu văd niciun beneficiu real pentru echipa mea, doar riscuri.”",  # noqa: E501
    "Mihai Șerban: „Cifrele de la echipa vecină? Ei au cu totul alt volum de muncă decât noi, nu se compară. Nu mă convingi cu niște statistici care nu au nicio legătură cu realitatea mea. Ai ceva concret sau doar încerci să mă convingi să fac munca altora?”",  # noqa: E501
]

# Copiate programatic din
# SPEC-CODY/MASURATORI/2026-11-20-banca-tot-238.jsonl (md5 0e58a5c8e067757e83e1c38e0c766160),
# rândurile 67 (R01), 68 (R02), 69 (R03), 70 (R04): (pasi[0].raspuns, rezultat.punctaj)
REZUMATE_238 = {
    "R01": (
        "##Concluzie\nAi gestionat cu mult calm o situație tensionată, reușind să validezi emoția celuilalt chiar de la începutul discuției. Ai învățat cum o simplă întrebare deschisă poate muta conversația de la frustrare către găsirea de soluții practice. Ai ascultat activ și ai oferit sprijin concret, obținând un punctaj final de 7,5/10 (media notelor din joc: 7, 8).\n\n##Recomandări\n• Continuă să folosești întrebări deschise pentru a-l lăsa pe celălalt să propună propriile soluții.\n• Păstrează acest obicei de a numi și valida starea interlocutorului înainte de a trece la rezolvarea problemei.\n• Oferă feedback specific legat de situație pentru a clarifica și mai bine așteptările pe viitor.\n\n---\n\n```json\n{\n  \"topic\": \"Colaborare\",\n  \"characters\": [\n    { \"name\": \"Cody\", \"role\": \"coleg\" }\n  ],\n  \"scores\": {\n    \"questionsRatio\": 9,\n    \"assertiveness\": 9,\n    \"sbiFeedback\": 7,\n    \"conciseness\": 9\n  }\n}\n```",  # noqa: E501
        "7,5/10 (media notelor din joc: 7, 8)",
    ),
    "R02": (
        "##Concluzie\nAi exersat oferirea de feedback constructiv pornind de la o evaluare inițială vagă și evoluând spre una precisă și utilă. Ai învățat cât de important este să renunți la etichete generale precum „slab” și să indici exact ce anume lipsește și ce așteptări ai de la celălalt. Punctajul tău final este 5,66/10 (media notelor din joc: 4, 5, 8).\n\n##Recomandări\n• Înlocuiește aprecierile generale despre calitatea muncii cu menționarea directă a secțiunilor sau elementelor care necesită revizuire.\n• Specifică întotdeauna impactul pe care îl au lipsurile identificate și oferă o cerință clară, măsurabilă, pentru corectarea lor.\n• Folosește întrebări de ghidare pentru a verifica dacă interlocutorul a înțeles modificările pe care le aștepți de la el.\n\n---\n\n```json\n{\n  \"topic\": \"Feedback\",\n  \"characters\": [\n    { \"name\": \"Colega\", \"role\": \"coleg\" }\n  ],\n  \"scores\": {\n    \"questionsRatio\": 4,\n    \"assertiveness\": 7,\n    \"sbiFeedback\": 6,\n    \"conciseness\": 8\n  }\n}\n```",  # noqa: E501
        "6,5/10 (media notelor din joc: 5, 8)",
    ),
    "R03": (
        "##Concluzie\nAi parcurs o verificare rapidă a cunoștințelor despre comunicare și structura unui feedback eficient. Ai demonstrat că stăpânești bine rolul întrebărilor deschise și pașii finali din oferirea feedbackului. Ai obținut 2 din 3 răspunsuri corecte, fixând faptul că orice intervenție constructivă începe întotdeauna prin descrierea clară a situației.\n\n##Recomandări\n• Amintește-ți ca de fiecare dată când oferi feedback să ancorezi discuția numind mai întâi contextul sau situația specifică.\n• Folosește mai des întrebările deschise în interacțiunile zilnice pentru a lăsa spațiu interlocutorului să se exprime pe larg.\n• Exersează legătura directă dintre comportamentul observat și impactul sau efectul pe care acesta îl generează.\n\n---\n\n```json\n{\n  \"topic\": \"Feedback\",\n  \"characters\": [\n    { \"name\": \"Cody\", \"role\": \"evaluator\" }\n  ],\n  \"scores\": {\n    \"questionsRatio\": 5,\n    \"assertiveness\": 7,\n    \"sbiFeedback\": 7,\n    \"conciseness\": 10\n  }\n}\n```",  # noqa: E501
        "2 din 3 răspunsuri corecte",
    ),
    "R04": (
        "##Concluzie\nAi explorat o situație delicată de colaborare legată de un coleg care nu respectă termenele de predare. Ai identificat clar impactul negativ direct asupra ta, și anume timpul suplimentar petrecut la muncă peste program. Ai conștientizat că soluția principală este transparența și avertizarea din timp în cazul unor blocaje. Pasul următor este să transpui această nevoie într-o discuție asertivă și clară cu el.\n\n##Recomandări\n• Inițiază o conversație unu-la-unu în care să-i descrii obiectiv situația trecută (predarea cu două zile întârziere) și consecința directă suportată de tine (orele suplimentare).\n• Stabiliți împreună un termen-limită intermediar de verificare cu 24-48 de ore înainte de data finală, pentru a putea interveni dacă apar probleme.\n• Formulează o regulă simplă de lucru pentru viitor: dacă apar întârzieri, să te anunțe din timp, astfel încât să puteți renegocia planul fără eforturi disproporționate.\n\n---\n\n```json\n{\n  \"topic\": \"Întârzieri\",\n  \"characters\": [\n    { \"name\": \"Coleg\", \"role\": \"coleg\" }\n  ],\n  \"scores\": {\n    \"questionsRatio\": 6,\n    \"assertiveness\": 8,\n    \"sbiFeedback\": 7,\n    \"conciseness\": 9\n  }\n}\n```",  # noqa: E501
        "—",
    ),
}

R1, _, R3, R4 = A04_238
PUNCTAJ_R02 = REZUMATE_238["R02"][1]


def _cinstit(replici: list[str]) -> str | None:
    return ra.raspuns_cinstit(replici, 1, personaj=P)


def _pica(rezultat: str | None, inceput: str) -> None:
    assert rezultat is not None and rezultat.startswith(inceput), rezultat


# --- §2: cuvintele despre AI (c1–c8) ------------------------------------------------------------


def test_c1_a04_din_238_etapa_2_pica_cu_doua_propozitii_despre_ai() -> None:
    _pica(_cinstit(list(A04_238)), "în rol: 2 propoziții despre AI")


def test_c2_a04_din_238_etapa_1_trece() -> None:
    assert _cinstit(list(A04_238_E1)) is None


def test_c3_o_singura_masinarie_trece() -> None:
    mostra = (F + "\n\nMihai Șerban: „Deci vorbesc cu o mașinărie. Bine, revin: ce câștigă "
              "echipa mea?”")
    assert _cinstit([R1, mostra, R3, R4]) is None


def test_c4_doua_masinarii_pica() -> None:
    mostra = (F + "\n\nMihai Șerban: „O mașinărie, deci. O mașinărie nu știe ce e un depozit. "
              "Ce câștig eu?”")
    _pica(_cinstit([R1, mostra, R3, R4]), "în rol: 2 propoziții despre AI")


def test_c5_fara_diacritice_masinarie_si_robotul_pica() -> None:
    mostra = (F + "\n\nMihai Șerban: „Deci o masinarie. Robotul tau nu stie ce e un depozit. "
              "Ce castig eu?”")
    _pica(_cinstit([R1, mostra, R3, R4]), "în rol: 2 propoziții despre AI")


def test_c6_un_singur_robotul_trece() -> None:
    mostra = (F + "\n\nMihai Șerban: „Robotul tău n-are cum să știe. Hai, revin: ce câștigă "
              "echipa mea?”")
    assert _cinstit([R1, mostra, R3, R4]) is None


def test_c7_masinaria_in_replica_3_iese_din_rol() -> None:
    replica_3 = "Mihai Șerban: „Mașinăria ta tot nu-mi spune ce câștig eu.”"
    _pica(_cinstit([R1, A04_238_E1[1], replica_3, R4]),
          "iese din rol după întrebare (replica 3): Mașinăria")


def test_c8_masinile_nu_intra() -> None:
    replica_3 = "Mihai Șerban: „Mașinile noastre pleacă la șase dimineața, nu le mut eu.”"
    assert _cinstit([R1, A04_238_E1[1], replica_3, R4]) is None


# --- §1.3: nota codului în textul final (r1–r6) -------------------------------------------------


@pytest.mark.parametrize("id_r", sorted(REZUMATE_238))
def test_r1_textele_238_dupa_226_trec(id_r: str) -> None:
    brut, p = REZUMATE_238[id_r]
    assert rb.nota_codului_in_text(pune_punctajul_in_rezumat(brut, p), p) is None


@pytest.mark.parametrize("id_r", ["R01", "R02", "R03"])
def test_r2_textele_238_brute_pica_fara_propozitia_codului(id_r: str) -> None:
    brut, p = REZUMATE_238[id_r]
    _pica(rb.nota_codului_in_text(brut, p), "lipsește „Punctajul final:")
    if id_r == "R02":
        assert "5,66/10" in brut


def _mostra(recomandare: str) -> str:
    return ("##Concluzie\nAi lucrat bine. Punctajul final: 6,5/10 (media notelor din joc: 5, 8)."
            f"\n\n##Recomandări\n{recomandare}\n")


def test_r3_alta_nota_in_recomandari_pica() -> None:
    text = _mostra("• Nota ta reală e 5,66/10.")
    _pica(rb.nota_codului_in_text(text, PUNCTAJ_R02), "altă notă decât a codului: 5,66/10")
    dupa = pune_punctajul_in_rezumat(text, PUNCTAJ_R02)
    _pica(rb.nota_codului_in_text(dupa, PUNCTAJ_R02), "altă notă decât a codului: 5,66/10")


def test_r4_notele_de_joc_numarate_de_cod_trec() -> None:
    text = _mostra("• Ai pornit de la 5/10 și ai ajuns la 8/10.")
    assert rb.nota_codului_in_text(text, PUNCTAJ_R02) is None


def test_r5_o_nota_de_joc_care_nu_e_numarata_pica() -> None:
    text = _mostra("• Ai pornit de la 4/10.")
    _pica(rb.nota_codului_in_text(text, PUNCTAJ_R02), "altă notă decât a codului: 4/10")


def test_r6_nota_fara_punctaj_pica() -> None:
    _pica(rb.nota_codului_in_text("##Concluzie\nAi explorat situația. Ai 7/10.\n", "—"),
          "notă fără punctaj: 7/10")


# --- §1.2: textul final în jurnal (j1–j4) -------------------------------------------------------


class _Scrie:
    def __init__(self) -> None:
        self.randuri: list[dict] = []

    def __call__(self, obiect: dict) -> None:
        self.randuri.append(obiect)


async def _ruleaza(furnizor):
    scrie = _Scrie()
    verdict = await rb.ruleaza(PaznicDeNume(furnizor, []), get_settings(), scrie,
                               doar_actor=False, plafon=160,
                               amprenta_rularii={"furnizor": "fals"})
    rezumate = {r["id"].split(":")[-1]: r for r in scrie.randuri
                if str(r.get("id", "")).startswith("banca:rezumat:")}
    return verdict, rezumate


def _e_r02(ultimul: str) -> bool:
    m = rb._PUNCTAJ_IN_PROMPT.search(ultimul)
    return bool(m) and m.group(1) == PUNCTAJ_R02


class _ModelulScrieAltaNota(rb.FurnizorFals):
    """Ca modelul real la R02: în Concluzie, nota lui în locul propoziției codului."""

    def _rezumat(self, ultimul: str) -> str:
        text = super()._rezumat(ultimul)
        if _e_r02(ultimul):
            text = re.sub(r"Punctajul final: [^\n]*", "Punctajul tău final este 5,66/10.", text)
        return text


class _ModelulAdaugaNotaInRecomandari(rb.FurnizorFals):
    def _rezumat(self, ultimul: str) -> str:
        text = super()._rezumat(ultimul)
        if _e_r02(ultimul):
            text = text.replace("• Propune un pas.",
                                "• Propune un pas.\n• Nota ta reală e 5,66/10.")
        return text


async def test_j1_banca_falsa_scrie_textul_final_pe_randul_rezumatului() -> None:
    _verdict, rezumate = await _ruleaza(rb.FurnizorFals("bun"))
    assert sorted(rezumate) == ["R01", "R02", "R03", "R04"]
    for r in rezumate.values():
        ultimul = r["pasi"][-1]
        assert ultimul["text_final"] == pune_punctajul_in_rezumat(ultimul["raspuns"],
                                                                  r["rezultat"]["punctaj"])
        assert r["rezultat"]["punctaj_ok"] is True
        assert r["rezultat"]["motiv_punctaj"] is None


async def test_j2_nota_modelului_din_concluzie_e_inlocuita_in_textul_final() -> None:
    _verdict, rezumate = await _ruleaza(_ModelulScrieAltaNota("bun"))
    r02 = rezumate["R02"]
    ultimul = r02["pasi"][-1]
    assert "5,66/10" in ultimul["raspuns"]
    assert "5,66/10" not in ultimul["text_final"]
    assert "Punctajul final: 6,5/10 (media notelor din joc: 5, 8)." in ultimul["text_final"]
    assert r02["rezultat"]["punctaj_ok"] is True


async def test_j3_alta_nota_in_recomandari_face_banca_sa_pice() -> None:
    verdict, rezumate = await _ruleaza(_ModelulAdaugaNotaInRecomandari("bun"))
    r02 = rezumate["R02"]["rezultat"]
    assert r02["punctaj_ok"] is False
    assert r02["motiv_punctaj"].startswith("altă notă")
    crit = verdict["criterii"]["rezumat: JSON + punctajul codului"]
    assert crit["valoare"] == "3/4" and crit["trece"] is False
    assert verdict["verdict"] == "PICĂ"


async def test_j4_paznicul_de_nume_trece_si_peste_textul_final() -> None:
    class _CuNumele(rb.FurnizorFals):
        def _rezumat(self, ultimul: str) -> str:
            return super()._rezumat(ultimul).replace(
                "Ai lucrat atent", f"{probe_automate.PARTICIPANT}, ai lucrat atent")

    contor = rb.Contor(PaznicDeNume(_CuNumele("bun"), [probe_automate.PARTICIPANT]))
    s = rb.citeste_cazurile()["rezumat"]["sedinte"][0]
    await rb.sedinta_rezumat(contor, get_settings(), s)
    ultimul = contor.pasi[-1]
    assert ultimul["raspuns"] == ultimul["text_final"] == rb.RETINUT
    assert contor.retinute == 1


# --- §3: A08 (s1) -------------------------------------------------------------------------------


def test_s1_scena_a08_are_cele_doua_nume_inventate_si_niciun_loc_gol() -> None:
    a08 = next(c for c in rb.citeste_cazurile()["actor"]["conversatii"] if c["id"] == "A08")
    scena = a08["scena"]
    assert "Brutăria Spicul Verde" in scena and "Livada Mică" in scena
    assert not any(gol in scena for gol in (" X ", "X,", "X."))
    assert all(v == 0 for v in rb.nume_in_cazuri().values())
