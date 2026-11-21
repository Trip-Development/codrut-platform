"""Verificările urcării cu aprobare din GitHub — plicul 243 (A1).

Rulează ca `automation / checks` din `app-ci.yml`: `python3 -m unittest discover -p 'test_*.py'`.
"""

import json
import unittest

from urcare_verificari import (
    Oprit,
    citeste_corpul,
    compara_setari,
    rezumat,
    verifica_aprobarea,
    verifica_arborele,
    verifica_atinse,
    verifica_cererea,
    verifica_intrarile,
    verifica_portile,
    verifica_sursa,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
ARBORE = "c" * 40
REPO = "Trip-Development/codrut-platform"

CORP_BUN = f"""Pachetul 22 pe live.

pachet: 22
candidat: {SHA_A}
arbore: {ARBORE}
banca: {SHA_B}
lucrari: 234, 235, 236
proba-andrei: un role-play scurt; Tabloul pe proiect
"""


class CorpulCererii(unittest.TestCase):
    def test_corpul_bun(self) -> None:
        corp = citeste_corpul(CORP_BUN)
        self.assertEqual(corp["pachet"], "22")
        self.assertEqual(corp["candidat"], SHA_A)
        self.assertEqual(corp["lucrari"], ["234", "235", "236"])
        self.assertEqual(corp["proba-andrei"], "un role-play scurt; Tabloul pe proiect")

    def test_fara_banca_e_oprit(self) -> None:
        with self.assertRaises(Oprit) as prins:
            citeste_corpul(CORP_BUN.replace(f"banca: {SHA_B}\n", ""))
        self.assertIn("banca", str(prins.exception))

    def test_sha_scurt_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            citeste_corpul(CORP_BUN.replace(f"candidat: {SHA_A}", "candidat: aaaaaaa"))

    def test_rand_repetat_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            citeste_corpul(CORP_BUN + "pachet: 23\n")

    def test_lucrari_fara_numere_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            citeste_corpul(CORP_BUN.replace("lucrari: 234, 235, 236", "lucrari: multe"))


class Arborele(unittest.TestCase):
    def test_acelasi_arbore_trece(self) -> None:
        verifica_arborele(ARBORE, ARBORE, ARBORE)

    def test_arbore_diferit_de_al_sha_ului_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_arborele(ARBORE, "d" * 40, ARBORE)

    def test_arbore_diferit_de_al_candidatului_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_arborele(ARBORE, ARBORE, "d" * 40)


ASTEPTATE = """# setările pachetului 22 pe live, înainte de urcare
CODRUT_VERTEX_REGION=eu
CODRUT_GENERATION_ENGINES=(nesetat)
CODRUT_THINKING_BUDGET_EVALUATOR=(nesetat)|1024
"""


class Setarile(unittest.TestCase):
    def test_toate_bune(self) -> None:
        citite = ("CODRUT_VERTEX_REGION=eu\nCODRUT_GENERATION_ENGINES=(nesetat)\n"
                  "CODRUT_THINKING_BUDGET_EVALUATOR=(nesetat)\nprompt=v3.12\n")
        self.assertEqual(compara_setari(ASTEPTATE, citite), [])

    def test_regiunea_nesetata_e_abatere(self) -> None:
        citite = ("CODRUT_VERTEX_REGION=(nesetat)\nCODRUT_GENERATION_ENGINES=(nesetat)\n"
                  "CODRUT_THINKING_BUDGET_EVALUATOR=1024\n")
        abateri = compara_setari(ASTEPTATE, citite)
        self.assertEqual(len(abateri), 1)
        self.assertIn("CODRUT_VERTEX_REGION", abateri[0])

    def test_motoarele_setate_cand_trebuie_nesetate_e_abatere(self) -> None:
        citite = ("CODRUT_VERTEX_REGION=eu\nCODRUT_GENERATION_ENGINES=vertex\n"
                  "CODRUT_THINKING_BUDGET_EVALUATOR=(nesetat)\n")
        abateri = compara_setari(ASTEPTATE, citite)
        self.assertEqual(len(abateri), 1)
        self.assertIn("CODRUT_GENERATION_ENGINES", abateri[0])

    def test_gandirea_nesetata_sau_1024_e_buna(self) -> None:
        for valoare in ("(nesetat)", "1024"):
            citite = ("CODRUT_VERTEX_REGION=eu\nCODRUT_GENERATION_ENGINES=(nesetat)\n"
                      f"CODRUT_THINKING_BUDGET_EVALUATOR={valoare}\n")
            self.assertEqual(compara_setari(ASTEPTATE, citite), [], valoare)

    def test_setarea_lipsa_din_citire_e_abatere(self) -> None:
        abateri = compara_setari(ASTEPTATE, "CODRUT_VERTEX_REGION=eu\n")
        self.assertEqual(len(abateri), 2)


class CeAtingePachetul(unittest.TestCase):
    def test_deploy_vechi_atins_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_atinse(["backend/src/x.py", ".github/workflows/_deploy-vps.yml"])

    def test_numele_atinse(self) -> None:
        atinse = verifica_atinse(["backend/src/x.py", "compose.prod.yaml", "frontend/a.ts",
                                  "backend/migrations/versions/0072_x.py", "infra/docker/f"])
        self.assertEqual(atinse, ["compose", "infra", "migrari", "ecranele"])

    def test_nimic_special(self) -> None:
        self.assertEqual(verifica_atinse(["backend/src/x.py"]), [])


class Intrarile(unittest.TestCase):
    def test_picarea_simulata_pe_live_e_oprita(self) -> None:
        with self.assertRaises(Oprit):
            verifica_intrarile("production", "true")

    def test_picarea_simulata_pe_proba_e_permisa(self) -> None:
        verifica_intrarile("proba", "true")
        verifica_intrarile("production", "false")

    def test_mediu_necunoscut_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_intrarile("prod", "false")


class Aprobarea(unittest.TestCase):
    def test_aprobatorul_exista(self) -> None:
        mediu = {"protection_rules": [
            {"type": "branch_policy"},
            {"type": "required_reviewers",
             "reviewers": [{"type": "User", "reviewer": {"login": "andreyvacaru"}}]},
        ]}
        verifica_aprobarea(mediu)

    def test_fara_required_reviewers_e_oprit(self) -> None:
        with self.assertRaises(Oprit) as prins:
            verifica_aprobarea({"protection_rules": [{"type": "branch_policy"}]})
        self.assertIn("aprobarea obligatorie", str(prins.exception))

    def test_alt_aprobator_e_oprit(self) -> None:
        mediu = {"protection_rules": [
            {"type": "required_reviewers",
             "reviewers": [{"type": "User", "reviewer": {"login": "altcineva"}}]},
        ]}
        with self.assertRaises(Oprit):
            verifica_aprobarea(mediu)


def rulare(**schimbari) -> dict:
    baza = {"conclusion": "success", "head_branch": "dev", "head_sha": SHA_A,
            "head_repository": {"full_name": REPO}}
    baza.update(schimbari)
    return baza


class SursaRularii(unittest.TestCase):
    def test_sursa_buna(self) -> None:
        verifica_sursa(rulare(), REPO)

    def test_depozit_strain_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_sursa(rulare(head_repository={"full_name": "strain/codrut-platform"}), REPO)

    def test_alta_ramura_sau_rosu_e_oprit(self) -> None:
        for gresit in (rulare(head_branch="feat/x"), rulare(conclusion="failure")):
            with self.assertRaises(Oprit):
                verifica_sursa(gresit, REPO)


def cerere(**schimbari) -> dict:
    baza = {
        "state": "OPEN", "baseRefName": "prod", "headRefName": "dev", "headRefOid": SHA_A,
        "mergeStateStatus": "CLEAN",
        "headRepository": {"name": "codrut-platform"},
        "headRepositoryOwner": {"login": "Trip-Development"},
        "statusCheckRollup": [
            {"name": "release / required", "conclusion": "SUCCESS", "status": "COMPLETED"},
            {"name": "release / exact-dev-tree", "conclusion": "SUCCESS", "status": "COMPLETED"},
            {"name": "release / validated-candidate", "conclusion": "SUCCESS",
             "status": "COMPLETED"},
        ],
    }
    baza.update(schimbari)
    return baza


class Cererea(unittest.TestCase):
    def test_cererea_buna(self) -> None:
        verifica_cererea(cerere(), SHA_A, REPO)
        verifica_portile(cerere())

    def test_varful_mutat_e_oprit(self) -> None:
        with self.assertRaises(Oprit):
            verifica_cererea(cerere(headRefOid=SHA_B), SHA_A, REPO)

    def test_cerere_dintr_o_copie_e_oprita(self) -> None:
        with self.assertRaises(Oprit):
            verifica_cererea(cerere(headRepositoryOwner={"login": "strain"}), SHA_A, REPO)

    def test_poarta_rosie_sau_numai_terminata_e_oprita(self) -> None:
        porti = cerere()["statusCheckRollup"]
        porti[0] = {"name": "release / required", "conclusion": "", "status": "COMPLETED"}
        with self.assertRaises(Oprit):
            verifica_portile(cerere(statusCheckRollup=porti))
        with self.assertRaises(Oprit):
            verifica_portile(cerere(mergeStateStatus="BLOCKED"))


class Rezumatul(unittest.TestCase):
    def test_fara_cifre_de_martor_si_fara_arond(self) -> None:
        text = rezumat(corp=citeste_corpul(CORP_BUN), pr="530", arbore=ARBORE,
                       migrari_noi=0, atinse=[])
        self.assertIn("Pachetul 22", text)
        self.assertIn("cccccccc", text)
        self.assertNotIn(ARBORE, text)
        self.assertNotIn("@", text)
        self.assertNotIn("MARTOR", text)
        self.assertIn("mă întorc singur", text)

    def test_cu_migrari_spune_fara_intoarcere(self) -> None:
        text = rezumat(corp=citeste_corpul(CORP_BUN), pr="530", arbore=ARBORE,
                       migrari_noi=2, atinse=["migrari"])
        self.assertIn("fără întoarcere singură", text)

    def test_repetitia_fara_cerere(self) -> None:
        text = rezumat(corp=None, pr="", arbore="", migrari_noi=0, atinse=[])
        self.assertIn("REPETIȚIE", text)
        self.assertNotIn("@", text)


class LinieDeComanda(unittest.TestCase):
    def test_rezumatul_iese_ca_json_valid_pentru_atinse(self) -> None:
        self.assertEqual(json.loads(json.dumps(verifica_atinse([]))), [])


if __name__ == "__main__":
    unittest.main()
