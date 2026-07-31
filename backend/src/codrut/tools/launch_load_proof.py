from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import stat
import time
import uuid
from array import array
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url

from codrut.core.config import Settings, get_settings
from codrut.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from codrut.core.database import Base, SessionLocal
from codrut.core.maintenance import MAINTENANCE_BYPASS_HEADER
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import (
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    ConsentAcceptance,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.identity.session_cookie import SESSION_COOKIE_NAME
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.scoring.models import ResultPublication, ScoringResult

FORMAT_VERSION = "codrut-launch-load-proof/v1"
PARTICIPANT_COUNT = 1_000
HOLD_SECONDS = 300
ACKNOWLEDGEMENT = "I_UNDERSTAND_CODEX_SYNTHETIC_LOAD_PROOF_V1"
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{7,47}$")
TAG_PREFIX = "codrut-load-proof:v1:"
READ_P95_LIMIT_MS = 750.0
AUTOSAVE_P95_LIMIT_MS = 1_000.0
SUBMIT_P95_LIMIT_MS = 1_500.0


@dataclass(frozen=True)
class ParticipantManifest:
    index: int
    user_id: str
    profile_id: str
    assignment_id: str
    invite_id: str
    email_send_id: str
    email: str
    token: str
    answers: dict[str, int]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ParticipantManifest:
        return cls(
            index=int(value["index"]),
            user_id=str(value["user_id"]),
            profile_id=str(value["profile_id"]),
            assignment_id=str(value["assignment_id"]),
            invite_id=str(value["invite_id"]),
            email_send_id=str(value["email_send_id"]),
            email=str(value["email"]),
            token=str(value["token"]),
            answers={str(key): int(answer) for key, answer in value["answers"].items()},
        )


@dataclass(frozen=True)
class LoadProofManifest:
    format_version: str
    run_id: str
    tag: str
    created_at: str
    environment: str
    database_name: str
    owner_user_id: str
    owner_email: str
    owner_password: str
    company_id: str
    company_name: str
    project_id: str
    project_name: str
    definition_id: str
    definition_key: str
    participants: tuple[ParticipantManifest, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> LoadProofManifest:
        return cls(
            format_version=str(value["format_version"]),
            run_id=str(value["run_id"]),
            tag=str(value["tag"]),
            created_at=str(value["created_at"]),
            environment=str(value["environment"]),
            database_name=str(value["database_name"]),
            owner_user_id=str(value["owner_user_id"]),
            owner_email=str(value["owner_email"]),
            owner_password=str(value["owner_password"]),
            company_id=str(value["company_id"]),
            company_name=str(value["company_name"]),
            project_id=str(value["project_id"]),
            project_name=str(value["project_name"]),
            definition_id=str(value["definition_id"]),
            definition_key=str(value["definition_key"]),
            participants=tuple(
                ParticipantManifest.from_dict(item) for item in value["participants"]
            ),
        )


@dataclass
class OperationMetrics:
    durations_ms: array[float] = field(default_factory=lambda: array("d"))
    errors: int = 0
    rate_limited: int = 0


class MetricsRecorder:
    def __init__(self) -> None:
        self.operations: dict[str, OperationMetrics] = {}

    def record(self, operation: str, duration_ms: float, status_code: int | None) -> None:
        metrics = self.operations.setdefault(operation, OperationMetrics())
        metrics.durations_ms.append(duration_ms)
        if status_code is None or status_code >= 400:
            metrics.errors += 1
        if status_code == 429:
            metrics.rate_limited += 1

    def report(self) -> dict[str, Any]:
        operation_reports = {
            name: _metric_report(metrics) for name, metrics in sorted(self.operations.items())
        }
        all_durations = array("d")
        errors = 0
        rate_limited = 0
        for metrics in self.operations.values():
            all_durations.extend(metrics.durations_ms)
            errors += metrics.errors
            rate_limited += metrics.rate_limited
        aggregate = _metric_report(
            OperationMetrics(
                durations_ms=all_durations,
                errors=errors,
                rate_limited=rate_limited,
            )
        )
        return {"aggregate": aggregate, "operations": operation_reports}


@dataclass(frozen=True)
class ResourceSample:
    cpu_percent: float | None
    free_memory_bytes: int
    disk_percent: float


@dataclass
class ResourceExtrema:
    samples: int = 0
    max_cpu_percent: float | None = None
    min_free_memory_bytes: int | None = None
    max_disk_percent: float = 0.0

    def record(self, sample: ResourceSample) -> None:
        self.samples += 1
        if sample.cpu_percent is not None:
            self.max_cpu_percent = (
                sample.cpu_percent
                if self.max_cpu_percent is None
                else max(self.max_cpu_percent, sample.cpu_percent)
            )
        if sample.free_memory_bytes > 0:
            self.min_free_memory_bytes = (
                sample.free_memory_bytes
                if self.min_free_memory_bytes is None
                else min(self.min_free_memory_bytes, sample.free_memory_bytes)
            )
        self.max_disk_percent = max(self.max_disk_percent, sample.disk_percent)

    def report(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "max_cpu_percent": (
                round(self.max_cpu_percent, 3) if self.max_cpu_percent is not None else None
            ),
            "min_free_memory_bytes": self.min_free_memory_bytes,
            "max_disk_percent": round(self.max_disk_percent, 3),
        }


def _resource_evidence_failure(
    extrema: ResourceExtrema,
    *,
    production: bool,
) -> str | None:
    if not production:
        return None
    if (
        extrema.samples < 2
        or extrema.max_cpu_percent is None
        or extrema.min_free_memory_bytes is None
    ):
        return "host CPU and memory evidence was not sampled completely"
    return None


@dataclass(frozen=True)
class RuntimeEvidence:
    captured_at_epoch: int
    backend_id: str
    backend_restart_count: int
    backend_oom_killed: bool
    backend_started_at: str
    backend_pool_timeout_count: int
    worker_id: str
    worker_restart_count: int
    worker_oom_killed: bool
    worker_started_at: str
    worker_pool_timeout_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalResourceSampler:
    def __init__(self) -> None:
        self._last_cpu: tuple[int, int] | None = None

    def sample(self) -> ResourceSample:
        memory = _linux_available_memory()
        disk = shutil.disk_usage("/")
        disk_percent = 100.0 * (disk.total - disk.free) / disk.total
        current_cpu = _linux_cpu_totals()
        cpu_percent: float | None = None
        if current_cpu is not None and self._last_cpu is not None:
            total_delta = current_cpu[0] - self._last_cpu[0]
            idle_delta = current_cpu[1] - self._last_cpu[1]
            if total_delta > 0:
                cpu_percent = 100.0 * (1.0 - idle_delta / total_delta)
        self._last_cpu = current_cpu
        return ResourceSample(
            cpu_percent=cpu_percent,
            free_memory_bytes=memory,
            disk_percent=disk_percent,
        )


class AbortController:
    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.reason: str | None = None

    def abort(self, reason: str) -> None:
        if not self.event.is_set():
            self.reason = reason
            self.event.set()


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RuntimeError(
            "Run ID must be 8-48 lowercase letters, numbers, or hyphens, starting "
            "with a letter or number."
        )
    return run_id


def synthetic_tag(run_id: str) -> str:
    return f"{TAG_PREFIX}{validate_run_id(run_id)}"


def require_guard(
    settings: Settings,
    *,
    run_id: str,
    acknowledgement: str | None,
    operation: str,
) -> None:
    validate_run_id(run_id)
    if acknowledgement != ACKNOWLEDGEMENT:
        raise RuntimeError(
            f"{operation} requires --ack {ACKNOWLEDGEMENT}. This is intentionally explicit."
        )
    if not settings.is_production:
        return
    if not settings.maintenance_mode:
        raise RuntimeError(f"Production {operation} requires maintenance_mode=true.")
    if not settings.email_brevo_sandbox_enabled:
        raise RuntimeError(f"Production {operation} requires Brevo sandbox mode.")
    if settings.email_provider != "brevo":
        raise RuntimeError(f"Production {operation} requires the Brevo provider.")
    bypass = (
        settings.maintenance_bypass_token.get_secret_value().strip()
        if settings.maintenance_bypass_token
        else ""
    )
    if len(bypass) < 32:
        raise RuntimeError(f"Production {operation} requires the maintenance bypass token.")


def validate_manifest(manifest: LoadProofManifest, *, expected_run_id: str | None = None) -> None:
    if manifest.format_version != FORMAT_VERSION:
        raise RuntimeError(f"Unsupported manifest format: {manifest.format_version!r}.")
    validate_run_id(manifest.run_id)
    if expected_run_id is not None and manifest.run_id != expected_run_id:
        raise RuntimeError("The explicit run ID does not match the manifest.")
    if manifest.tag != synthetic_tag(manifest.run_id):
        raise RuntimeError("Manifest tag does not match its run ID.")
    if manifest.company_name != f"[{manifest.tag}] Synthetic Tenant":
        raise RuntimeError("Manifest company name is not the exact synthetic tenant name.")
    if manifest.project_name != f"[{manifest.tag}] Participant Load Proof":
        raise RuntimeError("Manifest project name is not the exact synthetic project name.")
    if manifest.definition_key != _definition_key(manifest.run_id):
        raise RuntimeError("Manifest questionnaire key does not match its run ID.")
    created_at = datetime.fromisoformat(manifest.created_at)
    if created_at.tzinfo is None:
        raise RuntimeError("Manifest creation time must be timezone-aware.")
    if len(manifest.participants) != PARTICIPANT_COUNT:
        raise RuntimeError(f"Manifest must contain exactly {PARTICIPANT_COUNT} participants.")

    identifiers: dict[str, set[str]] = {
        "user": set(),
        "profile": set(),
        "assignment": set(),
        "invite": set(),
        "email_send": set(),
    }
    expected_indexes = set(range(1, PARTICIPANT_COUNT + 1))
    actual_indexes: set[int] = set()
    for participant in manifest.participants:
        actual_indexes.add(participant.index)
        expected_email = _participant_email(manifest.run_id, participant.index)
        if participant.email != expected_email:
            raise RuntimeError("Manifest participant email does not match the exact run scope.")
        if participant.answers != {"q1": 4}:
            raise RuntimeError("Manifest answers do not match the versioned proof definition.")
        for kind, raw_identifier in (
            ("user", participant.user_id),
            ("profile", participant.profile_id),
            ("assignment", participant.assignment_id),
            ("invite", participant.invite_id),
            ("email_send", participant.email_send_id),
        ):
            UUID(raw_identifier)
            if raw_identifier in identifiers[kind]:
                raise RuntimeError(f"Duplicate {kind} ID in manifest.")
            identifiers[kind].add(raw_identifier)
    if actual_indexes != expected_indexes:
        raise RuntimeError("Manifest participant indexes must be exactly 1 through 1000.")
    UUID(manifest.company_id)
    UUID(manifest.project_id)
    UUID(manifest.definition_id)
    UUID(manifest.owner_user_id)
    if manifest.owner_email != _owner_email(manifest.run_id):
        raise RuntimeError("Manifest owner email does not match the exact run scope.")
    if len(manifest.owner_password) < 32:
        raise RuntimeError("Manifest synthetic owner password is not a strong random secret.")


def validate_manifest_runtime(manifest: LoadProofManifest, settings: Settings) -> None:
    current_database = make_url(settings.database_url).database or ""
    if manifest.environment != settings.env:
        raise RuntimeError(
            "Manifest environment differs from the current runtime; refusing the operation."
        )
    if manifest.database_name != current_database:
        raise RuntimeError(
            "Manifest database differs from the current runtime; refusing the operation."
        )


def load_manifest(path: Path) -> LoadProofManifest:
    manifest = LoadProofManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    validate_manifest(manifest)
    return manifest


async def seed_synthetic_tenant(
    *,
    settings: Settings,
    run_id: str,
    acknowledgement: str | None,
    manifest_path: Path,
) -> LoadProofManifest:
    require_guard(
        settings,
        run_id=run_id,
        acknowledgement=acknowledgement,
        operation="seeding",
    )
    _require_outbox_capacity(settings)
    if manifest_path.exists():
        raise RuntimeError("Refusing to overwrite an existing load-proof manifest.")

    tag = synthetic_tag(run_id)
    now = datetime.now(UTC)
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    definition_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    owner_email = _owner_email(run_id)
    owner_password = secrets.token_urlsafe(48)
    company_name = f"[{tag}] Synthetic Tenant"
    project_name = f"[{tag}] Participant Load Proof"
    definition_key = _definition_key(run_id)
    participants: list[ParticipantManifest] = []

    async with SessionLocal() as session:
        await _require_no_unrelated_outbox_activity(
            session,
            exact_send_ids=set(),
            since=now,
        )
        existing = await session.scalar(select(Company.id).where(Company.name == company_name))
        existing_definition = await session.scalar(
            select(QuestionnaireDefinition.id).where(
                QuestionnaireDefinition.key == definition_key,
                QuestionnaireDefinition.version == 1,
            )
        )
        if existing is not None or existing_definition is not None:
            raise RuntimeError("This exact synthetic run already exists; refusing to merge data.")

        company = Company(id=company_id, name=company_name)
        project = CompanyProject(
            id=project_id,
            company_id=company_id,
            name=project_name,
            description=f"Exact synthetic launch proof {tag}.",
            project_type=tag,
            status=CompanyProjectStatus.active,
            starts_at=now - timedelta(hours=1),
            due_at=now + timedelta(days=2),
            form_opens_at=now - timedelta(hours=1),
            form_closes_at=now + timedelta(days=2),
        )
        definition = QuestionnaireDefinition(
            id=definition_id,
            key=definition_key,
            version=1,
            title="Synthetic load proof",
            description=f"Versioned synthetic definition for {tag}.",
            schema=_questionnaire_schema(),
            private_config={},
            feedback_policy={
                "participant_results": {
                    "publication": "scores_and_interpretation",
                    "target_types": ["self"],
                    "dimension_ids": ["load"],
                    "include_primary_result": True,
                }
            },
            trainer_visibility_policy={},
            package_id=tag,
            system_managed=False,
            active=True,
        )
        owner = User(
            id=owner_user_id,
            email=owner_email,
            password_hash=hash_password(owner_password),
            role=UserRole.trainer,
            account_type=UserAccountType.registered,
            terms_accepted_at=now,
            terms_version=CURRENT_TERMS_VERSION,
        )
        session.add_all(
            [
                company,
                project,
                definition,
                owner,
                CompanyMembership(
                    company_id=company_id,
                    user_id=owner_user_id,
                    role=CompanyMembershipRole.owner,
                ),
            ]
        )
        # The assignment-definition integrity trigger resolves the pinned
        # definition during assignment INSERT. Make the synthetic parent scope
        # visible before the bulk assignment flush.
        await session.flush()

        assignment_round_id = uuid.uuid4()
        expires_at = now + timedelta(days=2)
        outbox_release_after = now + timedelta(days=1)
        participant_users: list[User] = []
        participant_profiles: list[ParticipantProfile] = []
        project_memberships: list[ProjectMembership] = []
        assignments: list[QuestionnaireAssignment] = []
        invites: list[AssignmentInvite] = []
        email_sends: list[EmailSend] = []
        email_events: list[EmailEvent] = []
        consent_acceptances: list[ConsentAcceptance] = []
        for index in range(1, PARTICIPANT_COUNT + 1):
            user_id = uuid.uuid4()
            profile_id = uuid.uuid4()
            assignment_id = uuid.uuid4()
            invite_id = uuid.uuid4()
            email_send_id = uuid.uuid4()
            email = _participant_email(run_id, index)
            user = User(
                id=user_id,
                email=email,
                password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                role=UserRole.participant,
                account_type=UserAccountType.guest,
                terms_accepted_at=now,
                terms_version=CURRENT_TERMS_VERSION,
            )
            profile = ParticipantProfile(
                id=profile_id,
                company_id=company_id,
                user_id=user_id,
                full_name=f"Synthetic Load Participant {index:04d}",
                email=email,
                position="Synthetic participant",
                role_group=tag,
                anonymous_name=f"Load-{run_id}-{index:04d}"[:80],
            )
            assignment = QuestionnaireAssignment(
                id=assignment_id,
                company_id=company_id,
                project_id=project_id,
                assignment_round_id=assignment_round_id,
                respondent_profile_id=profile_id,
                questionnaire_key=definition_key,
                questionnaire_definition_id=definition_id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.invited,
                due_at=expires_at,
                invited_at=now,
            )
            claims = TaskLinkClaims(
                company_id=company_id,
                respondent_profile_id=profile_id,
                assignment_ids=(assignment_id,),
                project_id=project_id,
                expires_at=expires_at,
            )
            token = create_task_token(claims, settings)
            invite = AssignmentInvite(
                id=invite_id,
                company_id=company_id,
                project_id=project_id,
                respondent_profile_id=profile_id,
                token=token,
                status="active",
                expires_at=expires_at,
            )
            message_payload = _invitation_message_payload(
                settings=settings,
                email=email,
                action_url=f"{settings.public_app_url.rstrip('/')}/invite/{token}",
                assignment_id=assignment_id,
                run_id=run_id,
            )
            payload_fingerprint = _payload_fingerprint(message_payload)
            email_send = EmailSend(
                id=email_send_id,
                owner_id=owner_user_id,
                assignment_id=assignment_id,
                recipient_email=email,
                template_key="assignment_bundle",
                template_version=1,
                provider=settings.email_provider,
                idempotency_key=hashlib.sha256(
                    f"{tag}:invitation:{index}".encode()
                ).hexdigest(),
                payload_fingerprint=payload_fingerprint,
                message_payload=message_payload,
                sandbox_required=True,
                attempt_count=0,
                max_attempts=5,
                next_attempt_at=outbox_release_after,
                status=EmailSendStatus.queued,
                last_event_at=now,
            )
            participant_users.append(user)
            participant_profiles.append(profile)
            project_memberships.append(
                ProjectMembership(
                    company_id=company_id,
                    project_id=project_id,
                    participant_profile_id=profile_id,
                    position=profile.position,
                    role_group=tag,
                )
            )
            assignments.append(assignment)
            invites.append(invite)
            email_sends.append(email_send)
            email_events.append(
                EmailEvent(
                    email_send_id=email_send_id,
                    event_type=EmailEventType.queued,
                    occurred_at=now,
                )
            )
            consent_acceptances.append(
                ConsentAcceptance(
                    user_id=user_id,
                    respondent_profile_id=profile_id,
                    terms_version=CURRENT_TERMS_VERSION,
                    source="authenticated",
                    accepted_at=now,
                )
            )
            participants.append(
                ParticipantManifest(
                    index=index,
                    user_id=str(user_id),
                    profile_id=str(profile_id),
                    assignment_id=str(assignment_id),
                    invite_id=str(invite_id),
                    email_send_id=str(email_send_id),
                    email=email,
                    token=token,
                    answers={"q1": 4},
                )
            )

        # These models deliberately avoid broad ORM relationships. Flush the
        # synthetic graph in foreign-key order while retaining bulk inserts.
        for objects in (
            participant_users,
            participant_profiles,
            [*project_memberships, *consent_acceptances],
            assignments,
            [*invites, *email_sends],
            email_events,
        ):
            session.add_all(objects)
            await session.flush()

        manifest = LoadProofManifest(
            format_version=FORMAT_VERSION,
            run_id=run_id,
            tag=tag,
            created_at=now.isoformat(),
            environment=settings.env,
            database_name=make_url(settings.database_url).database or "",
            owner_user_id=str(owner_user_id),
            owner_email=owner_email,
            owner_password=owner_password,
            company_id=str(company_id),
            company_name=company_name,
            project_id=str(project_id),
            project_name=project_name,
            definition_id=str(definition_id),
            definition_key=definition_key,
            participants=tuple(participants),
        )
        validate_manifest(manifest, expected_run_id=run_id)
        _write_private_json(manifest_path, asdict(manifest), refuse_overwrite=True)
        try:
            await session.commit()
        except Exception:
            manifest_path.unlink(missing_ok=True)
            raise
    return manifest


async def _cancel_exact_unstarted_outbox(
    manifest: LoadProofManifest,
    *,
    wait_for_in_flight_seconds: float = 30.0,
) -> dict[str, int]:
    send_ids = {UUID(item.email_send_id) for item in manifest.participants}
    expected_by_send_id = {
        UUID(item.email_send_id): item for item in manifest.participants
    }
    owner_user_id = UUID(manifest.owner_user_id)
    deadline = time.monotonic() + wait_for_in_flight_seconds
    cancelled = 0
    while True:
        async with SessionLocal() as session:
            sends = (
                await session.execute(
                    select(EmailSend)
                    .where(EmailSend.id.in_(send_ids))
                    .with_for_update()
                )
            ).scalars().all()
            if not sends:
                return {"cancelled_unstarted": cancelled, "in_flight": 0}
            if {send.id for send in sends} != send_ids:
                raise RuntimeError("Outbox abort scope no longer matches the exact manifest.")
            for send in sends:
                participant = expected_by_send_id[send.id]
                if (
                    send.owner_id != owner_user_id
                    or send.assignment_id != UUID(participant.assignment_id)
                    or send.recipient_email != participant.email
                    or not send.sandbox_required
                ):
                    raise RuntimeError(
                        "Outbox abort scope differs from the exact sandbox manifest."
                    )
            now = datetime.now(UTC)
            in_flight = 0
            for send in sends:
                if send.status == EmailSendStatus.queued or (
                    send.status == EmailSendStatus.dispatching
                    and send.provider_request_started_at is None
                ):
                    send.status = EmailSendStatus.cancelled
                    send.cancelled_at = now
                    send.next_attempt_at = None
                    send.lease_token = None
                    send.lease_expires_at = None
                    send.last_event_at = now
                    await CommunicationsRepository(session).add_email_event(
                        send.id,
                        EmailEventType.cancelled,
                        occurred_at=now,
                    )
                    cancelled += 1
                elif send.status == EmailSendStatus.dispatching:
                    in_flight += 1
            await session.commit()
        if in_flight == 0:
            return {"cancelled_unstarted": cancelled, "in_flight": 0}
        if time.monotonic() >= deadline:
            return {"cancelled_unstarted": cancelled, "in_flight": in_flight}
        await asyncio.sleep(0.5)


async def _require_exact_owner_scope(
    session: Any,
    *,
    owner_user_id: UUID,
    expected_email_send_ids: set[UUID],
) -> None:
    unexpected: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        owner_column = table.c.get("owner_id")
        if owner_column is None:
            continue
        if table.name == EmailSend.__tablename__:
            actual_ids = set(
                (
                    await session.execute(
                        select(EmailSend.id).where(EmailSend.owner_id == owner_user_id)
                    )
                )
                .scalars()
                .all()
            )
            if actual_ids != expected_email_send_ids:
                raise RuntimeError(
                    "Synthetic owner outbox scope differs from the exact manifest."
                )
            continue
        count = int(
            await session.scalar(
                select(func.count()).select_from(table).where(owner_column == owner_user_id)
            )
            or 0
        )
        if count:
            unexpected[table.name] = count
    if unexpected:
        details = ", ".join(
            f"{table_name}={count}" for table_name, count in sorted(unexpected.items())
        )
        raise RuntimeError(
            f"Synthetic owner has data outside the load-proof fixture: {details}."
        )


async def cleanup_synthetic_tenant(
    *,
    settings: Settings,
    manifest: LoadProofManifest,
    run_id: str,
    acknowledgement: str | None,
) -> dict[str, Any]:
    require_guard(
        settings,
        run_id=run_id,
        acknowledgement=acknowledgement,
        operation="cleanup",
    )
    validate_manifest(manifest, expected_run_id=run_id)
    validate_manifest_runtime(manifest, settings)
    cancellation = await _cancel_exact_unstarted_outbox(manifest)
    if cancellation["in_flight"]:
        raise RuntimeError(
            "Synthetic outbox still has provider requests in flight; refusing cleanup."
        )
    company_id = UUID(manifest.company_id)
    project_id = UUID(manifest.project_id)
    definition_id = UUID(manifest.definition_id)
    participant_user_ids = {UUID(item.user_id) for item in manifest.participants}
    owner_user_id = UUID(manifest.owner_user_id)
    user_ids = participant_user_ids | {owner_user_id}
    profile_ids = {UUID(item.profile_id) for item in manifest.participants}
    assignment_ids = {UUID(item.assignment_id) for item in manifest.participants}
    invite_ids = {UUID(item.invite_id) for item in manifest.participants}
    email_send_ids = {UUID(item.email_send_id) for item in manifest.participants}

    async with SessionLocal() as session:
        company = await session.scalar(select(Company).where(Company.id == company_id))
        definition = await session.scalar(
            select(QuestionnaireDefinition).where(QuestionnaireDefinition.id == definition_id)
        )
        users = (
            await session.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
        ).all()
        email_sends = (
            await session.execute(
                select(EmailSend.id, EmailSend.assignment_id, EmailSend.recipient_email).where(
                    EmailSend.id.in_(email_send_ids)
                )
            )
        ).all()
        if company is None and definition is None and not users and not email_sends:
            return {"run_id": run_id, "already_absent": True, "deleted_participants": 0}
        if (
            company is None
            or definition is None
            or len(users) != PARTICIPANT_COUNT + 1
            or len(email_sends) != PARTICIPANT_COUNT
        ):
            raise RuntimeError("Synthetic cleanup scope is partial; refusing any deletion.")
        if company.name != manifest.company_name:
            raise RuntimeError("Company identity no longer matches the exact manifest.")

        project = await session.scalar(
            select(CompanyProject).where(
                CompanyProject.id == project_id,
                CompanyProject.company_id == company_id,
            )
        )
        if (
            project is None
            or project.name != manifest.project_name
            or project.project_type != manifest.tag
        ):
            raise RuntimeError("Project identity no longer matches the exact manifest.")
        if (
            definition.key != manifest.definition_key
            or definition.version != 1
            or definition.package_id != manifest.tag
        ):
            raise RuntimeError("Definition identity no longer matches the exact manifest.")

        actual_profiles = set(
            (
                await session.execute(
                    select(ParticipantProfile.id).where(
                        ParticipantProfile.company_id == company_id
                    )
                )
            )
            .scalars()
            .all()
        )
        actual_assignments = set(
            (
                await session.execute(
                    select(QuestionnaireAssignment.id).where(
                        QuestionnaireAssignment.company_id == company_id
                    )
                )
            )
            .scalars()
            .all()
        )
        actual_invites = set(
            (
                await session.execute(
                    select(AssignmentInvite.id).where(AssignmentInvite.company_id == company_id)
                )
            )
            .scalars()
            .all()
        )
        actual_project_memberships = list(
            (
                await session.execute(
                    select(
                        ProjectMembership.company_id,
                        ProjectMembership.project_id,
                        ProjectMembership.participant_profile_id,
                    ).where(
                        (ProjectMembership.project_id == project_id)
                        | (ProjectMembership.participant_profile_id.in_(profile_ids))
                    )
                )
            ).all()
        )
        expected_project_memberships = {
            (company_id, project_id, profile_id) for profile_id in profile_ids
        }
        actual_company_memberships = list(
            (
                await session.execute(
                    select(
                        CompanyMembership.company_id,
                        CompanyMembership.user_id,
                        CompanyMembership.role,
                    ).where(
                        (CompanyMembership.company_id == company_id)
                        | (CompanyMembership.user_id.in_(user_ids))
                    )
                )
            ).all()
        )
        expected_company_memberships = {
            (company_id, owner_user_id, CompanyMembershipRole.owner)
        }
        if actual_profiles != profile_ids:
            raise RuntimeError("Profile scope differs from the manifest; refusing cleanup.")
        if actual_assignments != assignment_ids:
            raise RuntimeError("Assignment scope differs from the manifest; refusing cleanup.")
        if actual_invites != invite_ids:
            raise RuntimeError("Invite scope differs from the manifest; refusing cleanup.")
        if (
            len(actual_project_memberships) != PARTICIPANT_COUNT
            or set(actual_project_memberships) != expected_project_memberships
        ):
            raise RuntimeError(
                "Project-membership scope differs from the manifest; refusing cleanup."
            )
        if (
            len(actual_company_memberships) != 1
            or set(actual_company_memberships) != expected_company_memberships
        ):
            raise RuntimeError(
                "Company-membership scope differs from the manifest; refusing cleanup."
            )

        actual_user_emails = {user_id: email for user_id, email in users}
        expected_user_emails = {
            UUID(item.user_id): item.email for item in manifest.participants
        }
        expected_user_emails[owner_user_id] = manifest.owner_email
        if actual_user_emails != expected_user_emails:
            raise RuntimeError("User scope differs from the manifest; refusing cleanup.")
        expected_send_scope = {
            UUID(item.email_send_id): (UUID(item.assignment_id), item.email)
            for item in manifest.participants
        }
        actual_send_scope = {
            send_id: (assignment_id, recipient_email)
            for send_id, assignment_id, recipient_email in email_sends
        }
        if actual_send_scope != expected_send_scope:
            raise RuntimeError("Outbox scope differs from the manifest; refusing cleanup.")
        await _require_exact_owner_scope(
            session,
            owner_user_id=owner_user_id,
            expected_email_send_ids=email_send_ids,
        )
        assignment_send_ids = set(
            (
                await session.execute(
                    select(EmailSend.id).where(EmailSend.assignment_id.in_(assignment_ids))
                )
            )
            .scalars()
            .all()
        )
        if assignment_send_ids != email_send_ids:
            raise RuntimeError("Unexpected outbox rows reference this run; refusing cleanup.")
        external_profiles = await session.scalar(
            select(ParticipantProfile.id).where(
                ParticipantProfile.user_id.in_(user_ids),
                ParticipantProfile.company_id != company_id,
            )
        )
        external_memberships = await session.scalar(
            select(CompanyMembership.id).where(
                CompanyMembership.user_id.in_(user_ids),
                CompanyMembership.company_id != company_id,
            )
        )
        if external_profiles is not None or external_memberships is not None:
            raise RuntimeError("A synthetic user is referenced outside the run; refusing cleanup.")

        email_result = await session.execute(
            delete(EmailSend).where(EmailSend.id.in_(email_send_ids))
        )
        if email_result.rowcount != PARTICIPANT_COUNT:
            raise RuntimeError("Exact outbox deletion did not affect 1,000 rows.")
        company_result = await session.execute(
            delete(Company).where(
                Company.id == company_id,
                Company.name == manifest.company_name,
            )
        )
        if company_result.rowcount != 1:
            raise RuntimeError("Exact company deletion did not affect one row.")
        definition_result = await session.execute(
            delete(QuestionnaireDefinition).where(
                QuestionnaireDefinition.id == definition_id,
                QuestionnaireDefinition.key == manifest.definition_key,
                QuestionnaireDefinition.version == 1,
                QuestionnaireDefinition.package_id == manifest.tag,
            )
        )
        if definition_result.rowcount != 1:
            raise RuntimeError("Exact definition deletion did not affect one row.")
        user_result = await session.execute(delete(User).where(User.id.in_(user_ids)))
        if user_result.rowcount != PARTICIPANT_COUNT + 1:
            raise RuntimeError("Exact user deletion did not affect 1,001 rows.")
        await session.commit()
    return {
        "run_id": run_id,
        "already_absent": False,
        "deleted_participants": PARTICIPANT_COUNT,
    }


async def exercise_participant(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    participant: ParticipantManifest,
    maintenance_headers: dict[str, str],
    recorder: MetricsRecorder,
    abort: AbortController,
) -> tuple[dict[str, str], str]:
    verify = await _request(
        client,
        recorder,
        abort,
        "invite_verify",
        "GET",
        f"{base_url}/api/auth/invite/verify",
        headers={**maintenance_headers, "Cookie": ""},
        params={"token": participant.token},
    )
    tasks = verify.json().get("tasks", [])
    if not any(str(task.get("assignment_id")) == participant.assignment_id for task in tasks):
        raise RuntimeError("Invite verification omitted the manifest assignment.")

    exchange = await _request(
        client,
        recorder,
        abort,
        "invite_exchange",
        "POST",
        f"{base_url}/api/auth/invite/exchange",
        headers={**maintenance_headers, "Cookie": ""},
        json={"token": participant.token, "replace_existing_session": False},
    )
    if exchange.json().get("action") != "secure_link_ready":
        raise RuntimeError("Invite exchange did not create a secure-link session.")
    session_cookie = exchange.cookies.get(SESSION_COOKIE_NAME)
    csrf_cookie = exchange.cookies.get(CSRF_COOKIE_NAME)
    if not session_cookie or not csrf_cookie:
        raise RuntimeError("Invite exchange did not return the session and CSRF cookies.")
    auth_headers = {
        **maintenance_headers,
        "Cookie": (
            f"{SESSION_COOKIE_NAME}={session_cookie}; {CSRF_COOKIE_NAME}={csrf_cookie}"
        ),
        CSRF_HEADER_NAME: csrf_cookie,
    }
    path = (
        f"{base_url}/api/forms/secure-links/{participant.token}/assignments/"
        f"{participant.assignment_id}"
    )
    await _request(
        client,
        recorder,
        abort,
        "definition_read",
        "GET",
        f"{path}/definition",
        headers=auth_headers,
    )
    await _request(
        client,
        recorder,
        abort,
        "task_read",
        "GET",
        f"{path}/response",
        headers=auth_headers,
    )
    autosave = await _request(
        client,
        recorder,
        abort,
        "autosave",
        "PUT",
        f"{path}/response",
        headers=auth_headers,
        json={"answers": participant.answers},
    )
    if autosave.json().get("status") != "draft":
        raise RuntimeError("Autosave did not persist a draft response.")
    submit = await _request(
        client,
        recorder,
        abort,
        "submit",
        "POST",
        f"{path}/response/submit",
        headers=auth_headers,
        json={"answers": participant.answers},
    )
    if submit.json().get("status") != "submitted":
        raise RuntimeError("Submit was not accepted as submitted.")
    final_response = await _request(
        client,
        recorder,
        abort,
        "post_submit_read",
        "GET",
        f"{path}/response",
        headers=auth_headers,
    )
    if final_response.json().get("status") != "submitted":
        raise RuntimeError("Post-submit read did not return the submitted response.")
    return auth_headers, path


def _read_runtime_evidence(
    path: Path | None,
    *,
    production: bool,
) -> RuntimeEvidence | None:
    if path is None:
        if production:
            raise RuntimeError(
                "Production proof requires --runtime-evidence from the host monitor."
            )
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("Runtime evidence is unavailable.") from exc
    values: dict[str, str] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            values[key] = value
    required = {
        "captured_at_epoch",
        "backend_id",
        "backend_restart_count",
        "backend_oom_killed",
        "backend_started_at",
        "backend_pool_timeout_count",
        "worker_id",
        "worker_restart_count",
        "worker_oom_killed",
        "worker_started_at",
        "worker_pool_timeout_count",
    }
    if required - values.keys():
        raise RuntimeError("Runtime evidence is incomplete.")
    for key in ("backend_oom_killed", "worker_oom_killed"):
        if values[key] not in {"true", "false"}:
            raise RuntimeError("Runtime evidence contains invalid boolean values.")
    try:
        evidence = RuntimeEvidence(
            captured_at_epoch=int(values["captured_at_epoch"]),
            backend_id=values["backend_id"],
            backend_restart_count=int(values["backend_restart_count"]),
            backend_oom_killed=values["backend_oom_killed"] == "true",
            backend_started_at=values["backend_started_at"],
            backend_pool_timeout_count=int(values["backend_pool_timeout_count"]),
            worker_id=values["worker_id"],
            worker_restart_count=int(values["worker_restart_count"]),
            worker_oom_killed=values["worker_oom_killed"] == "true",
            worker_started_at=values["worker_started_at"],
            worker_pool_timeout_count=int(values["worker_pool_timeout_count"]),
        )
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Runtime evidence contains invalid values.") from exc
    if (
        evidence.captured_at_epoch < 0
        or evidence.backend_restart_count < 0
        or evidence.backend_pool_timeout_count < 0
        or evidence.worker_restart_count < 0
        or evidence.worker_pool_timeout_count < 0
    ):
        raise RuntimeError("Runtime evidence contains invalid negative counters.")
    if abs(int(time.time()) - evidence.captured_at_epoch) > 15:
        raise RuntimeError("Runtime evidence is stale.")
    if (
        not evidence.backend_id
        or not evidence.worker_id
        or evidence.backend_oom_killed
        or evidence.worker_oom_killed
    ):
        raise RuntimeError("Runtime evidence does not show healthy API and worker containers.")
    return evidence


def _runtime_evidence_failure(
    baseline: RuntimeEvidence | None,
    current: RuntimeEvidence | None,
) -> str | None:
    if baseline is None:
        return None
    if current is None:
        return "runtime evidence disappeared during the proof"
    if (
        current.backend_id != baseline.backend_id
        or current.worker_id != baseline.worker_id
        or current.backend_started_at != baseline.backend_started_at
        or current.worker_started_at != baseline.worker_started_at
        or current.backend_restart_count != baseline.backend_restart_count
        or current.worker_restart_count != baseline.worker_restart_count
    ):
        return "API or worker container restarted during the proof"
    if current.backend_oom_killed or current.worker_oom_killed:
        return "API or worker container reported an OOM kill"
    if (
        current.backend_pool_timeout_count > baseline.backend_pool_timeout_count
        or current.worker_pool_timeout_count > baseline.worker_pool_timeout_count
    ):
        return "database pool timeout detected"
    return None


async def run_load_proof(
    *,
    settings: Settings,
    manifest: LoadProofManifest,
    run_id: str,
    acknowledgement: str | None,
    base_url: str,
    ramp_seconds: int,
    read_interval_seconds: float,
    report_path: Path,
    runtime_evidence_path: Path | None = None,
) -> dict[str, Any]:
    require_guard(
        settings,
        run_id=run_id,
        acknowledgement=acknowledgement,
        operation="load execution",
    )
    _require_outbox_capacity(settings)
    validate_manifest(manifest, expected_run_id=run_id)
    validate_manifest_runtime(manifest, settings)
    normalized_base_url = _normalize_base_url(base_url)
    if settings.is_production and normalized_base_url != _normalize_base_url(
        settings.public_app_url
    ):
        raise RuntimeError("Production proof target must equal CODRUT_PUBLIC_APP_URL.")
    if not 1 <= ramp_seconds <= 300:
        raise RuntimeError("Ramp must be between 1 and 300 seconds.")
    if not 1.0 <= read_interval_seconds <= 30.0:
        raise RuntimeError("Read interval must be between 1 and 30 seconds.")
    if report_path.exists():
        raise RuntimeError("Refusing to overwrite an existing load-proof report.")
    runtime_baseline = _read_runtime_evidence(
        runtime_evidence_path,
        production=settings.is_production,
    )

    bypass = (
        settings.maintenance_bypass_token.get_secret_value()
        if settings.maintenance_bypass_token
        else ""
    )
    maintenance_headers = (
        {MAINTENANCE_BYPASS_HEADER: bypass} if settings.maintenance_mode else {}
    )
    recorder = MetricsRecorder()
    abort = AbortController()
    resource_extrema = ResourceExtrema()
    started_at = datetime.now(UTC)
    started = time.monotonic()
    outbox_release = await _release_exact_outbox(manifest, settings=settings)
    outbox_started = time.monotonic()
    outbox_task = asyncio.create_task(
        _monitor_exact_outbox(
            manifest,
            abort=abort,
            started=outbox_started,
        )
    )
    processing_task = asyncio.create_task(
        _monitor_exact_processing(
            manifest,
            abort=abort,
            started=started,
        )
    )
    limits = httpx.Limits(
        max_connections=PARTICIPANT_COUNT + 50,
        max_keepalive_connections=PARTICIPANT_COUNT + 50,
    )
    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=False) as client:
        monitor_stop = asyncio.Event()
        monitor = asyncio.create_task(
            _monitor(
                client,
                base_url=normalized_base_url,
                maintenance_headers=maintenance_headers,
                recorder=recorder,
                abort=abort,
                stop=monitor_stop,
                production=settings.is_production,
                resource_extrema=resource_extrema,
                runtime_evidence_path=runtime_evidence_path,
                runtime_baseline=runtime_baseline,
            )
        )
        initial_tasks = [
            asyncio.create_task(
                _ramped_initial_flow(
                    client,
                    base_url=normalized_base_url,
                    participant=participant,
                    delay=(participant.index - 1) * ramp_seconds / PARTICIPANT_COUNT,
                    maintenance_headers=maintenance_headers,
                    recorder=recorder,
                    abort=abort,
                )
            )
            for participant in manifest.participants
        ]
        initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)
        initial_exceptions = [
            result for result in initial_results if isinstance(result, BaseException)
        ]
        if initial_exceptions and not abort.reason:
            abort.abort(f"participant workflow failed: {initial_exceptions[0]}")

        hold_results: list[Any] = []
        trainer_result: Any = None
        if not abort.event.is_set():
            hold_starts = time.monotonic()
            hold_ends = hold_starts + HOLD_SECONDS
            hold_tasks = [
                asyncio.create_task(
                    _hold_reads(
                        client,
                        path=result[1],
                        auth_headers=result[0],
                        hold_ends=hold_ends,
                        read_interval_seconds=read_interval_seconds,
                        recorder=recorder,
                        abort=abort,
                    )
                )
                for result in initial_results
                if isinstance(result, tuple)
            ]
            trainer_task = asyncio.create_task(
                _trainer_aggregate_result_read(
                    processing_task,
                    client,
                    base_url=normalized_base_url,
                    manifest=manifest,
                    maintenance_headers=maintenance_headers,
                    recorder=recorder,
                    abort=abort,
                )
            )
            hold_results = await asyncio.gather(*hold_tasks, return_exceptions=True)
            trainer_result = await asyncio.gather(trainer_task, return_exceptions=True)
        monitor_stop.set()
        await monitor

    exceptions = initial_exceptions + [
        result for result in hold_results if isinstance(result, BaseException)
    ]
    if isinstance(trainer_result, list):
        exceptions.extend(
            result for result in trainer_result if isinstance(result, BaseException)
        )
    outbox_report = await outbox_task
    processing_report = await processing_task
    if exceptions and not abort.reason:
        abort.abort(f"participant workflow failed: {exceptions[0]}")
    abort_outbox = {"cancelled_unstarted": 0, "in_flight": 0}
    if abort.reason:
        abort_outbox = await _cancel_exact_unstarted_outbox(manifest)
        if abort_outbox["in_flight"]:
            abort.abort(
                "synthetic provider requests remained in flight after the abort deadline"
            )
    metrics = recorder.report()
    acceptance_failures = evaluate_acceptance(metrics)
    if abort.reason:
        acceptance_failures.insert(0, abort.reason)
    if abort_outbox["in_flight"]:
        acceptance_failures.append(
            "synthetic provider requests remained in flight after the abort deadline"
        )
    if outbox_report["accepted_or_delivered"] != PARTICIPANT_COUNT:
        acceptance_failures.append("sandbox outbox did not drain all 1,000 invitation sends")
    if (
        processing_report["completed_jobs"] != PARTICIPANT_COUNT
        or processing_report["scores"] != PARTICIPANT_COUNT
        or processing_report["active_publications"] != PARTICIPANT_COUNT
    ):
        acceptance_failures.append(
            "submission processing did not produce exactly 1,000 jobs, scores, and publications"
        )
    completed_at = datetime.now(UTC)
    runtime_final = _read_runtime_evidence(
        runtime_evidence_path,
        production=settings.is_production,
    )
    runtime_failure = _runtime_evidence_failure(runtime_baseline, runtime_final)
    if runtime_failure:
        acceptance_failures.append(runtime_failure)
    resource_failure = _resource_evidence_failure(
        resource_extrema,
        production=settings.is_production,
    )
    if resource_failure:
        acceptance_failures.append(resource_failure)
    resource_report = resource_extrema.report()
    report = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "tag": manifest.tag,
        "participant_count": PARTICIPANT_COUNT,
        "ramp_seconds": ramp_seconds,
        "hold_seconds": HOLD_SECONDS,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "successful": not acceptance_failures,
        "abort_reason": abort.reason,
        "acceptance_failures": acceptance_failures,
        "outbox": {
            **outbox_report,
            **outbox_release,
            **abort_outbox,
            "drain_limit_seconds": HOLD_SECONDS,
        },
        "submission_processing": processing_report,
        "thresholds": {
            "read_p95_ms": READ_P95_LIMIT_MS,
            "autosave_p95_ms": AUTOSAVE_P95_LIMIT_MS,
            "submit_p95_ms": SUBMIT_P95_LIMIT_MS,
            "max_error_rate": 0.01,
            "max_429": 0,
            "max_cpu_percent_for_seconds": {"percent": 90, "seconds": 60},
            "min_free_memory_bytes": 1_073_741_824,
            "max_disk_percent": 80,
            "max_readiness_unhealthy_seconds": 30,
        },
        "metrics": metrics,
        "resources": resource_report,
        "runtime_evidence": {
            "baseline": runtime_baseline.to_dict() if runtime_baseline else None,
            "final": runtime_final.to_dict() if runtime_final else None,
        },
    }
    _write_private_json(report_path, report, refuse_overwrite=True)
    return report


