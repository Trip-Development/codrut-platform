#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 EVIDENCE_PATH STOP_PATH" >&2
  exit 2
fi

evidence_path=$1
stop_path=$2
evidence_dir=$(dirname "$evidence_path")
mkdir -p "$evidence_dir"
chmod 700 "$evidence_dir"
umask 077

monitor_started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

capture() {
  backend_container=$(docker compose -f compose.yaml -f compose.prod.yaml ps -q backend)
  worker_container=$(docker compose -f compose.yaml -f compose.prod.yaml ps -q worker)
  if [ -z "$backend_container" ] || [ -z "$worker_container" ]; then
    echo "Backend and worker containers must both be running." >&2
    return 1
  fi
  backend_id=$(docker inspect --format '{{.Id}}' "$backend_container")
  backend_restart_count=$(docker inspect --format '{{.RestartCount}}' "$backend_container")
  backend_oom_killed=$(docker inspect --format '{{.State.OOMKilled}}' "$backend_container")
  backend_started_at=$(docker inspect --format '{{.State.StartedAt}}' "$backend_container")
  backend_pool_timeout_count=$(
    docker logs --since "$monitor_started_at" "$backend_container" 2>&1 |
      awk '
        BEGIN { count = 0 }
        {
          line = tolower($0)
          if (line ~ /database_pool_timeout/ || line ~ /queuepool limit/ || line ~ /connection pool timed out/) {
            count += 1
          }
        }
        END { print count }
      '
  )
  worker_id=$(docker inspect --format '{{.Id}}' "$worker_container")
  worker_restart_count=$(docker inspect --format '{{.RestartCount}}' "$worker_container")
  worker_oom_killed=$(docker inspect --format '{{.State.OOMKilled}}' "$worker_container")
  worker_started_at=$(docker inspect --format '{{.State.StartedAt}}' "$worker_container")
  worker_pool_timeout_count=$(
    docker logs --since "$monitor_started_at" "$worker_container" 2>&1 |
      awk '
        BEGIN { count = 0 }
        {
          line = tolower($0)
          if (line ~ /database_pool_timeout/ || line ~ /queuepool limit/ || line ~ /connection pool timed out/) {
            count += 1
          }
        }
        END { print count }
      '
  )
  temporary_path="${evidence_path}.tmp.$$"
  {
    printf 'captured_at_epoch=%s\n' "$(date +%s)"
    printf 'backend_id=%s\n' "$backend_id"
    printf 'backend_restart_count=%s\n' "$backend_restart_count"
    printf 'backend_oom_killed=%s\n' "$backend_oom_killed"
    printf 'backend_started_at=%s\n' "$backend_started_at"
    printf 'backend_pool_timeout_count=%s\n' "$backend_pool_timeout_count"
    printf 'worker_id=%s\n' "$worker_id"
    printf 'worker_restart_count=%s\n' "$worker_restart_count"
    printf 'worker_oom_killed=%s\n' "$worker_oom_killed"
    printf 'worker_started_at=%s\n' "$worker_started_at"
    printf 'worker_pool_timeout_count=%s\n' "$worker_pool_timeout_count"
  } >"$temporary_path"
  mv "$temporary_path" "$evidence_path"
}

while [ ! -e "$stop_path" ]; do
  capture
  sleep 2
done
capture
