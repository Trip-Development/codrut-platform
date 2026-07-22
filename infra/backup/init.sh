#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

# shellcheck source=infra/backup/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

plan_only=false
[[ "${1:-}" == "--plan" ]] && plan_only=true

backup_preflight_restic_config

if ${plan_only}; then
  backup_log "PLAN: initialize encrypted Restic repository '${RESTIC_REPOSITORY}'."
  exit 0
fi

backup_require_command restic
backup_log "Initializing encrypted Restic repository."
if ! restic init; then
  backup_die "Repository initialization failed. Verify the endpoint, bucket permissions, and encryption credential."
fi
backup_log "Repository initialized successfully."
