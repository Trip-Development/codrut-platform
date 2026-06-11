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
3. Let the required aggregate checks pass before merging.
4. Merge the `dev -> prod` PR. The `VPS Deployment` workflow deploys only from
   `refs/heads/prod`.

Emergency production fixes may use a `hotfix/*` branch directly into `prod`
when waiting for a full `dev` promotion would leave production broken. A merged
hotfix must be back-merged into `dev` immediately after the production deploy
passes, so `dev` remains the source of the next normal release.

The deploy workflow also allows `workflow_dispatch`, but the run must execute
from `refs/heads/prod` and requires `confirm_prod_ref=prod`. Dispatching the
workflow from another branch fails before images are built.

Treat the `prod` GitHub Environment as the final approval and secret boundary.
Use the acceptance checklist before opening the release PR; do not use manual
dispatch to promote unmerged feature refs or non-hotfix branches. The staging
workflow exists but is optional/deferred for the current client-ready push unless
`ENABLE_STAGING_DEPLOY=true` is intentionally enabled.

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

## Staging

`VPS Staging Deployment` runs from `dev` when the repository variable
`ENABLE_STAGING_DEPLOY` is set to `true`, and it can also be started manually
with `workflow_dispatch`. It uses the `staging` GitHub Environment, so staging
must have its own environment secrets before automatic deploys are enabled.
Manual staging dispatch is guarded to `refs/heads/dev` by default; use the
`allow_non_dev_ref=true` input only for an explicit test deployment from another
branch.

If staging shares the same VPS host as production, set these staging-only
environment secrets so it does not overwrite production Compose state:

- `CODRUT_DEPLOY_DIR`, for example `/opt/codrut-platform-staging`
- `CODRUT_COMPOSE_PROJECT_NAME`, for example `codrut-platform-staging`

Prefer a separate staging host or database before real client data enters the
system.

## Required Checks

Use the aggregate job names in GitHub branch protection or rulesets. They are
stable wrappers around the lower-level jobs, so renaming or splitting internal
jobs does not silently weaken the policy.

For PRs into `dev`, require:

- `app-ci / required`
- `policy / required`
- `security / required`

For PRs into `prod`, require:

- `app-ci / required`
- `policy / required`
- `security / required`
- `release / required`

`app-ci / required` runs backend, frontend, and Compose checks for PRs into
`dev`. For normal `dev -> prod` promotion PRs it skips those duplicated dev
checks and requires the Playwright E2E job instead. For `hotfix/* -> prod`, it
runs backend, frontend, Compose, and E2E checks because the change bypasses
`dev`. `release / required` then validates the production Compose config and
runtime image builds. `policy / required` allows production PRs only from `dev`
or `hotfix/*`, and skips that source-branch check on non-production PRs.

## Images

The deployment workflows separate build and deploy work:

- `_image-build.yml` builds backend/frontend images with BuildKit cache and can
  either build-only for release gates or push SHA-tagged images for deploys.
- `_deploy-vps.yml` runs behind the selected GitHub Environment, consumes the exact
  image refs from `build-images`, writes the VPS `.env`, pulls those images,
  migrates, recreates app services, asserts running image refs, and checks
  health.
- `deploy-vps.yml` is the production caller. `deploy-staging.yml` is the staging
  caller.

Backend and frontend images are tagged with immutable `sha-<commit>` refs:

```text
ghcr.io/<owner>/<repo>-backend:sha-<sha>
ghcr.io/<owner>/<repo>-frontend:sha-<sha>
```

The VPS `.env` stores those SHA image refs in `BACKEND_IMAGE` and
`FRONTEND_IMAGE`. It does not deploy `latest`.

Production manual dispatch validates `refs/heads/prod` before any image build or
push occurs. The reusable deploy workflow repeats that guard before SSH deploy.

Required GitHub secrets for the `VPS Deployment` workflow:

