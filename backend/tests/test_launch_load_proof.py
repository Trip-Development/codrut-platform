from __future__ import annotations

import os
import stat
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from codrut.modules.communications.models import EmailSendStatus
from codrut.modules.identity.session_cookie import SESSION_COOKIE_NAME
from codrut.tools.launch_load_proof import (
    ACKNOWLEDGEMENT,
    CSRF_COOKIE_NAME,
    FORMAT_VERSION,
    PARTICIPANT_COUNT,
    AbortController,
    LoadProofManifest,
    MetricsRecorder,
    ParticipantManifest,
    ResourceExtrema,
    ResourceSample,
    _read_runtime_evidence,
    _request,
    _require_no_unrelated_outbox_activity,
    _require_outbox_capacity,
    _resource_evidence_failure,
    _runtime_evidence_failure,
    _summarize_outbox_statuses,
    _write_private_json,
    evaluate_acceptance,
    evaluate_live_thresholds,
    exercise_participant,
    require_guard,
    synthetic_tag,
    validate_manifest,
    validate_manifest_runtime,
)


def _manifest() -> LoadProofManifest:
    run_id = "launch-2026-07-30"
    tag = synthetic_tag(run_id)
    participants = tuple(
        ParticipantManifest(
            index=index,
            user_id=str(uuid4()),
            profile_id=str(uuid4()),
            assignment_id=str(uuid4()),
            invite_id=str(uuid4()),
            email_send_id=str(uuid4()),
            email=f"load-proof-{run_id}-{index:04d}@example.com",
            token=f"signed-token-{index}",
            answers={"q1": 4},
        )
        for index in range(1, PARTICIPANT_COUNT + 1)
    )
    return LoadProofManifest(
        format_version=FORMAT_VERSION,
        run_id=run_id,
        tag=tag,
        created_at="2026-07-30T10:00:00+00:00",
        environment="test",
        database_name="codrut_test",
        owner_user_id=str(uuid4()),
        owner_email=f"load-proof-owner-{run_id}@example.com",
        owner_password="random-owner-password-" + ("x" * 32),
        company_id=str(uuid4()),
        company_name=f"[{tag}] Synthetic Tenant",
        project_id=str(uuid4()),
        project_name=f"[{tag}] Participant Load Proof",
        definition_id=str(uuid4()),
        definition_key="load_proof_launch_2026_07_30",
        participants=participants,
    )


def test_manifest_requires_exact_tagged_1_000_participant_scope() -> None:
    manifest = _manifest()

    validate_manifest(manifest, expected_run_id=manifest.run_id)

    with pytest.raises(RuntimeError, match="exactly 1000"):
        validate_manifest(replace(manifest, participants=manifest.participants[:-1]))
    duplicated = replace(
        manifest.participants[1],
        user_id=manifest.participants[0].user_id,
    )
    with pytest.raises(RuntimeError, match="Duplicate user"):
        validate_manifest(
            replace(
                manifest,
                participants=(manifest.participants[0], duplicated)
                + manifest.participants[2:],
            )
        )
    duplicated_send = replace(
        manifest.participants[1],
        email_send_id=manifest.participants[0].email_send_id,
    )
    with pytest.raises(RuntimeError, match="Duplicate email_send"):
        validate_manifest(
            replace(
                manifest,
                participants=(manifest.participants[0], duplicated_send)
                + manifest.participants[2:],
            )
        )


def test_manifest_runtime_must_match_environment_and_database() -> None:
    manifest = _manifest()
    settings = SimpleNamespace(
        env="test",
        database_url="postgresql+asyncpg://user:pass@db/codrut_test",
    )

    validate_manifest_runtime(manifest, settings)

    with pytest.raises(RuntimeError, match="environment"):
        validate_manifest_runtime(replace(manifest, environment="production"), settings)
    with pytest.raises(RuntimeError, match="database"):
        validate_manifest_runtime(replace(manifest, database_name="other"), settings)


