#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

# shellcheck source=infra/backup/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

plan_only=false
[[ "${1:-}" == "--plan" ]] && plan_only=true

backup_preflight_restic_config
backup_validate_isolated_restore
backup_resolve_secret RESTORE_POSTGRES_PASSWORD RESTORE_POSTGRES_PASSWORD_FILE

restore_root="${RESTORE_ROOT:-/restore}"
rehearsal_id="${RESTORE_REHEARSAL_ID:-$(date -u +'%Y%m%dT%H%M%SZ')-$$}"
backup_validate_rehearsal_id "${rehearsal_id}"
restore_target="${restore_root%/}/${rehearsal_id}"
snapshot="${RESTORE_SNAPSHOT:-latest}"
backup_host="${BACKUP_HOST:-codrut-controlled-pilot}"

if ${plan_only}; then
  backup_log "PLAN: restore snapshot '${snapshot}' into new path '${restore_target}'."
  backup_log "PLAN: validate the pg_dump archive, create new database '${RESTORE_POSTGRES_DB}' on isolated host '${RESTORE_POSTGRES_HOST}', and restore into it."
  backup_log "PLAN: verify the Alembic head, foreign-key integrity, critical manifest counts, and every campaign asset SHA-256 hash."
  backup_log "PLAN: never write to '${POSTGRES_HOST}/${POSTGRES_DB}' or '${BACKUP_ASSET_DIR:-/data/campaign-assets}'."
  exit 0
fi

backup_require_command createdb
backup_require_command dropdb
backup_require_command find
backup_require_command pg_isready
backup_require_command pg_restore
backup_require_command psql
backup_require_command restic
backup_require_command sha256sum
backup_preflight_repository

[[ ! -e "${restore_target}" ]] ||
  backup_die "Restore target '${restore_target}' already exists; refusing to overwrite rehearsal evidence."
mkdir -p "${restore_target}"

target_port="${RESTORE_POSTGRES_PORT:-5432}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
export PGPASSWORD="${RESTORE_POSTGRES_PASSWORD:-}"

backup_log "Checking isolated PostgreSQL restore target."
if ! pg_isready \
  --host "${RESTORE_POSTGRES_HOST}" \
  --port "${target_port}" \
  --username "${RESTORE_POSTGRES_USER}" \
  --dbname postgres >/dev/null; then
  backup_die "Isolated PostgreSQL target is unavailable; live data was not touched."
fi

existing_database="$(psql \
  --host "${RESTORE_POSTGRES_HOST}" \
  --port "${target_port}" \
  --username "${RESTORE_POSTGRES_USER}" \
  --dbname postgres \
  --tuples-only \
  --no-align \
  --command "SELECT 1 FROM pg_database WHERE datname = '${RESTORE_POSTGRES_DB}'")"
[[ -z "${existing_database}" ]] ||
  backup_die "Restore database '${RESTORE_POSTGRES_DB}' already exists; refusing to overwrite it."

backup_log "Restoring encrypted snapshot into isolated filesystem target."
if ! restic restore "${snapshot}" \
  --host "${backup_host}" \
  --tag codrut-controlled-pilot \
  --tag database-and-campaign-assets \
  --verify \
  --target "${restore_target}"; then
  backup_die "Restic restore failed; no database was created."
fi

dump_path="$(find "${restore_target}" -type f -path '*/database/codrut.dump' -print -quit)"
[[ -n "${dump_path}" ]] || backup_die "Restored snapshot does not contain the expected PostgreSQL dump."
if ! pg_restore --list "${dump_path}" >/dev/null; then
  backup_die "The restored PostgreSQL archive failed pg_restore validation."
fi

manifest_path="$(find "${restore_target}" -type f -path '*/metadata/manifest.txt' -print -quit)"
asset_hashes_path="$(find "${restore_target}" -type f -path '*/metadata/campaign-assets.sha256' -print -quit)"
[[ -n "${manifest_path}" ]] || backup_die "Restored snapshot does not contain its validation manifest."
[[ -n "${asset_hashes_path}" ]] ||
  backup_die "Restored snapshot does not contain its campaign asset hash manifest."

manifest_value() {
  local key="$1"
  awk -F= -v key="${key}" '
    $1 == key {
      sub(/^[^=]*=/, "")
      print
      found = 1
    }
    END { if (!found) exit 1 }
  ' "${manifest_path}"
}

[[ "$(manifest_value format)" == "codrut-controlled-pilot-v2" ]] ||
  backup_die "Restore manifest format is unsupported or incomplete."
expected_alembic_head="$(manifest_value alembic_head)"
[[ "${expected_alembic_head}" =~ ^[A-Za-z0-9_]+$ ]] ||
  backup_die "Restore manifest Alembic head is invalid."

critical_tables=(
  users
  companies
  participant_profiles
  questionnaire_assignments
  campaigns
  email_sends
)
declare -A expected_counts=()
for table_name in "${critical_tables[@]}"; do
  expected_count="$(manifest_value "count.${table_name}")"
  [[ "${expected_count}" =~ ^[0-9]+$ ]] ||
    backup_die "Restore manifest count for ${table_name} is invalid."
  expected_counts["${table_name}"]="${expected_count}"
done
expected_asset_count="$(manifest_value count.campaign_assets)"
[[ "${expected_asset_count}" =~ ^[0-9]+$ ]] ||
  backup_die "Restore manifest campaign asset count is invalid."

