import asyncio
import json
import sys
from datetime import datetime, timezone
from sqlalchemy import select

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import CompanyProject, ParticipantProfile
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.service import PracticeSessionService


async def main():
    settings = get_settings()
    async with SessionLocal() as db:
        service = PracticeSessionService(session=db, settings=settings)
        proj = (await db.execute(select(CompanyProject).limit(1))).scalar_one_or_none()
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()

        if not proj or not user:
            print("No project or user found, querying stare summary directly", flush=True)
            summary = await service.get_stare_summary()
            summary_dict = summary.model_dump() if hasattr(summary, "model_dump") else summary
            with open("/tmp/05-stare-dupa.json", "w") as f:
                json.dump(summary_dict, f, indent=2, default=str)
            return

        principal = SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=UserRole.participant,
            session_token="dev_session_token_live_test",
            consent_current=True,
            terms_accepted_at=datetime.now(timezone.utc),
            terms_version=CURRENT_TERMS_VERSION,
        )
        print(
            f"Pornire sesiune live pentru proiectul {proj.name} cu participantul {principal.email}...",
            flush=True,
        )

        sess = await service.start_session(
            principal=principal,
            project_id=proj.id,
            kind=SessionKind.roleplay,
        )
        await db.commit()
        print(f"Sesiune creată: {sess.id}", flush=True)

        # Turn 1
        print("Trimitere replica 1...", flush=True)
        p1, a1, st = await service.submit_turn(
            principal=principal,
            session_id=sess.id,
            text="Salut, vreau să exersez o conversație dificilă cu un coleg.",
        )
        await db.commit()
        print(f"Replica 1 gata. Cached tokens: {getattr(a1, 'cached_tokens', 0)}", flush=True)

        # Turn 2
        print("Trimitere replica 2...", flush=True)
        p2, a2, st = await service.submit_turn(
            principal=principal,
            session_id=sess.id,
            text="Colegul meu întârzie frecvent cu livrabilele și afectează echipa.",
        )
        await db.commit()
        print(f"Replica 2 gata. Cached tokens: {getattr(a2, 'cached_tokens', 0)}", flush=True)

        # Turn 3
        print("Trimitere replica 3...", flush=True)
        p3, a3, st = await service.submit_turn(
            principal=principal,
            session_id=sess.id,
            text="Vreau să îi spun direct dar fără să creez tensiuni inutile.",
        )
        await db.commit()
        print(f"Replica 3 gata. Cached tokens: {getattr(a3, 'cached_tokens', 0)}", flush=True)

        # Verificare /stare
        summary = await service.get_stare_summary()
        summary_dict = summary.model_dump() if hasattr(summary, "model_dump") else summary
        with open("/tmp/05-stare-dupa.json", "w") as f:
            json.dump(summary_dict, f, indent=2, default=str)
        print(f"Stare după: {summary_dict}", flush=True)

        # Tablou dashboard
        dash_service = PracticeDashboardService(session=db)
        dash_data = await dash_service.get_participant_dashboard_data(
            principal=principal, project_id=proj.id
        )
        dash_dict = dash_data.model_dump() if hasattr(dash_data, "model_dump") else dash_data
        with open("/tmp/08-tablou-raw.json", "w") as f:
            json.dump(dash_dict, f, indent=2, default=str)
        print(
            f"Tablou extras cu {len(dash_dict.get('competencies', []))} competențe.",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
