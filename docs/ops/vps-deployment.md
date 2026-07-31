# VPS Deployment

Production deployment uses the same base Compose topology with the production
overlay:

```sh
docker compose -f compose.yaml -f compose.prod.yaml config
docker compose -f compose.yaml -f compose.prod.yaml pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --force-recreate --no-build --pull never --remove-orphans --wait backend worker frontend
```

Secrets must be supplied through environment files or GitHub Environment secrets on the VPS, never committed to the repository.

## Release Gate

Production releases follow the repo branch policy:

1. Merge feature PRs into `dev`.
2. Open the release PR from `dev` into `prod`.
3. Let the release tree and exact-candidate checks pass.
4. Merge the `dev -> prod` PR. The `VPS Deployment` workflow deploys only from
   `refs/heads/prod`.

Routine production merge commits are not back-merged into `dev`. The `prod`
branch uses loose required status checks, while `release / required` proves
that the exact `dev` head has a successful immutable candidate and that the
proposed merge tree is identical to the `dev` tree. This keeps both long-lived
branches without ancestry-sync PRs.

Route emergency fixes through a focused PR into `dev`, then promote `dev`
normally. Direct `hotfix/* -> prod` releases are intentionally rejected because
production-only content would require a back-merge and make the next release
ambiguous.

The deploy workflow also allows `workflow_dispatch`, but the run must execute
from `refs/heads/prod` and requires `confirm_prod_ref=prod`. Dispatching the
workflow from another branch fails before images are built.

Treat the `prod` GitHub Environment as the secret boundary. Do not use manual
dispatch to promote unmerged feature refs or branches other than `dev`.

## Current Production Checkpoint

The 2026-06-11 client-ready production checkpoint was:

- Feature PR into `dev`, then release PR from `dev` into `prod`.
- Production deployment through `VPS Production Deployment`.
- Public health checks passed for:
  - `${CODRUT_PUBLIC_APP_URL}/api/health/live`
  - `${CODRUT_PUBLIC_APP_URL}/api/health/ready`
- Public `/` and `/login` loaded without server-side exception digests.
- Protected trainer and participant routes redirected to `/login` without
  server-side exception digests.

Core workflow verification for that checkpoint covered:

- Roster import without automatic invite sending.
- Default assignment plan generation and duplicate-safe save.
- Secure link generation separate from email sending.
- Local Mailpit transactional email smoke.
- Questionnaire save/submit.
- Lencioni, Distress Drivers, and 360 iCARE scoring/aggregation.

## Required Checks

Use the aggregate job names in GitHub branch protection or rulesets. They are
stable wrappers around the lower-level jobs, so renaming or splitting internal
jobs does not silently weaken the policy.

For PRs into `dev`, require:

- `app-ci / required`
- `security / required`

For PRs into `prod`, require:

- `release / required`

Feature PR checks are risk-scoped instead of running every suite for every
change:

- backend changes run Ruff, a fresh migration, and backend tests without the
  slower coverage pass;
- database changes additionally run Alembic drift validation;
- API contract changes additionally verify the OpenAPI snapshot and generated
  frontend types;
- frontend changes run lint, type checking, and unit tests; the production
  build is proven once by the immutable `dev` candidate;
- workflow/script changes run only the automation helper tests plus shell and
  workflow-YAML parsing;
- public API contract generation runs only for router, schema, application
  entrypoint, dependency, or committed contract changes.

The `Dev Candidate` has one job: build the deployable immutable images once.
Coverage, full builds, broad suites, and browser automation are local/on-demand
diagnostics, not blocking passes repeated on every PR.
Native CodeQL remains the code-scanning gate. Human/Codex review is requested
when the diff benefits from it instead of running another automatic scan.

Use loose required status checks for `dev` and `prod`. `app-ci / required`,
`security / required`, and native CodeQL run only on feature PRs into `dev`.

After a change lands on `dev`, `Dev Candidate` builds SHA-tagged images once,
without running a second application test layer. The production PR does not
rerun checks or rebuild images. `release / required` accepts only `dev`, locates
the successful candidate for the exact proposed SHA, and verifies that the
`prod + dev` merge tree equals the `dev` tree.

## Images

The deployment workflows separate build and deploy work:

- `_image-build.yml` builds backend/frontend images with BuildKit cache.
  `Dev Candidate` uses it to push the SHA-tagged release candidate once.
- `_deploy-vps.yml` runs behind the selected GitHub Environment, consumes the exact
  candidate image refs, pre-pulls both images, stages `.env.next`, migrates,
  atomically promotes the staged environment, recreates app services, asserts
  running image refs, and checks health. Compose commands inside the SSH
  heredoc close stdin so they cannot consume the remaining deployment script.
