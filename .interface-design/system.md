# Cody Interface System

This is the authoritative interface contract for CF0002. During Sequence 01,
install this document verbatim at `projects/codrut-platform/.interface-design/system.md`
on `feat/cohesive-frontend-rework`, replacing the report-only file currently at
that path. The protected report rules near the end of this document incorporate
the useful content of that older file; do not keep two competing system files.

## Product intent and users

Cody is professional software for facilitated workshops, coaching, structured
reflection, participant progress, organizational coordination, and evidence-led
results. It should feel like a calm editorial workbench: clear, deliberate,
capable, and quiet enough for sensitive work.

Use these operating assumptions unless current route evidence disproves them:

- Trainers and administrators are primarily laptop/desktop operators managing
  companies, projects, invitations, questionnaires, communications, and
  reports. Favor scan speed, moderate information density, stable navigation,
  and clear operational state.
- Participants are primarily mobile or narrow-screen users completing one
  meaningful task at a time. Favor low cognitive load, privacy and progress
  context, explicit recovery, and one clear next action.
- Public and identity visitors are occasional users deciding whether to trust
  the product or regain access. Favor concise explanation and an obvious path.

These assumptions guide presentation only. They do not authorize changes to
permissions, route access, product outcomes, or domain behavior.

## Design direction

- Character: calm, evidence-led, professional coaching software.
- Material: matte layered surfaces with quiet borders and background shifts.
- Brand anchor: the existing canonical burgundy `#890505`.
- Typography: Geist Sans everywhere, including public and authentication.
- Density: one regular spacing language; no separate compact mode.
- Depth strategy: surfaces and borders for ordinary hierarchy; shadows only for
  popovers, menus, dialogs, and genuinely floating chrome.
- Avoid generic dashboard tile grids, nested card mazes, decorative icon
  containers, glass work surfaces, gradient-led styling, oversized headings,
  excessive pills, and motion used as decoration.

### Locked visual signature: coaching-context rail

Use one restrained coaching-context rail when it materially connects the
current stage or status, privacy/delivery context, and next meaningful action.
It is a functional orientation device, not decoration.

Approved placements are participant project progress, trainer company/project
context, invitations and delivery state, questionnaire save/progress context,
and communication readiness. Use it at most once per view. On wide screens it
may be a quiet secondary rail; on narrow screens it becomes an inline band near
the relevant workflow. Do not turn it into a generic stepper or a stack of
cards. Do not insert it into report visualizations: reports retain their
protected compact evidence-row signature defined below.

## Protected behavior

Presentation work must preserve current scoring, aggregation, privacy
thresholds, publication, comparison, drill-down, export, print, assignment and
invitation delivery, secure links, idempotency, account/session isolation,
questionnaire versioning, editor save, autosave, draft recovery, validation,
submission, communication eligibility/delivery, authorization, persistence,
URL state, and error semantics. The CF0002 parity ledger is the route-level
contract. If a visual change conflicts with it, preserve behavior and stop for
an owner decision.

## Semantic color tokens

Define tokens once in the existing theme layer. Components consume semantic
roles, never route-local palette values.

| Role | Light | Dark | Use |
|---|---|---|---|
| canvas | `#F7F8F8` | `#101214` | App background |
| surface | `#FFFFFF` | `#171A1D` | Primary work surface |
| surface-muted | `#EEF1F2` | `#202429` | Secondary grouping |
| surface-raised | `#FFFFFF` | `#24292E` | Menus and floating layers |
| sidebar | `#F7F8F8` | `#101214` | Shell navigation; separate with border |
| foreground | `#1D2126` | `#ECEFF1` | Primary text |
| muted-foreground | `#66707A` | `#AAB2B9` | Supporting text |
| border | `rgba(29,33,38,.12)` | `rgba(236,239,241,.12)` | Ordinary separation |
| control | `#F1F3F4` | `#121518` | Inset controls |
| control-border | `rgba(29,33,38,.18)` | `rgba(236,239,241,.18)` | Control edges |
| brand-core | `#890505` | `#890505` | Identity and primary fill |
| brand-text | `#890505` | `#C56A7D` | Inline brand accent |
| focus-ring | `rgba(137,5,5,.45)` | `rgba(197,106,125,.55)` | Focus indication |
| success-ink | `#237A4B` | `#58C98A` | Completed/success |
| warning-ink | `#8A5714` | `#E2A54E` | Attention/warning |
| danger-ink | `#B4232E` | `#F1737B` | Destructive/error |
| info-ink | `#25699A` | `#6EB5E1` | Neutral information |