def test_runtime_evidence_is_fresh_and_fails_on_restart_timeout_or_oom(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_path = tmp_path / "runtime.env"
    monkeypatch.setattr("codrut.tools.launch_load_proof.time.time", lambda: 1_000)
    evidence_path.write_text(
        "\n".join(
            (
                "captured_at_epoch=995",
                "backend_id=backend",
                "backend_restart_count=0",
                "backend_oom_killed=false",
                "backend_started_at=api-start",
                "backend_pool_timeout_count=0",
                "worker_id=worker",
                "worker_restart_count=0",
                "worker_oom_killed=false",
                "worker_started_at=worker-start",
                "worker_pool_timeout_count=0",
            )
        ),
        encoding="utf-8",
    )
    baseline = _read_runtime_evidence(evidence_path, production=True)

    assert baseline is not None
    assert _runtime_evidence_failure(baseline, baseline) is None
    assert (
        _runtime_evidence_failure(
            baseline,
            replace(baseline, worker_restart_count=1),
        )
        == "API or worker container restarted during the proof"
    )
    assert (
        _runtime_evidence_failure(
            baseline,
            replace(baseline, worker_pool_timeout_count=1),
        )
        == "database pool timeout detected"
    )
    assert (
        _runtime_evidence_failure(
            baseline,
            replace(baseline, backend_pool_timeout_count=1),
        )
        == "database pool timeout detected"
    )
    assert (
        _runtime_evidence_failure(
            baseline,
            replace(baseline, backend_oom_killed=True),
        )
        == "API or worker container reported an OOM kill"
    )


def test_resource_extrema_records_production_evidence() -> None:
    extrema = ResourceExtrema()
    extrema.record(ResourceSample(cpu_percent=None, free_memory_bytes=10, disk_percent=40))
    extrema.record(ResourceSample(cpu_percent=75, free_memory_bytes=5, disk_percent=60))

    assert extrema.report() == {
        "samples": 2,
        "max_cpu_percent": 75,
        "min_free_memory_bytes": 5,
        "max_disk_percent": 60,
    }
    assert _resource_evidence_failure(extrema, production=True) is None


def test_production_resource_evidence_fails_closed_when_incomplete() -> None:
    extrema = ResourceExtrema()
    extrema.record(ResourceSample(cpu_percent=None, free_memory_bytes=10, disk_percent=40))

    assert _resource_evidence_failure(extrema, production=False) is None
    assert (
        _resource_evidence_failure(extrema, production=True)
        == "host CPU and memory evidence was not sampled completely"
    )


def test_production_guard_requires_maintenance_sandbox_ack_and_run_id() -> None:
    safe_settings = SimpleNamespace(
        is_production=True,
        maintenance_mode=True,
        email_brevo_sandbox_enabled=True,
        email_provider="brevo",
        maintenance_bypass_token=SimpleNamespace(
            get_secret_value=lambda: "m" * 32,
        ),
    )
    require_guard(
        safe_settings,
        run_id="launch-2026-07-30",
        acknowledgement=ACKNOWLEDGEMENT,
        operation="seeding",
    )

    with pytest.raises(RuntimeError, match="maintenance_mode"):
        require_guard(
            SimpleNamespace(**{**safe_settings.__dict__, "maintenance_mode": False}),
            run_id="launch-2026-07-30",
            acknowledgement=ACKNOWLEDGEMENT,
            operation="cleanup",
        )
    with pytest.raises(RuntimeError, match="sandbox"):
        require_guard(
            SimpleNamespace(
                **{**safe_settings.__dict__, "email_brevo_sandbox_enabled": False}
            ),
            run_id="launch-2026-07-30",
            acknowledgement=ACKNOWLEDGEMENT,
            operation="cleanup",
        )
    with pytest.raises(RuntimeError, match="--ack"):
        require_guard(
            safe_settings,
            run_id="launch-2026-07-30",
            acknowledgement="yes",
            operation="cleanup",
        )


def test_outbox_capacity_preflight_requires_launch_settings() -> None:
    _require_outbox_capacity(
        SimpleNamespace(
            email_daily_send_cap=2_000,
            email_outbox_batch_size=100,
            email_outbox_concurrency=8,
        )
    )

    with pytest.raises(RuntimeError, match="2,000-message"):
        _require_outbox_capacity(
            SimpleNamespace(
                email_daily_send_cap=1_999,
                email_outbox_batch_size=100,
                email_outbox_concurrency=8,
            )
        )


async def test_load_proof_refuses_unrelated_outbox_activity() -> None:
    class FakeSession:
        async def scalar(self, _statement):
            return 1

    with pytest.raises(RuntimeError, match="Unrelated email outbox activity"):
        await _require_no_unrelated_outbox_activity(
            FakeSession(),
            exact_send_ids={uuid4()},
            since=datetime.now(UTC),
        )


def test_metrics_include_percentiles_errors_and_automatic_abort_thresholds() -> None:
    recorder = MetricsRecorder()
    for duration in range(1, 101):
        recorder.record("definition_read", float(duration), 200)
    recorder.record("definition_read", 101.0, 429)
    report = recorder.report()

    operation = report["operations"]["definition_read"]
    assert operation["p50_ms"] == 51.0
    assert operation["p95_ms"] == 96.0
    assert operation["p99_ms"] == 100.0
    assert operation["errors"] == 1
    assert operation["rate_limited"] == 1
    assert evaluate_live_thresholds(report) == (
        "received HTTP 429 for a valid distinct secure-link session"
    )


def test_acceptance_requires_each_initial_operation_exactly_1_000_times() -> None:
    recorder = MetricsRecorder()
    for operation in (
        "invite_verify",
        "invite_exchange",
        "definition_read",
        "task_read",
        "autosave",
        "submit",
        "post_submit_read",
        "trainer_aggregate_result_read",
    ):
        expected_count = 1 if operation == "trainer_aggregate_result_read" else PARTICIPANT_COUNT
        for _ in range(expected_count):
            recorder.record(operation, 10.0, 200)

    assert evaluate_acceptance(recorder.report()) == []

    recorder.record("submit", 10.0, 200)
    assert any("submit" in failure for failure in evaluate_acceptance(recorder.report()))


def test_outbox_summary_requires_all_1_000_sandbox_sends_to_succeed() -> None:
    counts, successful, failed = _summarize_outbox_statuses(
        [EmailSendStatus.accepted] * 999 + [EmailSendStatus.dispatching]
    )

    assert counts == {"accepted": 999, "dispatching": 1}
    assert successful == 999
    assert failed == 0

    _counts, successful, failed = _summarize_outbox_statuses(
        [EmailSendStatus.delivered] * 999 + [EmailSendStatus.indeterminate]
    )
    assert successful == 999
    assert failed == 1


async def test_machine_readable_database_pool_timeout_aborts_load() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={
                "error": {
                    "code": "database_pool_timeout",
                    "message": "Database unavailable.",
                }
            },
        )

    abort = AbortController()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await _request(
                client,
                MetricsRecorder(),
                abort,
                "task_read",
                "GET",
                "https://codrut.example/api/participants/tasks",
            )

    assert abort.reason == "database pool timeout detected"


