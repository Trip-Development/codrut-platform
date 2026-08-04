# CF0002 Current-Dev Parity Ledger

Baseline: product `origin/dev` at `ee63802` on 2026-08-04. The route inventory
contains 44 `page.tsx` entries. This ledger is derived from the current route
tree, current tests, and current product documentation. It does not reuse an
older `origin/prod` comparison as fresh redesign authorization.

During Sequence 01, copy this ledger to
`docs/frontend-redesign-parity-ledger.md` on the feature branch. Update the
product copy with evidence and dispositions as work proceeds. Retain
`docs/product-overhaul-route-matrix.md` as historical controlled-pilot/release
evidence; do not overwrite it.

Disposition keys:

- `unmigrated`: current `dev` behavior is the baseline; no CF0002 change proved.
- `preserved`: migrated presentation with the same capability and outcomes.
- `replaced-approved`: owner approved a different interaction serving the same
  goal after parity proof.
- `blocked`: evidence is missing or a proposed change crosses the contract.

Every entry starts `unmigrated`. A route becomes `preserved` only after its
named behavior proof and relevant live check pass. Visual review alone is not
proof of data, security, delivery, persistence, or calculation parity.

## Public, legal, and identity

| Route | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/` | Public product page and role entry | Trainer and participant access paths remain reachable | Composition, copy, tokens, local photography, responsive hierarchy | `app/page.test.tsx`; live links/themes/viewports | unmigrated |
| `/login` | Participant authentication | Session restoration, errors, return path, and role boundary | Shared auth shell, copy, fields, states | `app/login/page.test.tsx`; auth contracts; live failure/success | unmigrated |
| `/trainer/login` | Trainer authentication | Trainer entry and session/role isolation | Shared auth shell, copy, fields, states | `app/trainer/login/page.test.tsx`; auth contracts; live failure/success | unmigrated |
| `/register` | Invite-aware registration | Invite context, password policy, field recovery, account outcome | Auth shell, hierarchy, feedback | `app/register/page.test.tsx`; password/auth contracts; invite journey | unmigrated |
| `/reset-password` | Password reset request | Request semantics and explicit pending/failure/success recovery | Auth shell, copy, form states | `app/reset-password/page.test.tsx`; password contracts | unmigrated |
| `/update-password` | Token-based password update | Token validation, password policy, error and success recovery | Auth shell, copy, form states | `app/update-password/page.test.tsx`; password contracts | unmigrated |
| `/onboarding` | Authentication-aware compatibility/redirect entry | Existing redirect destination and old-link behavior | Loading/redirect presentation only | route inspection and authenticated/anonymous smoke | unmigrated |
| `/confidentialitate` | Romanian privacy policy | Legal content, navigation, and readable access remain | Reading layout, typography, responsive spacing | `app/confidentialitate/page.test.tsx`; content diff; live read | unmigrated |
| `/termeni` | Romanian terms | Legal content, navigation, and readable access remain | Reading layout, typography, responsive spacing | content diff and route smoke | unmigrated |
| `/cookies` | Necessary-cookie disclosure | Current disclosure and access remain; no invented consent behavior | Reading layout, typography, responsive spacing | content diff and runtime cookie assumption check | unmigrated |

## Anonymous invitations

| Route | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/invite/[token]` | Invitation lookup and registration or secure-link entry | Valid, invalid, expired, consent, exchange-failure, permanent-account, and secure-link paths | Hierarchy, copy, state presentation, accessible controls | `app/invite/[token]/page.test.tsx`; auth contracts; seeded invite journey | unmigrated |
| `/invite/[token]/tasks/[taskId]` | Secure invitation-task compatibility entry | Token/task resolution, stale-link recovery, and safe destination | Shell and state presentation | dedicated page test; questionnaire runner tests; seeded secure task | unmigrated |

## Participant