White on `#890505` has sufficient contrast for filled controls. Dark-mode
inline burgundy uses `#C56A7D`; `#890505` remains the unchanged brand core and
primary fill. Never reuse burgundy as a generic error or warning. Semantic
states use text or icon plus color, not color alone. Derive quiet semantic
backgrounds from these ink families and the current surface.

Set the correct browser `color-scheme` and theme color. Verify controls and
scrollbars in both themes, including native selects on Windows-like rendering.

## Typography and numbers

Use Geist Sans through `next/font`; remove Fraunces only after its last consumer
migrates. Do not add another font. Use a small, deliberate scale:

| Role | Size / line height | Weight |
|---|---|---|
| metadata | `12 / 16px` | 500 |
| compact body and label | `14 / 20px` | 400-600 |
| body and control | `16 / 24px` | 400-600 |
| section heading | `20 / 28px` | 600 |
| app page heading | `28 / 34px` | 600 |
| public hero maximum | `40 / 46px` | 600 |

Use sentence case in Romanian product UI. Use tabular numerals for comparisons,
scores, counts, and aligned dates. Keep line lengths readable and layouts
resilient to short, average, and very long user-generated content.

## Spacing, size, radius, and motion

- Spacing: `4, 8, 12, 16, 20, 24, 32, 48, 64` px.
- Page padding: 16 px mobile, 24 px tablet/desktop, and 32 px only for spacious
  public reading surfaces. Workspaces remain fluid up to 1600 px.
- Controls: 36 px on desktop; 44 px on mobile. Mobile text inputs use at least
  16 px text. Borderless icon controls use a 32 px desktop and 44 px mobile hit
  area with a 16-18 px glyph.
- Radius: 6 px controls, 8 px surfaces, 10 px overlays. Child radii remain
  concentric and no larger than parent radii. Pills are reserved for genuine
  compact status or segmented selection.
- Motion: 120-180 ms for feedback. Transition named `opacity` and `transform`
  properties only by default; never `transition: all`. Respect reduced motion.
  Avoid animation when immediate state change communicates better.

## App anatomy and navigation

- At `>=1024px`, use a labeled 248 px sidebar with minimal top chrome.
- Below `1024px`, use a labeled drawer or sheet. Never substitute an unexplained
  icon-only navigation rail.
- Every route family has a skip link, accurate document title, one `h1`, and a
  stable main landmark.
- The page header accepts an optional breadcrumb, title, concise supporting
  text, and at most one primary outcome action.
- Put search, filter, sort, and view controls in one toolbar below the header.
  Preserve existing URL state so refresh and Back/Forward continue to work.
- Use links for navigation and buttons for actions. Back actions return to the
  referring in-app route when possible and use a safe fallback for direct visits.
- Let CSS flex, grid, and intrinsic sizing handle responsive flow. Avoid JS
  measurement when browser layout can solve it.

## Interaction language

### Buttons and icons

- Primary actions are labeled. Destructive, rare, and Cody-specific actions are
  also labeled and cannot depend on an unfamiliar glyph.
- Conventional secondary actions may be icon-only and borderless. Their entire
  hit area gets quiet hover, pressed, selected, disabled, and focus-visible
  feedback. Give every icon-only button an accessible name and a concise
  tooltip when the meaning is not immediately standard.
