# Product Overhaul Review Packet

UI gate: approved by the product owner on 2026-07-22

Branch: `codex/frontend-greenfield-rebuild`

Base: `origin/dev` at `c465b50`

The verification recorded in this packet was completed before release promotion. Production promotion follows the repository's feature-to-dev-to-prod pull request workflow.

## Product Result

- The accepted zinc, white, burgundy, and Geist direction remains intact.
- Auth and landing keep their accepted layout. The public page follows the system theme and has no theme control.
- Authenticated account menus use one `System`, `Light`, or `Dark` selector. `System` is the default and follows operating-system changes.
- Dark mode uses a deep true red (`#C92A2A`) for brand fills and `#FF6B6B` for readable active text. Light surfaces are neutral `#FAFAFA`, `#FFFFFF`, and `#F4F4F5`; unused warm-cream tokens and obsolete gradient utilities were removed.
- Companies, projects, participants, assignments, invitations, contacts, and campaign recipients use compact, table-first workspaces with explicit states.
- Filter dropdowns on company, project, and campaign recipient workspaces use the shared searchable Radix combobox with automatic search focus, keyboard navigation, diacritic-insensitive matching, and existing URL persistence.
- Questionnaire editing uses a section navigator, selected-question canvas, contextual inspector, version controls, explicit save state, and participant renderer preview.
- Campaigns use progressive disclosure, retained form values, field-level errors, retry, explicit send readiness, recipient selection, durable dispatch, cancellation, and idempotency.
- Participant routes use a calmer task hierarchy, focus-mode questionnaires, Back-triggered draft persistence, privacy-gated results, and participant-safe Romanian result labels.

## Deployed Parity

The durable route comparison is in `docs/product-overhaul-route-matrix.md`.

- No deployed customer route is missing locally.
- `/dev/routes` is intentionally retired because it has no customer capability.
- Existing auth, invite, registration, secure-link, questionnaire, roster, assignment, invitation, reporting, campaign, contact, and template goals remain reachable.
- Assignments and invitation delivery are separated into dedicated routes without removing plan generation, regeneration, manual assignment, send, resend, or delivery state.
- Company navigation is reduced to Projects and all-company Participants; Settings remains a header action.
- `/participant/chat` remains the existing support placeholder. No chatbot or roleplay behavior is included in this release.

## Local Preview

`just seed-local-preview` is explicit, repeatable, persisted in PostgreSQL, and rejected in production.

Current seed:

- 3 companies
- 6 projects
- 10 participants
- 21 assignments
- 3 campaigns
- 8 contacts
- PCM, Lencioni, distress-driver, and iCARE synthetic samples, including invented statement-specific participant choices rather than bare numeric labels
- Four iCARE review targets, one partial draft, two completed anonymous reviews, and a visible privacy-threshold aggregate
- Draft, sent, opened, clicked, replied, viewed, unsubscribed, suppressed, completed, and failed states

Local route-scoped authentication bypass resolves real seeded database users and permissions without cookie switching. Production configuration rejects auth bypass and demo fallback.

## Protected Content

- Complete official questionnaires, campaign templates, scoring formulas, and private interpretations are absent from the implementation repository head.
- Public source contains schemas and synthetic fixtures only.
- The active local-only package is stored outside the implementation repository at `.campaign/cache/protected-content/codrut-leadership-pilot-2026-v3.json`.
- The package inventory is 4 questionnaires and 8 official templates. Its validated checksum is `47fcb5891d7f7c0c43c6d430de4607d5add3759b2070f53c8129361cbadaeae7`.
- Versioned package validation, transactional import, activation, immutable system definitions, assignment version pinning, duplicate-safe retries, and import audit records are implemented.
- Package re-versioning now projects participant-safe schema before calculating the final checksum; private response and scoring metadata remains in `private_config` and is never copied into participant schema.
- Participant APIs return public schema, approved result labels, scores, and permitted interpretation only. Private scoring configuration is not serialized.

The re-versioned package imports questionnaires as immutable active version `3` definitions and campaign templates as immutable active version `9` or `11` definitions. The local import audit records package `codrut-leadership-pilot-2026-v3`. Existing assignments remain pinned and were not repointed. Synthetic version `9001` samples remain available for local assignments without replacing the active protected definition.