- `SSH_PRIVATE_KEY`, `HETZNER_VPS_IP`, `SSH_USER`
- `CODRUT_HOST`
- `TRAEFIK_ACME_EMAIL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `CODRUT_REDIS_URL`
- `CODRUT_SESSION_SECRET`
- `CODRUT_CORS_ORIGINS`
- `CODRUT_PUBLIC_APP_URL`
- `CODRUT_EMAIL_PROVIDER`
- `CODRUT_EMAIL_FROM_ADDRESS`
- `CODRUT_EMAIL_FROM_NAME`
- `CODRUT_EMAIL_BREVO_API_KEY`
- `CODRUT_DB_VOLUME_PATH`

Optional environment secrets:

- `CODRUT_DEPLOY_DIR` defaults to `/opt/codrut-platform`.
- `CODRUT_COMPOSE_PROJECT_NAME` defaults to `codrut-platform`.

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

Set `CODRUT_CORS_ORIGINS` as a JSON array, not a comma-separated string:

```text
["https://app.example.com"]
```

Before using real participant data, verify:

- HTTPS and routing through Traefik.
- Postgres backup and restore.
- Redis persistence expectations.
- Application logs and restart policy.
- Internal staging acceptance from the June release checklist.

## Deployment Checks

The `build-images` job validates `compose.yaml` plus `compose.prod.yaml` before
building images. The `deploy-vps` job copies both Compose files to
`/opt/codrut-platform`, writes the production `.env`, validates Compose again on
the VPS, pulls the SHA-tagged images, runs migrations, and force-recreates only
the app services
(`backend`, `worker`, and `frontend`) with
`docker compose up -d --force-recreate --no-build --pull never --wait backend worker frontend`
when the installed Compose version supports it. `--no-build --pull never` makes
the rollout use the exact images that were just pulled instead of rebuilding or
implicitly changing refs during startup. The database, Redis, and Traefik
containers are not force-recreated during ordinary app rollouts. The migration
step disables container stdin so it cannot consume the remaining SSH deploy
script before the app service recreate runs.

After startup, the workflow checks:

- Running backend, worker, and frontend container image refs against the
  `BACKEND_IMAGE` and `FRONTEND_IMAGE` values stored in `/opt/codrut-platform/.env`.
  The workflow repeats this assertion in a separate SSH command after the
  remote deploy script returns, so a skipped recreate cannot produce a false
  green deployment.
- Backend health inside the VPS container network:
  `http://127.0.0.1:8000/api/health/live`.
- Public health through the configured app URL:
  `${CODRUT_PUBLIC_APP_URL}/api/health/live`.

The workflow summary records the deployed release SHA, deployed image refs, and
the previous frontend/backend image refs from the deploy job.

## Rollback

Rollback is manual and image-ref based:

1. Open the failed `VPS Deployment` run summary and copy the previous
   `FRONTEND_IMAGE` and `BACKEND_IMAGE` values.
2. SSH into the VPS and edit `/opt/codrut-platform/.env` so those two variables
   point at the previous image refs.
3. Validate and restart:

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

4. Verify image refs and health:

   ```sh
   docker compose -f compose.yaml -f compose.prod.yaml ps backend worker frontend
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q backend)" --format '{{ index .Config.Image }}'
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q worker)" --format '{{ index .Config.Image }}'
   docker inspect "$(docker compose -f compose.yaml -f compose.prod.yaml ps -q frontend)" --format '{{ index .Config.Image }}'
   docker compose -f compose.yaml -f compose.prod.yaml exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=10).read()"
   curl --fail --silent --show-error "${CODRUT_PUBLIC_APP_URL%/}/api/health/live"
   ```

   The backend and worker image refs must match `BACKEND_IMAGE`; the frontend
   image ref must match `FRONTEND_IMAGE`.

Rollback to an older application image does not undo database migrations. Check
the migration notes before rolling back across schema changes.