| Route | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/participant` | Participant project/task home | Assignment visibility, progress, navigation, permissions, and recovery | Sequence 01 prototype; shell, hierarchy, compact inline contextual cue | `ParticipantClientWorkspace.test.tsx`; context/task tests; seeded live prototype | preserved |
| `/participant/dashboard` | Participant dashboard compatibility entry | Existing destination and Back/refresh behavior | Compatibility/loading presentation only | route inspection plus authenticated smoke | unmigrated |
| `/participant/questionnaires` | Assigned questionnaire list | Persisted assignments, targets, drafts, completion/result states | List archetype, state presentation, copy | participant context and questionnaire contract tests; seeded list | unmigrated |
| `/participant/questionnaires/[key]` | Questionnaire completion | Pinned definition, answers, autosave/draft, Back recovery, validation, submission | Runner composition, progress/save context, controls, states | page, return-href, runner, and questionnaire contract tests; live draft/submit | unmigrated |
| `/participant/tasks/[taskId]` | Task compatibility entry | Existing task resolution and old links | Compatibility/loading presentation only | task-display and route/API contract checks | unmigrated |
| `/participant/results` | Policy-controlled participant results | Calculations, publication/privacy threshold, no raw answers/formula, comparison and recovery | Protected report shell/tokens/accessibility only | participant results test; report/score tests; seeded expected values | unmigrated |
| `/participant/account` | Account and program settings | Account mutations, password validation, program data, error recovery | Settings archetype, form hierarchy and feedback | account page/workspace and account-settings tests | unmigrated |
| `/participant/consent` | Persisted legal consent | Required version, acceptance persistence, protected-route gating | Guided layout, copy, states | `ConsentForm.test.tsx`; auth contract; seeded consent journey | unmigrated |
| `/participant/onboarding` | Participant onboarding compatibility entry | Existing destination and session boundary | Compatibility/loading presentation only | route inspection plus authenticated smoke | unmigrated |
| `/participant/final-evaluation` | Final evaluation workflow | Existing evaluation assignment, answers, submit and recovery | Guided flow presentation only | route/API inspection; questionnaire runner/contracts; seeded journey | unmigrated |
| `/participant/chat` | Existing placeholder/bounded surface | Do not imply or add AI coaching/roleplay capability | Harmonize shell and honest empty/placeholder state only | route inspection; navigation and copy review | unmigrated |

## Trainer core and companies

| Route | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/trainer` | Trainer overview and work entry | Access to current trainer work and permissions | Overview archetype, operational hierarchy, states | trainer layout test; authenticated seeded smoke | preserved |
| `/trainer/companies` | Company list, search/filter, creation and direct actions | Persisted mutations, URL/filter state, permissions and errors | Sequence 01 prototype; list archetype and controls | `CompaniesWorkspace.test.tsx`; trainer-company contracts; seeded mutations | preserved |
| `/trainer/companies/[companyId]` | Company workspace and project/participant access | Correct company identity, navigation, data and permissions | Detail archetype, section navigation, compact inline context | company panels/tabs tests; seeded navigation | preserved |
| `/trainer/companies/[companyId]/participants` | Company-wide participant roster | Roster data, search, project relation, access and errors | Data view and responsive substitution | participant table/contracts; seeded roster comparison | preserved |
| `/trainer/companies/[companyId]/settings` | Company settings | Existing backend mutation, validation, permissions and recovery | Settings/form archetype | `CompanySettingsWorkspace.test.tsx`; trainer-company contracts | preserved |
| `/trainer/companies/[companyId]/teams` | Company team workspace | Current team data, mutations, permissions and recovery | List/detail presentation and states | `TeamsWorkspace.test.tsx`; seeded team journey | preserved |
| `/trainer/companies/[companyId]/invitations` | Company invitation compatibility/delivery access | Delivery state, resend/recovery, secure links, idempotency | Invitation status/action presentation | `InvitationsWorkspace.test.tsx`; invite contracts; seeded delivery journey | preserved |

## Trainer projects, questionnaires, and settings