async def test_participant_flow_exercises_security_and_submission_endpoints() -> None:
    participant = _manifest().participants[0]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/api/auth/invite/verify":
            return httpx.Response(
                200,
                json={"tasks": [{"assignment_id": participant.assignment_id}]},
            )
        if path == "/api/auth/invite/exchange":
            return httpx.Response(
                200,
                headers=[
                    ("set-cookie", f"{SESSION_COOKIE_NAME}=session-value; Path=/; HttpOnly"),
                    ("set-cookie", f"{CSRF_COOKIE_NAME}=csrf-value; Path=/"),
                ],
                json={"action": "secure_link_ready"},
            )
        if path.endswith("/definition"):
            return httpx.Response(200, json={"key": "load_proof"})
        if path.endswith("/response/submit"):
            return httpx.Response(200, json={"status": "submitted"})
        if request.method == "PUT":
            return httpx.Response(200, json={"status": "draft"})
        if path.endswith("/response"):
            status_value = "submitted" if any(
                prior.url.path.endswith("/response/submit") for prior in requests
            ) else "draft"
            return httpx.Response(200, json={"status": status_value})
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await exercise_participant(
            client,
            base_url="https://codrut.example",
            participant=participant,
            maintenance_headers={"X-Codrut-Maintenance-Token": "bypass"},
            recorder=MetricsRecorder(),
            abort=AbortController(),
        )

    assert [request.method for request in requests] == [
        "GET",
        "POST",
        "GET",
        "GET",
        "PUT",
        "POST",
        "GET",
    ]
    mutation_requests = [request for request in requests if request.method in {"PUT", "POST"}][1:]
    assert mutation_requests
    for request in mutation_requests:
        assert request.headers["x-csrf-token"] == "csrf-value"
        assert f"{SESSION_COOKIE_NAME}=session-value" in request.headers["cookie"]
        assert request.headers["x-codrut-maintenance-token"] == "bypass"


def test_private_json_refuses_overwrite_and_uses_owner_only_permissions(
    tmp_path: Path,
) -> None:
    output = tmp_path / "manifest.json"

    _write_private_json(output, {"secret": "token"}, refuse_overwrite=True)

    assert stat.S_IMODE(os.stat(output).st_mode) == 0o600
    with pytest.raises(FileExistsError):
        _write_private_json(output, {"secret": "replacement"}, refuse_overwrite=True)
