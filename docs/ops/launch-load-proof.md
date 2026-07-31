# Launch load proof

`codrut.tools.launch_load_proof` is the versioned, bounded launch test for the
accepted capacity target: exactly 1,000 secure-link participants, a controlled
ramp, a five-minute hold, and exactly 1,000 sandboxed invitation outbox sends.
Brevo sandbox mode is a mandatory production safety gate. Sandbox requests
exercise the provider boundary without delivering messages or creating normal
Brevo email logs.

Do not run this during normal use. Production seeding, execution, and cleanup
require all of the following:

- `CODRUT_ENV=production`
- `CODRUT_MAINTENANCE_MODE=true`
- `CODRUT_EMAIL_BREVO_SANDBOX_ENABLED=true`
- the configured maintenance bypass token
- an explicit run ID
- the exact acknowledgement
  `I_UNDERSTAND_CODEX_SYNTHETIC_LOAD_PROOF_V1`

The tool also requires the acknowledgement outside production. This prevents an
accidental local or staging seed from being mistaken for normal test fixtures.

## What it proves

The seed creates one uniquely tagged company and project, one versioned,
supported Lencioni scoring fixture, and exactly 1,000 guest users. Each participant has
one profile, one project membership, one assignment, one signed secure-link
invite, one held invitation outbox row, and current synthetic consent state.
The seed holds every outbox row in the future so the normal worker cannot drain
it before the measured run begins.

The HTTP phase uses the public application origin and exercises the same
boundaries as the participant browser:

1. invite verification;
2. invite exchange and secure-session cookies;
3. questionnaire definition and response reads;
4. CSRF-protected autosave;
5. CSRF-protected submit acceptance;
6. post-submit read;
7. asynchronous scoring and participant-result publication;
8. one real trainer aggregate result read containing all 1,000 scores;
9. simultaneous definition and submitted-response reads for five minutes.

At run start the tool verifies and releases only the 1,000 outbox IDs in the
manifest. The normal worker must accept or deliver every sandboxed invitation
inside five minutes. The report includes release time, drain duration, and
counts for every outbox status. Seed and run must occur on the same UTC day.
Seeding fails when any normal message is queued or in flight. Release and live
monitoring also fail if a non-synthetic outbox row becomes active or records a
delivery event after the synthetic run was seeded, so maintenance cannot hide
or accidentally deliver a real backlog.
Before release, the tool proves that at least 1,000 messages remain within the
configured 2,000-message daily cap and records capacity before and after the
proof. A failed, bounced, cancelled, indeterminate, missing, or late send fails
the proof.

It records p50, p95, p99, error count, error rate, and HTTP 429 count for every
operation and in aggregate. The run aborts automatically when readiness is
unhealthy for 30 seconds, valid sessions receive a 429, the error rate exceeds
1%, a database pool timeout is reported, local free memory drops below 1 GB,
root disk use exceeds 80%, CPU remains above 90% for one minute, or a live p95
limit is breached. A machine-readable `database_pool_timeout` response aborts
the proof immediately.

Acceptance remains strict:

- read p95 below 750 ms;
- autosave p95 below 1 second;
- submit p95 below 1.5 seconds;
- request failures below 1%;
- no HTTP 429 for valid distinct sessions;
- exactly 1,000 successful initial flows.
- exactly 1,000 accepted or delivered sandbox outbox rows within five minutes.
- exactly 1,000 completed processing jobs, scores, and active result publications.
- one successful trainer aggregate read containing all 1,000 scored assignments.

## Maintenance sequence

Take and restore-test the PostgreSQL backup before seeding. Confirm the normal
email worker is healthy and that no unexpected delivery backlog exists. The
sandbox requirement is persisted on each synthetic outbox row: enabling sandbox
permission never changes delivery behavior for normal messages, while synthetic
rows fail closed if permission is removed.

Run from the deployed Compose directory on the VPS. The host directory is a
persistent, private bind mount; do not use an unmounted one-off container because
its manifest would disappear and make exact cleanup impossible. The host monitor
updates runtime evidence every two seconds. The proof fails if the API or worker
restarts, reports an OOM kill, emits a database-pool timeout, or the evidence
becomes stale.