created_target_database=false
restore_succeeded=false
cleanup_failed_restore() {
  local status=$?
  if [[ "${restore_succeeded}" != true && "${created_target_database}" == true ]]; then
    backup_log "Restore failed; removing only the newly created isolated database."
    dropdb \
      --host "${RESTORE_POSTGRES_HOST}" \
      --port "${target_port}" \
      --username "${RESTORE_POSTGRES_USER}" \
      "${RESTORE_POSTGRES_DB}" >/dev/null 2>&1 || true
  fi
  exit "${status}"
}
trap cleanup_failed_restore EXIT

backup_log "Creating new isolated rehearsal database '${RESTORE_POSTGRES_DB}'."
createdb \
  --host "${RESTORE_POSTGRES_HOST}" \
  --port "${target_port}" \
  --username "${RESTORE_POSTGRES_USER}" \
  "${RESTORE_POSTGRES_DB}"
created_target_database=true

backup_log "Restoring PostgreSQL dump into the isolated rehearsal database."
pg_restore \
  --host "${RESTORE_POSTGRES_HOST}" \
  --port "${target_port}" \
  --username "${RESTORE_POSTGRES_USER}" \
  --dbname "${RESTORE_POSTGRES_DB}" \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  "${dump_path}"

backup_target_scalar() {
  local query="$1"
  psql \
    --host "${RESTORE_POSTGRES_HOST}" \
    --port "${target_port}" \
    --username "${RESTORE_POSTGRES_USER}" \
    --dbname "${RESTORE_POSTGRES_DB}" \
    --tuples-only \
    --no-align \
    --set ON_ERROR_STOP=1 \
    --command "${query}" | tr -d '[:space:]'
}

actual_alembic_head="$(backup_target_scalar "SELECT version_num FROM alembic_version")"
[[ "${actual_alembic_head}" == "${expected_alembic_head}" ]] ||
  backup_die "Restored Alembic head does not match the snapshot manifest."

for table_name in "${critical_tables[@]}"; do
  actual_count="$(backup_target_scalar "SELECT count(*) FROM ${table_name}")"
  [[ "${actual_count}" == "${expected_counts[${table_name}]}" ]] ||
    backup_die "Restored row count for ${table_name} does not match the snapshot manifest."
done

foreign_key_count="$(backup_target_scalar "SELECT count(*) FROM pg_catalog.pg_constraint WHERE contype = 'f'")"
invalid_constraint_count="$(backup_target_scalar "SELECT count(*) FROM pg_catalog.pg_constraint WHERE contype IN ('c', 'f', 'p', 'u') AND NOT convalidated")"
[[ "${foreign_key_count}" =~ ^[0-9]+$ && "${foreign_key_count}" -gt 0 ]] ||
  backup_die "Restore completed without foreign-key constraints; rehearsal is invalid."
[[ "${invalid_constraint_count}" == "0" ]] ||
  backup_die "Restore contains unvalidated integrity constraints."

table_count="$(psql \
  --host "${RESTORE_POSTGRES_HOST}" \
  --port "${target_port}" \
  --username "${RESTORE_POSTGRES_USER}" \
  --dbname "${RESTORE_POSTGRES_DB}" \
  --tuples-only \
  --no-align \
  --command "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'")"
[[ "${table_count}" =~ ^[0-9]+$ && "${table_count}" -gt 0 ]] ||
  backup_die "Restore completed without any public tables; rehearsal is invalid."

asset_restore_dir="$(find "${restore_target}" -type d -path '*/assets/campaign-assets' -print -quit)"
[[ -n "${asset_restore_dir}" ]] ||
  backup_die "Restored snapshot does not contain the campaign asset directory."
asset_count="$(find "${asset_restore_dir}" -type f | wc -l | tr -d ' ')"
[[ "${asset_count}" == "${expected_asset_count}" ]] ||
  backup_die "Restored campaign asset count does not match the snapshot manifest."
hash_count="$(wc -l <"${asset_hashes_path}" | tr -d '[:space:]')"
[[ "${hash_count}" == "${expected_asset_count}" ]] ||
  backup_die "Campaign asset hash manifest count does not match the snapshot manifest."
if [[ "${expected_asset_count}" -gt 0 ]]; then
  (
    cd "${asset_restore_dir}"
    sha256sum --check --strict "${asset_hashes_path}"
  ) >/dev/null || backup_die "One or more restored campaign assets failed SHA-256 validation."
fi

evidence_path="${restore_target}/restore-evidence.txt"
printf '%s\n' \
  "result=success" \
  "completed_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
  "snapshot_selector=${snapshot}" \
  "target_host=${RESTORE_POSTGRES_HOST}" \
  "target_database=${RESTORE_POSTGRES_DB}" \
  "alembic_head=${actual_alembic_head}" \
  "public_tables=${table_count}" \
  "foreign_keys=${foreign_key_count}" \
  "users=${expected_counts[users]}" \
  "companies=${expected_counts[companies]}" \
  "participants=${expected_counts[participant_profiles]}" \
  "assignments=${expected_counts[questionnaire_assignments]}" \
  "campaigns=${expected_counts[campaigns]}" \
  "email_sends=${expected_counts[email_sends]}" \
  "campaign_assets=${asset_count}" \
  >"${evidence_path}"

restore_succeeded=true
trap - EXIT
backup_log "Restore rehearsal succeeded. Evidence: ${evidence_path}"
backup_log "The isolated database is intentionally left available for review and is never copied over live data."
