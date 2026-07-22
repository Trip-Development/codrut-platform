#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command_name="${1:-}"
[[ -n "${command_name}" ]] || {
  printf 'Usage: entrypoint.sh {init|backup|retention|check|restore-rehearsal|evidence} [options]\n' >&2
  exit 2
}
shift

case "${command_name}" in
  init) exec "${script_dir}/init.sh" "$@" ;;
  backup) exec "${script_dir}/backup.sh" "$@" ;;
  retention) exec "${script_dir}/retention.sh" "$@" ;;
  check) exec "${script_dir}/check.sh" "$@" ;;
  restore-rehearsal) exec "${script_dir}/restore-rehearsal.sh" "$@" ;;
  evidence)
    find "${RESTORE_ROOT:-/restore}" -type f -name restore-evidence.txt -print -exec sed -n '1,120p' {} \;
    ;;
  *)
    printf "Unknown backup command '%s'.\n" "${command_name}" >&2
    exit 2
    ;;
esac
