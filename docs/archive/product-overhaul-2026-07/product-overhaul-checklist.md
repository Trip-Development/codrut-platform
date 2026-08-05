# Product Overhaul Checklist

UI gate: approved by the product owner on 2026-07-22

Status keys: `todo`, `active`, `verified`, `blocked`.

| Surface | Design | Backend | States and a11y | Tests | Status |
| --- | --- | --- | --- | --- | --- |
| `/` landing | preserve, copy audit | contact action | header and links | component smoke | verified |
| Auth and account recovery | preserve, copy audit | session and password policy | pending, error, restored session | integration | verified |
| Invite and onboarding | simplify | invite and consent | invalid, expired, accepted | integration | verified |
| Trainer shell | compact rail | session and CSRF | navigation, logout, error | component | verified |
| Trainer dashboard | operational hierarchy | summary APIs | loading, empty, partial failure | component | verified |
| Companies | table-first | company APIs | filter, empty, create failure | component | verified |
| Company overview and projects | remove repeated summaries | company/project APIs | loading, empty, mutation | integration | verified |
| Teams and organization | task-first | team APIs | empty, conflict, failure | integration | verified |
| Projects and participants | table-first | project/roster APIs | import and mutation states | integration | verified |
| Assignments | dedicated matrix | assignment plan APIs | proposed, saved, invalid | integration | verified |
| Invitations | delivery table | invite dispatch APIs | ready, sent, failed, retry | integration | verified |
| Questionnaires catalog/editor | editor workspace | forms APIs | dirty, saving, invalid, version | integration | verified |
| Participant questionnaires | focus mode | response APIs | autosave, submit, recovery | integration | verified |
| Participant dashboard/account | calm task hierarchy | participant APIs | loading, empty, error | integration | verified |
| Results and reports | interpretation-first | scoring/report APIs | privacy, insufficient data | domain and integration | verified |
| Communication navigation | stable URL views | email summary APIs | loading, empty, partial failure | integration | verified |
| Campaigns and recipients | progressive workbench | campaign APIs | validation, save, send, retry | domain and integration | verified |
| Contacts and imports | CRM table | recipient APIs | preview, invalid row, import failure | domain and integration | verified |
| Templates | focused editor | template APIs | dirty, preview, version | integration | verified |
| Trainer and participant settings | concise forms | identity/settings APIs | save, validation, destructive | integration | verified |
| Legal pages | owner-approved public content | none | keyboard and links | route smoke | verified |
| Error, not-found, loading | shared hierarchy | retry paths | focus and announcements | component | verified |

## Cross-Cutting Gates

- [x] Current implementation checkpointed locally before overhaul work.
- [x] Current `origin/dev` is contained and branch started from current `origin/prod`.
- [x] Local preview data is explicit, persisted, repeatable, and blocked in production.
- [x] Local routes resolve persisted trainer and participant users without login or cookie switching; production rejects the bypass.
- [x] No failed backend mutation can be represented as local success.
- [x] CSP, CSRF, authorization, rate limit, upload, and email-policy checks pass.
- [x] Password rules match across browser validation, OpenAPI, and backend validation.
- [x] Critical domain coverage reaches the agreed thresholds without slow duplicate tests. Backend coverage is 88.19% statements, 81.43% branches, and 86.82% lines; critical workflow branch coverage ranges from 85.00% to 91.07%. Frontend coverage is 82.00% statements and 75.30% branches.
- [x] Future training-assistant extension points were audited without adding premature chatbot behavior or dependencies.
- [x] Desktop route matrix passes in the in-app browser at 1496px and the 744px vertical-tab width used for annotations, with no document overflow.
- [x] Mobile smoke has no broken navigation, document overflow, or blocked navigation action.
- [ ] Final diff, screenshots, coverage, bundle report, and known risks are ready for human review. Coverage, bundle, diff, risks, and in-app DOM inspection are recorded; durable screenshots and final human visual approval remain open.
- [x] Protected content v3 is participant-schema projected, checksum-validated, imported, and activated locally without repointing legacy or synthetic assignments.
- [x] Migrations are rehearsed against a synthetic production-shaped `0033` database. The guarded rehearsal proves 195-participant retention, bounded lock failure, owner-isolation cloning, normalized duplicate repair, relationship retention, unsafe rollback protection, upgrade through `0044`, and no model drift without reading production data.
- [x] The 195-participant fake-provider simulation passes, the focused Brevo adapter/webhook/outbox suite passes, and the owner confirms the authorized Brevo test is working and approved for the controlled pilot.
- [x] External backup credentials and restore rehearsal are deferred from this release gate by the owner. Local encrypted backup restore evidence remains recorded.
- [x] Romanian privacy, terms, and cookie text is owner-approved for the controlled pilot.
- [x] Final Docker cleanup is recorded without stopping or pruning the active review stack. The isolated rehearsal container, dedicated rehearsal volume, obsolete rehearsal image, and temporary proof directories were removed after evidence capture; all seven review-stack services remain running.
- [x] No PR, push, merge, or deployment before explicit approval.
