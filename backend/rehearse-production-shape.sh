#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${backend_dir}/.." && pwd)"
database_name="${CODRUT_REHEARSAL_DATABASE:-cody_production_shape_rehearsal}"

case "${database_name}" in
    *_rehearsal) ;;
    *)
        printf 'Refusing database without the _rehearsal suffix: %s\n' "${database_name}" >&2
        exit 2
        ;;
esac

compose=(docker compose -f compose.yaml -f compose.dev.yaml)
database_url="postgresql+asyncpg://codrut:codrut@db:5432/${database_name}"
fixture_path="${backend_dir}/tests/fixtures/production_shape_0033.sql"
lock_process_id=""
lock_log=""

cleanup() {
    if [[ -n "${lock_process_id}" ]] && kill -0 "${lock_process_id}" 2>/dev/null; then
        kill "${lock_process_id}" 2>/dev/null || true
        wait "${lock_process_id}" 2>/dev/null || true
    fi
    if [[ -n "${lock_log}" ]]; then
        rm -f "${lock_log}"
    fi
    if [[ "${CODRUT_KEEP_REHEARSAL_DATABASE:-0}" == "1" ]]; then
        printf 'Keeping disposable database %s for inspection.\n' "${database_name}"
        return
    fi
    "${compose[@]}" exec -T db dropdb --if-exists -U codrut "${database_name}" >/dev/null
}
trap cleanup EXIT

cd "${repo_dir}"
"${compose[@]}" exec -T db dropdb --if-exists -U codrut "${database_name}" >/dev/null
"${compose[@]}" exec -T db createdb -U codrut "${database_name}"

run_alembic() {
    "${compose[@]}" exec -T \
        -e CODRUT_DATABASE_URL="${database_url}" \
        -e CODRUT_MIGRATION_LOCK_TIMEOUT_MS="${CODRUT_MIGRATION_LOCK_TIMEOUT_MS:-5000}" \
        -e CODRUT_MIGRATION_STATEMENT_TIMEOUT_MS="${CODRUT_MIGRATION_STATEMENT_TIMEOUT_MS:-900000}" \
        backend \
        uv run alembic "$@"
}

run_psql() {
    "${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U codrut -d "${database_name}" "$@"
}

wallclock_milliseconds() {
    python3 -c 'import time; print(time.time_ns() // 1_000_000)'
}

run_alembic upgrade 0033_email_send_idempotency
run_psql < "${fixture_path}"

printf '\nPre-migration shape:\n'
run_psql -P pager=off -c "
select
    (select count(*) from participant_profiles) as participants,
    (select count(*) from sessions) as sessions,
    (select count(*) from campaign_recipients) as contacts,
    (select count(*) from campaign_recipient_memberships) as memberships,
    (select count(*) from campaign_recipient_events) as events,
    (select count(*) from email_sends) as sends;
"

lock_log="$(mktemp -t cody-migration-lock.XXXXXX)"
run_psql -c "begin; lock table sessions in access exclusive mode; select pg_sleep(2); commit;" \
    >"${lock_log}" 2>&1 &
lock_process_id=$!
lock_acquired=0
for _ in $(seq 1 40); do
    if [[ "$(run_psql -Atc "
        select count(*)
        from pg_locks held_lock
        join pg_class relation on relation.oid = held_lock.relation
        where relation.relname = 'sessions'
          and held_lock.mode = 'AccessExclusiveLock'
          and held_lock.granted
    ")" == "1" ]]; then
        lock_acquired=1
        break
    fi
    sleep 0.05
done
if [[ ${lock_acquired} -ne 1 ]]; then
    printf 'Unable to establish the synthetic migration lock.\n' >&2
    exit 5
fi

lock_test_started="$(wallclock_milliseconds)"
set +e
lock_test_output="$(CODRUT_MIGRATION_LOCK_TIMEOUT_MS=250 run_alembic upgrade 0034_invite_session_link 2>&1)"
lock_test_status=$?
set -e
lock_test_milliseconds=$(( $(wallclock_milliseconds) - lock_test_started ))
if [[ ${lock_test_status} -eq 0 ]] || [[ "${lock_test_output}" != *"lock timeout"* ]]; then
    printf 'Expected a bounded PostgreSQL lock-timeout failure:\n%s\n' "${lock_test_output}" >&2
    exit 6