| Route | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/trainer/projects` | Searchable/filterable project list | Project lifecycle, direct navigation, URL state, permissions | List archetype, toolbar, responsive data view | `ProjectsWorkspace.test.tsx`; project controls; seeded list | preserved |
| `/trainer/projects/[projectId]` | Project summary and active section navigation | Correct project, permissions, section URLs and data | Detail archetype, tabs/compact inline context | `ProjectTabs.test.tsx`; project-data tests; seeded navigation | preserved |
| `/trainer/projects/[projectId]/participants` | Roster import, participant and account access | Import validation/persistence, roster operations, access recovery | Data view, importer composition, responsive controls | participant workspace, roster importer/format tests; seeded import | preserved |
| `/trainer/projects/[projectId]/participants/[participantId]` | Participant and assignment/account-link detail | Correct identity, assignments, account-link repair authorization and recovery | Detail hierarchy and state presentation | profile-data and account-link repair tests; seeded detail | preserved |
| `/trainer/projects/[projectId]/assignments` | Assignment planning and creation | Generation/regeneration/manual assignment/save, idempotency, permissions and errors | Editor/workspace composition, control language, states | assignment/API contract tests discovered during packet; seeded create/retry | preserved |
| `/trainer/projects/[projectId]/invitations` | Invitation preparation, dispatch and delivery | Recipients/tasks, send/resend, secure links, delivery state, recovery and idempotency | Delivery workspace hierarchy, statuses, actions | invite/API contracts and outbox evidence; seeded prepare/send/retry | preserved |
| `/trainer/projects/[projectId]/org-chart` | Organization chart view/edit | Existing graph data, edits, permissions and persistence | Editor composition, controls, responsive/local scroll | `org-chart.test.tsx`; seeded edit/reload | preserved |
| `/trainer/projects/[projectId]/reports` | Project report overview | Aggregation, privacy thresholds, comparisons, drill-down, export/print | Protected report exceptions only | report overview/detail/cycle/print tests; seeded expected values | preserved |
| `/trainer/projects/[projectId]/reports/lencioni` | Lencioni report detail | Raw 3-9 scale meaning, comparison direction, privacy, Back/export/print | Protected report shell/tokens/accessibility only | report detail/score/cycle tests; seeded values | preserved |
| `/trainer/projects/[projectId]/reports/leadership/[participantId]` | Individual leadership report | Correct participant, iCARE perspectives, privacy, comparison and navigation | Protected report shell/tokens/accessibility only | leadership page, iCARE, report detail tests; seeded values | preserved |
| `/trainer/projects/[projectId]/settings` | Project settings | Existing mutations, validation, permissions and recovery | Settings/form archetype | `ProjectSettingsForm.test.tsx`; project-data contracts | preserved |
| `/trainer/questionnaires` | Questionnaire catalog/editor | Versioning, protected definitions, explicit saves, preview boundary and errors | Editor archetype, structure/inspector, save context | `QuestionnairesWorkspace.test.tsx`; questionnaire contracts; seeded edit/reload | preserved |
| `/trainer/settings` | Trainer account settings | Account/security mutations, validation, session and recovery | Settings/form archetype | account-settings/auth/password tests; seeded mutation | preserved |

## Trainer communication

`/trainer/email` owns three URL-addressed views. Treat each as a separate
capability even though there is one route file.

| Route state | Current `dev` capability | Protected outcome and recovery | Allowed CF0002 change | Required proof | Disposition |
|---|---|---|---|---|---|
| `/trainer/email?view=campaigns` | Campaign list/editor, recipient selection, test/send readiness and durable state | Content, eligibility, validation, send/test-send, delivery status, errors and retry | Communication archetype, progressive detail, status/action hierarchy | email workspace/validation and communication contract tests; authorized seeded rehearsal | preserved |
| `/trainer/email?view=contacts` | Searchable contacts, segment filtering and import | Import validation, recipient eligibility, inactive/invalid state, URL state and persistence | Table/toolbar, borderless conventional edit actions, import states | archived contacts, roster/import and communication tests; seeded import | preserved |
| `/trainer/email?tab=templates` | Template catalog/editor | Protected/system ownership, trainer templates, saves and source boundary | Editor composition, save state and controls | communication contracts and affected editor tests discovered in packet; seeded edit/reload | preserved |

## Cross-route invariants

These are checked for every changed route where relevant:

- authorization and role isolation;
- accurate document title, landmark, heading order, skip link, accessible names,
  keyboard operation, focus preservation/restoration, and 200% zoom;
- loading, sparse/dense, empty, error, permission-denied, disabled, stale,
  success, retry, and unsaved-change recovery;
- responsive behavior at 390x844, 768x1024, 1440x900, and 1728x1117 with no
  document-level overflow;
- both themes, correct semantic status, no reliance on color alone, no console
  error, and no hydration loss of input value or focus;
- preserved URL state and Back/Forward behavior;
- no unexplained shared or touched-route bundle increase above 10%.

## Exact cleanup candidates

This is a candidate ledger, not a deletion instruction. Confirm consumers and
coverage in the named migration slice.

| Candidate | Current evidence | Planned disposition | Required proof |
|---|---|---|---|
| `.interface-design/system.md` | Tracked, report-only system | Replace in Sequence 01 with CF0002 `system.md`; protected report rules are already incorporated | Diff confirms all useful report rules remain |
| `frontend/test-results/.last-run.json` | Tracked generated last-run state | Remove in Sequence 01 only if no script or CI consumer exists; ignore future generated residue if appropriate | `rg` consumer search; targeted/full test commands still work |
| `docs/product-overhaul-checklist.md` | Tracked prior visual approval artifact | Archive in Sequence 01 to `docs/archive/product-overhaul-2026-07/` without rewriting history | Links/consumers updated; Git move visible |
| `docs/product-overhaul-review-packet.md` | Tracked prior visual approval artifact | Archive in Sequence 01 beside the checklist | Links/consumers updated; Git move visible |
| `docs/product-overhaul-route-matrix.md` | Historical `origin/prod` vs controlled-pilot matrix | Retain as historical evidence; do not use as CF0002 current baseline | New ledger exists and is referenced by guidance |
| Fraunces import in `frontend/src/components/auth/auth-shell.tsx` | Current remaining split typography consumer; test mock exists in `frontend/src/test/setup.ts` | Remove font import and its test mock after auth shell migrates to Geist | Auth-shell tests and build pass; no Fraunces consumer remains |
| `frontend/public/landing/codrut-team-session.png` | Tracked local photography | Retain and prefer for public/auth use | Image dimensions, loading, alt, and responsive proof |
| `frontend/public/landing/codrut-workshop-table.png` | Tracked local photography | Retain and prefer for public/auth use | Image dimensions, loading, alt, and responsive proof |

Do not run a repository-wide deletion sweep. Add candidates only when a current
consumer is identified. Delete a test only when its behavior is intentionally
gone with approval or equivalent named surviving coverage passes.

## Packet evidence record

After each task packet, append a concise record to the product copy of this
ledger: routes touched, disposition changes, protected tests run, live journeys
checked, removals and consumer proof, authored product additions/deletions,
tests/docs generated separately, bundle movement if measured, and unresolved
risk. Do not rerun broad checks merely to fill a gate document.

### Sequence 01 foundation packet — 2026-08-04

- Routes touched: shared tokens/shell and prototype hooks only; `/trainer/companies`
  and `/participant` remain `unmigrated` until route-level parity proof passes.
- Protected baseline: `just frontend-test` completed with 83 files, 620 passed,
  62 failed, and 24 failed files before CF0002 edits; the existing
  `ParticipantClientWorkspace.test.tsx` passed all 27 tests, while
  `CompaniesWorkspace.test.tsx` reported 4 failures.
- Baseline checks: `just frontend-lint` passed; `just frontend-typecheck`
  passed; `just frontend-build` passed. Baseline shared First Load JS was
  103 kB, `/trainer/companies` was 167 kB, and `/participant` was 174 kB.
- Seeded live baseline: `just dev` and `just seed-local-preview` succeeded with
  3 companies, 6 projects, 10 participants, 32 assignments, 3 campaigns, and
  8 contacts. Both routes were inspected at 1440x900 and 390x844 in light
  theme; each showed one existing console error and no disposition is marked
  preserved from visual evidence alone. Baseline screenshots are retained
  locally under `output/playwright/` and are not product code.
- Foundation changes: authoritative `.interface-design/system.md`, nested
  `frontend/AGENTS.md`, semantic token layer, 248px shell, and mobile header
  action; no shared coaching-context rail remains.
- Cleanup evidence: `.last-run.json` has no repository consumers and was
  removed as generated residue; the old checklist and review packet moved
  unchanged to `docs/archive/product-overhaul-2026-07/`; the historical route
  matrix remains retained. Fraunces remains because auth-shell is still its
  live consumer.
- Remaining risk: route-level state, keyboard/focus, dark-theme, responsive,
  console, and bundle proof is still open at the prototype gate.

### Sequence 01 two-prototype packet — 2026-08-04

- Routes: `/trainer/companies` and `/participant`. Both dispositions are now
  `owner-gate`; no shared-pattern propagation or Sequence 02 work started.
- Trainer prototype: preserved backend-provided company rows, URL-backed search
  and filters, selection/export, creation modal entry, pagination, direct links,
  status/stage semantics, and discoverable local table scrolling. Kept operational
  context in the existing list summary/table actions and retained one mobile
  header create action without changing APIs or persistence behavior.
- Participant prototype: preserved project context selection, questionnaire
  links, task expansion/local persistence, completion/result visibility, privacy
  copy, and progress calculations. Added one compact task-header cue, a quieter
  participant hierarchy, semantic dark-mode inline accents, and retained the
  protected result presentation path.
- Focused proof: `CompaniesWorkspace.test.tsx` and
  `ParticipantClientWorkspace.test.tsx` passed, 34/34 tests.
- Required Compose proof: `just frontend-lint` passed; `just frontend-typecheck`
  passed; `just frontend-build` passed; `just frontend-test` completed with 83
  files, 681 passed, 1 failed, 682 total. The sole failure is the existing
  `src/api/runtime-pcm-contracts.test.ts` fallback-disablement assertion; it
  failed before CF0002 changes and is outside these routes.
- Seeded live proof: `just seed-local-preview` data was inspected on both routes
  at 1440x900 and 390x844, in light and dark themes. Accessible snapshots retain
  one `h1`, named landmarks, task/company actions, table headers, progressbar,
  and keyboard-addressable controls. Both mobile documents measured
  `scrollWidth === clientWidth === 375` (390px viewport with scrollbar).
- Browser console: each route retains the existing local auth-bypass
  `GET /api/auth/csrf` 401 console error; no new route or hydration error was
  observed. This remains an explicit owner-gate risk, not a claim of clean
  console proof.
- Screenshots: `output/playwright/cf0002-trainer-companies-1440-light.png`,
  `cf0002-trainer-companies-1440-dark.png`,
  `cf0002-trainer-companies-390-light.png`,
  `cf0002-trainer-companies-390-dark.png`,
  `cf0002-participant-1440-light.png`,
  `cf0002-participant-1440-dark.png`,
  `cf0002-participant-390-light.png`, and
  `cf0002-participant-390-dark.png` are local owner-review evidence and are
  intentionally not product code.
- Bundle proof: shared First Load JS remains 103 kB; `/trainer/companies`
  remains 167 kB; `/participant` remains 174 kB. No new production dependency,
  backend/API/schema change, protected workflow deletion, or generated contract
  change was made.
- Cleanup and scope: the generated last-run file remains removed with no
  consumer; prior checklist/review packet remain unchanged in the dated archive;
  the historical route matrix remains retained; Fraunces remains because the
  auth shell still consumes it. Authored product files are 228 additions and
  86 deletions from `origin/dev`; focused test changes are 8 additions and 1
  deletion. Both remain well below the task's ~1,000-line pause threshold;
  docs/evidence are reported separately.
- Stop condition: wait for owner approval of both real-data prototypes in both
  themes and representative mobile/desktop states before propagating these
  patterns to any additional route.

### Sequence 01 correction packet — 2026-08-04

- Owner feedback applied: removed the standalone “Orientarea ta / Operare
  trainer” panels and deleted the shared rail component. `.interface-design/system.md`
  now explicitly withdraws this pattern and permits only a compact cue inside
  an existing header or actionable section.
- Trainer correction: kept a single header-level `Companie nouă` action on
  mobile; replaced stacked mobile filters with search plus one `Filtre` Sheet
  trigger that exposes active-filter count; made the mobile hamburger
  borderless; replaced horizontal mobile table hunting with prioritized,
  identity-first rows using the same semantic table DOM; and assigned deliberate
  desktop column widths so company names and statuses remain readable.
- The temporary `devIndicators: false` workaround was removed from Next config.
  Framework developer chrome is not treated as product UI and production-like
  captures remain the appropriate clean evidence surface.
- Participant correction: replaced the action-like burgundy cue with neutral
  supporting guidance inside the existing task header. No standalone
  orientation panel or duplicate action surface remains.
- Correction proof: focused trainer/participant tests passed 35/35; affected
  frontend lint passed; Compose typecheck passed; and an isolated Compose
  production build passed with shared First Load JS 103 kB,
  `/trainer/companies` 167 kB, and `/participant` 174 kB. The full suite was not
  rerun because the shared-foundation gate already ran it and recorded its one
  unchanged baseline failure.
- Visual proof: both prototypes were rechecked with seeded data at 390x844 and
  1440x900 in light and dark themes. Both widths measured document
  `scrollWidth === innerWidth`; mobile company identity, state, progress, and
  next action remain together; desktop company links have no internal overflow;
  and status badges render at one line/24px height.
- Proxy owner decision: approved on the owner's explicit instruction to proceed
  in their place. `/trainer/companies` and `/participant` are now `preserved`.
  Sequence 01 may advance. Push and PR creation remain explicitly deferred to
  the final combined owner review gate.

### Sequence 02 packet 1 — shell, overview, and lists

- `/trainer` and `/trainer/projects` now consume the approved flat surface,
  status, filter, and responsive data-row language; `/trainer/companies`
  remains the approved prototype consumer.
- Project URL-state, searchable filters, archive/restore behavior, direct links,
  project status/type/date meaning, and error recovery are unchanged. Mobile
  filters use one Sheet trigger with active-state count; project and trainer
  operational tables preserve one semantic DOM while presenting prioritized
  rows below `768px`.
- Project status color now uses semantic roles: active information, draft
  warning, completed success, archived muted. Burgundy is no longer a generic
  project-status color.
- Proof: `ProjectsWorkspace.test.tsx` and `trainer/layout.test.tsx` passed
  11/11; targeted ESLint passed. Seeded `/trainer/projects` and `/trainer` at
  390x844 had `scrollWidth === innerWidth === 390`, retained all actions and
  accessible row content, and showed no standalone context rail.

### Sequence 02 packet 2 — detail and organization

- Company and project detail routes now share one matte identity/header and
  underline-navigation language. The former full burgundy company billboard
  and segmented shadow tab treatment were removed; `#890505` remains the exact
  brand/action accent. Conventional back/settings actions are borderless icon
  controls with accessible names and titles.
