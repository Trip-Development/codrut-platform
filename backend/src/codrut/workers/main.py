import asyncio
import logging

import httpx
from arq import cron
from arq.connections import RedisSettings

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.service import (
    CommunicationsService,
    EmailOutboxClaim,
    EmailOutboxProcessor,
    email_outbox_batch_with_outcomes,
)
from codrut.modules.forms import models as forms_models  # noqa: F401
from codrut.modules.forms.processing import (
    claim_due_submission_processing,
    process_claimed_submission,
    record_submission_processing_failure,
)
from codrut.modules.health.service import publish_worker_heartbeat
from codrut.modules.identity import models as identity_models  # noqa: F401

logger = logging.getLogger(__name__)


async def health_check(ctx: dict) -> str:
    logger.debug("Worker health check context keys: %s", sorted(ctx.keys()))
    return "ok"


async def record_worker_heartbeat(ctx: dict) -> None:
    await publish_worker_heartbeat(ctx["redis"])


async def process_email_outbox(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        provider = build_email_provider(settings, client=client)
        async with SessionLocal() as session:
            claims, housekeeping = await EmailOutboxProcessor(
                session,
                provider,
                settings,
            ).claim_due(limit=settings.email_outbox_batch_size)

        semaphore = asyncio.Semaphore(settings.email_outbox_concurrency)

        async def process_claim(claim: EmailOutboxClaim) -> str:
            async with semaphore:
                try:
                    async with SessionLocal() as claim_session:
                        return await EmailOutboxProcessor(
                            claim_session,
                            provider,
                            settings,
                        ).process_claim(claim)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Email outbox claim failed outside the provider boundary.",
                        extra={
                            "email_event": "claim_processing_failed",
                            "email_send_id": str(claim.send_id),
                            "error_type": type(exc).__name__,
                        },
                    )
                    return "indeterminate"

        outcomes = await asyncio.gather(*(process_claim(claim) for claim in claims))
        result = email_outbox_batch_with_outcomes(housekeeping, list(outcomes))
    if result.claimed or result.failed:
        logger.info(
            "Email outbox batch claimed=%d accepted=%d retried=%d failed=%d "
            "cancelled=%d indeterminate=%d",
            result.claimed,
            result.accepted,
            result.retried,
            result.failed,
            result.cancelled,
            result.indeterminate,
        )
    return {
        "claimed": result.claimed,
        "accepted": result.accepted,
        "retried": result.retried,
        "failed": result.failed,
        "cancelled": result.cancelled,
        "indeterminate": result.indeterminate,
    }


async def process_questionnaire_submissions(_ctx: dict) -> dict[str, int]:
    async with SessionLocal() as session:
        claims = await claim_due_submission_processing(session)
        await session.commit()

    completed = 0
    retried = 0
    failed = 0
    for claim in claims:
        try:
            async with SessionLocal() as session:
                processed = await process_claimed_submission(session, claim)
                await session.commit()
                completed += int(processed)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Questionnaire submission processing failed.",
                extra={
                    "submission_event": "processing_failed",
                    "job_id": str(claim.job_id),
                    "error_type": type(exc).__name__,
                },
            )
            async with SessionLocal() as failure_session:
                outcome = await record_submission_processing_failure(
                    failure_session,
                    claim,
                    exc,
                )
                await failure_session.commit()
            retried += outcome == "retried"
            failed += outcome == "failed"

    if claims:
        logger.info(
            "Questionnaire submissions claimed=%d completed=%d retried=%d failed=%d",
            len(claims),
            completed,
            retried,
            failed,
        )
    return {
        "claimed": len(claims),
        "completed": completed,
        "retried": retried,
        "failed": failed,
    }


async def purge_archived_campaign_recipients(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    totals = {"examined": 0, "purged": 0, "deferred": 0}
    while True:
        async with SessionLocal() as session:
            result = await CommunicationsService(session).purge_due_campaign_recipients(
                settings=settings,
                limit=100,
            )
            await session.commit()
        totals["examined"] += result.examined
        totals["purged"] += result.purged
        totals["deferred"] += result.deferred
        if result.examined < 100:
            break
    if totals["examined"]:
        logger.info(
            "Campaign contact purge examined=%d purged=%d deferred=%d",
            totals["examined"],
            totals["purged"],
            totals["deferred"],
        )
    return totals


async def review_email_suppressions(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    totals = {"examined": 0, "retained": 0, "needs_review": 0, "deleted": 0}
    while True:
        async with SessionLocal() as session:
            result = await CommunicationsService(session).review_due_email_suppressions(
                settings=settings,
                limit=100,
            )
            await session.commit()
        totals["examined"] += result.examined
        totals["retained"] += result.retained
        totals["needs_review"] += result.needs_review
        totals["deleted"] += result.deleted
        if result.examined < 100:
            break
    if totals["examined"]:
        logger.info(
            "Email suppression review examined=%d retained=%d needs_review=%d deleted=%d",
            totals["examined"],
            totals["retained"],
            totals["needs_review"],
            totals["deleted"],
        )
    return totals


class WorkerSettings:
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.worker_max_jobs
    functions = [health_check]
    cron_jobs = [
        cron(
            record_worker_heartbeat,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=False,
        ),
        cron(
            process_email_outbox,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=True,
        ),
        cron(
            process_questionnaire_submissions,
            second=set(range(0, 60, 2)),
            run_at_startup=True,
            unique=False,
        ),
        cron(
            purge_archived_campaign_recipients,
            hour=2,
            minute=15,
            run_at_startup=False,
            unique=True,
        ),
        cron(
            review_email_suppressions,
            hour=2,
            minute=45,
            run_at_startup=False,
            unique=True,
        ),
    ]


async def main() -> None:
    from arq.worker import create_worker

    worker = create_worker(WorkerSettings)
    try:
        await worker.async_run()
    except asyncio.CancelledError:
        logger.info("Worker shutdown requested")


if __name__ == "__main__":
    asyncio.run(main())