fi
if [[ ${lock_test_milliseconds} -gt 2500 ]]; then
    printf 'The 250ms lock timeout took too long to return: %sms.\n' \
        "${lock_test_milliseconds}" >&2
    exit 8
fi
if [[ "$(run_psql -Atc 'select version_num from alembic_version')" != "0033_email_send_idempotency" ]]; then
    printf 'The failed lock rehearsal advanced the migration revision.\n' >&2
    exit 7
fi
wait "${lock_process_id}"
lock_process_id=""
printf '\nLock contention: Pass (250ms limit, failed safely in %sms).\n' "${lock_test_milliseconds}"

migration_started="$(wallclock_milliseconds)"
run_alembic upgrade 0035_contact_owner_isolation
migration_milliseconds=$(( $(wallclock_milliseconds) - migration_started ))

run_psql -c "
do \$\$
declare
    cross_owner_memberships integer;
    cross_owner_sends integer;
    duplicate_contacts integer;
    participant_count integer;
    session_count integer;
begin
    select count(*) into cross_owner_memberships
    from campaign_recipient_memberships membership
    join campaigns campaign on campaign.id = membership.campaign_id
    join campaign_recipients recipient on recipient.id = membership.recipient_id
    where campaign.owner_id is distinct from recipient.owner_id;

    select count(*) into cross_owner_sends
    from email_sends send
    join campaigns campaign on campaign.id = send.campaign_id
    join campaign_recipients recipient on recipient.id = send.campaign_recipient_id
    where campaign.owner_id is distinct from recipient.owner_id;

    select count(*) into duplicate_contacts
    from (
        select owner_id, lower(email)
        from campaign_recipients
        where email is not null
        group by owner_id, lower(email)
        having count(*) > 1
    ) duplicates;

    select count(*) into participant_count from participant_profiles;
    select count(*) into session_count from sessions;

    if cross_owner_memberships <> 0 or cross_owner_sends <> 0 then
        raise exception 'owner isolation failed: memberships %, sends %',
            cross_owner_memberships, cross_owner_sends;
    end if;
    if duplicate_contacts <> 0 then
        raise exception 'normalized duplicate repair failed: % groups remain', duplicate_contacts;
    end if;
    if participant_count <> 195 or session_count <> 195 then
        raise exception 'pilot-shape rows changed: participants %, sessions %',
            participant_count, session_count;
    end if;
end
\$\$;
"

printf '\nPost-0035 shape (wall time: %sms):\n' "${migration_milliseconds}"
run_psql -P pager=off -c "
select
    (select count(*) from participant_profiles) as participants,
    (select count(*) from sessions) as sessions,
    (select count(*) from campaign_recipients) as contacts,
    (select count(*) from campaign_recipient_memberships) as memberships,
    (select count(*) from campaign_recipient_events) as events,
    (select count(*) from email_sends) as sends,
    (select count(*) from campaign_recipients where owner_id = '00000000-0000-4000-8000-000000000002') as owner_two_contacts;
"

set +e
rollback_output="$(run_alembic downgrade 0034_invite_session_link 2>&1)"
rollback_status=$?
set -e
if [[ ${rollback_status} -eq 0 ]]; then
    printf 'Expected the unsafe owner-isolation rollback to be blocked.\n' >&2
    exit 3
fi
if [[ "${rollback_output}" != *"Cannot restore global campaign contact email uniqueness"* ]]; then
    printf 'Rollback failed for an unexpected reason:\n%s\n' "${rollback_output}" >&2
    exit 4
fi
printf '\nRollback boundary: Pass (unsafe 0035 downgrade blocked).\n'

run_alembic upgrade head
run_alembic check

printf '\nFinal revision and retained row counts:\n'
run_alembic current
run_psql -P pager=off -c "
select
    (select count(*) from participant_profiles) as participants,
    (select count(*) from sessions) as sessions,
    (select count(*) from campaign_recipients) as contacts,
    (select count(*) from campaign_recipient_memberships) as memberships,
    (select count(*) from campaign_recipient_events) as events,
    (select count(*) from email_sends) as sends;
"
printf '\nSynthetic production-shaped migration rehearsal: Pass.\n'
