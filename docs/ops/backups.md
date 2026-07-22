# Controlled-pilot backups

Codruț backups are encrypted Restic snapshots containing two sources:

- a PostgreSQL custom-format dump created with `pg_dump`;
- the campaign asset volume mounted read-only.

The backup process never copies PostgreSQL data files. A successful command applies the
locked retention policy of 14 daily, 8 weekly, and 6 monthly restore points. Backup,
retention, integrity checks, and restore rehearsal are explicit one-shot commands in
`compose.backup.yaml`.

## Security and preflight

Keep credentials outside the repository in a root-readable environment file or secret
manager. The scripts accept `RESTIC_PASSWORD_FILE`, `AWS_ACCESS_KEY_ID_FILE`,
`AWS_SECRET_ACCESS_KEY_FILE`, and `POSTGRES_PASSWORD_FILE` for mounted secrets. Do not put
the Restic password or Object Storage keys in Compose YAML, shell history, CI output, or
the application `.env` committed to Git.

The Object Storage key should be restricted to the dedicated backup bucket. The Restic
password is independent of the S3 credentials and must be retained in the operational
password manager. Losing it makes the repository unrecoverable.

Required environment:

```dotenv
RESTIC_REPOSITORY=s3:https://fsn1.your-objectstorage.com/your-private-bucket/codrut
RESTIC_PASSWORD_FILE=/run/secrets/restic_password
AWS_ACCESS_KEY_ID_FILE=/run/secrets/hetzner_access_key
AWS_SECRET_ACCESS_KEY_FILE=/run/secrets/hetzner_secret_key
AWS_DEFAULT_REGION=eu-central-1
POSTGRES_DB=codrut
POSTGRES_USER=codrut
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

Use the Hetzner location endpoint assigned to the bucket, such as `fsn1`, `nbg1`, or
`hel1`. The `s3:https://...` prefix is required by Restic. No bucket is created by these
scripts.

Before enabling the schedule:

1. Confirm the bucket exists, versioning and access policy are intentional, and the host
   can reach the endpoint.
2. Confirm the PostgreSQL user can run `pg_dump` and the campaign asset volume is
   readable.
3. When using file-based secrets, mount their directory read-only at `/run/secrets` and
   make the files readable only by the backup container's `postgres` user (UID 999).
4. Run the plan commands. Plans validate configuration but do not contact PostgreSQL or
   S3 and never print secret values.

```bash
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup backup --plan
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup check --plan
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup retention --plan
```

For file-based secrets, add
`-v /etc/codrut/backup-secrets:/run/secrets:ro` to each `docker compose run` command. A
root-owned systemd environment file may instead provide the direct variables to Compose;
it must never be stored in the checkout.

## Initialize and back up

Initialization is explicit. It fails rather than silently replacing an existing or
unreachable repository.

```bash
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup init
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup backup
```

`backup` first verifies the repository and PostgreSQL connection, creates a private
temporary dump, checks that it is non-empty, and records a versioned validation manifest.
The manifest pins the Alembic head, critical table row counts, campaign asset count, and
one SHA-256 digest per asset. Restic then stores the dump, manifest, and read-only asset
directory in one encrypted snapshot. The temporary dump is removed on success and
failure. If `pg_dump` or manifest collection fails, Restic is not invoked. If Restic
fails, retention is not invoked. Every failure is reported to stderr and returns a
non-zero status suitable for systemd alerting.

Set `CODRUT_BACKUP_APPLY_RETENTION=false` only when retention runs in a separate managed
job. The independent command remains:

```bash
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup retention
```

## Integrity checks

The default check reads repository metadata and a 5 percent data subset. Run it weekly.
Run a full data check monthly or before a high-risk migration.

```bash
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup check
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup check --full
docker compose -f compose.yaml -f compose.backup.yaml run --rm backup check --metadata
```

A failed check is a launch blocker. Do not prune additional snapshots until the failure
is understood and a known-good restore point is identified.

## Isolated restore rehearsal

The rehearsal service restores files into a new directory in the dedicated
`backup_rehearsal_workspace` volume. It then creates a new database in an ephemeral
PostgreSQL container backed by `tmpfs`. The script refuses a target PostgreSQL host equal
to the source host, refuses the source database name, refuses an existing target database,
and refuses an existing filesystem target. It never writes restored assets to the live
campaign asset volume.

```bash
docker compose \
  -f compose.yaml \
  -f compose.backup.yaml \
  --profile backup-rehearsal \
  up --build --abort-on-container-exit --exit-code-from backup-rehearsal backup-rehearsal

docker compose \
  -f compose.yaml \
  -f compose.backup.yaml \
  --profile backup-rehearsal \
  run --rm --no-deps backup-rehearsal evidence
```

The rehearsal rejects a missing or mismatched Alembic head, critical row count, foreign
key set, validated integrity constraint, asset count, or asset hash. The evidence file
records completion time, target identity, migration head, table and foreign-key counts,
critical object counts, and asset count without credentials. Capture it before stopping
the rehearsal stack. The ephemeral database disappears when its container stops. Remove
the dedicated rehearsal volume only after evidence has been archived:

```bash
docker compose -f compose.yaml -f compose.backup.yaml --profile backup-rehearsal down
docker volume rm "${COMPOSE_PROJECT_NAME:-codrut-platform}_backup_rehearsal_workspace"
```

Do not use `down -v` against the main Codruț project.

## Scheduling

Deployable systemd units are tracked in `infra/backup/systemd`. They use a single
non-blocking `flock` lock so backup and integrity jobs cannot overlap, run the backup
container as a one-shot process, and leave scheduling failures visible to systemd.
Install them only on the intended VPS after reviewing the paths:

```bash
sudo install -m 0644 infra/backup/systemd/codrut-backup.service /etc/systemd/system/
sudo install -m 0644 infra/backup/systemd/codrut-backup.timer /etc/systemd/system/
sudo install -m 0644 infra/backup/systemd/codrut-backup-check.service /etc/systemd/system/
sudo install -m 0644 infra/backup/systemd/codrut-backup-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codrut-backup.timer codrut-backup-check.timer
sudo systemctl list-timers 'codrut-backup*'
```

Keep `/etc/codrut/backup.env` root-owned with mode `0600`, and keep mounted secret files
under `/etc/codrut/backup-secrets`. Test both services manually before enabling timers:

```bash
sudo systemctl start codrut-backup.service
sudo systemctl status codrut-backup.service
sudo systemctl start codrut-backup-check.service
sudo journalctl -u codrut-backup.service -u codrut-backup-check.service
```

Route non-zero unit exits and missed timers to the operations alert channel. The tracked
units do not configure an alert provider because that is infrastructure-specific. A cron
installation is acceptable when systemd is unavailable, but must use `flock`, an absolute
Compose path, the same protected environment file, and alert on non-zero exit. Never allow
overlapping backup jobs.

## Launch evidence caveat

Passing unit tests, Compose validation, and `--plan` is not backup evidence. Before the
controlled pilot, operations must run an actual encrypted backup and isolated restore
rehearsal against a scrubbed production-shaped snapshot, archive the evidence file and
command transcript, verify representative row counts and campaign assets, and record the
measured backup and restore durations. A successful live repository integrity check and
documented access to the Restic password are also required launch evidence.
