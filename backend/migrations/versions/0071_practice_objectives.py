"""practice_objectives: obiectivele de aplicare si alegerea omului

Plicul 230 (Cody 2.0, linia 1, L1-P1). Doua tabele si o coloana goala:
- practice_objectives: lista de obiective a unui training (`catalog`), intai cele 12 de
  comunicare asertiva, aprobate de Andrei (17-18 nov 2026);
- practice_objective_choices: ce obiectiv si-a ales fiecare om, pe proiect, cu istoric la
  schimbare (`replaced_at` gol = alegerea curenta);
- practice_program_settings.objective_catalog: ce lista foloseste proiectul (gol = niciuna;
  toate proiectele de azi raman exact cum sunt).

Cele 12 se incarca AICI, prin functia comuna din `codrut.modules.practice.obiective` (scrie cu
`sa.table`, nu cu modelele), ca la urcarea pe live sa nu ramana niciun pas de mana.

Revision ID: 0071_practice_objectives
Revises: 0070_practice_consent
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0071_practice_objectives"
down_revision = "0070_practice_consent"
branch_labels = None
depends_on = None

# Plicul 235 („230b"): cele 12 obiective, ÎNGHEȚATE aici. Migrarea nu mai importă nimic din
# `codrut` și nu mai citește niciun fișier, ca rezultatul ei să nu depindă de cum arată codul
# sau JSON-ul mai târziu. Textul de mai jos e produs de `.audit/cody-plic235/ingheata.py` din
# `obiective/comunicare-asertiva.json` (amprenta 073eb142…), nu scris de mână.
CATALOG = 'comunicare-asertiva'
NUME = 'Comunicare asertivă'
OBIECTIVE = ({'nr': 1,
  'titlu': 'Să spun „nu” unei sarcini în plus, fără să mă scuz.',
  'situatie': 'vineri, 17:00, șeful îți mai dă un raport „urgent”.',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor',
                 'Gestionarea propriilor reacții emoționale'],
  'semn_de_reusita': 'refuză sau negociază termenul clar, fără justificări lungi.'},
 {'nr': 2,
  'titlu': 'Să răspund calm la o critică vagă.',
  'situatie': '„Raportul tău e neglijent, mă întreb dacă ești potrivit.”',
  'competente': ['Ascultare activă', 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'cere exemple concrete și propune un plan, fără să se apere.'},
 {'nr': 3,
  'titlu': 'Să cer resursele de care am nevoie.',
  'situatie': 'șeful vrea rezultate în două săptămâni, fără oameni în plus.',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'propune un schimb concret (rezultate parțiale contra resurse).'},
 {'nr': 4,
  'titlu': 'Să cer o mărire sau o promovare.',
  'situatie': 'ai evaluarea anuală peste o săptămână și vrei să ceri o mărire de salariu.',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor',
                 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'vine cu fapte și cu o cerere clară, rămâne calm la primul „nu”.'},
 {'nr': 5,
  'titlu': 'Să îi dau feedback șefului.',
  'situatie': 'îți schimbă prioritățile de trei ori pe săptămână.',
  'competente': ['Feedback constructiv', 'Gestionarea propriilor reacții emoționale'],
  'semn_de_reusita': 'descrie ce s-a întâmplat (fapte), nu ce crede despre șef.'},
 {'nr': 6,
  'titlu': 'Să dau feedback unui coleg mai vechi care întârzie livrările.',
  'situatie': 'colegul cu 10 ani în firmă a predat a treia oară raportul lunar cu două zile '
              'întârziere, iar tu îl preiei pentru client.',
  'competente': ['Feedback constructiv', 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'spune faptele și efectul asupra lui, cere un termen concret și nu se '
                     'scuză pentru că e mai tânăr.'},
 {'nr': 7,
  'titlu': 'Să opresc un coleg care mă întrerupe în ședințe.',
  'situatie': 'în ședința de luni, un coleg îți taie vorba a doua oară și îți preia ideea.',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor',
                 'Gestionarea propriilor reacții emoționale'],
  'semn_de_reusita': 'își termină ideea calm și ferm („Lasă-mă să termin, te rog”), fără '
                     'ironie și fără să tacă.'},
 {'nr': 8,
  'titlu': 'Să refuz un coleg care îmi pasează munca lui.',
  'situatie': '„Tu te pricepi mai bine la Excel, fă-mi și mie tabelul până mâine.”',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'spune „nu” sau propune o variantă (îi arată cum se face), fără '
                     'justificări lungi și fără să-l acuze.'},
 {'nr': 9,
  'titlu': 'Să ies dintr-un conflict care se tot repetă.',
  'situatie': 'aceeași ceartă cu colegul de la alt departament, la fiecare predare de proiect.',
  'competente': ['Ascultare activă', 'Reformulare activă', 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'separă ce s-a întâmplat de ce a interpretat, reformulează nevoia '
                     'celuilalt și propune o regulă comună.'},
 {'nr': 10,
  'titlu': 'Să țin o limită cu un client care cere ceva în afara contractului.',
  'situatie': 'clientul cere „doar o mică modificare” care înseamnă trei zile de muncă, fără '
              'cost în plus.',
  'competente': ['Exprimarea asertivă a nevoilor și limitelor',
                 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'recunoaște nevoia clientului, spune clar ce intră în contract și oferă o '
                     'variantă (ofertă separată sau alt termen).'},
 {'nr': 11,
  'titlu': 'Să răspund la o întrebare la care nu știu răspunsul, în fața clientului.',
  'situatie': 'la prezentare, directorul clientului întreabă de o cifră pe care n-o ai.',
  'competente': ['Gestionarea propriilor reacții emoționale', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'spune deschis că nu știe acum, verifică ce anume vrea omul să afle și '
                     'promite răspunsul cu un termen.'},
 {'nr': 12,
  'titlu': 'Să dau feedback corectiv unui om din echipă care a greșit de mai multe ori.',
  'situatie': 'același om a trimis a treia oară oferta cu prețuri greșite.',
  'competente': ['Feedback constructiv',
                 'Ascultare activă',
                 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'descrie faptele și efectul, ascultă explicația fără să o accepte ca '
                     'scuză și stabilesc împreună un pas concret.'})


def _tabelul_obiectivelor() -> sa.TableClause:
    return sa.table(
        "practice_objectives",
        sa.column("id", sa.Uuid()),
        sa.column("catalog", sa.String()),
        sa.column("catalog_name", sa.String()),
        sa.column("order_index", sa.Integer()),
        sa.column("title", sa.Text()),
        sa.column("situation", sa.Text()),
        sa.column("success_sign", sa.Text()),
        sa.column("competencies", postgresql.JSONB()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


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
    op.add_column(
        "practice_program_settings",
        sa.Column("objective_catalog", sa.String(length=100), nullable=True),
    )
    op.create_table(
        "practice_objectives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog", sa.String(length=100), nullable=False),
        sa.Column("catalog_name", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("success_sign", sa.Text(), nullable=False),
        sa.Column("competencies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog", "order_index", name="uq_practice_objectives_catalog_order"
        ),
    )
    op.create_index("ix_practice_objectives_catalog", "practice_objectives", ["catalog"])
    op.create_table(
        "practice_objective_choices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Uuid(), nullable=False),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"], ["participant_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["practice_objectives.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_practice_objective_choices_participant_profile_id", "practice_objective_choices",
        ["participant_profile_id"],
    )
    op.create_index(
        "ix_practice_objective_choices_project_id", "practice_objective_choices", ["project_id"]
    )
    op.create_index(
        "ix_practice_objective_choices_objective_id", "practice_objective_choices",
        ["objective_id"],
    )
    # o singura alegere curenta pe om si proiect
    op.create_index(
        "uq_practice_objective_choices_current", "practice_objective_choices",
        ["participant_profile_id", "project_id"], unique=True,
        postgresql_where=sa.text("replaced_at IS NULL"),
    )
    acum = datetime.now(UTC)
    op.bulk_insert(
        _tabelul_obiectivelor(),
        [
            {
                "id": uuid.uuid4(), "catalog": CATALOG, "catalog_name": NUME,
                "order_index": o["nr"], "title": o["titlu"], "situation": o["situatie"],
                "success_sign": o["semn_de_reusita"], "competencies": list(o["competente"]),
                "is_active": True, "created_at": acum, "updated_at": acum,
            }
            for o in OBIECTIVE
        ],
    )


def downgrade() -> None:
    # intai alegerile, apoi obiectivele, apoi coloana
    op.drop_index(
        "uq_practice_objective_choices_current", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_objective_id", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_project_id", table_name="practice_objective_choices"
    )
    op.drop_index(
        "ix_practice_objective_choices_participant_profile_id",
        table_name="practice_objective_choices",
    )
    op.drop_table("practice_objective_choices")
    op.drop_index("ix_practice_objectives_catalog", table_name="practice_objectives")
    op.drop_table("practice_objectives")
    op.drop_column("practice_program_settings", "objective_catalog")
