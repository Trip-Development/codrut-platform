#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

# shellcheck source=infra/backup/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

plan_only=false
[[ "${1:-}" == "--plan" ]] && plan_only=true

backup_preflight_restic_config

readonly -a retention_args=(
  forget
  --tag codrut-controlled-pilot
  --group-by host,tags
  --keep-daily 14
  --keep-weekly 8
  --keep-monthly 6
  --prune
)

if ${plan_only}; then
  backup_log "PLAN: restic ${retention_args[*]}"
  backup_log "PLAN: retain 14 daily, 8 weekly, and 6 monthly restore points."
  exit 0
fi

backup_preflight_repository
backup_log "Applying retention: 14 daily, 8 weekly, and 6 monthly restore points."
if ! restic "${retention_args[@]}"; then
  backup_die "Retention failed. Existing snapshots were not reported as successfully pruned."
fi
backup_log "Retention completed successfully."
