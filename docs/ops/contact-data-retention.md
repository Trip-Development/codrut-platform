# Contact data retention and suppression

This runbook defines the operational boundary between the recoverable contact
Archive, purged delivery history, and the do-not-contact record required to
honour hard bounces and unsubscribes. It is a data-handling control, not a claim
that every related record becomes anonymous after 30 days.

## Data lifecycle

| State | Data retained | Operational rule |
| --- | --- | --- |
| Active | Contact identity, campaign memberships, and delivery history | Available only to the owning trainer |
| Archived | Contact identity and terminal history until `purge_after` | Hidden from normal lists and selection; memberships and unsent work are removed immediately |
| Purged | Aggregate delivery outcome plus short-lived keyed token/provider mappings | The direct contact, memberships, and row-level send/event history are deleted after counts are materialized |
| Do not contact | Keyed normalized-email fingerprint, owner, reason, and review metadata | Protected pseudonymous personal data used only to prevent another send after a permanent failure, unsubscribe, or unresolved provider outcome |

The default Archive recovery window is 30 days, configured by
`CODRUT_CAMPAIGN_RECIPIENT_ARCHIVE_RETENTION_DAYS`. Purge must:

1. defer while a provider request is actively in flight instead of reporting a
   false cancellation;
2. remove direct contact identifiers and campaign memberships;
3. materialize aggregate campaign counts, then delete row-level terminal
   delivery/event history, rendered payloads, precise timestamps, and provider
   identifiers;
4. convert accepted or indeterminate outcomes older than the configured
   seven-day reconciliation window to an aggregate `indeterminate` result and
   preserve a do-not-contact fingerprint instead of retaining direct data
   forever; and
5. retain a keyed recipient-token mapping for the contact review window and
   keyed provider-message/event receipts for their separate expiry window, so
   old unsubscribe links and late permanent provider events work without
   recovering the email address or retaining event type/timestamps per row.

`CODRUT_CAMPAIGN_RECIPIENT_PURGE_ENABLED` defaults to `true` after the contact
privacy contract migration. The bridge migration scrubs rollback-compatible
suppression values before the final contract removes the compatibility column,
so purge never depends on a retained full email.
`CODRUT_CAMPAIGN_RECIPIENT_DELIVERY_RECONCILIATION_DAYS` defaults to seven days.
`CODRUT_CAMPAIGN_DELIVERY_TOMBSTONE_RETENTION_DAYS` separately defaults to
365 days. Delivery and deduplication receipts are deleted at that deadline even
when a contact's do-not-contact fingerprint remains justified.

Restoring an archived contact does not clear hard-bounce or unsubscribe
protection. Correcting a bounced address leaves the old address blocked and
requires an explicit activation decision for the corrected address.

## Suppression fingerprints are personal data

The fingerprint is a keyed HMAC of the normalized email address and trainer
owner. It reduces exposure if the suppression table is read without the key,
but the application can still test an address against it. Treat it as
pseudonymous personal data with the same access, backup, incident-response, and
audit controls as other personal data. Do not describe it as anonymous.

The 30-day Archive window does not apply automatically to suppression
fingerprints. Retaining a fingerprint requires a documented purpose, a review
date, restricted access, and deletion when the purpose no longer justifies it.
The default review cadence is 365 days, configured by
`CODRUT_EMAIL_SUPPRESSION_REVIEW_DAYS`. The daily worker applies the configured
review policy to due fingerprints and records the system reviewer, decision,
legal/operational basis, and next review or deletion date in
`email_suppression_reviews`. Unknown restriction reasons fail closed: they are
quarantined as `needs_review` for an authorized human decision, never deleted
automatically. Recipient-token tombstones without a do-not-contact reason expire
at the end of their defined review window; contact tombstones with a restriction
follow the same annual necessity review as suppression fingerprints. Provider
message/event receipts expire separately and contain only keyed fingerprints,
campaign scope, and the expiry needed for late-event handling.