- `deploy-vps.yml` is the production caller. `deploy-staging.yml` retains its
  historical filename but now only builds the immutable `dev` candidate.

Backend and frontend images are tagged with immutable `sha-<commit>` refs:

```text
ghcr.io/<owner>/<repo>-backend:sha-<sha>
ghcr.io/<owner>/<repo>-frontend:sha-<sha>
```

The VPS `.env` stores those SHA image refs in `BACKEND_IMAGE` and
`FRONTEND_IMAGE`. It does not deploy `latest`.

Production manual dispatch validates `refs/heads/prod` before resolving the
existing candidate images. The reusable deploy workflow repeats that guard
before SSH deploy.

Required GitHub secrets for the `VPS Deployment` workflow:

- `SSH_PRIVATE_KEY`, `HETZNER_VPS_IP`, `SSH_USER`
- `CODRUT_HOST`
- `TRAEFIK_ACME_EMAIL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `CODRUT_REDIS_URL`
- `CODRUT_SESSION_SECRET`
- `CODRUT_TASK_LINK_SECRET`
- `CODRUT_CAMPAIGN_ASSET_SIGNING_SECRET`
- `CODRUT_EMAIL_SUPPRESSION_FINGERPRINT_SECRET`
- `CODRUT_CORS_ORIGINS`
- `CODRUT_PUBLIC_APP_URL`
- `CODRUT_EMAIL_PROVIDER`
- `CODRUT_EMAIL_FROM_ADDRESS`
- `CODRUT_EMAIL_FROM_NAME`
- `CODRUT_EMAIL_BREVO_API_KEY`
- `CODRUT_EMAIL_WEBHOOK_TOKEN`
- `CODRUT_RATE_LIMIT_TRUSTED_PROXIES`
- `CODRUT_DB_VOLUME_PATH`

Optional environment secrets:

- `CODRUT_DEPLOY_DIR` defaults to `/opt/codrut-platform`.
- `CODRUT_COMPOSE_PROJECT_NAME` defaults to `codrut-platform`.
- `CODRUT_MIGRATION_LOCK_TIMEOUT_MS` defaults to `5000` so deployment fails
  instead of waiting indefinitely for a conflicting database lock.
- `CODRUT_MIGRATION_STATEMENT_TIMEOUT_MS` defaults to `900000` and bounds the
  total execution time of any migration statement.
- `CODRUT_CAMPAIGN_RECIPIENT_ARCHIVE_RETENTION_DAYS` defaults to `30`.
- `CODRUT_CAMPAIGN_RECIPIENT_DELIVERY_RECONCILIATION_DAYS` defaults to `7`.
- `CODRUT_CAMPAIGN_RECIPIENT_PURGE_ENABLED` defaults to `true` for the
  fingerprint-aware application. During its expand rollout, suppression rows
  still retain normalized emails for compatibility with the previous image;
  the later contract release removes them only after this application becomes
  the retained rollback.
- `CODRUT_CAMPAIGN_DELIVERY_TOMBSTONE_RETENTION_DAYS` defaults to `365` and
  bounds late-provider lookup receipts independently of do-not-contact review.
- `CODRUT_EMAIL_SUPPRESSION_REVIEW_DAYS` defaults to `365`.

For the current single-host Compose deployment, the workflow derives
`CODRUT_DATABASE_URL` from the `POSTGRES_*` secrets and writes the database into a
`postgres-data` subdirectory under the Hetzner volume path.

`CODRUT_DB_VOLUME_PATH` should point at the mounted Hetzner volume root, for example:

```text
/mnt/HC_Volume_105944446
```

Set `CODRUT_PUBLIC_APP_URL` to the final HTTPS origin, for example:

```text
https://app.example.com
```

The session, task-link, campaign-asset, suppression-fingerprint, and Brevo
webhook secrets must each contain at least 32 characters and must be different.
Generate the suppression-fingerprint secret once with a cryptographically
secure generator, for example `openssl rand -hex 32`, store it in the production
secret manager, and back it up with the other recovery credentials. It must be
present before the contact-archive migration or application rollout. Do not
replace it during a routine deploy: changing it makes existing do-not-contact
fingerprints unreachable. Follow the controlled procedure in
[Contact data retention and suppression](contact-data-retention.md) if
compromise requires rotation.

Production accepts only the `brevo` email provider and fails startup when the
Brevo API key or webhook bearer token is missing.

Configure the Brevo outbound webhook after the release is reachable over HTTPS:

1. Create an independent high-entropy token and store the same value as the
   `CODRUT_EMAIL_WEBHOOK_TOKEN` secret in the `prod` GitHub Environment.
2. In Brevo, open Integrations, Webhooks, add an outbound webhook, and choose the
   Transactional email category.
3. Set the URL to
   `${CODRUT_PUBLIC_APP_URL}/api/communications/webhooks/brevo`.
4. Select token authentication and enter the webhook token. Do not reuse the
   Brevo API key, session secret, or link-signing secrets.
5. Enable request/sent, delivered, opened, clicked, soft and hard bounce,
   blocked, invalid, error, unsubscribe, and spam/complaint events.
6. Send one event at a time, activate the webhook, and run Brevo's test request
   after deployment. A valid callback returns HTTP 200; a missing or incorrect
   token returns HTTP 401.

Brevo documents bearer-token webhook authentication at
<https://developers.brevo.com/docs/secured-webhooks>.

Set `CODRUT_CORS_ORIGINS` as a JSON array, not a comma-separated string:

```text
["https://app.example.com"]
```

Before using real participant data, verify:

- HTTPS and routing through Traefik.
- Postgres backup and restore.
- Redis persistence expectations.
- Application logs and restart policy.
- Production Compose validation against the staged candidate configuration.

## Deployment Checks

PR infrastructure checks validate `compose.yaml` plus `compose.prod.yaml`.
The `Dev Candidate` workflow builds immutable images, and the production
workflow refuses to rebuild a missing candidate. The `deploy-vps` job copies both Compose files to
`/opt/codrut-platform`, checks capacity, pulls the SHA-tagged images, and stages
the candidate configuration as `.env.next`. It validates Compose and runs
migrations against that staged configuration before atomically replacing the
live `.env` and force-recreating only the app services
(`backend`, `worker`, and `frontend`) with
`docker compose up -d --force-recreate --no-build --pull never --wait backend worker frontend`
when the installed Compose version supports it. `--no-build --pull never` makes
the rollout use the exact images that were just pulled instead of rebuilding or
implicitly changing refs during startup. The database, Redis, and Traefik
containers are not force-recreated during ordinary app rollouts. The migration
step and every Compose exec disable container stdin so they cannot consume the
remaining SSH deploy script before the app service recreate runs. Alembic
applies transaction-local PostgreSQL lock and statement timeouts before running
any online migration.

Rollback refs are captured from the images of the running backend, worker, and
frontend containers before `.env.next` is staged. The workflow does not trust a
possibly stale image ref inside `.env` as evidence of the live release. It
preserves the complete prior configuration as mode-`0600` `.env.rollback`, with
its image refs corrected from the actual containers. After cutover, a separate
SSH command reasserts all three running image refs before public readiness can
pass.

Before promotion, `backend/rehearse-production-shape.sh` can recreate the
synthetic `0033` legacy shape, prove bounded lock failure, upgrade through
`0044`, validate owner isolation and duplicate repair, exercise the documented
unsafe rollback boundary, run `alembic check`, and remove its guarded
`*_rehearsal` database. It uses only `.invalid` email addresses and never reads
the active development or production database.

Before any image pull, the deploy runs
`.github/scripts/check_vps_capacity.sh preflight / 85 8` on the VPS. The
deployment stops before downloading layers when root usage is above 85% or
less than 8 GiB is available. A separate daily `VPS Capacity Check` workflow
warns at 80% and fails at 90%. Investigate a warning before the next deploy;
do not solve it with a global Docker prune.

Production Compose bounds every service's `json-file` logs to five 10 MB
files. The API defaults to four Uvicorn workers. Each API process and the
email worker use an explicit SQLAlchemy pool of five connections, five
overflow connections, and a ten-second acquisition timeout.

After startup, the workflow checks:

- Running backend, worker, and frontend container image refs against the
  `BACKEND_IMAGE` and `FRONTEND_IMAGE` values stored in `/opt/codrut-platform/.env`.
  The workflow repeats this assertion in a separate SSH command after the
  remote deploy script returns, so a skipped recreate cannot produce a false
  green deployment.
- Backend readiness inside the VPS container network:
  `http://127.0.0.1:8000/api/health/ready`. Readiness requires PostgreSQL, Redis,
  the current Alembic head, a fresh worker heartbeat, and a healthy outbox backlog.
