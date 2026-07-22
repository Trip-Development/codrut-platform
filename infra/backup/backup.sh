#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

# shellcheck source=infra/backup/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

plan_only=false
[[ "${1:-}" == "--plan" ]] && plan_only=true

backup_preflight_restic_config
backup_preflight_source_database_config

asset_dir="${BACKUP_ASSET_DIR:-/data/campaign-assets}"
apply_retention="${BACKUP_APPLY_RETENTION:-true}"

if ${plan_only}; then
  backup_log "PLAN: verify the Restic repository and PostgreSQL source."
  backup_log "PLAN: pg_dump '${POSTGRES_DB}' in custom format to a private temporary directory."
  backup_log "PLAN: record the Alembic head, critical table counts, and SHA-256 hashes for every campaign asset."
  backup_log "PLAN: restic backup the database dump and '${asset_dir}' with controlled-pilot tags."
  if backup_is_true "${apply_retention}"; then
    backup_log "PLAN: retain 14 daily, 8 weekly, and 6 monthly restore points."
  else
    backup_log "PLAN: retention is disabled for this invocation."
  fi
  exit 0
fi

backup_require_command pg_dump
backup_require_command pg_isready
backup_require_command psql
backup_require_command cp
backup_require_command restic
backup_require_command sha256sum
backup_require_command sort
backup_require_command xargs
backup_preflight_repository
[[ -d "${asset_dir}" && -r "${asset_dir}" ]] ||
  backup_die "Campaign asset directory '${asset_dir}' is missing or unreadable."

export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
postgres_port="${POSTGRES_PORT:-5432}"

backup_log "Checking PostgreSQL source availability."
if ! pg_isready \
  --host "${POSTGRES_HOST}" \
  --port "${postgres_port}" \
  --username "${POSTGRES_USER}" \
  --dbname "${POSTGRES_DB}" >/dev/null; then
  backup_die "PostgreSQL source is unavailable; no snapshot was created."
fi

staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/codrut-backup.XXXXXX")"
cleanup() {
  rm -rf -- "${staging_dir}"
}
trap cleanup EXIT

mkdir -p \
  "${staging_dir}/database" \
  "${staging_dir}/metadata" \
  "${staging_dir}/assets/campaign-assets"
dump_path="${staging_dir}/database/codrut.dump"
manifest_path="${staging_dir}/metadata/manifest.txt"
asset_hashes_path="${staging_dir}/metadata/campaign-assets.sha256"
staged_asset_dir="${staging_dir}/assets/campaign-assets"
created_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

backup_source_scalar() {
  local query="$1"
  psql \
    --host "${POSTGRES_HOST}" \
    --port "${postgres_port}" \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --tuples-only \
    --no-align \
    --set ON_ERROR_STOP=1 \
    --command "${query}" | tr -d '[:space:]'
}

critical_tables=(
  users
  companies
  participant_profiles
  questionnaire_assignments
  campaigns
  email_sends
)
alembic_head_before="$(backup_source_scalar "SELECT version_num FROM alembic_version")"
declare -A critical_counts_before=()
for table_name in "${critical_tables[@]}"; do
  critical_counts_before["${table_name}"]="$(
    backup_source_scalar "SELECT count(*) FROM ${table_name}"
  )"
done

backup_log "Creating PostgreSQL custom-format dump."
if ! pg_dump \
  --host "${POSTGRES_HOST}" \
  --port "${postgres_port}" \
  --username "${POSTGRES_USER}" \
  --dbname "${POSTGRES_DB}" \
  --format custom \
  --no-password \
  --file "${dump_path}"; then
  backup_die "pg_dump failed; the temporary dump will be removed and Restic will not run."
fi
[[ -s "${dump_path}" ]] || backup_die "pg_dump produced an empty archive; Restic will not run."

alembic_head="$(backup_source_scalar "SELECT version_num FROM alembic_version")"
[[ "${alembic_head}" =~ ^[A-Za-z0-9_]+$ ]] ||
  backup_die "The source database does not have one valid Alembic head."
[[ "${alembic_head}" == "${alembic_head_before}" ]] ||
  backup_die "The database migration head changed during pg_dump; refusing an ambiguous snapshot."

declare -A critical_counts=()
for table_name in "${critical_tables[@]}"; do
  count="$(backup_source_scalar "SELECT count(*) FROM ${table_name}")"
  [[ "${count}" =~ ^[0-9]+$ ]] ||
    backup_die "Could not record a valid row count for ${table_name}."
  [[ "${count}" == "${critical_counts_before[${table_name}]}" ]] ||
    backup_die "The ${table_name} row count changed during pg_dump; refusing an ambiguous snapshot."
  critical_counts["${table_name}"]="${count}"
done

backup_log "Copying campaign assets into the private snapshot staging directory."
cp -a "${asset_dir}/." "${staged_asset_dir}/"
(
  cd "${staged_asset_dir}"
  find . -type f -print0 | sort -z | xargs -0 -r sha256sum
) >"${asset_hashes_path}"
asset_count="$(wc -l <"${asset_hashes_path}" | tr -d '[:space:]')"

printf '%s\n' \
  "format=codrut-controlled-pilot-v2" \
  "created_at=${created_at}" \
  "database=${POSTGRES_DB}" \
  "assets=/assets/campaign-assets" \
  "alembic_head=${alembic_head}" \
  "count.users=${critical_counts[users]}" \
  "count.companies=${critical_counts[companies]}" \
  "count.participant_profiles=${critical_counts[participant_profiles]}" \
  "count.questionnaire_assignments=${critical_counts[questionnaire_assignments]}" \
  "count.campaigns=${critical_counts[campaigns]}" \
  "count.email_sends=${critical_counts[email_sends]}" \
  "count.campaign_assets=${asset_count}" \
  >"${manifest_path}"

backup_host="${BACKUP_HOST:-codrut-controlled-pilot}"
backup_log "Writing encrypted database and campaign asset snapshot to Restic."
if ! restic backup \
  --host "${backup_host}" \
  --tag codrut-controlled-pilot \
  --tag database-and-campaign-assets \
  "${staging_dir}"; then
  backup_die "Restic backup failed. The database dump remains only in the private temporary directory and will now be removed."
fi

if backup_is_true "${apply_retention}"; then
  "${BACKUP_SCRIPT_DIR}/retention.sh"
fi

backup_log "Backup completed successfully at ${created_at}."
