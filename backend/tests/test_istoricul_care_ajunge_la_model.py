"""Lacatul plicului 64: ce istoric ajunge de fapt la model.

Replica omului se salveaza in baza INAINTE de a chema modelul si ramane salvata cand
modelul refuza. Omul vede eroarea, mai apasa o data, se salveaza inca un rand identic.
In sesiunea auditorului, pe 7 septembrie, au ajuns SASE randuri identice unul dupa altul,
fara niciun raspuns intre ele — iar generarile urmatoare primeau conversatia asta stricata.

Testele de aici ruleaza bucla ADEVARATA din `add_participant_turn`, decupata din codul viu,
ca sa nu se verifice o copie care poate ramane in urma.
"""

import inspect
import textwrap
from dataclasses import dataclass

from codrut.contracts.generation import GenerationMessage
from codrut.modules.practice.models import TurnRole
from codrut.modules.practice.service import PracticeSessionService


@dataclass
class ReplicaDeProba:
    """Cat ii trebuie buclei dintr-o replica: rolul si textul."""

    role: TurnRole
    text: str


def _mesajele_trimise_la_model(existing_turns, text: str) -> list[GenerationMessage]:
    """Ruleaza bucla din `add_participant_turn`, luata din codul viu."""
    linii = inspect.getsource(PracticeSessionService.add_participant_turn).splitlines()
    start = next(
        i for i, linie in enumerate(linii) if "messages: list[GenerationMessage] = []" in linie
    )
    sfarsit = next(
        i
        for i, linie in enumerate(linii)
        if i > start and 'messages.append(GenerationMessage(role="user", text=text))' in linie
    )
    bloc = textwrap.dedent("\n".join(linii[start : sfarsit + 1]))

    mediu: dict = {
        "GenerationMessage": GenerationMessage,
        "TurnRole": TurnRole,
        "existing_turns": existing_turns,
        "text": text,
    }
    exec(bloc, mediu)  # noqa: S102 — dinadins: verificam codul viu, nu o copie
    return mediu["messages"]


def test_replicile_lipite_ale_omului_ajung_una_singura():
    """Trei replici lipite plus cea de acum: la model pleaca UNA, si aia e cea de acum."""
    istoric = [
        ReplicaDeProba(TurnRole.actor, "Salut. Esti gata sa incepem?"),
        ReplicaDeProba(TurnRole.participant, "prima incercare"),
        ReplicaDeProba(TurnRole.participant, "a doua incercare"),
        ReplicaDeProba(TurnRole.participant, "a treia incercare"),
    ]

    mesaje = _mesajele_trimise_la_model(istoric, "replica de acum")

    assert [m.role for m in mesaje] == ["model", "user"]
    assert [m.text for m in mesaje] == [
        "Salut. Esti gata sa incepem?",
        "replica de acum",
    ]
    for urma in ("prima incercare", "a doua incercare", "a treia incercare"):
        assert urma not in [m.text for m in mesaje]


def test_un_istoric_normal_ramane_neatins():
    """Om, actor, om, actor: nu se pierde nimic si nu se schimba ordinea."""
    istoric = [
        ReplicaDeProba(TurnRole.actor, "Salut."),
        ReplicaDeProba(TurnRole.participant, "Buna."),
        ReplicaDeProba(TurnRole.actor, "Ce s-a intamplat vineri?"),
        ReplicaDeProba(TurnRole.participant, "Raportul a intarziat."),
        ReplicaDeProba(TurnRole.actor, "Si tu ce ai facut?"),
    ]

    mesaje = _mesajele_trimise_la_model(istoric, "Am vorbit cu el luni dimineata.")

    assert [m.role for m in mesaje] == ["model", "user", "model", "user", "model", "user"]
    assert [m.text for m in mesaje] == [
        "Salut.",
        "Buna.",
        "Ce s-a intamplat vineri?",
        "Raportul a intarziat.",
        "Si tu ce ai facut?",
        "Am vorbit cu el luni dimineata.",
    ]


def test_doua_replici_ale_actorului_nu_se_string_intre_ele():
    """Strangerea e numai pentru urmele omului. Ce a spus actorul ramane cum a fost."""
    istoric = [
        ReplicaDeProba(TurnRole.actor, "Prima parte."),
        ReplicaDeProba(TurnRole.actor, "A doua parte."),
    ]

    mesaje = _mesajele_trimise_la_model(istoric, "am inteles")

    assert [m.text for m in mesaje] == ["Prima parte.", "A doua parte.", "am inteles"]


def test_cazul_auditorului_sase_randuri_identice():
    """Sase orfani identici plus retrimiterea: modelul vede replica O SINGURA DATA."""
    intrebarea = "te rog sa imi zici cum stam"
    istoric = [ReplicaDeProba(TurnRole.actor, "Spune-mi ce s-a intamplat.")]
    istoric += [ReplicaDeProba(TurnRole.participant, intrebarea) for _ in range(6)]

    mesaje = _mesajele_trimise_la_model(istoric, intrebarea)

    assert len(mesaje) == 2
    assert [m.role for m in mesaje] == ["model", "user"]
    assert mesaje[-1].text == intrebarea
