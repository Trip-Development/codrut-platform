"""practice_daily_situations + practice_daily_replies: „O replică pe zi” (L2-P1)

Plicul 236 (Cody 2.0, linia 2). Două tabele noi și cele 36 de situații ale catalogului
`comunicare-asertiva` (3 pe fiecare dintre cele 12 obiective):
- ordinea 1 = situația obiectivului din L1 (aceeași cu `practice_objectives.situation`);
- ordinile 2 și 3 = situațiile aprobate de Andrei (panoul, 20 nov 2026 14:53,
  [replica-pe-zi-situatii]), copiate literă cu literă.

Datele sunt INGHETATE in migrare (ca la 0071/0072): niciun import din `codrut`, niciun fisier
citit. Constanta e produsa de `.audit/cody-plic236/ingheata_situatii.py` din
`obiective/situatii-comunicare-asertiva.json` (amprenta aaca6c5d…fb325), nu scrisa de mana.

- practice_daily_situations: situatiile, legate de obiectiv (RESTRICT), unice pe
  (obiectiv, ordine);
- practice_daily_replies: replica zilei a omului, raspunsul profesorului si nota citita de cod;
  una singura pe om, proiect si zi (ziua in ora Romaniei), aparata si de baza.

`downgrade` scoate intai replicile, apoi situatiile. Obiectivele (12 + 10) nu se ating.

Revision ID: 0073_practice_daily_replies
Revises: 0072_practice_objectives_fb
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0073_practice_daily_replies"
down_revision = "0072_practice_objectives_fb"
branch_labels = None
depends_on = None

CATALOG = 'comunicare-asertiva'
SITUATII = ({'obiectiv_nr': 1,
  'ordine': 1,
  'text': 'vineri, 17:00, șeful îți mai dă un raport „urgent”.'},
 {'obiectiv_nr': 1,
  'ordine': 2,
  'text': 'Luni dimineață, șeful îți cere să preiei și ședința săptămânală a altui '
          'departament, „doar o lună”.'},
 {'obiectiv_nr': 1,
  'ordine': 3,
  'text': 'Ai deja trei termene vineri. Șeful îți scrie pe chat: „Mai bagi și '
          'prezentarea pentru board, da?”'},
 {'obiectiv_nr': 2,
  'ordine': 1,
  'text': '„Raportul tău e neglijent, mă întreb dacă ești potrivit.”'},
 {'obiectiv_nr': 2,
  'ordine': 2,
  'text': 'După ședință, șeful îți spune: „Nu te-am simțit implicat în proiect în '
          'ultima vreme.”'},
 {'obiectiv_nr': 2,
  'ordine': 3,
  'text': 'În evaluare scrie: „Comunicarea trebuie îmbunătățită.” Nimic altceva.'},
 {'obiectiv_nr': 3,
  'ordine': 1,
  'text': 'șeful vrea rezultate în două săptămâni, fără oameni în plus.'},
 {'obiectiv_nr': 3,
  'ordine': 2,
  'text': 'Proiectul s-a dublat, dar bugetul a rămas același. Ai cinci minute cu '
          'șeful înainte de comitet.'},
 {'obiectiv_nr': 3,
  'ordine': 3,
  'text': 'Colegul care te ajuta pleacă în concediu trei săptămâni, chiar în '
          'perioada de lansare.'},
 {'obiectiv_nr': 4,
  'ordine': 1,
  'text': 'ai evaluarea anuală peste o săptămână și vrei să ceri o mărire de '
          'salariu.'},
 {'obiectiv_nr': 4,
  'ordine': 2,
  'text': 'Ai preluat de jumătate de an atribuțiile unui coleg care a plecat, fără '
          'nicio schimbare de salariu.'},
 {'obiectiv_nr': 4,
  'ordine': 3,
  'text': 'Șeful îți spune: „Promovarea anul ăsta nu se poate, poate la anul.”'},
 {'obiectiv_nr': 5,
  'ordine': 1,
  'text': 'îți schimbă prioritățile de trei ori pe săptămână.'},
 {'obiectiv_nr': 5,
  'ordine': 2,
  'text': 'Șeful îți corectează e-mailurile către client după ce le-ai trimis deja, '
          'cu clientul în copie.'},
 {'obiectiv_nr': 5,
  'ordine': 3,
  'text': 'În ședințe, șeful răspunde el la întrebările adresate ție.'},
 {'obiectiv_nr': 6,
  'ordine': 1,
  'text': 'colegul cu 10 ani în firmă a predat a treia oară raportul lunar cu două '
          'zile întârziere, iar tu îl preiei pentru client.'},
 {'obiectiv_nr': 6,
  'ordine': 2,
  'text': 'Colegul cu experiență îți spune: „Lasă, că știu eu cum se face, îl trimit '
          'mâine.” E a doua oară luna asta.'},
 {'obiectiv_nr': 6,
  'ordine': 3,
  'text': 'Datele de la el vin incomplete și tu trebuie să le refaci noaptea.'},
 {'obiectiv_nr': 7,
  'ordine': 1,
  'text': 'în ședința de luni, un coleg îți taie vorba a doua oară și îți preia '
          'ideea.'},
 {'obiectiv_nr': 7,
  'ordine': 2,
  'text': 'Prezinți rezultatele trimestrului și colegul intervine: „Pe scurt, ce '
          'vrea să zică e…”'},
 {'obiectiv_nr': 7,
  'ordine': 3,
  'text': 'În call, colegul începe să vorbească peste tine chiar când ajungi la '
          'propunerea ta.'},
 {'obiectiv_nr': 8,
  'ordine': 1,
  'text': '„Tu te pricepi mai bine la Excel, fă-mi și mie tabelul până mâine.”'},
 {'obiectiv_nr': 8,
  'ordine': 2,
  'text': '„Tu ai mai făcut raportul ăsta, nu-l faci și pe al meu? Durează zece '
          'minute.”'},
 {'obiectiv_nr': 8,
  'ordine': 3,
  'text': 'Colegul îți trimite un e-mail cu șeful în copie: „X se ocupă de asta, că '
          'are mai multă experiență.” Nu v-ați înțeles așa.'},
 {'obiectiv_nr': 9,
  'ordine': 1,
  'text': 'aceeași ceartă cu colegul de la alt departament, la fiecare predare de '
          'proiect.'},
 {'obiectiv_nr': 9,
  'ordine': 2,
  'text': 'Iar ședință de predare, iar aceeași replică: „Voi nu ne dați niciodată '
          'informațiile la timp.”'},
 {'obiectiv_nr': 9,
  'ordine': 3,
  'text': 'Colegul de la alt departament îți scrie: „Din nou ne-ați încurcat '
          'planificarea.”'},
 {'obiectiv_nr': 10,
  'ordine': 1,
  'text': 'clientul cere „doar o mică modificare” care înseamnă trei zile de muncă, '
          'fără cost în plus.'},
 {'obiectiv_nr': 10,
  'ordine': 2,
  'text': 'Clientul te sună sâmbătă seara pentru o modificare „urgentă” care nu e '
          'urgentă.'},
 {'obiectiv_nr': 10,
  'ordine': 3,
  'text': 'Clientul cere încă o rundă de revizii, a patra, deși contractul prevede '
          'două.'},
 {'obiectiv_nr': 11,
  'ordine': 1,
  'text': 'la prezentare, directorul clientului întreabă de o cifră pe care n-o ai.'},
 {'obiectiv_nr': 11,
  'ordine': 2,
  'text': 'Clientul te întreabă în ședință cât costă o funcție pe care n-ați '
          'discutat-o niciodată.'},
 {'obiectiv_nr': 11,
  'ordine': 3,
  'text': 'Un specialist de la client îți pune o întrebare tehnică foarte detaliată, '
          'de față cu toată echipa lui.'},
 {'obiectiv_nr': 12,
  'ordine': 1,
  'text': 'același om a trimis a treia oară oferta cu prețuri greșite.'},
 {'obiectiv_nr': 12,
  'ordine': 2,
  'text': 'Același om din echipă a întârziat a patra oară la ședința cu clientul.'},
 {'obiectiv_nr': 12,
  'ordine': 3,
  'text': 'Omul îți spune: „Toată lumea greșește prețurile, nu doar eu.”'})


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "practice_daily_situations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["practice_objectives.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "objective_id", "order_index", name="uq_practice_daily_situations_objective_order"
        ),
    )
    op.create_index(
        "ix_practice_daily_situations_objective_id", "practice_daily_situations",
        ["objective_id"],
    )
    op.create_table(
        "practice_daily_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("situation_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("teacher_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"], ["participant_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["situation_id"], ["practice_daily_situations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        # o singura replica pe zi, pe om si proiect
        sa.UniqueConstraint(
            "participant_profile_id", "project_id", "day",
            name="uq_practice_daily_replies_profile_project_day",
        ),
    )
    op.create_index(
        "ix_practice_daily_replies_participant_profile_id", "practice_daily_replies",
        ["participant_profile_id"],
    )
    op.create_index(
        "ix_practice_daily_replies_project_id", "practice_daily_replies", ["project_id"]
    )
    op.create_index(
        "ix_practice_daily_replies_situation_id", "practice_daily_replies", ["situation_id"]
    )
    for s in SITUATII:
        op.execute(
            sa.text(
                "INSERT INTO practice_daily_situations "
                "(id, objective_id, order_index, text, is_active, created_at, updated_at) "
                "SELECT :id, o.id, :ordine, :text, true, now(), now() "
                "FROM practice_objectives o "
                "WHERE o.catalog = :catalog AND o.order_index = :nr"
            ).bindparams(
                id=uuid.uuid4(), ordine=s["ordine"], text=s["text"], catalog=CATALOG,
                nr=s["obiectiv_nr"],
            )
        )
    op.execute(sa.text(
        "DO $$ BEGIN IF (SELECT count(*) FROM practice_daily_situations) <> 36 THEN "
        "RAISE EXCEPTION 'situatiile zilei: trebuiau 36'; END IF; END $$"
    ))


def downgrade() -> None:
    # intai replicile, apoi situatiile
    op.drop_index("ix_practice_daily_replies_situation_id", table_name="practice_daily_replies")
    op.drop_index("ix_practice_daily_replies_project_id", table_name="practice_daily_replies")
    op.drop_index(
        "ix_practice_daily_replies_participant_profile_id", table_name="practice_daily_replies"
    )
    op.drop_table("practice_daily_replies")
    op.drop_index(
        "ix_practice_daily_situations_objective_id", table_name="practice_daily_situations"
    )
    op.drop_table("practice_daily_situations")