- Do not put icons in decorative circles or bordered containers. A plus icon is
  a plain glyph inside the button hit area, not a plus-in-a-circle illustration.
- Do not use icon-only controls merely to save space when recognition is weak.

### Forms and mutations

- Use persistent visible labels, meaningful `name`, appropriate `type`,
  `inputmode`, `autocomplete`, and selective `spellcheck`. Placeholders show an
  example or pattern; they do not replace labels.
- Never block paste or browser zoom. Preserve password-manager and one-time-code
  behavior.
- Keep submit enabled when submission is how validation is revealed. Disable
  only while in flight or when the action is impossible, and show the reason.
- A loading button keeps its original label and adds progress. Avoid spinner
  flicker with delayed/minimum loading presentation when needed.
- Put errors beside the failed field or region, focus the first invalid field,
  preserve entered data, and state the recovery action.
- Warn before navigation when unsaved work could be lost. Optimistic mutations
  must reconcile failures with rollback, Undo, or an explicit retry path.

### Search, filters, tables, and status

- Use one search pattern with a clear label, optional clear icon, predictable
  keyboard behavior, and URL-persisted value where the current route supports
  shareable filtering.
- Mobile filters open in a labeled sheet and summarize active filters at the
  trigger. Do not scatter route-local filter buttons around the header.
- Tables remain semantic tables when comparison across columns matters. Below
  768 px, use prioritized rows/cards only when that representation preserves
  all actions and meanings; local horizontal scroll is allowed for genuinely
  tabular data and must be discoverable.
- Prefer dot-plus-label status. Use identical status terms across list, detail,
  notifications, reports, and participant surfaces.

### Overlays and focus

- Use existing native or Radix primitives. Dialogs and sheets trap focus,
  restore it to the trigger, close predictably, and expose a named close action.
- Menus support keyboard movement and Escape. Do not nest interactive controls
  inside an interactive row.
- Preserve focus through mutations and URL-state changes. Hydration must not
  discard input focus or value.

## Page archetypes

1. **Public/auth/legal:** focused reading path, concise trust signals, and no
   separate decorative design dialect.
2. **List/index:** header, optional actionable summary, unified toolbar, data
   view, pagination, and designed sparse/dense/loading/empty/error states.
3. **Detail/workspace:** identity header, stable section navigation, primary
   work area, and the coaching-context rail only when it advances the task.
4. **Editor:** stable structure navigation, focused canvas, contextual inspector,
   explicit save state, keyboard-safe overlays, and no nested card maze.
5. **Guided participant flow:** privacy/progress context, one clear next action,
   mobile-first hierarchy, and explicit recovery.
6. **Report/evidence:** preserve current information architecture and domain
   meaning; harmonize only shell, tokens, controls, copy, accessibility, and
   responsive composition.

## State and recovery contract

Every affected surface implements the relevant loading, sparse, dense, empty,
partial, disabled, success, failure, permission-denied, stale, retry, and
offline/reconnect state. Skeletons match final geometry and avoid layout shift.
No screen ends without a meaningful next step or recovery path. Do not hide
errors solely in toasts. No document-level horizontal overflow is allowed;
intentional editor/table scrolling is local and visible.

## Copy

The voice is a calm expert coach: direct, specific, supportive, and
non-performative. Use outcome labels instead of generic “Continuă” or
“Confirmă”. Keep nouns and status language consistent. Error copy explains the
exit. Remove joke, placeholder, and unprofessional seeded/demo language only
when doing so does not alter test or product semantics.

## Photography and media

Reuse the local assets `frontend/public/landing/codrut-team-session.png` and
`frontend/public/landing/codrut-workshop-table.png` before considering new
media. Use photography only where it builds trust or explains the workshop
world on public/auth surfaces. Use `next/image`, stable dimensions, responsive
sizes, useful alt text or empty alt for decoration, and no remote asset
dependency. Adding or generating imagery is a stop-point decision, not an
implementation-agent design choice.

