#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  check_vps_capacity.sh preflight [path] [max-used-percent] [min-free-gib]
  check_vps_capacity.sh scheduled [path] [warning-percent] [failure-percent]
EOF
}

require_integer() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "${name} must be a non-negative integer; received ${value}." >&2
    exit 2
  fi
}

mode="${1:-}"
target_path="${2:-/}"

case "$mode" in
  preflight)
    max_used_percent="${3:-85}"
    min_free_gib="${4:-8}"
    require_integer "max-used-percent" "$max_used_percent"
    require_integer "min-free-gib" "$min_free_gib"
    ;;
  scheduled)
    warning_percent="${3:-80}"
    failure_percent="${4:-90}"
    require_integer "warning-percent" "$warning_percent"
    require_integer "failure-percent" "$failure_percent"
    if (( warning_percent >= failure_percent )); then
      echo "warning-percent must be lower than failure-percent." >&2
      exit 2
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

read -r available_kib used_percent_raw < <(
  df -Pk "$target_path" | awk 'NR == 2 { print $4, $5 }'
)
used_percent="${used_percent_raw%%%}"

require_integer "available-kib" "$available_kib"
require_integer "used-percent" "$used_percent"

available_gib="$(awk -v available_kib="$available_kib" \
  'BEGIN { printf "%.2f", available_kib / 1024 / 1024 }')"

echo "Capacity: path=${target_path} used=${used_percent}% free=${available_gib}GiB"

if [[ "$mode" == "preflight" ]]; then
  min_free_kib=$((min_free_gib * 1024 * 1024))
  if (( used_percent > max_used_percent )); then
    echo "Deployment blocked: disk usage ${used_percent}% exceeds ${max_used_percent}%." >&2
    exit 1
  fi
  if (( available_kib < min_free_kib )); then
    echo "Deployment blocked: ${available_gib}GiB free is below ${min_free_gib}GiB." >&2
    exit 1
  fi
  echo "CAPACITY_STATUS=ok"
  exit 0
fi

if (( used_percent >= failure_percent )); then
  echo "CAPACITY_STATUS=failure"
  echo "Capacity failure: disk usage ${used_percent}% is at or above ${failure_percent}%." >&2
  exit 1
fi
if (( used_percent >= warning_percent )); then
  echo "CAPACITY_STATUS=warning"
  echo "Capacity warning: disk usage ${used_percent}% is at or above ${warning_percent}%."
  exit 0
fi

echo "CAPACITY_STATUS=ok"