async def _release_exact_outbox(
    manifest: LoadProofManifest,
    *,
    settings: Settings,
) -> dict[str, Any]:
    send_ids = {UUID(item.email_send_id) for item in manifest.participants}
    now = datetime.now(UTC)
    manifest_created_at = datetime.fromisoformat(manifest.created_at)
    if manifest_created_at.astimezone(UTC).date() != now.date():
        raise RuntimeError("Seed and measured outbox release must occur on the same UTC day.")
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    expected_by_send_id = {
        UUID(item.email_send_id): item for item in manifest.participants
    }
    async with SessionLocal() as session:
        repository = CommunicationsRepository(session)
        await repository.acquire_email_capacity_lock()
        await _require_no_unrelated_outbox_activity(
            session,
            exact_send_ids=send_ids,
            since=manifest_created_at,
        )
        sends = (
            await session.execute(
                select(EmailSend)
                .where(EmailSend.id.in_(send_ids))
                .with_for_update()
            )
        ).scalars().all()
        if {send.id for send in sends} != send_ids:
            raise RuntimeError("Outbox release scope does not match the exact manifest.")
        if any(send.status != EmailSendStatus.queued for send in sends):
            raise RuntimeError("Outbox must be entirely queued before exact release.")
        if any(send.owner_id != UUID(manifest.owner_user_id) for send in sends):
            raise RuntimeError("Outbox owner does not match the exact synthetic trainer.")
        for send in sends:
            participant = expected_by_send_id[send.id]
            expected_payload = _invitation_message_payload(
                settings=settings,
                email=participant.email,
                action_url=(
                    f"{settings.public_app_url.rstrip('/')}/invite/{participant.token}"
                ),
                assignment_id=UUID(participant.assignment_id),
                run_id=manifest.run_id,
            )
            if (
                send.assignment_id != UUID(participant.assignment_id)
                or send.recipient_email != participant.email
                or send.provider != settings.email_provider
                or send.template_key != "assignment_bundle"
                or send.template_version != 1
                or not send.sandbox_required
                or send.message_payload != expected_payload
                or send.payload_fingerprint != _payload_fingerprint(expected_payload)
            ):
                raise RuntimeError(
                    "Outbox payload differs from the exact sandbox manifest; refusing release."
                )
        active_today = int(
            await session.scalar(
                select(func.count(EmailSend.id)).where(
                    EmailSend.status.in_(
                        (
                            EmailSendStatus.queued,
                            EmailSendStatus.dispatching,
                            EmailSendStatus.accepted,
                            EmailSendStatus.delivered,
                        )
                    ),
                    EmailSend.created_at >= day_start,
                )
            )
            or 0
        )
        available_before_proof = settings.email_daily_send_cap - (
            active_today - PARTICIPANT_COUNT
        )
        if available_before_proof < PARTICIPANT_COUNT:
            raise RuntimeError(
                "Daily email capacity cannot accommodate the exact 1,000-send proof."
            )
        for send in sends:
            send.next_attempt_at = now
            send.last_event_at = now
        await session.commit()
    return {
        "released_at": now.isoformat(),
        "daily_cap": settings.email_daily_send_cap,
        "active_today_at_release": active_today,
        "available_before_proof": available_before_proof,
        "remaining_capacity_after_proof": available_before_proof - PARTICIPANT_COUNT,
    }


