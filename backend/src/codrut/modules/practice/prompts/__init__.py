from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from codrut.modules.practice.models import SessionKind

logger = logging.getLogger(__name__)

# v2.1 (plicul 37): la role-play perechea actor+evaluare a fost pusa la loc, blocul de
# quiz si memoria chiar ajung la model. Compozitia promptului s-a schimbat, deci
# sesiunile de dinainte si de dupa nu se mai pot compara sub aceeasi versiune.
CODY_PROMPT_VERSION = "v2.3"

_PROMPTS_DIR = Path(__file__).parent

REGULI_GENERALE_TEMPLATE = (_PROMPTS_DIR / "reguli-generale.md").read_text(encoding="utf-8").strip()
ACTOR_PROMPT = (_PROMPTS_DIR / "actor.md").read_text(encoding="utf-8").strip()
EVALUARE_PROMPT = (_PROMPTS_DIR / "evaluare.md").read_text(encoding="utf-8").strip()
COACHING_PROMPT = (_PROMPTS_DIR / "coaching.md").read_text(encoding="utf-8").strip()
QUIZ_PROMPT = (_PROMPTS_DIR / "quiz.md").read_text(encoding="utf-8").strip()
REZUMAT_TEMPLATE = (_PROMPTS_DIR / "rezumat.md").read_text(encoding="utf-8").strip()

CORE_SLOTS = [
    # Cine e Codrut. Astea patru au fost singurele pana la plicul 38.
    ("PROFIL-ANDREI", ["codrut-profil-v2.md", "codrut-profil-mod-de-lucru-v3-0.md"]),
    ("FILOZOFIE", ["codrut-filozofie-v2.md"]),
    ("TON-SI-COMPORTAMENT", ["ton-si-comportament.md"]),
    ("REGULI-COMPORTAMENT", ["reguli-comportament.md"]),
    # Ce preda Andrei. Statea in acelasi dosar si nu intra niciodata in prompt, deci
    # Codrut stia cine e, dar nu si cursul pe care il tine.
    #
    # Slotul vine ULTIMUL dinadins: prefixul constant ramane neschimbat, ca memoria de
    # context sa se prinda pe el.
    #
    # Deliberat NU intra restul teoriei (cum-primesti-feedback,
    # cum-imi-controlez-reactiile, cum-gestionam-teama-in-comunicare,
    # cum-transmit-informatia) si niciunul din cele 41 de fisiere reel-*.md: cu tot,
    # promptul ar sari de la 87 KB la 159 KB, adica de doua ori cat aplicatia veche.
    # 35 KB e proportia din vechi.
    ("TEORIA-TEMEI", [
        "codrut-comunicare-asertiva-v1-0.md",
        "feedback-theory-partea-1.md",
        "feedback-theory-part-2.md",
        "cum-spui-nu.md",
    ]),
]

_MATERIAL_CACHE: dict[str, tuple[str, int]] = {}


def resolve_biblioteca_dir(configured_path: str = "") -> Path | None:
    candidates: list[Path] = []
    if configured_path:
        candidates.append(Path(configured_path))
    env_p = os.environ.get("BIBLIOTECA_PATH")
    if env_p:
        candidates.append(Path(env_p))
    candidates.extend([
        Path("/opt/codrut-platform/BIBLIOTECA"),
        Path("/opt/cody-test/BIBLIOTECA"),
        Path("/app/BIBLIOTECA"),
        Path.cwd() / "BIBLIOTECA",
        Path.cwd().parent / "BIBLIOTECA",
    ])
    for parent in _PROMPTS_DIR.parents:
        candidates.append(parent / "BIBLIOTECA")

    for c in candidates:
        miez = c / "02-pachete" / "comunicare-asertiva-si-feedback" / "00-miez"
        if miez.exists() and miez.is_dir():
            return miez
    return None


def get_core_material(biblioteca_path: str = "") -> tuple[str, int]:
    cache_key = biblioteca_path or "default"
    if cache_key in _MATERIAL_CACHE:
        return _MATERIAL_CACHE[cache_key]

    miez_dir = resolve_biblioteca_dir(biblioteca_path)
    if not miez_dir:
        logger.warning("Folderul BIBLIOTECA 00-miez nu a fost gasit.")
        return "", 0

    sections: list[str] = []
    for label, fnames in CORE_SLOTS:
        parts: list[str] = []
        for fn in fnames:
            fp = miez_dir / fn
            if fp.exists():
                parts.append(fp.read_text(encoding="utf-8").strip())
            else:
                logger.warning(f"Fisierul {fn} lipseste din {miez_dir}")
        full_content = "\n\n".join(parts)
        if full_content:
            sections.append(f"\n\n--- {label} ---\n{full_content}")

    combined = "".join(sections)
    byte_count = len(combined.encode("utf-8"))
    _MATERIAL_CACHE[cache_key] = (combined, byte_count)
    return combined, byte_count


