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

run_alembic upgrade 0044_communications_hardening
run_psql -c "
insert into questionnaire_definitions (
    id, key, version, title, schema, active,
    feedback_policy, trainer_visibility_policy, system_managed
) values (
    '20000000-0000-4000-8000-000000000001',
    'lencioni', 1, 'Synthetic Lencioni', '{}'::jsonb, true,
    '{}'::jsonb, '{}'::jsonb, false
);

insert into teams (id, company_id, name, type)
values (
    '21000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000100',
    'Synthetic Leadership',
    'leadership'
);

insert into team_memberships (id, team_id, participant_profile_id, role)
values
    (
        '21100000-0000-4000-8000-000000000001',
        '21000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'leader'
    ),
    (
        '21100000-0000-4000-8000-000000000002',
        '21000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000002',
        'member'
    );

insert into questionnaire_assignments (
    id, company_id, project_id, assignment_round_id,
    respondent_profile_id, questionnaire_key, questionnaire_definition_id,
    target_type, target_team_id, access_mode, status, visibility_policy,
    reminder_count
) values
    (
        '22000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000100',
        '00000000-0000-4000-8000-000000000200',
        '23000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'lencioni', '20000000-0000-4000-8000-000000000001',
        'team', '21000000-0000-4000-8000-000000000001',
        'account_link', 'scored', 'trainer_raw_review', 0
    ),
    (
        '22000000-0000-4000-8000-000000000002',
        '00000000-0000-4000-8000-000000000100',
        '00000000-0000-4000-8000-000000000200',
        '23000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000002',
        'lencioni', '20000000-0000-4000-8000-000000000001',
        'team', '21000000-0000-4000-8000-000000000001',
        'account_link', 'scored', 'trainer_raw_review', 0
    );

insert into result_publications (
    id, publication_key, participant_profile_id, company_id, project_id,
    assignment_round_id, questionnaire_definition_id, questionnaire_key,
    source_assignment_id, kind, source_count, policy_snapshot, published_at
) values
    (
        '24000000-0000-4000-8000-000000000001',
        'individual:22000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000100',
        '00000000-0000-4000-8000-000000000200',
        '23000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        'lencioni', '22000000-0000-4000-8000-000000000001',
        'individual', 1, '{}'::jsonb, now()
    ),
    (
        '24000000-0000-4000-8000-000000000002',
        concat_ws(
            ':',
            'aggregate-360',
            '10000000-0000-4000-8000-000000000001',
            '00000000-0000-4000-8000-000000000200',
            '23000000-0000-4000-8000-000000000001',
            '20000000-0000-4000-8000-000000000001'
        ),
        '10000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000100',
        '00000000-0000-4000-8000-000000000200',
        '23000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        'lencioni', null, 'aggregate_360', 2, '{}'::jsonb, now()
    );
"

run_alembic upgrade head
run_alembic check

run_psql -c "
do \$\$
declare
    project_count integer;
    initial_cycle_count integer;
    unscoped_project_assignments integer;
    duplicate_cycle_questionnaires integer;
    retained_assignments integer;
    unscoped_publications integer;
    rewritten_aggregate_keys integer;
    cycle_team_members integer;
    guarded_assignments integer;
begin
    select count(*) into project_count from company_projects;
    select count(*) into initial_cycle_count
    from assessment_cycles
    where sequence = 1 and name = 'Evaluare inițială';
    select count(*) into unscoped_project_assignments
    from questionnaire_assignments
    where project_id is not null and assessment_cycle_id is null;
    select count(*) into duplicate_cycle_questionnaires
    from (
        select assessment_cycle_id, questionnaire_key
        from assessment_cycle_questionnaires
        group by assessment_cycle_id, questionnaire_key
        having count(*) > 1
    ) duplicates;
    select count(*) into retained_assignments
    from questionnaire_assignments
    where id in (
        '22000000-0000-4000-8000-000000000001',
        '22000000-0000-4000-8000-000000000002'
    )
      and questionnaire_definition_id = '20000000-0000-4000-8000-000000000001';
    select count(*) into unscoped_publications
    from result_publications
    where id in (
        '24000000-0000-4000-8000-000000000001',
        '24000000-0000-4000-8000-000000000002'
    )
      and assessment_cycle_id is null;
    select count(*) into rewritten_aggregate_keys
    from result_publications publication
    where publication.id = '24000000-0000-4000-8000-000000000002'
      and publication.publication_key = concat_ws(
          ':',
          'aggregate-360',
          publication.participant_profile_id::text,
          publication.project_id::text,
          publication.assessment_cycle_id::text,
          publication.assignment_round_id::text,
          publication.questionnaire_definition_id::text
      );
    select count(*) into cycle_team_members
    from assessment_cycle_team_memberships
    where team_id = '21000000-0000-4000-8000-000000000001';
    select count(*) into guarded_assignments
    from questionnaire_assignments
    where id in (
        '22000000-0000-4000-8000-000000000001',
        '22000000-0000-4000-8000-000000000002'
    )
      and cycle_shape_guard = assessment_cycle_id;

    if initial_cycle_count <> project_count then
        raise exception 'cycle backfill mismatch: projects %, initial cycles %',
            project_count, initial_cycle_count;
    end if;
    if unscoped_project_assignments <> 0 then
        raise exception 'cycle backfill left % project assignments unscoped',
            unscoped_project_assignments;
    end if;
    if duplicate_cycle_questionnaires <> 0 then
        raise exception 'cycle questionnaire backfill left % duplicate keys',
            duplicate_cycle_questionnaires;
    end if;
    if retained_assignments <> 2 then
        raise exception 'cycle migration retained only % of 2 synthetic assignments',
            retained_assignments;
    end if;
    if unscoped_publications <> 0 or rewritten_aggregate_keys <> 1 then
        raise exception 'publication backfill mismatch: unscoped %, rewritten keys %',
            unscoped_publications, rewritten_aggregate_keys;
    end if;
    if cycle_team_members <> 2 then
        raise exception 'team snapshot backfill expected 2 members, found %',
            cycle_team_members;
    end if;
    if guarded_assignments <> 2 then
        raise exception 'assignment guard backfill expected 2 rows, found %',
            guarded_assignments;
    end if;
end
\$\$;
"

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