- A healthy worker container, backed by the same Redis heartbeat.
- Public readiness through the configured app URL:
  `${CODRUT_PUBLIC_APP_URL}/api/health/ready`.

The workflow summary records the deployed release SHA, deployed image refs, and
the previous frontend/backend image refs from the deploy job.

Image retention runs after readiness as best-effort housekeeping. A retention
failure produces a warning and leaves all images in place; it does not turn a
healthy application deployment into a failed release. The daily capacity check
will still expose accumulating disk use.

Only after both internal and public readiness pass, the deploy runs
`.github/scripts/retain_codrut_images.sh`. It first proves that all current and
previous rollback refs exist locally, then removes other tags only from the
resolved Codrut backend and frontend repositories and finally removes
unreferenced dangling layers. It never runs a global image, volume, network, or
system prune. If either previous ref is unavailable, retention is skipped so a
deploy cannot erase its only rollback candidate.

## Rollback

Rollback is manual and image-ref based:

1. Open the failed `VPS Deployment` run summary and copy the previous
   `FRONTEND_IMAGE` and `BACKEND_IMAGE` values.
2. When reverting a database at `0056_email_send_sandbox_scope` to the retained
   `0052_contact_archive` bridge image, announce maintenance and block
   participant and trainer mutations. Leave the current worker running until
   both compatibility counts are zero:

   ```sh
   cd /opt/codrut-platform
   docker compose -f compose.yaml -f compose.prod.yaml exec -T db sh -lc '
     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tAc "
       select '\''sandbox_outbox'\'', count(*)
       from email_sends
       where sandbox_required
         and status in ('\''queued'\'', '\''dispatching'\'')
       union all
       select '\''submission_jobs'\'', count(*)
       from submission_processing_jobs
       where status in ('\''queued'\'', '\''processing'\'');
     "
   '
   ```

   The result must be `0` for both rows. The bridge worker cannot honor
   per-message sandbox delivery and does not process asynchronous submission
   jobs. A nonzero count blocks rollback: resolve sandbox work and let
   submission processing drain under the current image, then rerun the query.
   Once both counts are zero, stop the current worker to close the race before
   changing image refs:

   ```sh
   docker compose -f compose.yaml -f compose.prod.yaml stop worker
   ```

