"""Scriptul cheii înguste de urcare (`infra/urcare/cody-urcare.sh`) — plicul 243 (A1).

Rulează scriptul cu `bash`, într-un folder temporar, cu `docker`, `curl` și `flock` falși pe
`PATH` (scriu ce li s-a cerut) și un `cody-urcare.conf` fals. Niciun server, nicio rețea.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "urcare" / "cody-urcare.sh"
BASH = shutil.which("bash") or "/bin/bash"
SHA_NOU = "1" * 40
SHA_VECHI = "0" * 40
REPO_IMG = "ghcr.io/trip-development/codrut-platform"

DOCKER_FALS = r'''#!/usr/bin/env python3
import os, sys
fals = os.environ["FAKE_DIR"]
args = sys.argv[1:]
with open(os.path.join(fals, "docker.log"), "a") as f:
    f.write(" ".join(args) + "\n")

def citeste(nume, implicit=""):
    cale = os.path.join(fals, nume)
    return open(cale).read() if os.path.exists(cale) else implicit

def imagine(serviciu):
    env = {}
    for rand in open(os.path.join(os.environ["FAKE_APP"], ".env")):
        if "=" in rand:
            k, v = rand.rstrip("\n").split("=", 1)
            env[k] = v
    return env["FRONTEND_IMAGE"] if "frontend" in serviciu else env["BACKEND_IMAGE"]

if args[0] == "compose":
    i = 1
    while i < len(args) and args[i] in ("--env-file", "-f", "-p"):
        i += 2
    rest = args[i:]
    cmd = rest[0]
    if cmd == "ps":
        print("id-" + rest[-1])
    elif cmd == "config":
        sys.exit(1 if os.path.exists(os.path.join(fals, "config-pica")) else 0)
    elif cmd == "exec":
        interior = rest[3:]
        if interior[0] == "printenv":
            v = os.environ.get(interior[1])
            if v is None:
                sys.exit(1)
            print(v)
        elif interior[0] == "python":
            cod = interior[2]
            if "get_settings" in cod:
                print("prompt=v3.12\nprovider=vertex\nregiunea=eu\nactor=model-a\n"
                      "profesor=model-p\ngandire_profesor=1024\ngandire_actor=0\n"
                      "timp=120 15\nmotoare=vertex")
            else:
                print(citeste("sanatate", "200").strip())
        elif interior[0] == "sh":
            sql = sys.stdin.read()
            if "MARTOR" in sql:
                print(citeste("martori").strip())
            elif "ACTIVITATE" in sql:
                print(citeste("activitate").strip())
            else:
                print(citeste("migrare").strip())
    elif cmd == "run":
        if "alembic" in rest and os.path.exists(os.path.join(fals, "migrare-noua")):
            open(os.path.join(fals, "migrare"), "w").write(citeste("migrare-noua"))
elif args[0] == "inspect":
    tinta = args[-1]
    if "StartedAt" in " ".join(args):
        print("2026-11-21T10:00:00Z")
    else:
        print(imagine(tinta))
elif args[0] == "logs":
    sys.stdout.write(citeste("jurnal"))
'''

CURL_FALS = r'''#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_DIR/curl.log"
iesire=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then iesire="$2"; shift; fi
  shift
done
[[ -n "$iesire" ]] && printf 'services: {}\n' > "$iesire"
printf '200'
'''

FLOCK_FALS = "#!/usr/bin/env bash\nexit 0\n"

AJUTATOARE = {
    "capture_codrut_rollback.sh": textwrap.dedent("""\
        #!/usr/bin/env bash
        grep -E '^(BACKEND|FRONTEND)_IMAGE=' .env > "$1"
        cp .env "$2"
        """),
    "assert_codrut_release.sh": "#!/usr/bin/env bash\nexit 0\n",
    "check_vps_capacity.sh": "#!/usr/bin/env bash\nexit 0\n",
    "retain_codrut_images.sh": "#!/usr/bin/env bash\nexit 0\n",
}

ENV_INITIAL = textwrap.dedent(f"""\
    COMPOSE_PROJECT_NAME=cody-test
    BACKEND_IMAGE={REPO_IMG}-backend:test-{SHA_VECHI}
    FRONTEND_IMAGE={REPO_IMG}-frontend:test-{SHA_VECHI}
    CODRUT_RELEASE_SHA={SHA_VECHI}
    POSTGRES_PASSWORD=parola-falsa-de-test
    CODRUT_SESSION_SECRET=valoare-falsa-de-test
    CODRUT_PUBLIC_APP_URL=https://exemplu.test
    """)

MARTORI = textwrap.dedent("""\
    MARTOR|questionnaire_assignments|10|aaa
    MARTOR|competency_scores|5|bbb
    MARTOR|practice_sessions|3
    MARTOR|email_sends|7
    """)

LINISTE = textwrap.dedent("""\
    ACTIVITATE|trimiteri_15min|0
    ACTIVITATE|atingeri_15min|0
    ACTIVITATE_CODY|replici_15min|0
    ACTIVITATE_CODY|sesiuni_atinse_15min|0
    """)


class CodyUrcare(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.fals = self.tmp / "fals"
        self.app = self.tmp / "app"
        self.lib = self.tmp / "lib"
        self.stare = self.tmp / "stare"
        for d in (self.bin, self.fals, self.app, self.lib):
            d.mkdir()
        for nume, continut in (("docker", DOCKER_FALS), ("curl", CURL_FALS),
                               ("flock", FLOCK_FALS)):
            cale = self.bin / nume
            cale.write_text(continut, encoding="utf-8")
            cale.chmod(0o755)
        for nume, continut in AJUTATOARE.items():
            (self.lib / nume).write_text(continut, encoding="utf-8")
        (self.app / ".env").write_text(ENV_INITIAL, encoding="utf-8")
        (self.app / "compose.test.yaml").write_text("services: {}\n", encoding="utf-8")
        (self.fals / "migrare").write_text("0070_practice_consent\n", encoding="utf-8")
        (self.fals / "martori").write_text(MARTORI, encoding="utf-8")
        (self.fals / "activitate").write_text(LINISTE, encoding="utf-8")
        (self.fals / "jurnal").write_text(
            "ok\nTraceback (most recent call last)\nmotiv=timp\nmotiv=timp\n", encoding="utf-8")
        self.conf = self.tmp / "cody-urcare.conf"
        self.conf.write_text(textwrap.dedent(f"""\
            LOC=proba
            DIR={self.app}
            COMPOSE_FILES="compose.test.yaml"
            COMPOSE_SURSE="infra/test/compose.test.yaml"
            ENV_FILE=.env
            SERV_BACKEND=testbackend
            SERV_WORKER=testworker
            SERV_FRONTEND=testfrontend
            SERV_DB=testdb
            IMAGINE_REPO={REPO_IMG}
            ETICHETA=test-
            GITHUB_REPO=Trip-Development/codrut-platform
            STARE_DIR={self.stare}
            LOG_FILE={self.tmp}/cody-urcare.log
            LOCK_FILE={self.tmp}/cody-urcare.lock
            LIB_DIR={self.lib}
            """), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def ruleaza(self, comanda: str, intrare: str = "") -> subprocess.CompletedProcess:
        mediu = {
            "PATH": f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": str(self.tmp),
            "FAKE_DIR": str(self.fals),
            "FAKE_APP": str(self.app),
            "CODY_URCARE_CONF": str(self.conf),
            "SSH_ORIGINAL_COMMAND": comanda,
            # dinadins în mediul procesului: `setari` nu are voie să-l tipărească
            "CODRUT_SESSION_SECRET": "secret-din-mediu-fals",
            "CODRUT_VERTEX_REGION": "eu",
        }
        r = subprocess.run(  # noqa: S603 - argumente fixe, scriptul din depozit
            [BASH, str(SCRIPT)], input=intrare, capture_output=True, text=True, env=mediu,
            timeout=60, check=False,
        )
        for flux in (r.stdout, r.stderr):
            self.assertNotIn("@", flux, comanda)
            self.assertNotIn("POSTGRES_", flux, comanda)
            self.assertNotIn("SECRET", flux, comanda)
            self.assertNotIn("parola-falsa-de-test", flux, comanda)
            self.assertNotIn("valoare-falsa-de-test", flux, comanda)
        return r

    def comenzi_docker(self) -> list[str]:
        cale = self.fals / "docker.log"
        return cale.read_text(encoding="utf-8").splitlines() if cale.exists() else []

    def fara_db_dupa_up(self) -> None:
        for rand in self.comenzi_docker():
            cuvinte = rand.split()
            for verb in ("up", "restart", "stop", "start", "rm"):
                if verb in cuvinte:
                    dupa = cuvinte[cuvinte.index(verb):]
                    self.assertNotIn("testdb", dupa, rand)
                    self.assertNotIn("db", dupa, rand)

    # --- comenzi refuzate ---------------------------------------------------------------

    def test_sintaxa_scriptului(self) -> None:
        r = subprocess.run([BASH, "-n", str(SCRIPT)], capture_output=True, text=True,  # noqa: S603
                           check=False)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_comanda_straina_e_refuzata(self) -> None:
        for comanda in ("cat /etc/passwd", "stare; id", "id", "", "stare extra",
                        "pune abc 1", f"pune {SHA_NOU} x1", f"pune {SHA_NOU}",
                        "martori altceva 1", "intoarce", "jurnal 1 2"):
            r = self.ruleaza(comanda)
            self.assertEqual(r.returncode, 64, comanda)
            self.assertIn("comandă nepermisă", r.stdout + r.stderr)
        self.assertEqual(self.comenzi_docker(), [])

    # --- citiri ---------------------------------------------------------------------------

    def test_stare(self) -> None:
        r = self.ruleaza("stare")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("loc=proba", r.stdout)
        self.assertIn(f"backend={REPO_IMG}-backend:test-{SHA_VECHI}", r.stdout)
        self.assertIn("migrare=0070_practice_consent", r.stdout)
        self.assertIn("sanatate_interna=200", r.stdout)

    def test_setari_numai_numele_scrise_in_script(self) -> None:
        r = self.ruleaza("setari")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CODRUT_VERTEX_REGION=eu", r.stdout)
        self.assertIn("CODRUT_GENERATION_ENGINES=(nesetat)", r.stdout)
        self.assertIn("prompt=v3.12", r.stdout)
        self.assertIn("motoare=vertex", r.stdout)
        self.assertNotIn("secret-din-mediu-fals", r.stdout)
        cerute = [c for c in self.comenzi_docker() if "printenv" in c]
        self.assertEqual(len(cerute), 9)

    def test_fereastra(self) -> None:
        self.assertIn("fereastra=libera", self.ruleaza("fereastra").stdout)
        (self.fals / "activitate").write_text(LINISTE.replace("replici_15min|0",
                                                              "replici_15min|2"))
        r = self.ruleaza("fereastra")
        self.assertIn("fereastra=ocupata", r.stdout)
        self.assertNotIn("2", r.stdout.replace("fereastra=ocupata", ""))

    def test_martori_dupa_fara_inainte_e_refuzat(self) -> None:
        r = self.ruleaza("martori dupa 1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("martori_dupa_refuzat=lipsa_inainte", r.stdout)

    def test_martori_identici_si_scazuti(self) -> None:
        r = self.ruleaza("martori inainte 5")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("martori_inainte=scris", r.stdout)
        self.assertIn("martori=4", r.stdout)
        self.assertNotIn("aaa", r.stdout)
        r = self.ruleaza("martori dupa 5")
        self.assertIn("martori=buni", r.stdout)
        (self.fals / "martori").write_text(
            MARTORI.replace("competency_scores|5|bbb", "competency_scores|6|ccc")
                   .replace("practice_sessions|3", "practice_sessions|4"))
        r = self.ruleaza("martori dupa 5")
        self.assertIn("competency_scores=crescut", r.stdout)
        self.assertIn("practice_sessions=crescut", r.stdout)
        self.assertIn("martori=buni", r.stdout)
        (self.fals / "martori").write_text(MARTORI.replace("email_sends|7", "email_sends|6")
                                           .replace("|10|aaa", "|10|zzz"))
        r = self.ruleaza("martori dupa 5")
        self.assertEqual(r.returncode, 1)
        self.assertIn("email_sends=SCAZUT", r.stdout)
        self.assertIn("questionnaire_assignments=SCHIMBAT", r.stdout)
        self.assertIn("martori=RAI", r.stdout)
        self.assertNotIn("zzz", r.stdout)

    def test_jurnal_numai_numaratori(self) -> None:
        r = self.ruleaza("jurnal 5")
        self.assertIn("traceback=1", r.stdout)
        self.assertIn("campul_vechi=0", r.stdout)
        self.assertIn("fara_nota_timp=2", r.stdout)
        self.assertNotIn("most recent", r.stdout)

    # --- scrieri ----------------------------------------------------------------------------

    def test_pune_schimba_numai_cele_trei_randuri(self) -> None:
        r = self.ruleaza(f"pune {SHA_NOU} 9", intrare="token-fals-ghcr\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pus=da", r.stdout)
        self.assertIn("migrare_schimbata=nu", r.stdout)
        self.assertNotIn("token-fals-ghcr", r.stdout + r.stderr)
        dupa = (self.app / ".env").read_text().splitlines()
        inainte = ENV_INITIAL.splitlines()
        trei = ("BACKEND_IMAGE=", "FRONTEND_IMAGE=", "CODRUT_RELEASE_SHA=")
        self.assertEqual([x for x in dupa if not x.startswith(trei)],
                         [x for x in inainte if not x.startswith(trei)])
        self.assertIn(f"BACKEND_IMAGE={REPO_IMG}-backend:test-{SHA_NOU}", dupa)
        self.assertIn(f"FRONTEND_IMAGE={REPO_IMG}-frontend:test-{SHA_NOU}", dupa)
        self.assertIn(f"CODRUT_RELEASE_SHA={SHA_NOU}", dupa)
        self.assertFalse((self.app / ".env.next").exists())
        self.assertTrue((self.app / ".env.rollback").exists())
        self.assertTrue(any(" up " in f" {c} " for c in self.comenzi_docker()))
        self.fara_db_dupa_up()

    def test_pune_cu_configurare_stricata_nu_atinge_env(self) -> None:
        (self.fals / "config-pica").write_text("")
        r = self.ruleaza(f"pune {SHA_NOU} 9", intrare="token-fals-ghcr\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PICAT", r.stdout)
        self.assertEqual((self.app / ".env").read_text(), ENV_INITIAL)
        self.assertFalse(any(" up " in f" {c} " for c in self.comenzi_docker()))

    def test_pune_fara_token_e_refuzat(self) -> None:
        r = self.ruleaza(f"pune {SHA_NOU} 9", intrare="")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.app / ".env").read_text(), ENV_INITIAL)

    def test_intoarce_cu_migrare_schimbata_e_refuzat(self) -> None:
        (self.fals / "migrare-noua").write_text("0071_ceva_nou\n")
        r = self.ruleaza(f"pune {SHA_NOU} 7", intrare="token-fals-ghcr\n")
        self.assertIn("migrare_schimbata=da", r.stdout)
        inainte_de_intoarcere = len(self.comenzi_docker())
        r = self.ruleaza("intoarce 7")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("intoarcere_refuzata=migrare", r.stdout)
        dupa = self.comenzi_docker()[inainte_de_intoarcere:]
        self.assertFalse(any(" up " in f" {c} " for c in dupa), dupa)
        self.assertIn(f"test-{SHA_NOU}", (self.app / ".env").read_text())

    def test_intoarce_fara_stare_e_refuzat(self) -> None:
        r = self.ruleaza("intoarce 8")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("intoarcere_refuzata=lipsa_stare", r.stdout)
        self.assertEqual(self.comenzi_docker(), [])

    def test_intoarce_dupa_pune_fara_migrare(self) -> None:
        self.ruleaza(f"pune {SHA_NOU} 3", intrare="token-fals-ghcr\n")
        r = self.ruleaza("intoarce 3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("intors=da", r.stdout)
        self.assertIn(f"test-{SHA_VECHI}", (self.app / ".env").read_text())
        self.assertTrue((self.app / ".env.inainte-de-intoarcere-3").exists())
        self.fara_db_dupa_up()

    def test_retine(self) -> None:
        self.ruleaza(f"pune {SHA_NOU} 4", intrare="token-fals-ghcr\n")
        self.assertIn("retinere=ok", self.ruleaza("retine 4").stdout)


if __name__ == "__main__":
    unittest.main()