## Backend And Operations

- Added durable email outbox rows with immutable payloads, idempotency keys, payload conflict detection, leases, `SKIP LOCKED` claiming, bounded retries, stale-lease recovery, cancellation, and auditable state transitions.
- Campaign and invitation requests queue delivery. Assignment invitation state changes only after provider acceptance.
- The worker restarts cleanly and treats intentional cancellation as normal shutdown instead of emitting a failure-looking traceback; real processing exceptions still propagate.
- Added protected-content and consent audit boundaries.
- Anonymous and authenticated consent records persist legal-document version, timestamp, invite/session identity, profile identity, and source.
- Result policy is questionnaire-specific. iCARE uses `max(2, min(3, eligible non-self reviewers))` and never publishes one-person aggregates.
- Updated password policy to 12 through 128 characters, no composition rules, local common-password rejection, and bounded k-anonymous breach checking.
- Campaign assets are decoded, dimension and pixel checked, metadata-normalized, ownership-scoped, uploaded during save, and cleaned up after failed persistence.
- Production Compose requires public URL, separate signing secrets, verified sender identity, authenticated Brevo callbacks, and trusted proxy configuration. It hard-disables auth bypass and demo fallback.
- Encrypted Restic backup, retention, integrity-check, and isolated restore tooling is implemented for PostgreSQL dumps and campaign assets with 14 daily, 8 weekly, and 6 monthly restore points.

Migrations added:

- `0037_protected_content_boundary`
- `0038_durable_email_outbox`
- `0039_consent_acceptance_audit`
- `0040_project_scoped_invites`
- `0041_assignment_rounds`
- `0042_delivery_events_reminders`
- `0043_result_publication_audit`
- `0044_communications_delivery_hardening`

The local database and isolated restored database are at `0044`; `alembic check` reports no model drift. A guarded synthetic production-shaped rehearsal recreated the legacy `0033` shape with 195 participants, 195 sessions, 197 contacts, 297 campaign memberships, 20 events, and 50 sends. A conflicting lock produced a bounded failure in 1.154 seconds without advancing the revision. The subsequent `0034` through `0044` upgrade completed, retained all participant and session rows, removed normalized duplicates, repaired cross-owner relationships, and preserved send ownership. The documented unsafe downgrade boundary correctly blocked. The disposable rehearsal database was removed after proof. No production or August-pilot data was read.

## Synthetic Pilot Proof

The destructive simulator was rerun during the dedicated readiness pass only against a fresh local database named `cody_controlled_pilot_simulation`. Its guards require a non-production database ending in `_simulation`, the exact synthetic acknowledgement, exactly 195 participants, exactly 17 leaders, and an allowance of at least 750 messages. The database was dropped after the report was recorded.

- 195 participants, 17 permanent leadership accounts, and 178 secure-link accounts
- 195 assignments submitted, scored, and recorded in the publication audit
- 195 invitations with 190 delivered, 5 bounced, and 3 transient failures recovered
- 20 participants received 2 reminder rounds, for 40 reminder events
- 195 campaign recipients, including 5 globally suppressed before dispatch, 185 delivered, 5 bounced, 2 unsubscribed, and 6 suppressed in total
- 0 duplicate campaign rows after retry and 10 deliveries cancelled before dispatch
- 425 provider-accepted synthetic messages

No production database, participant, address, provider, or message was accessed by this proof.

## Mutation And Recovery Evidence

- Campaign creation and editing retain values after validation, network, permission, and server errors.
- Backend validation locations map to Romanian field messages and focus the first invalid field.
- Retrying a failed campaign save reuses retained form state and does not emit false success.
- Campaign send remains blocked with a visible reason for missing content, recipients, image, video thumbnail, or delivery state.
- Contact import preserves blank or invalid email rows as inactive records under the established Romanian rules.
- Questionnaire autosave exposes pending/failure through the primary action and does not add persistent `Draft salvat` clutter.
- API adapters do not translate backend failure into local success.
- Unexpected API failures can carry a correlation identifier without exposing sensitive details.

## Browser Review