- Company projects, company participants, project rosters, and participant
  project history retain one semantic table DOM and use prioritized mobile rows
  below `768px`; desktop keeps deliberate widths and bounded local scrolling.
  Search, URL state, import/add/edit, account-link repair, settings mutations,
  team membership, org-chart expansion, and participant privacy copy are
  unchanged. The existing company Teams surface is reachable again through the
  canonical company section navigation; no duplicate project Teams route was
  reintroduced.
- Project workflow warnings now use warning semantics instead of burgundy;
  scored counts use information color; completion/success remains green.
  Decorative status icon containers and ordinary surface shadows were removed.
- Proof: the seven directly affected detail/roster/organization suites passed
  34/34; the six protected team/settings/profile/account-link/data suites passed
  25/25; targeted ESLint passed. Seeded company detail and project roster at
  390x844 retained named navigation/actions and measured
  `scrollWidth === innerWidth === 390`.

### Sequence 02 packet 3 — assignments and invitations

- Company Invitations is now reachable through the canonical company section
  navigation. Project assignment and invitation routes keep the same cycle,
  generation, save, recipient-selection, send/resend, secure-link, delivery,
  and URL-filter behavior.
- Saved assignments and invitation recipients retain one semantic table DOM.
  Below `768px`, identity and primary action lead each row while questionnaire,
  target, delivery, account, task, and next-step context remain visible without
  document-level horizontal scrolling. Desktop retains the full columns and
  bounded table scrolling.
