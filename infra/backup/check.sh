#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

# shellcheck source=infra/backup/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

plan_only=false
check_mode="${RESTIC_CHECK_MODE:-subset}"

for argument in "$@"; do
  case "${argument}" in
    --plan) plan_only=true ;;
    --full) check_mode=full ;;
    --metadata) check_mode=metadata ;;
    *) backup_die "Unknown check option '${argument}'. Use --metadata, --full, or --plan." ;;
  esac
done

backup_preflight_restic_config

check_args=(check)
case "${check_mode}" in
  metadata) ;;
  subset)
    subset="${RESTIC_CHECK_READ_DATA_SUBSET:-5%}"
    [[ "${subset}" =~ ^([0-9]+([.][0-9]+)?%|[0-9]+/[0-9]+)$ ]] ||
      backup_die "RESTIC_CHECK_READ_DATA_SUBSET must be a percentage or n/t partition."
    check_args+=("--read-data-subset=${subset}")
    ;;
  full) check_args+=(--read-data) ;;
  *) backup_die "RESTIC_CHECK_MODE must be metadata, subset, or full." ;;
esac

if ${plan_only}; then
  backup_log "PLAN: restic ${check_args[*]}"
  exit 0
fi

backup_preflight_repository
backup_log "Running Restic repository integrity check (${check_mode})."
if ! restic "${check_args[@]}"; then
  backup_die "Repository integrity check failed. Do not expire additional snapshots until investigated."
fi
backup_log "Repository integrity check completed successfully."