The in-app browser verified populated local routes and backend data for:

- landing, auth direction, and absence of a public theme button
- participant dashboard, four iCARE targets, questionnaire runner, account, and results
- company list, searchable company participants, and project-first company navigation
- project list, searchable project participants, assignments, regenerated plan action, invitations, organization, reports, and settings
- questionnaire catalog and three-column editor behavior
- campaigns, bounded recipient list, searchable recipient filters, contacts, templates, and campaign validation/recovery states

Specific checks:

- Project `Participanți` has `aria-current="page"` after client navigation.
- Company and project participant tables both have name, email, role, and manager search.
- Participant iCARE results show `Dezvoltare`, `Colaborare`, `Claritate`, and `Adaptare`; private dimension identifiers do not reach visible copy.
- The active stack logs show successful backend and route requests without unhandled server errors during the pass.
- The previously failing direct questionnaire route now receives an explicit loopback-only participant role and preserves it through `Headers`; the in-app browser loaded the synthetic iCARE questionnaire without login or account switching.
- A fresh in-app browser pass rendered landing, auth, trainer dashboard, companies, projects, questionnaires, all three communication views, participant dashboard, questionnaires, results, account, company participants, and every project workspace route without a fatal page state or console warning/error.
- The project company filter opened with its search field active, keyboard semantics exposed, and all seeded options available.
- Selecting `Atelier Meridian` persisted `company=<id>` in the URL and remained selected after a full refresh.
- At the 744px vertical-tab width, company, project, participant, invitation, contact, questionnaire, results, and account routes had zero document-level horizontal overflow; wide tables scrolled only inside their bounded table region.
- A sampled client-navigation trace moved the sidebar selector directly from `Proiecte` to `Companii`; `Acasă` never became active during the transition.
- Campaign creation with an empty name retained the value, kept the modal open, marked the field invalid, focused it, and displayed `Adaugă un nume pentru campanie.`
- The synthetic iCARE runner displayed participant-facing behavior choices for every statement and no bare `1` through `4` options.

The in-app browser DOM, interaction, and screenshot paths work. The expanded desktop account menu was captured after the theme-selector width fix. A complete durable before/after image set for every review route is still missing from this packet.

## Verification

| Check | Result |
| --- | --- |
| Backend Ruff | Pass |
| Backend tests | 715 passed, 1 third-party Starlette/httpx deprecation warning |
| Frontend tests and coverage | 490 passed across 62 files |
| Frontend ESLint | Pass |
| Frontend TypeScript | Pass |
| Next production build | Pass, 28 static pages generated |
| OpenAPI snapshot | Current |
| Generated TypeScript API client | Regenerated and contract-tested, 62 focused contract tests pass |
| Alembic current | `0044_communications_delivery_hardening` |
| Alembic model check | No new upgrade operations detected |
| Development Compose config | Pass |
| Production Compose config | Rejects missing required identity values and passes with complete placeholders |
| Local encrypted backup/restore | Pass, snapshot `2e4644e8`, full integrity check, restored at `0044` with 30 tables and 50 foreign keys |
| Synthetic production-shaped migration rehearsal | Pass, bounded lock failure, legacy duplicate/ownership repair, upgrade through `0044`, no drift |
| Focused Brevo webhook suite | 10 passed; provider and outbox behavior is also covered by the full backend suite; owner confirms the authorized Brevo test is working and approved |
| Local health | Live and ready pass; database, Redis, migration, worker, and outbox are all `ok` |
| Frontend production dependency audit | No known vulnerabilities |
| Git whitespace check | Pass |

Measured coverage:

- Backend: 88.19% statements, 81.43% branches, and 86.82% line coverage.
- Frontend: 82.00% statements, 75.30% branches, 82.72% functions, and 84.41% lines.

Critical backend workflow branch coverage is 86.36% for authentication, 85.13% for campaign delivery, 86.27% for assignments, 85.00% for questionnaire persistence and protected content, 91.07% for scoring, and 89.38% for participant policy. These tests exercise decisions, failures, privacy boundaries, retries, and state transitions rather than padding coverage with implementation assertions. Package-wide branch coverage is lower because it also includes thin routers and repository query variants; the overall backend remains above the agreed 75% baseline. The frontend meets its 75% branch baseline with behavior tests covering authentication recovery, invitation states, campaign validation, adapter failures, searchable filters, shell loading, modal focus, report privacy, and malformed score exclusion.