async def _require_no_unrelated_outbox_activity(
    session: Any,
    *,
    exact_send_ids: set[UUID],
    since: datetime,
) -> None:
    statement = select(func.count(EmailSend.id)).where(
        (
            EmailSend.status.in_(
                (
                    EmailSendStatus.queued,
                    EmailSendStatus.dispatching,
                )
            )
        )
        | (EmailSend.last_event_at >= since)
    )
    if exact_send_ids:
        statement = statement.where(EmailSend.id.notin_(exact_send_ids))
    unrelated_count = int(await session.scalar(statement) or 0)
    if unrelated_count:
        raise RuntimeError(
            "Unrelated email outbox activity exists during maintenance; "
            "refusing the synthetic load proof."
        )


async def _monitor_exact_outbox(
    manifest: LoadProofManifest,
    *,
    abort: AbortController,
    started: float,
) -> dict[str, Any]:
    send_ids = {UUID(item.email_send_id) for item in manifest.participants}
    deadline = started + HOLD_SECONDS
    latest_counts: dict[str, int] = {}
    while not abort.event.is_set():
        try:
            async with SessionLocal() as session:
                await _require_no_unrelated_outbox_activity(
                    session,
                    exact_send_ids=send_ids,
                    since=datetime.fromisoformat(manifest.created_at),
                )
                rows = (
                    await session.execute(
                        select(EmailSend.id, EmailSend.status).where(
                            EmailSend.id.in_(send_ids)
                        )
                    )
                ).all()
        except Exception:  # noqa: BLE001
            abort.abort("outbox status telemetry failed")
            break
        if {send_id for send_id, _status in rows} != send_ids:
            abort.abort("outbox rows disappeared outside exact-run cleanup")
            break
        latest_counts, successful, failed = _summarize_outbox_statuses(
            [status_value for _send_id, status_value in rows]
        )
        if successful == PARTICIPANT_COUNT:
            return {
                "accepted_or_delivered": successful,
                "failed_terminal": 0,
                "drain_seconds": round(time.monotonic() - started, 3),
                "status_counts": latest_counts,
            }
        if failed:
            abort.abort("sandbox outbox entered a failed terminal state")
            break
        if time.monotonic() >= deadline:
            abort.abort("sandbox outbox did not drain within five minutes")
            break
        try:
            await asyncio.wait_for(abort.event.wait(), timeout=2.0)
        except TimeoutError:
            continue
    successful, failed = _outbox_terminal_counts(latest_counts)
    return {
        "accepted_or_delivered": successful,
        "failed_terminal": failed,
        "drain_seconds": None,
        "status_counts": latest_counts,
    }


