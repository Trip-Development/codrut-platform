\set ON_ERROR_STOP on

-- Synthetic legacy data only. The deterministic .invalid addresses cannot receive mail.
insert into users (id, email, password_hash, role)
values
    ('00000000-0000-4000-8000-000000000001', 'synthetic.trainer.one@example.invalid', 'not-a-login-hash', 'trainer'),
    ('00000000-0000-4000-8000-000000000002', 'synthetic.trainer.two@example.invalid', 'not-a-login-hash', 'trainer');

insert into companies (id, name)
values ('00000000-0000-4000-8000-000000000100', 'Synthetic Production Shape');

insert into company_projects (id, company_id, name, status)
values (
    '00000000-0000-4000-8000-000000000200',
    '00000000-0000-4000-8000-000000000100',
    'Synthetic 195 Participant Pilot',
    'active'
);

insert into participant_profiles (id, company_id, full_name, email)
select
    ('10000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    '00000000-0000-4000-8000-000000000100'::uuid,
    'Synthetic Participant ' || series,
    'synthetic.participant.' || series || '@example.invalid'
from generate_series(1, 195) as series;

insert into project_memberships (
    id,
    company_id,
    project_id,
    participant_profile_id,
    active
)
select
    ('11000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    '00000000-0000-4000-8000-000000000100'::uuid,
    '00000000-0000-4000-8000-000000000200'::uuid,
    ('10000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    true
from generate_series(1, 195) as series;

insert into sessions (id, user_id, token_hash, expires_at)
select
    ('12000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    '00000000-0000-4000-8000-000000000001'::uuid,
    lpad(series::text, 64, '0'),
    now() + interval '30 days'
from generate_series(1, 195) as series;

insert into campaigns (
    id,
    owner_id,
    name,
    segment,
    status,
    subject,
    html_body,
    text_body,
    recipient_memberships_initialized
)
values
    (
        '00000000-0000-4000-8000-000000000301',
        '00000000-0000-4000-8000-000000000001',
        'Synthetic Campaign One',
        'past_customer',
        'ready',
        'Synthetic subject one',
        '<p>Synthetic body one</p>',
        'Synthetic body one',
        true
    ),
    (
        '00000000-0000-4000-8000-000000000302',
        '00000000-0000-4000-8000-000000000002',
        'Synthetic Campaign Two',
        'potential_customer',
        'draft',
        'Synthetic subject two',
        '<p>Synthetic body two</p>',
        'Synthetic body two',
        true
    );

insert into campaign_recipients (
    id,
    owner_id,
    email,
    contact_name,
    organization_name,
    segment,
    source,
    status
)
select
    ('20000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    '00000000-0000-4000-8000-000000000001'::uuid,
    'synthetic.contact.' || series || '@example.invalid',
    'Synthetic Contact ' || series,
    'Synthetic Organization',
    'past_customer',
    'rehearsal',
    case
        when series = 194 then 'suppressed'::campaignrecipientstatus
        when series = 195 then 'unsubscribed'::campaignrecipientstatus
        else 'active'::campaignrecipientstatus
    end
from generate_series(1, 195) as series;

-- The old global constraint is case-sensitive, so this is a valid pre-0035 collision.
insert into campaign_recipients (
    id,
    owner_id,
    email,
    contact_name,
    organization_name,
    segment,
    source,
    status,
    updated_at
)
values
    (
        '40000000-0000-4000-8000-000000000001',
        '00000000-0000-4000-8000-000000000001',
        'Pilot.Duplicate@example.invalid',
        null,
        'Synthetic Primary Organization',
        'past_customer',
        'legacy-import',
        'active',
        now() - interval '1 day'
    ),
    (
        '40000000-0000-4000-8000-000000000002',
        '00000000-0000-4000-8000-000000000001',
        'pilot.duplicate@example.invalid',
        'Synthetic Duplicate Name',
        null,
        'past_customer',
        'legacy-import',
        'suppressed',
        now()
    );

insert into campaign_recipient_memberships (id, campaign_id, recipient_id, source)
select
    gen_random_uuid(),
    '00000000-0000-4000-8000-000000000301'::uuid,
    recipient.id,
    'rehearsal'
from campaign_recipients recipient;

-- These legacy links intentionally point campaign two at owner one's contacts.
insert into campaign_recipient_memberships (id, campaign_id, recipient_id, source)
select
    gen_random_uuid(),
    '00000000-0000-4000-8000-000000000302'::uuid,
    ('20000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    'legacy-cross-owner'
from generate_series(1, 100) as series;

insert into campaign_recipient_events (
    id,
    recipient_id,
    event_type,
    variant_key,
    occurred_at
)
select
    gen_random_uuid(),
    ('20000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    'opened',
    'synthetic',
    now() - make_interval(hours => series)
from generate_series(1, 20) as series;

insert into email_sends (
    id,
    recipient_email,
    template_key,
    template_version,
    provider,
    status,
    campaign_id,
    campaign_recipient_id,
    idempotency_key
)
select
    ('50000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    'synthetic.contact.' || series || '@example.invalid',
    'synthetic_rehearsal',
    1,
    'fake',
    'queued',
    '00000000-0000-4000-8000-000000000302'::uuid,
    ('20000000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
    'synthetic-rehearsal-' || series
from generate_series(1, 50) as series;