def build_quiz_block(
    quiz_competency: str = "mix",
    is_first: bool = True,
    project_competencies: list[str] | None = None,
) -> str:
    is_mix = quiz_competency == "mix"
    nr = 7 if is_mix else 5
    comps = ", ".join(project_competencies) if project_competencies else "toate competentele de comunicare"
    target = f"toate competențele: {comps}" if is_mix else f'competența "{quiz_competency}"'

    if is_first:
        return (
            f"\n\n---\nMOD QUIZ ACTIV — {('Mix complet' if is_mix else quiz_competency)}\n\n"
            f"REGULI ABSOLUTE:\n"
            f"1. NUMĂR FIX: Generezi EXACT {nr} întrebări numerotate 1-{nr}. La a {nr}-a întrebare, după răspuns, afișezi scorul și te oprești.\n"
            f'2. FORMAT: "Întrebarea N/{nr}: [întrebare]\\nA. ...\\nB. ...\\nC. ...\\nD. ..."\n'
            f"3. DISTRIBUȚIE VARIANTE CORECTE: Distribuie răspunsurile corecte între A, B, C, D. Max 2 la aceeași literă.\n"
            f'4. DUPĂ FIECARE RĂSPUNS: corect/greșit + 1 frază explicație. Apoi IMEDIAT "Întrebarea [N+1]/{nr}:".\n'
            f'5. PRIMUL TĂU MESAJ: scrie direct "Întrebarea 1/{nr}:" fără salut.\n'
            f'6. SCOR FINAL: "🏆 Scor final: X/{nr} (Y%)"\n'
            f"7. INTERZIS: coaching, întrebări deschise, ieșire din quiz.\n"
            f"Tema: {target}.\n---"
        )
    return (
        f"\n\n---\n⚠️ MOD QUIZ ACTIV\n"
        f"COMPETENȚĂ: {target}\n"
        f"NR TOTAL: {nr}\n"
        f'După răspuns: "✓/✗ + explicație" → "[🏆 Scor: X pct]" → "Întrebarea [N+1]/{nr}:"\n'
        f"INTERZIS: coaching, fraze de tranziție, ieșire din quiz.\n---"
    )


