"""Verificările urcării cu o singură aprobare din GitHub — plicul 243 (A1).

Funcții mici, testabile (`test_urcare_verificari.py`), chemate din `_urcare.yml` prin linia de
comandă. Fiecare verificare picată ridică `Oprit`; linia de comandă tipărește atunci
„OPRIT: <motiv>” și iese cu 1. Depozitul e public, deci tot ce se tipărește aici ajunge în
jurnalul public al rulării: numai verdicte și sha-uri scurte, nicio cifră din bază, nicio adresă.
Numai biblioteca standard.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

APROBATOR = "andreyvacaru"
MEDII = ("proba", "production")
RAMURA_SURSA = "dev"
RAMURA_TINTA = "prod"
PORTI_OBLIGATORII = (
    "release / required",
    "release / exact-dev-tree",
    "release / validated-candidate",
)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_CAMPURI_SHA = ("candidat", "arbore", "banca")
_CAMPURI_CERUTE = ("pachet", "candidat", "arbore", "banca", "lucrari")
_CAMPURI_STIUTE = (*_CAMPURI_CERUTE, "proba-andrei")
DEPLOY_VECHI = ".github/workflows/_deploy-vps.yml"

# Ce atinge pachetul, pe nume (ordinea e cea în care apare pe pagină).
_ATINSE = (
    ("compose", lambda f: re.match(r"^compose[^/]*\.ya?ml$", f) is not None),
    ("infra", lambda f: f.startswith("infra/")),
    (".github", lambda f: f.startswith(".github/")),
    ("migrari", lambda f: f.startswith("backend/migrations/")),
    ("ecranele", lambda f: f.startswith("frontend/")),
    (".env", lambda f: Path(f).name.startswith(".env")),
    ("Dockerfile", lambda f: Path(f).name.startswith("Dockerfile")),
)


class Oprit(Exception):  # noqa: N818 - numele spune ce vede omul: „OPRIT”
    """O verificare a picat: rularea se oprește înainte de orice schimbare."""


def scurt(sha: str) -> str:
    return sha[:8]


def citeste_corpul(text: str) -> dict:
    """Rândurile fixe din corpul cererii `dev` → `prod` (§2 pct. 8). Lipsă sau greșit = OPRIT."""
    gasite: dict = {}
    for rand in text.splitlines():
        m = re.match(r"^\s*([a-z-]+):\s*(.*?)\s*$", rand)
        if not m or m.group(1) not in _CAMPURI_STIUTE:
            continue
        cheie, valoare = m.group(1), m.group(2)
        if cheie in gasite:
            raise Oprit(f"rândul «{cheie}:» apare de două ori în corpul cererii")
        gasite[cheie] = valoare
    lipsa = [c for c in _CAMPURI_CERUTE if not gasite.get(c)]
    if lipsa:
        raise Oprit("în corpul cererii lipsește: " + ", ".join(f"«{c}:»" for c in lipsa))
    if not re.fullmatch(r"[0-9]{1,4}", gasite["pachet"]):
        raise Oprit("«pachet:» nu e un număr")
    for camp in _CAMPURI_SHA:
        if not _SHA.match(gasite[camp]):
            raise Oprit(f"«{camp}:» nu e un sha întreg de 40 de caractere")
    lucrari = [x.strip() for x in gasite["lucrari"].split(",")]
    if not lucrari or not all(re.fullmatch(r"[0-9]{2,4}[a-z]?(-[A-Z0-9]+)?", x) for x in lucrari):
        raise Oprit("«lucrari:» nu e o listă de numere de plic")
    gasite["lucrari"] = lucrari
    return gasite


def verifica_arborele(arbore_declarat: str, arbore_sha: str, arbore_candidat: str) -> None:
    if not (arbore_declarat == arbore_sha == arbore_candidat):
        raise Oprit(
            f"arborele nu se potrivește: declarat {scurt(arbore_declarat)}, al vârfului "
            f"{scurt(arbore_sha)}, al candidatului {scurt(arbore_candidat)}"
        )


def _setari(text: str) -> dict[str, str]:
    valori: dict[str, str] = {}
    for rand in text.splitlines():
        rand = rand.strip()
        if not rand or rand.startswith("#") or "=" not in rand:
            continue
        cheie, valoare = rand.split("=", 1)
        valori[cheie.strip()] = valoare.strip()
    return valori


def compara_setari(asteptate: str, citite: str) -> list[str]:
    """Fiecare rând așteptat `NUME=a|b` trebuie să fie în citire, cu una din valori.

    Rândurile citite care nu sunt în fișierul așteptat nu contează. Întoarce lista abaterilor
    (numai numele și valorile setărilor din fișier — valori publice: modele, regiune, timpi).
    """
    citit = _setari(citite)
    abateri = []
    for nume, permise in _setari(asteptate).items():
        variante = [v.strip() for v in permise.split("|")]
        if nume not in citit:
            abateri.append(f"{nume}: lipsește din citire (așteptat {permise})")
        elif citit[nume] not in variante:
            abateri.append(f"{nume}: {citit[nume]} (așteptat {permise})")
    return abateri


def verifica_atinse(fisiere: list[str]) -> list[str]:
    """Numele celor atinse; `_deploy-vps.yml` atins = OPRIT (hotărârea 5: pe calea veche)."""
    if DEPLOY_VECHI in fisiere:
        raise Oprit("pachetul schimbă felul vechi de urcare — urcă pe calea veche")
    return [nume for nume, se_potriveste in _ATINSE if any(se_potriveste(f) for f in fisiere)]


def verifica_intrarile(mediu: str, simuleaza_picare: str) -> None:
    if mediu not in MEDII:
        raise Oprit(f"mediu necunoscut: {mediu}")
    if mediu == "production" and simuleaza_picare.strip().lower() == "true":
        raise Oprit("picarea simulată nu se face niciodată pe live")


def verifica_aprobarea(mediu_json: dict) -> None:
    """V0: mediul `production` are aprobator obligatoriu pe Andrei; altfel nu se urcă."""
    for regula in mediu_json.get("protection_rules") or []:
        if regula.get("type") != "required_reviewers":
            continue
        for aprobator in regula.get("reviewers") or []:
            if (aprobator.get("reviewer") or {}).get("login") == APROBATOR:
                return
    raise Oprit("lipsește aprobarea obligatorie — nu urc fără ea")


def verifica_sursa(rulare: dict, repo: str) -> None:
    """V1: rularea „Release Gate” care a pornit urcarea e verde, pe `dev`, din depozitul nostru."""
    if rulare.get("conclusion") != "success":
        raise Oprit("„Release Gate” nu e verde")
    if rulare.get("head_branch") != RAMURA_SURSA:
        raise Oprit("„Release Gate” nu e pe ramura dev")
    if (rulare.get("head_repository") or {}).get("full_name") != repo:
        raise Oprit("cererea vine din altă copie a depozitului")


def verifica_cererea(cerere: dict, sha: str, repo: str) -> None:
    """V1: cererea e deschisă, `dev` → `prod`, din depozitul nostru, cu vârful așteptat."""
    if cerere.get("state") != "OPEN":
        raise Oprit("cererea nu e deschisă")
    if cerere.get("baseRefName") != RAMURA_TINTA or cerere.get("headRefName") != RAMURA_SURSA:
        raise Oprit("cererea nu e dev → prod")
    proprietar = (cerere.get("headRepositoryOwner") or {}).get("login", "")
    nume = (cerere.get("headRepository") or {}).get("name", "")
    if f"{proprietar}/{nume}" != repo:
        raise Oprit("cererea vine din altă copie a depozitului")
    if cerere.get("headRefOid") != sha:
        raise Oprit("vârful cererii s-a mișcat")


def verifica_portile(cerere: dict) -> None:
    """V5: porțile „release” au `conclusion = SUCCESS` (nu doar terminate) și cererea e CLEAN."""
    concluzii: dict[str, str] = {}
    for poarta in cerere.get("statusCheckRollup") or []:
        nume = poarta.get("name") or poarta.get("context") or ""
        concluzii[nume] = (poarta.get("conclusion") or poarta.get("state") or "").upper()
    rosii = [p for p in PORTI_OBLIGATORII if concluzii.get(p) != "SUCCESS"]
    if rosii:
        raise Oprit("porți care nu sunt verzi: " + ", ".join(rosii))
    if cerere.get("mergeStateStatus") != "CLEAN":
        raise Oprit("cererea nu se poate îmbina curat")


def rezumat(*, corp: dict | None, pr: str, arbore: str, migrari_noi: int,
            atinse: list[str]) -> str:
    """Pagina pe care o citește Andrei pe telefon ÎNAINTE de Approve (forma din §4)."""
    if corp is None:
        return "\n".join([
            "## REPETIȚIE — așteaptă aprobarea ta",
            "Nu urc nimic. După ce apeși Approve, citesc live-ul (setări, să nu exerseze",
            "nimeni, datele de control) și mă opresc. Așa vedem că îți vine cererea pe telefon.",
            "",
        ])
    intoarcere = (
        "0 → dacă ceva pică, mă întorc singur la pachetul de acum"
        if migrari_noi == 0
        else "DA → fără întoarcere singură; dacă ceva pică, scrii «dă înapoi» în Terminal"
    )
    return "\n".join([
        f"## Pachetul {corp['pachet']} — așteaptă aprobarea ta",
        f"Ce aduce: lucrările {', '.join(corp['lucrari'])} (din cererea #{pr})",
        f"✓ candidatul legat (arborele {scurt(arbore)}…)   ✓ banca de probă neatinsă   "
        "✓ porțile GitHub verzi",
        f"Migrări noi în bază: {intoarcere}",
        f"Atinge și: {', '.join(atinse) if atinse else '(nimic)'}",
        "După ce apeși Approve: verific live-ul (setări, să nu exerseze nimeni), urc, verific iar.",
        "Dacă ceva nu e bine după urcare, dau înapoi singur. Nu apeși nimic altceva.",
        "",
    ])


# --- linia de comandă (chemată din `_urcare.yml`) ----------------------------------------------


def _json(cale: str):
    return json.loads(Path(cale).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("intrari")
    a.add_argument("--mediu", required=True)
    a.add_argument("--simuleaza-picare", required=True)
    a = sub.add_parser("aprobare")
    a.add_argument("mediu_json")
    a = sub.add_parser("sursa")
    a.add_argument("eveniment_json")
    a.add_argument("--repo", required=True)
    a = sub.add_parser("cerere")
    a.add_argument("cerere_json")
    a.add_argument("--sha", required=True)
    a.add_argument("--repo", required=True)
    a = sub.add_parser("corp")
    a.add_argument("cerere_json")
    a.add_argument("--camp", required=True, choices=_CAMPURI_STIUTE)
    a = sub.add_parser("arbore")
    a.add_argument("--declarat", required=True)
    a.add_argument("--al-sha", required=True)
    a.add_argument("--al-candidatului", required=True)
    a = sub.add_parser("atinse")
    a.add_argument("fisiere")
    a = sub.add_parser("porti")
    a.add_argument("cerere_json")
    a = sub.add_parser("setari")
    a.add_argument("asteptate")
    a.add_argument("citite")
    a = sub.add_parser("rezumat")
    a.add_argument("--cerere-json", default="")
    a.add_argument("--pr", default="")
    a.add_argument("--arbore", default="")
    a.add_argument("--migrari-noi", type=int, default=0)
    a.add_argument("--atinse", default="")
    args = p.parse_args(argv)

    try:
        if args.cmd == "intrari":
            verifica_intrarile(args.mediu, args.simuleaza_picare)
        elif args.cmd == "aprobare":
            verifica_aprobarea(_json(args.mediu_json))
        elif args.cmd == "sursa":
            verifica_sursa(_json(args.eveniment_json).get("workflow_run") or {}, args.repo)
        elif args.cmd == "cerere":
            verifica_cererea(_json(args.cerere_json), args.sha, args.repo)
        elif args.cmd == "corp":
            valoare = citeste_corpul(_json(args.cerere_json).get("body") or "")[args.camp]
            print(", ".join(valoare) if isinstance(valoare, list) else valoare)
        elif args.cmd == "arbore":
            verifica_arborele(args.declarat, args.al_sha, args.al_candidatului)
        elif args.cmd == "atinse":
            fisiere = [f for f in Path(args.fisiere).read_text(encoding="utf-8").splitlines() if f]
            print(",".join(verifica_atinse(fisiere)))
        elif args.cmd == "porti":
            verifica_portile(_json(args.cerere_json))
        elif args.cmd == "setari":
            abateri = compara_setari(Path(args.asteptate).read_text(encoding="utf-8"),
                                     Path(args.citite).read_text(encoding="utf-8"))
            if abateri:
                raise Oprit("setările diferă: " + "; ".join(abateri))
        elif args.cmd == "rezumat":
            corp = (citeste_corpul(_json(args.cerere_json).get("body") or "")
                    if args.cerere_json else None)
            print(rezumat(corp=corp, pr=args.pr, arbore=args.arbore,
                          migrari_noi=args.migrari_noi,
                          atinse=[x for x in args.atinse.split(",") if x]))
    except Oprit as exc:
        print(f"OPRIT: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