3. SSH into the VPS and edit `/opt/codrut-platform/.env` so those two variables
   point at the previous image refs.
4. Validate and restart:

   ```sh
   cd /opt/codrut-platform
   docker compose -f compose.yaml -f compose.prod.yaml config
   docker compose -f compose.yaml -f compose.prod.yaml pull
   docker compose -f compose.yaml -f compose.prod.yaml up -d --force-recreate --no-build --pull never --remove-orphans --wait backend worker frontend
   ```

   If the installed Compose version does not support `--wait`, use:

   ```sh
   docker compose -f compose.yaml -f compose.prod.yaml up -d --force-recreate --no-build --pull never --remove-orphans backend worker frontend
   ```

5. Verify image refs and health:

   ```sh
   docker compose -f compose.yaml -f compose.prod.yaml ps backend worker frontend
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q backend)" --format '{{ index .Config.Image }}'
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q worker)" --format '{{ index .Config.Image }}'
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q frontend)" --format '{{ index .Config.Image }}'
   docker compose -f compose.yaml -f compose.prod.yaml exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=10).read()"
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q worker)" --format '{{.State.Health.Status}}'
   curl --fail --silent --show-error "${CODRUT_PUBLIC_APP_URL%/}/api/health/ready"
   ```

   The backend and worker image refs must match `BACKEND_IMAGE`; the frontend
   image ref must match `FRONTEND_IMAGE`.

6. Before allowing a later deploy to delete older image tags, exercise the
   rollback once in the maintenance environment: switch to the recorded
   previous refs, recreate the three app services, verify internal and public
   readiness, then switch back to the candidate and repeat the checks. Confirm
   both pairs remain visible with `docker image inspect`.

Rollback to an older application image does not undo database migrations.
Migration `0053_contact_privacy_bridge` deliberately remains expand-only: it
backfills fingerprints while preserving the legacy suppression email and
normalized-email index. The current application dual-reads and dual-writes
both forms, so the immediately previous image can continue to enforce existing
and newly created restrictions during emergency rollback.

Do not run the destructive fingerprint-only contract while an older retained
image still reads or writes the legacy email. Promote and prove the
fingerprint-aware application first, keep it as the rollback image for the
contract release, take and restore a fresh backup, and only then scrub or drop
the compatibility value.

For the contact-archive expand release, archived active contacts are persisted
as `suppressed` with their prior status in the additive schema. The previous
image may display them as inactive, but it cannot select or send to them.
Avoid contact catalog mutations during that temporary rollback; return to the
fingerprint-aware image before resuming campaign operations.