- The five invitation filters collapse to one labeled native control on mobile;
  desktop retains the existing quick filter buttons. Delivery failures now use
  the destructive semantic role rather than the brand burgundy.
- Proof: `InvitationsWorkspace.test.tsx` and `CompanySectionTabs.test.tsx`
  passed 35/35; targeted ESLint passed. Seeded project assignments and
  invitations were checked at 390x844 and 1440x900; both measured
  `scrollWidth === innerWidth`, retained named assignment/invitation controls,
  and exposed the compact invitation filter on mobile.

### Sequence 02 packet 4 — questionnaire editor

- The catalog and editor retain definition loading, search, creation,
  versioning, dirty-state protection, explicit save/discard, retirement,
  structure editing, scales, and inspector behavior. Ordinary catalog shadows
  were removed and mobile catalog cards use denser vertical rhythm.
- The editor action header now forms two deliberate mobile rows: identity and
  save state remain readable, while version selection and the borderless
  discard/version/retire controls share a compact action row. The primary save
  action becomes an accessible icon control below `640px`. The mobile structure
  navigator is locally scrollable so the active editor remains reachable
  without traversing the complete questionnaire tree.
- Proof: `QuestionnairesWorkspace.test.tsx` passed 19/19 and targeted ESLint
  passed. The seeded catalog/editor was checked at 390x844 and 1440x900;
  document width matched viewport width at both sizes, mobile structure height
  remained bounded, and the three-column desktop editor remained intact.