This distinction follows the European Commission guidance on
[storage limitation](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/principles-gdpr/how-long-can-data-be-kept-and-it-necessary-update-it_en)
and on
[personal data and pseudonymisation](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/application-gdpr_en).
The privacy notice must state the do-not-contact purpose, data category,
retention/review approach, recipients, and applicable rights. A rights request
must be assessed against that purpose and the applicable legal basis rather
than answered with a blanket “deleted after 30 days” statement.

## Secret handling

`CODRUT_EMAIL_SUPPRESSION_FINGERPRINT_SECRET` must be:

- generated once with a cryptographically secure generator such as
  `openssl rand -hex 32`;
- at least 32 characters and different from session, task-link,
  campaign-asset, provider, and webhook secrets;
- stored in the deployment secret manager and recovery credential backup, never
  in Git, application logs, support exports, or shell transcripts; and
- supplied to both the API and worker before migration and startup.

The secret is intentionally stable. HMAC output cannot be re-keyed from the old
fingerprint alone, so an uncoordinated environment-variable rotation would
silently disable protection for already purged addresses.

If compromise requires rotation:

1. enter maintenance and pause contact import, send launch, archive purge, and
   suppression writes;
2. preserve the old key in the secret manager and record the incident;
3. ship and verify a versioned dual-key lookup path before changing the active
   key;
4. write new suppressions with the new key and check both key versions;
5. re-fingerprint records only where the normalized source address is still
   legitimately retained; and
6. keep the legacy lookup key under restricted access until every remaining
   legacy fingerprint reaches a documented review/deletion decision.

The current single-key runtime does not support an environment-only rotation.
Treat a proposed rotation without the dual-key migration as a launch blocker.

## Release and audit checks

Before promoting a release that introduces or changes this lifecycle:

- take and verify a database backup;
- confirm the suppression-fingerprint secret exists in every target environment
  and is not equal to another application secret;
- rehearse the migration with existing suppressions;
- prove Archive purge is idempotent and preserves aggregate counts;
- prove old unsubscribe links and late provider events resolve through keyed
  tombstones after direct-data deletion;
- prove cross-trainer access and fingerprint matching are denied;
- confirm the scheduled purge and annual review process have named owners; and
- update the privacy notice and retention register before processing live
  contacts under the new lifecycle.

## Expand/contract rollback window

The archive release first adds the fingerprint and review fields, then the
privacy bridge backfills and enforces them. The database retains the legacy
`email` column only as a rollback-compatibility field. The bridge replaces every
value with a deterministic `@invalid` placeholder and a trigger prevents a real
address from being stored there again. The application model and all lookups use
the keyed owner-scoped fingerprint, never the compatibility value.

Permanent and scheduled purge can run after the bridge migration succeeds.
Archiving, restoring, membership removal, queued-send cancellation, and the
reviewable retention timestamps remain available throughout the rollout.

Archive also stores the prior delivery status and changes an active archived
contact to `suppressed`. The immediately previous image does not understand
`archived_at`, but it therefore still treats every archived contact as
non-sendable. The fingerprint-aware image restores the prior status only when
no bounce or unsubscribe suppression was recorded while the contact was
archived.

An emergency rollback to the previous image remains service recovery, not a
normal campaign-operations window. Archived contacts can appear as inactive in
that older UI, so avoid contact catalog mutations until the fingerprint-aware
image is restored. Existing archive state cannot silently become sendable, and
participant flows and health checks remain available.

The bridge migration:

1. backfills any rows written by the previous image;
2. makes fingerprint, review date, and event owner non-null;
3. removes the legacy full-email uniqueness index;
4. scrubs the compatibility column and installs its enforcement trigger; and
5. enables permanent and scheduled purge in the fingerprint-aware application.

Do not remove the compatibility column while a retained rollback image still
maps it. A future cleanup may drop it only after both current and previous
images have been proven not to map the field. That cleanup is storage hygiene,
not a privacy dependency: no full address remains in the column after the
bridge.