## Performance and code boundaries

- Add no production dependency without the Festival stop-point review.
- Preserve route splitting. Lists must not eagerly load full editors or report
  engines. Prefer server components and narrow client boundaries.
- Avoid redundant providers, unstable context values, persistent blur, layout
  animation packages, and state copied from the URL into competing stores.
- Compare the recorded baseline build. Explain any increase above 10% in shared
  first-load JavaScript or a touched route; do not accept it by default.
- Extract a shared primitive on its second real use unless an existing primitive
  already owns the behavior. Record a short component-intent note once for each
  new shared pattern: purpose, owner archetype, states, and reuse boundary. Do
  not create per-component essays or duplicate the same rationale.

## Accessibility and browser quality

Target WCAG 2.2 AA while applying the product-relevant [Vercel Web Interface
Guidelines](https://vercel.com/design/guidelines): native semantics before ARIA,
named icon buttons, keyboard and focus management, reliable form behavior,
URL-backed view state, complete async/error states, reduced motion, resilient
content, accurate page titles, and measured responsive/performance proof. Vercel
brand preferences are not Cody requirements.

Verify representative surfaces at 390x844, 768x1024, 1440x900, and 1728x1117
in both themes. Test keyboard-only use, visible focus, accessible names,
contrast, 200% zoom, long Romanian strings, console errors, and overflow.

## Protected results exceptions

The pre-CF0002 report work is intentionally retained as a specialized consumer
of this app-wide system:

- Report signature: compact first-to-latest evidence rows that keep values,
  change, and interpretation together. Do not apply the coaching-context rail
  inside report visualizations.
- Keep comparison controls in one quiet bordered toolbar. Reuse
  `CycleComparisonToolbar`, `CycleComparisonBars`, `ResultSignalBadge`,
  `InterpretationDisclosure`, and `ReportSection` wherever currently shared.
- On desktop, use available width for side-by-side comparisons and three iCARE
  perspectives. On narrow screens, stack without document overflow and keep
  labels adjacent to values.
- Baseline is red and comparison is warm amber. Additional category colors use
  semantic chart tokens. Comparison bars are rounded, left-aligned, and directly
  labeled; do not add endpoint dots, rails, ticks, or guide lines.
- Percentage changes use percentage points. Lencioni uses raw points on its
  source 3-9 scale. Lower TA stress-driver scores are improvement; higher
  Lencioni and iCARE scores are improvement.
- Use paired donut charts for category distributions and bars for ordered
  numeric change. Charts use redundant labels and color-blind-safe distinctions.
- Interpretation disclosures look actionable and retain full source text
  without dominating scan flow.
- Preserve loading, empty, privacy-threshold, stale-link, export, print, and
  direct-visit Back behavior. Do not change report calculations or data flow.

## Migration and anti-bloat rules

- Replace the current presentation path; never leave a second token, primitive,
  shell, toolbar, form, status, or responsive system beside this one.
- Before deletion, name the current consumers, protected behavior, and coverage,
  then classify the artifact as retain, migrate, replace, archive, or remove.
- Delete only after the final consumer migrates and in that same slice. Age or
  appearance is not deletion evidence. Preserve behavior, authorization,
  privacy, persistence, recovery, and regression tests unless equivalent named
  coverage passes or the behavior is intentionally removed with owner approval.
- Use existing local assets and dependencies. No Storybook, Chromatic,
  permanent Playwright harness, animation library, or second icon system.
- Report authored product additions/deletions, tests, docs, generated files,
  dependencies, bundle movement, and retained legacy consumers separately.

## Five placement checks

Before propagating a new shared pattern, confirm it works in these contrasting
contexts: a dense trainer list, a trainer detail/editor, invitations or
communications, participant project home/questionnaire, and a report consumer.
The component may legitimately vary by archetype; its behavior and semantic
roles must remain one system.
