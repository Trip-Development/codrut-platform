# Codrut Platform Agent Instructions

## Purpose

Optimize for fast, clear delivery without weakening user-data, privacy,
migration, or production recovery boundaries. Festival and campaign tools are
optional unless the work is already linked to one or the user explicitly
chooses them.

## Working loop

1. Inspect the affected code and existing pattern once.
2. Make the smallest coherent change that fixes the actual problem.
3. Review the combined diff once, findings first.
4. Run the smallest checks that directly cover the changed risk.
5. Ship one coherent implementation PR with explicit remaining risk.

Do not add ceremony to small changes. Do not create custom infrastructure,
frameworks, or dependencies when a direct implementation is enough.

## Diff discipline

- Keep one user request on one branch and implementation PR unless a slice
  genuinely needs independent deployment or rollback.
- Prefer small logical commits inside that PR.
- When authored changes approach roughly 1,000 lines, pause and explain why the
  design cannot be smaller before adding more code. Generated contracts and
  release-transport diffs are reported separately from authored code.
- Do not compensate for a broad change with exhaustive branch tests. Add one
  focused regression test per changed behavior; reserve deeper matrices for
  authorization, privacy, migrations, concurrency, and data integrity.
- Prototype one representative UI section before repeating a new presentation
  pattern across the application.

## Verification

- No Playwright or universal end-to-end gate. Use focused browser inspection
  for changed routes when visual or interaction behavior matters.
- Run each meaningful check once. Rerun only the proof affected by a correction.
- Broaden beyond targeted tests only when changing shared APIs,
  authentication/authorization, persistence, migrations, build configuration,
  or another demonstrated cross-cutting boundary.
- Coverage, full builds, and full suites are optional diagnostics, not default
  PR requirements.
- CI remains path-scoped: backend changes run Ruff, migrations, and pytest;
  frontend changes run lint, typecheck, and Vitest; public contract changes
  verify generated OpenAPI types; infrastructure changes validate Compose.

Useful container-backed commands:

```sh
docker compose exec -T backend uv run ruff check <changed paths>
docker compose exec -T backend uv run pytest -q <focused tests>
docker compose exec -T frontend pnpm exec eslint <changed paths>
docker compose exec -T frontend pnpm typecheck
docker compose exec -T frontend pnpm test --run <focused tests>
```

## Git and release

- Never implement directly on `dev` or `prod`; branch from current
  `origin/dev` and preserve unrelated work.
- Deliver application changes through one PR into `dev`. Conventional Commit
  titles are preferred but are not enforced by a metadata gate. Issue links are
  optional.
- Squash feature PRs into `dev`. The post-merge candidate builds immutable
  backend/frontend images once.
- Production accepts only an exact tested `dev` promotion. Keep the release
  tree check, deployed-image proof, migration, readiness, disk retention, and
  rollback reference. Do not rebuild during promotion.
- Do not back-merge routine production merge commits into `dev`.
- Do not merge, deploy, or delete active work without user authorization.

## Safety boundaries

- Enforce authorization and tenant ownership on the backend; frontend guards
  are UX only.
- Treat invitations, sessions, identities, questionnaire answers, results,
  communications, and deletion as sensitive data flows.
- Use transactions, constraints, locks, and idempotency where retries or
  concurrent claims can occur.
- Add and verify an Alembic migration for schema changes. Back up and rehearse
  material production-data changes before mutation.
- Never log or commit secrets, tokens, passwords, questionnaire answers, or
  confidential respondent data.
- Keep OpenAPI and `frontend/src/api/generated/schema.d.ts` synchronized when a
  public router or schema changes; never hand-edit generated output.

## Frontend

- Reuse established components and semantic tokens before creating new UI.
- Check loading, empty, error, disabled, keyboard, focus, narrow viewport, and
  stale-session behavior when relevant.
- Prefer user-visible test locators and avoid fixed sleeps.

## Environment and cleanup

- Prefer the configured devcontainer and Compose stack for dependency installs,
  services, migrations, and application checks. Host tools are fine for quick
  read-only diagnostics.
- Use `rg` for discovery. Keep edits localized and avoid unrelated formatting.
- Never discard user work or use broad destructive cleanup. Resolve exact
  branches, worktrees, images, and paths before removal.

## Handoff

State what changed, why it is correct, what focused proof ran, and what remains.
Explain unusually large diffs plainly instead of hiding them behind process.
