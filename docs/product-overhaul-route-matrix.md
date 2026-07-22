# Codrut Route And Capability Matrix

Gate: `HUMAN_GATE_UI_PRODUCTION_READY`

This matrix compares the current `origin/prod` route tree with the local controlled-pilot branch. A route being present is not proof of launch readiness. The `Evidence` column names the remaining proof required before the gate can be approved.

Status keys:

- `preserved`: deployed capability remains available through the same route.
- `expanded`: the deployed capability remains and the local branch adds a controlled-pilot behavior.
- `replaced`: the same user goal is served through a deliberately different interaction.
- `retired`: intentionally removed with no customer capability loss.

## Public And Identity

| Route | Deployed behavior | Local controlled-pilot behavior | Intended decision | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/` | Public product page and role entry points | Accepted editorial landing direction, system theme only, reduced non-actionable copy | Preserve identity and access paths | preserved | in-app visual pass |
| `/login` | Participant authentication | Same authentication contract, consistent auth shell and validated session restoration | Participant entry remains distinct | preserved | auth integration suite |
| `/trainer/login` | Trainer authentication | Same contract and shared auth behavior | Trainer entry remains distinct | preserved | auth integration suite |
| `/register` | Invite-aware registration | Same flow with current password policy and field recovery | Preserve registration semantics | preserved | invite registration journey |
| `/reset-password` | Reset request | Same flow with explicit pending, failure, and success states | Preserve | preserved | identity tests |
| `/update-password` | Reset-token password update | Same flow with 12 to 128 character policy and common-password rejection | Preserve | preserved | identity tests |
| `/onboarding` | Authentication-aware redirect | Same compatibility route | Keep redirect for old links | preserved | route smoke |
| `/confidentialitate` | Not present | Romanian privacy policy | Owner-approved for the controlled pilot | expanded | route smoke and owner approval confirmed |
| `/termeni` | Not present | Romanian terms | Owner-approved for the controlled pilot | expanded | route smoke and owner approval confirmed |
| `/cookies` | Not present | Necessary-cookie disclosure without nonessential consent banner | Owner-approved for the controlled pilot while only session and CSRF cookies are used | expanded | runtime cookie inventory and owner approval confirmed |
| `/dev/routes` | Developer route index exposed by the app | Removed | No customer value and unsafe for production discovery | retired | route tree confirms removal |

## Anonymous Invitation

| Route | Deployed behavior | Local controlled-pilot behavior | Intended decision | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/invite/[token]` | Invitation lookup, registration or secure-link entry | Same entry goal with persisted consent, invalid/expired recovery, and explicit exchange failure | Preserve both permanent-account and secure-link flows | expanded | backend consent and invite tests |
| `/invite/[token]/tasks/[taskId]` | Task opens through the general questionnaire route | Dedicated compatibility route for invitation tasks | Keep old links and isolate secure task access | expanded | critical invite journey |

## Participant

