#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly BACKUP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

backup_log() {
  printf '[codrut-backup] %s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

backup_die() {
  backup_log "ERROR: $*"
  exit 1
}

backup_require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || backup_die "${name} is required."
}

backup_require_command() {
  local command_name="$1"
  command -v "${command_name}" >/dev/null 2>&1 ||
    backup_die "Required command '${command_name}' is not installed."
}

backup_resolve_secret() {
  local value_name="$1"
  local file_name="$2"
  local direct_value="${!value_name:-}"
  local file_path="${!file_name:-}"

  if [[ -n "${direct_value}" && -n "${file_path}" ]]; then
    backup_die "Set only one of ${value_name} or ${file_name}."
  fi
  if [[ -n "${file_path}" ]]; then
    [[ -r "${file_path}" ]] || backup_die "${file_name} does not reference a readable file."
    printf -v "${value_name}" '%s' "$(<"${file_path}")"
    export "${value_name}"
    unset "${file_name}"
  fi
}

backup_preflight_restic_config() {
  backup_require_env RESTIC_REPOSITORY
  backup_resolve_secret RESTIC_PASSWORD RESTIC_PASSWORD_FILE
  [[ -n "${RESTIC_PASSWORD:-}" ]] ||
    backup_die "Set RESTIC_PASSWORD or RESTIC_PASSWORD_FILE for repository encryption."

  if [[ "${RESTIC_REPOSITORY}" == s3:* ]]; then
    backup_resolve_secret AWS_ACCESS_KEY_ID AWS_ACCESS_KEY_ID_FILE
    backup_resolve_secret AWS_SECRET_ACCESS_KEY AWS_SECRET_ACCESS_KEY_FILE
    backup_require_env AWS_ACCESS_KEY_ID
    backup_require_env AWS_SECRET_ACCESS_KEY
  fi
}

backup_preflight_source_database_config() {
  backup_require_env POSTGRES_HOST
  backup_require_env POSTGRES_DB
  backup_require_env POSTGRES_USER
  backup_resolve_secret POSTGRES_PASSWORD POSTGRES_PASSWORD_FILE
  [[ -n "${POSTGRES_PASSWORD:-}" ]] ||
    backup_die "Set POSTGRES_PASSWORD or POSTGRES_PASSWORD_FILE for pg_dump."
  [[ "${POSTGRES_DB}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] ||
    backup_die "POSTGRES_DB must be a simple PostgreSQL identifier."
}

backup_preflight_repository() {
  backup_require_command restic
  if ! restic snapshots --json >/dev/null; then
    backup_die "Restic repository is unavailable or not initialized. Run the init command and verify credentials."
  fi
}

backup_is_true() {
  case "${1,,}" in
    1 | true | yes | on) return 0 ;;
    0 | false | no | off) return 1 ;;
    *) backup_die "Expected a boolean value, received '$1'." ;;
  esac
}

backup_validate_rehearsal_id() {
  local rehearsal_id="$1"
  [[ "${rehearsal_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] ||
    backup_die "RESTORE_REHEARSAL_ID may contain only letters, digits, dot, underscore, and hyphen."
}

backup_validate_isolated_restore() {
  backup_require_env POSTGRES_HOST
  backup_require_env POSTGRES_DB
  backup_require_env RESTORE_POSTGRES_HOST
  backup_require_env RESTORE_POSTGRES_DB
  backup_require_env RESTORE_POSTGRES_USER

  [[ "${RESTORE_POSTGRES_DB}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] ||
    backup_die "RESTORE_POSTGRES_DB must be a simple PostgreSQL identifier."
  [[ "${RESTORE_POSTGRES_HOST}" != "${POSTGRES_HOST}" ]] ||
    backup_die "Restore rehearsal refused: target PostgreSQL host must differ from the live source host."
  [[ "${RESTORE_POSTGRES_DB}" != "${POSTGRES_DB}" ]] ||
    backup_die "Restore rehearsal refused: target database name must differ from the live source database."

  local restore_root="${RESTORE_ROOT:-/restore}"
  [[ "${restore_root}" == /* ]] || backup_die "RESTORE_ROOT must be an absolute path."
  [[ "${restore_root}" != "/" ]] || backup_die "RESTORE_ROOT cannot be the filesystem root."
  [[ "${restore_root}" != *'/../'* && "${restore_root}" != */.. ]] ||
    backup_die "RESTORE_ROOT cannot contain parent traversal."
  [[ "${restore_root}" != "${BACKUP_ASSET_DIR:-/data/campaign-assets}" ]] ||
    backup_die "RESTORE_ROOT cannot be the live campaign asset path."
}