### Sequence 02 packet 5 — communication workspace

- Campaigns, contacts, archive, and templates now share one locally scrollable
  underline navigation instead of a floating segmented block. The workspace
  title and all four destinations fit the mobile document without widening it;
  the campaign editor, recipient selection, send readiness, imports, and URL
  state are unchanged.
- Contacts retain one semantic table DOM. Below `768px`, identity and the
  existing borderless edit/archive actions lead each row, with segment, status,
  and interaction totals grouped below. The three contact-type buttons collapse
  to one labeled native control on mobile; desktop retains the quick switcher.
- Template catalog/editor shadows and decorative preview containers were
  reduced, catalog density now matches the questionnaire catalog, and the
  catalog return action is a borderless accessible icon. Template ownership,
  versioning, validation, placeholders, explicit saves, and preview content are
  unchanged.
- Proof: the communication workspace, validation, and archive suites passed
  83/83; targeted ESLint passed. Seeded campaigns, contacts, and templates were
  checked at 390x844 with `scrollWidth === innerWidth`; recipient actions,
  contact filtering, and all navigation destinations remained named and
  reachable.

### Sequence 02 packet 6 — protected reports

- Report composition, aggregation order, score scales, privacy thresholds,
  cycle comparison, drill-down, printing, and all chart data remain unchanged.
  This packet only aligned report links/eyebrows with the semantic primary
  token, removed the ordinary disclosure shadow, and neutralized a decorative
  information icon; the canonical burgundy remains available to intentional
  chart encodings.
- Proof: overview, detail route, Lencioni section, leadership, comparison-bar,
  and iCARE perspective suites passed 25/25; targeted ESLint passed. The seeded
  report overview at 390x844 retained project/cycle context, print action,
  comparison controls, and `scrollWidth === innerWidth`.