| Route | Deployed behavior | Local controlled-pilot behavior | Intended decision | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/participant`, `/participant/dashboard` | Participant task overview | Same assignments with calmer hierarchy and populated local states | Preserve all active work and completion navigation | replaced | in-app route pass |
| `/participant/questionnaires` | Assigned questionnaire list | Same persisted assignments, targets, drafts, completion and result states | Preserve | preserved | participant integration tests |
| `/participant/questionnaires/[key]` | Questionnaire completion | Same renderer with automatic draft persistence, Back recovery, validation, and submit-only success emphasis | Preserve answers and immutable assignment version | expanded | persistence and focus tests |
| `/participant/tasks/[taskId]` | Task compatibility entry | Same task resolution | Preserve old task links | preserved | route and API tests |
| `/participant/results` | Available computed results | Policy-controlled scores and approved feedback; no raw responses or scoring formula | Publish only after scoring and privacy thresholds | expanded | scoring/privacy tests and pilot data rehearsal |
| `/participant/account` | Account and program information | Standard settings surface and consistent password validation | Preserve | replaced | account integration tests |
| `/participant/consent` | Not present | Authenticated consent surface backed by persisted legal version | Required before protected participant work when policy applies | expanded | consent tests |
| `/participant/onboarding` | Participant onboarding compatibility route | Same compatibility behavior | Preserve | preserved | route smoke |
| `/participant/final-evaluation` | Final evaluation route | Same workflow | Preserve until program policy explicitly changes | preserved | route smoke and API check |
| `/participant/chat` | Existing placeholder surface | Retained but not expanded into an AI product | Do not ship roleplay behavior in this release | preserved | future-boundary audit only |

## Trainer Core

| Route | Deployed behavior | Local controlled-pilot behavior | Intended decision | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/trainer` | Trainer overview | Operational queue and current activity instead of decorative metrics | Preserve access to all trainer work | replaced | in-app route pass |
| `/trainer/companies` | Company list and creation | Searchable table, status and activity filters, direct actions, persisted backend mutations | Preserve company lifecycle | expanded | component and API tests |
| `/trainer/companies/[companyId]` | Company overview | Project-first company workspace with Projects and Participants views | Preserve company projects and aggregate roster, remove redundant submenu | replaced | in-app route pass |
| `/trainer/companies/[companyId]/participants` | Participants embedded in overview | Dedicated searchable all-project roster | Preserve data while reducing page overload | expanded | search/table tests |
| `/trainer/companies/[companyId]/settings` | Company settings | Same settings contract, header action | Preserve | preserved | settings tests |
| `/trainer/companies/[companyId]/teams` | Not separately routed in prod | Dedicated team compatibility surface | Keep while team workflows are active | expanded | team integration tests |
| `/trainer/companies/[companyId]/invitations` | Invitation information inside company workspace | Dedicated compatibility surface | Keep delivery access while project invitations are primary | expanded | invite integration tests |
| `/trainer/projects` | Project list | Searchable, URL-persisted filters and readable desktop table | Preserve project lifecycle and direct navigation | expanded | component tests and in-app pass |
| `/trainer/projects/[projectId]` | Project summary | Same project object with concise summary and live active tabs | Preserve | replaced | route navigation tests |
| `/trainer/projects/[projectId]/participants` | Roster import and participant access | Same imports and accounts with searchable roster and access views | Preserve DB-backed roster operations | expanded | roster integration tests |
| `/trainer/projects/[projectId]/participants/[participantId]` | Participant detail | Same participant and assignment detail | Preserve | preserved | route/API tests |
| `/trainer/projects/[projectId]/assignments` | Assignment planning within invitation workspace | Dedicated assignment planning and advanced creation | Preserve generation, regeneration, manual assignment, and save | replaced | assignment integration tests |
| `/trainer/projects/[projectId]/invitations` | Invitation dispatch and delivery | Dedicated delivery surface with task count disclosure and recovery | Preserve dispatch, resend, secure links, and delivery state | replaced | outbox and invitation tests |
| `/trainer/projects/[projectId]/org-chart` | Organization chart | Same data and editing goal | Preserve | preserved | organization tests |
| `/trainer/projects/[projectId]/teams` | Project teams | Same team goal | Preserve | preserved | team tests |
| `/trainer/projects/[projectId]/reports` | Project reporting | Interpretation-first reports with privacy state, drill-down, print and export | Preserve calculations and exports | expanded | scoring/report tests and browser pass |
| `/trainer/projects/[projectId]/reports/lencioni` | Lencioni detail | Same report compatibility route | Preserve old links | preserved | report tests |
| `/trainer/projects/[projectId]/reports/drivers` | Stress-driver detail | Same report compatibility route | Preserve old links | preserved | report tests |
| `/trainer/projects/[projectId]/settings` | Project settings | Same backend contract with clearer mutation states | Preserve | expanded | settings tests |
| `/trainer/questionnaires` | Questionnaire catalog and editor | Version-aware workspace, protected definitions, explicit saves and participant-renderer preview | Preserve trainer access without exposing private scoring to participants or source | expanded | protected-content and editor tests |
| `/trainer/settings` | Trainer account settings | Same account/security goal | Preserve | preserved | identity tests |

## Communication

| Route | Deployed behavior | Local controlled-pilot behavior | Intended decision | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/trainer/email?view=campaigns` | Campaign creation and send controls | Campaign list with progressive detail, route-addressable full-height editor, draft-tolerant validation, explicit send readiness and durable dispatch status | Preserve content, recipients, test send and delivery; human review decides whether the focused editor remains modal or becomes a dedicated route | replaced | outbox tests, in-app review, and authorized email rehearsal |
| `/trainer/email?view=contacts` | Campaign contact management | Searchable CRM table, URL-persisted segment filter, import preview, inactive invalid rows, icon-only edit actions | Preserve import and recipient eligibility rules | replaced | import tests and browser pass |
| `/trainer/email?tab=templates` | Email template catalog/editor | Focused template editing behind protected/system ownership boundary | Preserve official and trainer templates without public source leakage | expanded | package import and template tests |

## Pilot Parity Conclusions

- No deployed customer route is missing from the local branch.
- `/dev/routes` is the only removed route and has no customer capability.
- The highest-risk parity changes are assignments/invitations, campaign dispatch, questionnaire definition versioning, participant consent, and result publication. They require backend integration evidence, not visual approval alone.
- Local authentication bypass and synthetic preview content are development adapters. Production configuration must reject both.
- The retained `/participant/chat` route is not evidence of chatbot readiness. Navigation registration, permissions, conversation storage, provider boundaries, trainer oversight, retention, cost, and safety remain future work documented separately.