def format_participant_memory(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return ""
    blocks: list[str] = []
    for idx, m in enumerate(memories):
        date_str = m.get("created_at", "")
        if isinstance(date_str, str) and len(date_str) >= 10:
            date_str = date_str[:10]
        else:
            date_str = "?"
        relevance = m.get("relevance_score", 100)
        comps = m.get("relevant_competencies", [])
        comps_str = f", competente: {', '.join(comps)}" if comps else ""

        ctx = m.get("personal_context") or {}
        ctx_lines: list[str] = []
        if ctx.get("role"):
            ctx_lines.append(f"  Rol: {ctx['role']}")
        if ctx.get("team_size"):
            ctx_lines.append(f"  Echipa: {ctx['team_size']}")
        if ctx.get("current_situation"):
            ctx_lines.append(f"  Situatie curenta: {ctx['current_situation']}")

        evo = m.get("evolution_signals") or {}
        evo_lines: list[str] = []
        if evo.get("progress"):
            evo_lines.append(f"  Progres: {'; '.join(evo['progress'])}")
        if evo.get("blockers"):
            evo_lines.append(f"  Blocaje: {'; '.join(evo['blockers'])}")
        if evo.get("recurring_patterns"):
            evo_lines.append(f"  Patternuri: {'; '.join(evo['recurring_patterns'])}")

        quotes = m.get("key_quotes") or []
        if quotes:
            formatted_quotes = [f'"{q}"' for q in quotes]
            quotes_text = f"  Citate: {' | '.join(formatted_quotes)}"
        else:
            quotes_text = ""

        block = (
            f"Sesiune {idx + 1} ({date_str}, relevanta {relevance}/100{comps_str}):\n"
            f"  {m.get('summary', '')}"
        )
        if ctx_lines:
            block += "\n" + "\n".join(ctx_lines)
        if evo_lines:
            block += "\n" + "\n".join(evo_lines)
        if quotes_text:
            block += "\n" + quotes_text
        blocks.append(block)

    memory_text = "\n\n".join(blocks)
    return (
        f"\n\n--- CE STIE CODRUT DESPRE ACEST PARTICIPANT (din sesiunile anterioare) ---\n"
        f"{memory_text}\n\n"
        f"FOLOSESTE aceasta memorie natural in conversatie: recunoaste contextul, fa referinta "
        f"la ce s-a discutat anterior cand e relevant, dar nu o cita textual ca un robot. "
        f"Daca e prima sesiune (memorie goala), nu mentiona nimic.\n"
        f"--- SFARSIT MEMORIE ---"
    )


def get_system_prompt_for_kind(
    kind: SessionKind | str,
    name: str = "Participant",
    history_length: int = 0,
    quiz_competency: str | None = None,
    project_competencies: list[str] | None = None,
    memories: list[dict[str, Any]] | None = None,
    biblioteca_path: str = "",
) -> str:
    material, _ = get_core_material(biblioteca_path)

    kind_val = kind.value if isinstance(kind, SessionKind) else str(kind)
    e_roleplay = kind_val == "roleplay"

    # Dynamic rules for first message vs subsequent transitions
    if history_length <= 1:
        dyn_rules = (
            f'- REGULA PRIMULUI MESAJ: DOAR saluți pe {name} cald și îl întrebi '
            f'"Cum îți merge ziua până acum?". INTERZIS orice frază de tranziție la subiect.'
        )
    else:
        dyn_rules = '- REGULA ANTI-SALUT: INTERZIS să mai folosești "Salut", "Bună".'
        # Biblioteca de tranzitii e de coaching: intreaba omul ce vrea sa discute.
        #
        # La role-play nu are ce cauta — `actor.md` cere exact opusul: „nu ceri
        # permisiunea, nu intrebi ce situatie vrea. Treci DIRECT la SETUP", iar
        # `reguli-comportament.md` §6 interzice frazele de tranzitie acolo. Pana la
        # plicul 37 nu ajungeau in role-play, fiindca `reguli_generale` nu se trimitea
        # deloc; au venit odata cu evaluarea, si de atunci in acelasi prompt stateau
        # doua instructiuni opuse.
        #
        # La role-play tranzitia E chiar SETUP-ul. La coaching si la quiz, biblioteca
        # ramane neatinsa.
        if not e_roleplay:
            dyn_rules += (
                '\n- BIBLIOTECA DE TRANZIȚII (ROTAȚIE RANDOM): Folosește OBLIGATORIU o singură dată una din: '
                '"Ce ai zice să trecem la subiectul principal de azi?" / '
                '"Spre ce provocare vrei să ne îndreptăm atenția acum?" / '
                '"Ce este cel mai important pentru tine să explorăm în această sesiune?" / '
                '"Hai să vedem, ce situație concretă vrei să abordăm împreună astăzi?" / '
                '"Cu ce crezi că ar fi cel mai util să începem discuția noastră?"\n'
                '- SENZORUL ANTI-PAPAGAL: Verifică istoricul. Dacă ai mai folosit recent o frază de tranziție, alege obligatoriu alta.'
            )

    reguli_generale = REGULI_GENERALE_TEMPLATE.replace("{dynamic_rules}", dyn_rules)

    memory_block = ""
    if memories and history_length <= 2:
        memory_block = format_participant_memory(memories)

    if kind_val == "roleplay":
        # Actorul si evaluarea merg impreuna, ca in aplicatia veche si ca in plicul 22:
        # „peste el vine coach.md SAU PERECHEA actor.md + evaluare.md, dupa mod".
        #
        # Pana la plicul 37 exista aici un comutator, `is_actor_role`, care la role-play
        # era intotdeauna adevarat — deci ramura cu evaluarea nu se atingea niciodata in
        # folosire reala. Asa s-a pierdut feedbackul imediat de dupa fiecare replica,
        # impreuna cu regula care ii interzice lui Codrut sa dea participantului fraza
        # gata formulata, si cu lista de jargon interzis din reguli-generale.
        #
        # Grija ca actorul sa nu iasa din rol in mijlocul scenei e deja in textul
        # evaluarii („IESI COMPLET DIN ROL" dupa replica participantului), deci nu are
        # nevoie de un comutator in cod.
        return (
            f"{material}\n\n---\n\n{reguli_generale}\n\n---\n\n"
            f"{ACTOR_PROMPT}\n\n---\n\n{EVALUARE_PROMPT}{memory_block}"
        )

    elif kind_val == "knowledge":
        # Quiz mode
        quiz_block = ""
        if quiz_competency:
            quiz_block = build_quiz_block(
                quiz_competency=quiz_competency,
                is_first=(history_length <= 1),
                project_competencies=project_competencies,
            )
        return f"{material}\n\n---\n\n{reguli_generale}\n\n---\n\n{QUIZ_PROMPT}{quiz_block}{memory_block}"

    else:
        # Coaching (strategie) or default
        return f"{material}\n\n---\n\n{reguli_generale}\n\n---\n\n{COACHING_PROMPT}{memory_block}"


def get_summary_prompt(name: str, opt_text: str, history: str) -> str:
    return REZUMAT_TEMPLATE.format(name=name, opt_text=opt_text, history=history)


# Compatibilitate
CODY_SYSTEM_PROMPT = get_system_prompt_for_kind("roleplay")

