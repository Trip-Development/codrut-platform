# Frontend Instructions

These instructions apply to `frontend/` and supplement the repository root
`AGENTS.md`. Follow the root file when rules are not frontend-specific.

## Authoritative contracts

- Read `../.interface-design/system.md` before changing UI.
- Read only the affected rows in
  `../docs/frontend-redesign-parity-ledger.md`; update their evidence and
  disposition after each completed CF0002 packet.
- Apply the product-relevant Vercel Web Interface Guidelines at
  `https://vercel.com/design/guidelines`. Vercel brand preferences do not
  override Cody's system.
- When CF0002 is active, use `fest context` and `fest next` from the product
  repo. Execute only the current task and its internal packet order.

## Behavior first

- A visual change must preserve current authorization, privacy, persistence,
  results/calculation, invitation/assignment delivery, questionnaire version,
  draft/submission, communication, URL-state, export/print, and recovery
  behavior.
- Do not change backend contracts or domain logic for presentation convenience.
  Stop when a requested UI requires a new product outcome, API, migration,
  service, dependency, workflow, or test harness.
- Keep the protected report components and meaning rules named in the interface
  system. Results are a minimal-change consumer, not a redesign playground.

## Interface implementation

- Use existing dependencies and approved shared primitives. Extract a new
  primitive on its second real use; do not create route-local copies or a
  parallel token/shell/form/toolbar/status system.
- Conventional secondary icon actions are borderless but keep a 32 px desktop
  and 44 px mobile hit area, visible focus, accessible name, and tooltip when
  meaning is not obvious. Primary, destructive, rare, and domain-specific
  actions remain labeled. Never use decorative icon circles.
- Implement relevant loading, sparse/dense, empty, partial, disabled, success,
  failure, permission-denied, stale, retry, and unsaved-change states.
- Preserve keyboard order, focus through mutations, focus trap/restore for
  overlays, form values through failure/hydration, URL-backed view state, and
  Back/Forward behavior.
- Verify both themes and responsive composition. No document-level horizontal
  overflow; intentional table/editor scrolling stays local and discoverable.
- Use semantic tokens only. Do not add raw palette values or another font/icon
  system without updating the authoritative system through an owner decision.

## Lean migration

- Before removing an artifact, name its consumers, protected behavior, and
  coverage in the parity/cleanup ledger. Remove it only after the final consumer
  migrates and in that same packet.
- Test age is not removal evidence. Preserve behavior, authorization, privacy,
  persistence, recovery, and regression coverage unless equivalent named tests
  pass or the owner approved removal of the behavior.
- Report authored product additions/deletions separately from tests, docs,
  generated files, archives, and dependencies. Pause before approximately
  1,000 authored product lines at the CF0002 prototype gate.

## Verification

Use the configured Compose/devcontainer workflow. Run the smallest affected
Vitest files during a packet. Run broad checks only at the risk gates named by
the active task:

```sh
just frontend-lint
just frontend-typecheck
just frontend-test
just frontend-build
```

Record exact commands and browser checks once. Gate files consume that evidence;
they do not rerun passing checks. Use user-visible locators and web-first
assertions for browser proof; do not add sleeps or brittle selectors.