async def _monitor_exact_processing(
    manifest: LoadProofManifest,
    *,
    abort: AbortController,
    started: float,
) -> dict[str, Any]:
    assignment_ids = {UUID(item.assignment_id) for item in manifest.participants}
    deadline = started + HOLD_SECONDS
    latest = {
        "completed_jobs": 0,
        "failed_jobs": 0,
        "scores": 0,
        "active_publications": 0,
    }
    while not abort.event.is_set():
        try:
            async with SessionLocal() as session:
                jobs = (
                    await session.execute(
                        select(
                            SubmissionProcessingJob.assignment_id,
                            SubmissionProcessingJob.status,
                        ).where(SubmissionProcessingJob.assignment_id.in_(assignment_ids))
                    )
                ).all()
                score_ids = set(
                    (
                        await session.execute(
                            select(ScoringResult.assignment_id).where(
                                ScoringResult.assignment_id.in_(assignment_ids)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                publication_ids = set(
                    (
                        await session.execute(
                            select(ResultPublication.source_assignment_id).where(
                                ResultPublication.source_assignment_id.in_(assignment_ids),
                                ResultPublication.revoked_at.is_(None),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
        except Exception:  # noqa: BLE001
            abort.abort("submission-processing telemetry failed")
            break
        statuses = {assignment_id: status for assignment_id, status in jobs}
        completed_jobs = sum(
            status == SubmissionProcessingStatus.completed for status in statuses.values()
        )
        failed_jobs = sum(
            status == SubmissionProcessingStatus.failed for status in statuses.values()
        )
        latest = {
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "scores": len(score_ids),
            "active_publications": len(publication_ids),
        }
        if (
            len(statuses) == PARTICIPANT_COUNT
            and completed_jobs == PARTICIPANT_COUNT
            and len(score_ids) == PARTICIPANT_COUNT
            and len(publication_ids) == PARTICIPANT_COUNT
        ):
            return {
                **latest,
                "drain_seconds": round(time.monotonic() - started, 3),
            }
        if failed_jobs:
            abort.abort("one or more submission-processing jobs failed")
            break
        if time.monotonic() >= deadline:
            abort.abort("scores and publications did not complete within five minutes")
            break
        try:
            await asyncio.wait_for(abort.event.wait(), timeout=2.0)
        except TimeoutError:
            continue
    return {**latest, "drain_seconds": None}


async def _trainer_aggregate_result_read(
    processing_task: asyncio.Task[dict[str, Any]],
    client: httpx.AsyncClient,
    *,
    base_url: str,
    manifest: LoadProofManifest,
    maintenance_headers: dict[str, str],
    recorder: MetricsRecorder,
    abort: AbortController,
) -> None:
    try:
        processing = await processing_task
        if processing["active_publications"] != PARTICIPANT_COUNT:
            raise RuntimeError("Result publication proof did not complete.")
        login = await _request(
            client,
            recorder,
            abort,
            "trainer_login",
            "POST",
            f"{base_url}/api/auth/login",
            headers={**maintenance_headers, "Cookie": ""},
            json={
                "email": manifest.owner_email,
                "password": manifest.owner_password,
            },
        )
        session_cookie = login.cookies.get(SESSION_COOKIE_NAME)
        if not session_cookie:
            raise RuntimeError("Synthetic trainer login did not return a session.")
        aggregate = await _request(
            client,
            recorder,
            abort,
            "trainer_aggregate_result_read",
            "GET",
            f"{base_url}/api/companies/{manifest.company_id}/reports/aggregate",
            headers={
                **maintenance_headers,
                "Cookie": f"{SESSION_COOKIE_NAME}={session_cookie}",
            },
            params={"project_id": manifest.project_id},
        )
        payload = aggregate.json()
        if (
            payload.get("total_assigned") != PARTICIPANT_COUNT
            or payload.get("total_completed") != PARTICIPANT_COUNT
            or len(payload.get("results", [])) != PARTICIPANT_COUNT
        ):
            raise RuntimeError("Trainer aggregate did not expose the exact scored fixture.")
    except Exception as exc:
        abort.abort(f"trainer aggregate result proof failed: {exc}")
        raise


def _summarize_outbox_statuses(
    statuses: list[EmailSendStatus],
) -> tuple[dict[str, int], int, int]:
    counts: dict[str, int] = {}
    for status_value in statuses:
        counts[status_value.value] = counts.get(status_value.value, 0) + 1
    successful, failed = _outbox_terminal_counts(counts)
    return counts, successful, failed


def _outbox_terminal_counts(counts: dict[str, int]) -> tuple[int, int]:
    successful = sum(
        counts.get(status.value, 0)
        for status in (EmailSendStatus.accepted, EmailSendStatus.delivered)
    )
    failed = sum(
        counts.get(status.value, 0)
        for status in (
            EmailSendStatus.failed,
            EmailSendStatus.bounced,
            EmailSendStatus.cancelled,
            EmailSendStatus.indeterminate,
        )
    )
    return successful, failed


async def _ramped_initial_flow(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    participant: ParticipantManifest,
    delay: float,
    maintenance_headers: dict[str, str],
    recorder: MetricsRecorder,
    abort: AbortController,
) -> tuple[dict[str, str], str]:
    try:
        await asyncio.wait_for(abort.event.wait(), timeout=delay)
    except TimeoutError:
        # The ramp delay elapsed without a global abort, so this participant may start.
        pass
    if abort.event.is_set():
        raise RuntimeError(abort.reason or "load proof aborted")
    return await exercise_participant(
        client,
        base_url=base_url,
        participant=participant,
        maintenance_headers=maintenance_headers,
        recorder=recorder,
        abort=abort,
    )


async def _hold_reads(
    client: httpx.AsyncClient,
    *,
    path: str,
    auth_headers: dict[str, str],
    hold_ends: float,
    read_interval_seconds: float,
    recorder: MetricsRecorder,
    abort: AbortController,
) -> None:
    while time.monotonic() < hold_ends and not abort.event.is_set():
        await _request(
            client,
            recorder,
            abort,
            "hold_definition_read",
            "GET",
            f"{path}/definition",
            headers=auth_headers,
        )
        await _request(
            client,
            recorder,
            abort,
            "hold_response_read",
            "GET",
            f"{path}/response",
            headers=auth_headers,
        )
        try:
            await asyncio.wait_for(abort.event.wait(), timeout=read_interval_seconds)
        except TimeoutError:
            continue


async def _monitor(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    maintenance_headers: dict[str, str],
    recorder: MetricsRecorder,
    abort: AbortController,
    stop: asyncio.Event,
    production: bool,
    resource_extrema: ResourceExtrema,
    runtime_evidence_path: Path | None,
    runtime_baseline: RuntimeEvidence | None,
) -> None:
    sampler = LocalResourceSampler()
    readiness_unhealthy_since: float | None = None
    high_cpu_since: float | None = None
    while not stop.is_set() and not abort.event.is_set():
        cycle_started = time.monotonic()
        try:
            response = await _request(
                client,
                recorder,
                abort,
                "readiness",
                "GET",
                f"{base_url}/api/health/ready",
                headers=maintenance_headers,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"readiness returned {response.status_code}")
            readiness_unhealthy_since = None
        except Exception:  # noqa: BLE001
            readiness_unhealthy_since = readiness_unhealthy_since or time.monotonic()
            if time.monotonic() - readiness_unhealthy_since >= 30:
                abort.abort("readiness was unhealthy for 30 seconds")

        sample = sampler.sample()
        resource_extrema.record(sample)
        if sample.free_memory_bytes <= 0:
            if production:
                abort.abort("local free-memory telemetry is unavailable")
        elif sample.free_memory_bytes < 1_073_741_824:
            abort.abort("free memory dropped below 1 GB")
        if sample.disk_percent > 80:
            abort.abort("root disk usage exceeded 80 percent")
        if sample.cpu_percent is not None and sample.cpu_percent > 90:
            high_cpu_since = high_cpu_since or time.monotonic()
            if time.monotonic() - high_cpu_since >= 60:
                abort.abort("CPU remained above 90 percent for one minute")
        else:
            high_cpu_since = None

        threshold_failure = evaluate_live_thresholds(recorder.report())
        if threshold_failure:
            abort.abort(threshold_failure)
        try:
            runtime_current = _read_runtime_evidence(
                runtime_evidence_path,
                production=production,
            )
        except RuntimeError as exc:
            abort.abort(str(exc))
        else:
            runtime_failure = _runtime_evidence_failure(runtime_baseline, runtime_current)
            if runtime_failure:
                abort.abort(runtime_failure)
        wait_seconds = max(0.0, 5.0 - (time.monotonic() - cycle_started))
        try:
            await asyncio.wait_for(stop.wait(), timeout=wait_seconds)
        except TimeoutError:
            continue


async def _request(
    client: httpx.AsyncClient,
    recorder: MetricsRecorder,
    abort: AbortController,
    operation: str,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    if abort.event.is_set():
        raise RuntimeError(abort.reason or "load proof aborted")
    started = time.perf_counter()
    status_code: int | None = None
    try:
        response = await client.request(method, url, **kwargs)
        status_code = response.status_code
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.casefold()
        try:
            error_code = str(exc.response.json().get("error", {}).get("code", ""))
        except (AttributeError, ValueError):
            error_code = ""
        if (
            error_code == "database_pool_timeout"
            or "pool_timeout" in body
            or ("database" in body and "pool" in body)
        ):
            abort.abort("database pool timeout detected")
        raise
    finally:
        recorder.record(operation, (time.perf_counter() - started) * 1_000.0, status_code)


def evaluate_live_thresholds(metrics: dict[str, Any]) -> str | None:
    aggregate = metrics["aggregate"]
    if aggregate["rate_limited"] > 0:
        return "received HTTP 429 for a valid distinct secure-link session"
    if aggregate["count"] >= 100 and aggregate["error_rate"] > 0.01:
        return "request error rate exceeded one percent"
    for name, operation in metrics["operations"].items():
        if operation["count"] < 100:
            continue
        limit = _p95_limit(name)
        if limit is not None and operation["p95_ms"] > limit:
            return f"{name} p95 exceeded {limit:.0f} ms"
    return None


def evaluate_acceptance(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    aggregate = metrics["aggregate"]
    if aggregate["error_rate"] >= 0.01:
        failures.append("request failure rate was not below one percent")
    if aggregate["rate_limited"] > 0:
        failures.append("one or more valid sessions received HTTP 429")
    operations = metrics["operations"]
    required_operations = {
        "invite_verify",
        "invite_exchange",
        "definition_read",
        "task_read",
        "autosave",
        "submit",
        "post_submit_read",
        "trainer_aggregate_result_read",
    }
    missing = sorted(
        name
        for name in required_operations
        if operations.get(name, {}).get("count")
        != (
            1
            if name == "trainer_aggregate_result_read"
            else PARTICIPANT_COUNT
        )
    )
    if missing:
        failures.append(f"exact 1,000-operation proof missing for: {', '.join(missing)}")
    for name, operation in operations.items():
        limit = _p95_limit(name)
        if limit is not None and operation["count"] and operation["p95_ms"] >= limit:
            failures.append(f"{name} p95 was not below {limit:.0f} ms")
    return failures


def _metric_report(metrics: OperationMetrics) -> dict[str, Any]:
    count = len(metrics.durations_ms)
    return {
        "count": count,
        "errors": metrics.errors,
        "error_rate": round(metrics.errors / count, 6) if count else 0.0,
        "rate_limited": metrics.rate_limited,
        "p50_ms": _percentile(metrics.durations_ms, 0.50),
        "p95_ms": _percentile(metrics.durations_ms, 0.95),
        "p99_ms": _percentile(metrics.durations_ms, 0.99),
    }


def _percentile(values: array[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(quantile * len(ordered)) - 1)
    return round(ordered[rank], 3)


def _p95_limit(operation: str) -> float | None:
    if operation == "autosave":
        return AUTOSAVE_P95_LIMIT_MS
    if operation == "submit":
        return SUBMIT_P95_LIMIT_MS
    if operation.endswith("_read") or operation in {
        "invite_verify",
        "definition_read",
        "task_read",
        "readiness",
    }:
        return READ_P95_LIMIT_MS
    return None


def _normalize_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("Base URL must be an absolute HTTP(S) origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Base URL must not contain credentials, query, or fragment.")
    if parsed.path not in {"", "/"}:
        raise RuntimeError("Base URL must be an origin without an /api path.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _require_outbox_capacity(settings: Settings) -> None:
    if settings.email_daily_send_cap < 2_000:
        raise RuntimeError("Load proof requires the configured 2,000-message daily cap.")
    if settings.email_outbox_batch_size < 100:
        raise RuntimeError("Load proof requires outbox batches of at least 100.")
    if settings.email_outbox_concurrency < 8:
        raise RuntimeError("Load proof requires at least eight concurrent provider requests.")


def _questionnaire_schema() -> dict[str, Any]:
    return {
        "schema_version": "questionnaire.v1",
        "audience": "participant",
        "instructions": "Synthetic launch-capacity proof only.",
        "scoring": {
            "method": "sum_by_group",
            "groups": [
                {
                    "id": "load",
                    "label": "Synthetic load",
                    "question_ids": ["q1"],
                }
            ],
            "interpretation": [
                {
                    "min": 1,
                    "max": 5,
                    "label": "Synthetic launch proof score.",
                }
            ],
        },
        "sections": [
            {
                "id": "load",
                "title": "Synthetic load",
                "questions": [
                    {
                        "id": "q1",
                        "code": "Q1",
                        "type": "likert",
                        "label": "Synthetic response",
                        "required": True,
                        "scale": [
                            {"value": value, "label": str(value)} for value in range(1, 6)
                        ],
                    }
                ],
            }
        ],
    }


def _definition_key(run_id: str) -> str:
    return f"load_proof_{run_id.replace('-', '_')}"


def _participant_email(run_id: str, index: int) -> str:
    return f"load-proof-{run_id}-{index:04d}@example.com"


def _owner_email(run_id: str) -> str:
    return f"load-proof-owner-{run_id}@example.com"


def _invitation_message_payload(
    *,
    settings: Settings,
    email: str,
    action_url: str,
    assignment_id: UUID,
    run_id: str,
) -> dict[str, object]:
    return {
        "version": 1,
        "to": email,
        "subject": f"Synthetic invitation load proof {run_id}",
        "html_body": (
            "<p>Synthetic launch-capacity proof.</p>"
            f'<p><a href="{action_url}">Open synthetic questionnaire</a></p>'
        ),
        "text_body": f"Synthetic launch-capacity proof: {action_url}",
        "from_address": settings.email_from_address,
        "reply_to": None,
        "assignment_ids": [str(assignment_id)],
        "reminder_assignment_ids": [],
        "delivery_kind": "invitation",
        "lifecycle_request_id": f"load-proof:{run_id}",
    }


def _payload_fingerprint(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _write_private_json(path: Path, value: Any, *, refuse_overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_EXCL if refuse_overwrite else os.O_TRUNC
    descriptor = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _linux_available_memory() -> int:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except OSError:
        return 0
    return 0


def _linux_cpu_totals() -> tuple[int, int] | None:
    try:
        first_line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None
    fields = [int(value) for value in first_line.split()[1:]]
    if len(fields) < 4:
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return sum(fields), idle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Versioned 1,000-participant launch proof.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("seed", "cleanup"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--run-id", required=True)
        subparser.add_argument("--manifest", required=True, type=Path)
        subparser.add_argument("--ack", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--run-id", required=True)
    run.add_argument("--manifest", required=True, type=Path)
    run.add_argument("--report", required=True, type=Path)
    run.add_argument("--base-url", required=True)
    run.add_argument("--ramp-seconds", type=int, default=60)
    run.add_argument("--read-interval-seconds", type=float, default=5.0)
    run.add_argument("--runtime-evidence", type=Path)
    run.add_argument("--ack", required=True)
    return parser


async def _main() -> None:
    args = _parser().parse_args()
    settings = get_settings()
    if args.command == "seed":
        manifest = await seed_synthetic_tenant(
            settings=settings,
            run_id=args.run_id,
            acknowledgement=args.ack,
            manifest_path=args.manifest,
        )
        print(json.dumps({"run_id": manifest.run_id, "participants": PARTICIPANT_COUNT}))
        return
    manifest = load_manifest(args.manifest)
    if args.command == "cleanup":
        result = await cleanup_synthetic_tenant(
            settings=settings,
            manifest=manifest,
            run_id=args.run_id,
            acknowledgement=args.ack,
        )
        print(json.dumps(result))
        return
    report = await run_load_proof(
        settings=settings,
        manifest=manifest,
        run_id=args.run_id,
        acknowledgement=args.ack,
        base_url=args.base_url,
        ramp_seconds=args.ramp_seconds,
        read_interval_seconds=args.read_interval_seconds,
        report_path=args.report,
        runtime_evidence_path=args.runtime_evidence,
    )
    print(json.dumps({"run_id": args.run_id, "successful": report["successful"]}))
    if not report["successful"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(_main())