Bundle:

- Shared first-load JavaScript: 103 kB.
- Largest listed first-load route: 165 kB for participant account/settings.
- The communication and questionnaire catalogs remain route-split rather than loading the full editor at the public entry point.

## Security And Privacy

- CSP, CSRF, session, authorization, rate-limit, upload, contact ownership, email sanitization, placeholder, unsubscribe, and security-header checks pass in the automated suite.
- Production configuration rejects placeholder or missing critical operational identity.
- Necessary session and CSRF cookies do not require a consent banner. Cookie, privacy, and terms text is owner-approved for the controlled pilot.
- Session restoration personalizes the remembered-user transition only after backend validation.
- Sensitive answers, tokens, formulas, and private interpretations are excluded from structured mutation logs.
- `pnpm audit --prod --audit-level=moderate` reports no known frontend production dependency vulnerabilities. The lockfile pins patched transitive `uuid@11.1.1`, `postcss@8.5.16`, `brace-expansion@1.1.16`, and `brace-expansion@2.1.2` releases.
- An ephemeral `pip-audit` run reports no known Python dependency vulnerabilities; the private `codrut-backend` package itself is correctly skipped because it is not published to PyPI.

## Post-Deployment Follow-Up

1. Run the authorized user acceptance pass, incorporate any newly observed defects, and repeat the affected verification before the real participant cohort begins.

The GitHub `prod` environment contains the Brevo provider, API key, sender address, sender name, and independent webhook token secret names. Their values were not read or printed. The owner confirms Brevo and legal approval for this controlled pilot.

Encrypted external backup configuration and restore rehearsal are explicitly deferred from this release gate by the owner. The existing local encrypted restore evidence remains recorded but is not a deployment prerequisite.

## Controlled Docker Cleanup

The first cleanup pass started from 12 images, 20 volumes, and 200 BuildKit records. It removed eight unattached `codrut-participant-edit_*` volumes, the unattached `codrut_frontend_build_tmp` volume, unreferenced runtime images, obsolete `traefik:v3.4`, and 40.8 MB of builder cache older than seven days.

The final proof pass started with:

- Images: 10 total, 5.996 GB, 330.7 MB reclaimable.
- Containers: 7 total, all active, 18.96 MB, none reclaimable.
- Volumes: 12 total, 11 active, 2.732 GB, 495.6 kB reclaimable.
- Build cache: 182 records, 25.44 GB, 20.59 GB reported reclaimable.

Verified and removed during the final pass:

- The dedicated `codrut-platform_backup_rehearsal_workspace` volume after confirming that no container referenced it.
- The unreferenced `codrut-platform-backup-rehearsal:latest` image.
- A seven-day builder prune found 0 B eligible; the remaining cache is newer than the preservation threshold.

Final state:

- Images: 9 total, 5.996 GB, 373.2 MB reclaimable.
- Containers: 7 total, all active, 18.96 MB, none reclaimable.
- Volumes: 11 total, all active, 2.732 GB, none reclaimable.
- Build cache: 182 records, 25.44 GB, 20.59 GB reported reclaimable but preserved by the age policy.

No global image, volume, network, or system prune ran. No active database, Redis, asset, dependency, build, devcontainer, or review-stack volume was removed. No orphaned Codruț networks or stopped containers remain. The seven-service `codrut-platform` review stack is running.

## Human Review Routes

1. `/trainer/companies`
2. `/trainer/companies/<company>/participants`
3. `/trainer/questionnaires`, then open a sample definition
4. `/trainer/projects/<project>/assignments`
5. `/trainer/projects/<project>/invitations`
6. `/trainer/email?view=campaigns`, including create validation and recipient disclosure
7. `/trainer/email?view=contacts`
8. `/participant/questionnaires`
9. `/participant/results`
10. `/participant/account`, including System, Light, and Dark theme selection

No shipping action is authorized until the remaining human and deployment-operation checks are resolved and this gate is explicitly approved.