```bash
set -u
cd /opt/codrut-platform

RUN_ID=launch-2026-08-01
ACK=I_UNDERSTAND_CODEX_SYNTHETIC_LOAD_PROOF_V1
LOAD_PROOF_DIR=/opt/codrut-platform/load-proof
CONTAINER_PROOF_DIR=/app/var/load-proof
MANIFEST=${CONTAINER_PROOF_DIR}/${RUN_ID}.manifest.json
REPORT=${CONTAINER_PROOF_DIR}/${RUN_ID}.report.json
RUNTIME_EVIDENCE=${CONTAINER_PROOF_DIR}/${RUN_ID}.runtime.env
HOST_RUNTIME_EVIDENCE=${LOAD_PROOF_DIR}/${RUN_ID}.runtime.env
MONITOR_STOP=${LOAD_PROOF_DIR}/${RUN_ID}.monitor-stop
COMPOSE_ARGS=(-f compose.yaml -f compose.prod.yaml)

# First set CODRUT_MAINTENANCE_MODE=true,
# CODRUT_EMAIL_BREVO_SANDBOX_ENABLED=true, and a 32+ character
# CODRUT_MAINTENANCE_BYPASS_TOKEN in the deployed .env, then recreate both
# processes so the proof does not rely on stale container configuration.
docker compose "${COMPOSE_ARGS[@]}" up -d --force-recreate backend worker
docker compose "${COMPOSE_ARGS[@]}" exec -T backend python -c \
  "from codrut.core.config import get_settings; s=get_settings(); assert s.maintenance_mode and s.email_brevo_sandbox_enabled"
docker compose "${COMPOSE_ARGS[@]}" exec -T worker python -c \
  "from codrut.core.config import get_settings; assert get_settings().email_brevo_sandbox_enabled"

install -d -m 700 "$LOAD_PROOF_DIR"

rm -f "$MONITOR_STOP"
./monitor_load_proof_runtime.sh "$HOST_RUNTIME_EVIDENCE" "$MONITOR_STOP" &
MONITOR_PID=$!
stop_monitor() {
  touch "$MONITOR_STOP"
  wait "$MONITOR_PID" 2>/dev/null || true
}
trap stop_monitor EXIT INT TERM

if ! docker compose "${COMPOSE_ARGS[@]}" run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$LOAD_PROOF_DIR:$CONTAINER_PROOF_DIR" \
  backend python -m codrut.tools.launch_load_proof seed \
  --run-id "$RUN_ID" \
  --manifest "$MANIFEST" \
  --ack "$ACK"; then
  stop_monitor
  trap - EXIT INT TERM
  exit 1
fi

docker compose "${COMPOSE_ARGS[@]}" run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$LOAD_PROOF_DIR:$CONTAINER_PROOF_DIR" \
  backend python -m codrut.tools.launch_load_proof run \
  --run-id "$RUN_ID" \
  --manifest "$MANIFEST" \
  --report "$REPORT" \
  --runtime-evidence "$RUNTIME_EVIDENCE" \
  --base-url https://codrut.andreivacaru.ro \
  --ramp-seconds 60 \
  --read-interval-seconds 5 \
  --ack "$ACK"

RUN_STATUS=$?
stop_monitor
trap - EXIT INT TERM
```

The manifest contains active invitation tokens. It is created with mode `0600`,
must stay outside Git, and must be handled as a secret until cleanup. The report
is also written with mode `0600` and is never overwritten.

After collecting the report, clean only that exact run while maintenance and
Brevo sandbox remain enabled:

```bash
docker compose "${COMPOSE_ARGS[@]}" run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$LOAD_PROOF_DIR:$CONTAINER_PROOF_DIR" \
  backend python -m codrut.tools.launch_load_proof cleanup \
  --run-id "$RUN_ID" \
  --manifest "$MANIFEST" \
  --ack "$ACK"
CLEANUP_STATUS=$?

test "$RUN_STATUS" -eq 0 && test "$CLEANUP_STATUS" -eq 0
```

Cleanup reads IDs from the manifest and then verifies the exact company name,
project name and tag, questionnaire key and package tag, all 1,000 emails, and
the complete profile, assignment, invite, outbox, participant-user, and
synthetic-owner ID sets. It also rejects owner-scoped communications data
outside the exact outbox fixture. Any partial, additional, renamed, shared, or
mismatched data makes cleanup fail closed. Cleanup cancels only requests which
have not reached the provider and refuses deletion while any exact-row request
is in flight. Outbox rows and their events are deleted by the exact manifest
IDs before the synthetic tenant. It never deletes by prefix,
date, tenant-wide wildcard, or an unresolved shell pattern. A repeated cleanup
is safe only when every manifested database record is already absent.

Keep the manifest and report with the maintenance evidence until the launch
review is complete, then remove those two explicit files through the approved
secret-evidence process. Disable Brevo sandbox, restore normal mutations, run
one controlled real-delivery canary, and recheck public readiness.
