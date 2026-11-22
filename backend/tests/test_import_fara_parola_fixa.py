"""Plicul 254: unealta de import din arhiva veche nu mai pune o parola fixa.

Contul nou facut de unealta primeste marcajul „fara parola” al aplicatiei
(`SHADOW_ACCOUNT_PASSWORD_HASH`). Omul isi pune parola singur: prin invitatie sau prin
„Am uitat parola”. Parola fixa de dinainte nu se scrie nicaieri: testul tine numai
amprenta ei (sha256), citita o data din istoria depozitului.

La cadere, testele spun numai cai de fisiere sau numere de rand, niciodata textul gasit.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.security import verify_password
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    PasswordResetToken,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.identity.schemas import PasswordResetRequest
from codrut.modules.identity.service import IdentityService
from codrut.tools import import_supabase_archive as unealta

# sha256 al parolei fixe de dinainte (plicul 254, K1). Parola insasi nu apare nicaieri.
AMPRENTA_TEXTULUI_VECHI = "2a9d8a2524fb0ddd764c1ad697085b1090255839565b32d654b0cee59e4d3e42"

RADACINA_DEPOZITULUI = Path(__file__).resolve().parents[2]
CALEA_UNELTEI = Path(unealta.__file__).resolve()
MARIME_MAXIMA = 2 * 1024 * 1024

_BUCATI = re.compile(r"[^\s\"'`<>()\[\]{},;=]{4,128}")
_INTRE_GHILIMELE = (re.compile(r'"([^"\n]{4,128})"'), re.compile(r"'([^'\n]{4,128})'"))


def _amprenta(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _textele_fisierului(cale: Path) -> list[str]:
    try:
        if cale.stat().st_size > MARIME_MAXIMA:
            return []
        brut = cale.read_bytes()
    except OSError:
        return []
    if b"\0" in brut:
        return []
    try:
        continut = brut.decode("utf-8")
    except UnicodeDecodeError:
        return []
    texte: list[str] = []
    if cale.suffix == ".py":
        try:
            arbore = ast.parse(continut)
        except (SyntaxError, ValueError):
            arbore = None
        if arbore is not None:
            texte.extend(
                nod.value
                for nod in ast.walk(arbore)
                if isinstance(nod, ast.Constant) and isinstance(nod.value, str)
            )
    texte.extend(_BUCATI.findall(continut))
    for tipar in _INTRE_GHILIMELE:
        texte.extend(tipar.findall(continut))
    return texte


def cai_care_contin_amprenta(radacina: Path, fisiere: list[Path], amprenta: str) -> list[str]:
    """Caile (relative) ale fisierelor in care un text are amprenta data. Niciodata textul."""
    cai: list[str] = []
    for cale in fisiere:
        if any(_amprenta(text) == amprenta for text in _textele_fisierului(cale)):
            cai.append(str(cale.relative_to(radacina)))
    return cai


def _fisierele_urmarite() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git nu e disponibil aici; testul se ruleaza pe copia intreaga (regula 9)")
    rezultat = subprocess.run(  # noqa: S603
        [git, "-C", str(RADACINA_DEPOZITULUI), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if rezultat.returncode != 0:
        pytest.skip("dosarul nu e un depozit git; testul se ruleaza pe copia intreaga (regula 9)")
    nume = [n for n in rezultat.stdout.decode("utf-8").split("\0") if n]
    return [RADACINA_DEPOZITULUI / n for n in nume if (RADACINA_DEPOZITULUI / n).is_file()]


def test_textul_vechi_lipseste_din_depozit() -> None:
    fisiere = _fisierele_urmarite()
    assert len(fisiere) > 100
    cai = cai_care_contin_amprenta(RADACINA_DEPOZITULUI, fisiere, AMPRENTA_TEXTULUI_VECHI)
    assert not cai, f"parola fixa de dinainte apare in: {cai}"


def test_detectorul_prinde_un_text_plantat(tmp_path: Path) -> None:
    plantat = secrets.token_urlsafe(12)
    amprenta = _amprenta(plantat)
    cu = tmp_path / "cu"
    cu.mkdir()
    (cu / "modul.py").write_text(f'VALOARE = "{plantat}"\n', encoding="utf-8")
    (cu / "note.md").write_text(f"Parola: {plantat}\n", encoding="utf-8")
    fara = tmp_path / "fara"
    fara.mkdir()
    (fara / "modul.py").write_text('VALOARE = "altceva-deloc"\n', encoding="utf-8")
    (fara / "note.md").write_text("Nimic de gasit aici.\n", encoding="utf-8")

    gasite = cai_care_contin_amprenta(tmp_path, sorted(cu.iterdir()), amprenta)
    assert sorted(gasite) == ["cu/modul.py", "cu/note.md"]
    assert cai_care_contin_amprenta(tmp_path, sorted(fara.iterdir()), amprenta) == []


def test_unealta_nu_are_parola_scrisa() -> None:
    arbore = ast.parse(CALEA_UNELTEI.read_text(encoding="utf-8"))
    apeluri: list[int] = []
    hashuri_scrise: list[int] = []
    for nod in ast.walk(arbore):
        if isinstance(nod, ast.Call):
            functia = nod.func
            nume = (
                functia.id
                if isinstance(functia, ast.Name)
                else functia.attr
                if isinstance(functia, ast.Attribute)
                else None
            )
            if nume == "hash_password":
                apeluri.append(nod.lineno)
        if (
            isinstance(nod, ast.Constant)
            and isinstance(nod.value, str)
            and "pbkdf2_sha256$" in nod.value
        ):
            hashuri_scrise.append(nod.lineno)
    assert not apeluri, f"hash_password e chemat in unealta la randurile: {apeluri}"
    assert not hashuri_scrise, f"hash scris in unealta la randurile: {hashuri_scrise}"


def _arhiva_inventata(dosar: Path, sufix: str, domeniu: str = "example.invalid") -> dict[str, str]:
    adrese = {
        "admin": f"admin-{sufix}@{domeniu}",
        "nou": f"nou-{sufix}@{domeniu}",
        "exista": f"exista-{sufix}@{domeniu}",
    }
    personale = {
        "users": [
            {
                "id": str(uuid.uuid4()),
                "email": adrese["admin"],
                "role": "admin",
                "profile_data": {"username": "Trainer Inventat"},
            },
            {
                "id": str(uuid.uuid4()),
                "email": adrese["nou"],
                "role": "user",
                "profile_data": {"username": "Participant Inventat"},
            },
            {
                "id": str(uuid.uuid4()),
                "email": adrese["exista"],
                "role": "user",
                "profile_data": {"username": "Participant Care Exista"},
            },
        ]
    }
    (dosar / "04-DATE-PERSONALE.json").write_text(json.dumps(personale), encoding="utf-8")
    (dosar / "05-scoruri-si-teste.json").write_text(
        json.dumps({"competency_scores": []}), encoding="utf-8"
    )
    return adrese


def _inlocuieste_arhiva_si_sesiunile(monkeypatch: pytest.MonkeyPatch, dosar: Path) -> None:
    monkeypatch.setattr(unealta, "find_archive_dir", lambda: dosar)
    monkeypatch.setattr(unealta, "SessionLocal", SessionLocal)


async def test_conturile_importate_sunt_fara_parola(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sufix = uuid.uuid4().hex[:10]
    adrese = _arhiva_inventata(tmp_path, sufix)
    hash_vechi = "parola-lui-pusa-de-el-hash"
    async with SessionLocal() as session:
        session.add(
            User(
                email=adrese["exista"],
                password_hash=hash_vechi,
                role=UserRole.participant,
                account_type=UserAccountType.registered,
            )
        )
        await session.commit()

    _inlocuieste_arhiva_si_sesiunile(monkeypatch, tmp_path)
    assert unealta.find_archive_dir() == tmp_path
    stats = await unealta.import_supabase_archive()

    assert stats["users"] == 2
    async with SessionLocal() as session:
        conturi = {
            u.email: u
            for u in (
                await session.execute(select(User).where(User.email.in_(list(adrese.values()))))
            ).scalars()
        }
    assert set(conturi) == set(adrese.values())
    for cheie in ("admin", "nou"):
        cont = conturi[adrese[cheie]]
        fara_parola = cont.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH
        assert fara_parola, f"contul «{cheie}» nu e «fara parola»"
        assert cont.account_type == UserAccountType.registered
        for _ in range(3):
            assert verify_password(secrets.token_urlsafe(12), cont.password_hash) is False
    assert conturi[adrese["admin"]].role == UserRole.trainer
    assert conturi[adrese["nou"]].role == UserRole.participant
    assert conturi[adrese["exista"]].role == UserRole.participant
    neschimbat = conturi[adrese["exista"]].password_hash == hash_vechi
    assert neschimbat, "contul care exista si-a schimbat hash-ul"


class _FurnizorDeEmailFals:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send(self, message):  # pragma: no cover - outbox-ul nu trimite in test
        self.messages.append(message)
        raise AssertionError("niciun email nu se trimite in test")


async def test_contul_importat_poate_cere_parola_noua(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sufix = uuid.uuid4().hex[:10]
    # „Am uitat parola” valideaza adresa si refuza domeniile .invalid.
    adrese = _arhiva_inventata(tmp_path, sufix, domeniu="example.com")
    _inlocuieste_arhiva_si_sesiunile(monkeypatch, tmp_path)
    furnizor = _FurnizorDeEmailFals()
    monkeypatch.setattr(
        "codrut.modules.identity.service.build_email_provider",
        lambda _settings: furnizor,
    )
    await unealta.import_supabase_archive()

    async with SessionLocal() as session:
        cont = (await session.execute(select(User).where(User.email == adrese["nou"]))).scalar_one()
        fara_parola = cont.password_hash == SHADOW_ACCOUNT_PASSWORD_HASH
        assert fara_parola, "contul importat nu e «fara parola»"
        assert cont.is_registered is True

        await IdentityService(session).request_password_reset(
            PasswordResetRequest(email=adrese["nou"]),
            request_id=f"plic254-{sufix}",
        )
        jetoane = list(
            (
                await session.execute(
                    select(PasswordResetToken).where(PasswordResetToken.user_id == cont.id)
                )
            ).scalars()
        )
        assert len(jetoane) == 1
        assert jetoane[0].used_at is None
        await session.rollback()
    assert furnizor.messages == []
