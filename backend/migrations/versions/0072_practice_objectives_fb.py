"""practice_objectives: al doilea catalog de obiective, Feedback (10 obiective)

Plicul 235 (Cody 2.0, linia 1). Cele 10 obiective pentru trainingul de Feedback, aprobate de
Andrei (panoul, 20 nov 2026, [m03-feedback]; titlul 5 corectat la 15:50, [m03-titlu-5]). Numai
date: nicio schimbare de structura (cheia unica e pe catalog + order_index). Niciun proiect nu
se leaga aici de lista asta.

Datele sunt INGHETATE in migrare (ca la 0071 dupa plicul 235): niciun import din `codrut`,
niciun fisier citit. Textul e produs de `.audit/cody-plic235/ingheata.py` din
`obiective/feedback.json` (amprenta 00a8b45f…), nu scris de mana.

`downgrade` scoate intai legaturile proiectelor de lista `feedback`, apoi alegerile facute pe
ea (se pierd), apoi cele 10. Cele 12 de comunicare asertiva nu se ating.

Revision ID: 0072_practice_objectives_fb
Revises: 0071_practice_objectives
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0072_practice_objectives_fb"
down_revision = "0071_practice_objectives"
branch_labels = None
depends_on = None

CATALOG = 'feedback'
NUME = 'Feedback'
OBIECTIVE = ({'nr': 1,
  'titlu': 'Să dau feedback despre ce a făcut omul, nu despre cine e.',
  'situatie': 'colegul a venit nepregătit la ședința cu clientul; îți vine să-i spui „ești '
              'dezorganizat”.',
  'competente': ['Feedback constructiv', 'Gestionarea propriilor reacții emoționale'],
  'semn_de_reusita': 'vorbește despre faptă și efect („a face”), nu pune etichete („a fi”).'},
 {'nr': 2,
  'titlu': 'Să dau feedback după EEC.',
  'situatie': 'un om din echipă răspunde târziu la mailurile clienților.',
  'competente': ['Feedback constructiv', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'spune exemplul, efectul și ce așteaptă de acum încolo, apoi verifică '
                     'dacă omul a înțeles la fel.'},
 {'nr': 3,
  'titlu': 'Să aleg momentul și locul potrivit.',
  'situatie': 'îți vine să-i spui colegului pe hol, în fața altora, imediat după greșeală.',
  'competente': ['Gestionarea propriilor reacții emoționale', 'Feedback constructiv'],
  'semn_de_reusita': 'amână cât trebuie, cere o discuție în doi și verifică dacă celălalt e '
                     'dispus să asculte (condițiile feedbackului).'},
 {'nr': 4,
  'titlu': 'Să dau feedback pozitiv care chiar spune ceva.',
  'situatie': 'colega a salvat o prezentare la client; ești tentat să spui doar „bravo”.',
  'competente': ['Feedback constructiv'],
  'semn_de_reusita': 'spune exact ce a făcut bine și ce efect a avut, ca să poată repeta.'},
 {'nr': 5,
  'titlu': 'Să dau feedback cuiva care se apără.',
  'situatie': '„Nu e vina mea, ceilalți au întârziat datele.”',
  'competente': ['Ascultare activă', 'Reformulare activă', 'Gestionarea reacțiilor celorlalți'],
  'semn_de_reusita': 'reformulează ce a auzit, nu intră în ceartă despre vină și duce discuția '
                     'la ce poate schimba omul (responsabilitatea 50/50).'},
 {'nr': 6,
  'titlu': 'Să primesc o critică fără să mă apăr.',
  'situatie': 'șeful îți spune că raportul tău a fost confuz pentru client.',
  'competente': ['Gestionarea propriilor reacții emoționale', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'ascultă până la capăt, cere un exemplu concret și mulțumește, fără scuze '
                     'lungi.'},
 {'nr': 7,
  'titlu': 'Să separ ce s-a întâmplat de ce cred că se spune despre mine.',
  'situatie': 'un coleg spune „la ședință ai vorbit prea mult” și tu auzi „nu ești bun”.',
  'competente': ['Gestionarea propriilor reacții emoționale', 'Reformulare activă'],
  'semn_de_reusita': 'reformulează doar faptul spus, fără interpretarea lui (cei 3 EU, '
                     'percepție vs realitate).'},
 {'nr': 8,
  'titlu': 'Să cer feedback.',
  'situatie': 'după prima ta prezentare în fața conducerii, nu știi cum a ieșit.',
  'competente': ['Verificarea înțelegerii', 'Ascultare activă'],
  'semn_de_reusita': 'pune o întrebare precisă („ce aș schimba la partea cu cifrele?”), nu una '
                     'generală („cum a fost?”).'},
 {'nr': 9,
  'titlu': 'Să dau feedback șefului meu.',
  'situatie': 'șeful îți schimbă sarcinile fără să te anunțe, iar tu afli de la colegi.',
  'competente': ['Feedback constructiv', 'Exprimarea asertivă a nevoilor și limitelor'],
  'semn_de_reusita': 'vorbește de pe poziția de adult (Berne), cu fapte și efect, și propune '
                     'un mod de lucru.'},
 {'nr': 10,
  'titlu': 'Să dau feedback de dezvoltare unui om bun care s-a oprit din creștere.',
  'situatie': 'cel mai bun om din echipă face de doi ani același lucru și pare plictisit.',
  'competente': ['Ascultare activă', 'Feedback constructiv', 'Verificarea înțelegerii'],
  'semn_de_reusita': 'întreabă înainte să sfătuiască, pornește de la ce vrea omul și stabilesc '
                     'împreună un prim pas.'})


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


def upgrade() -> None:
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
    # intai legaturile proiectelor, apoi alegerile, apoi obiectivele
    op.execute(sa.text(
        "UPDATE practice_program_settings SET objective_catalog = NULL "
        "WHERE objective_catalog = 'feedback'"
    ))
    op.execute(sa.text(
        "DELETE FROM practice_objective_choices WHERE objective_id IN "
        "(SELECT id FROM practice_objectives WHERE catalog = 'feedback')"
    ))
    op.execute(sa.text("DELETE FROM practice_objectives WHERE catalog = 'feedback'"))
