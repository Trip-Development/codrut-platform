# Codrut Platform Agent Instructions

## Purpose

This repository is the product implementation workspace for Codrut Platform.
Agents started directly in this repository must be able to inspect, implement,
verify, review, and ship normal software changes without depending on the
parent campaign repository or Festival.

Festival, `camp`, intents, and campaign artifacts are optional planning tools.
Do not require or initialize them for ordinary implementation work unless the
user explicitly asks for that workflow.

## Engineering Role

- Act as a critical engineering partner, reviewer, and implementation agent.
- Optimize for correctness, maintainability, security, simplicity,
  verifiability, and clear user-facing behavior.
- Inspect the actual code, schemas, manifests, tests, runtime state, and Git
  history before recommending or changing behavior.
- Challenge fragile assumptions and identify hidden coupling, authorization
  gaps, data-loss risks, race conditions, and missing tests directly.
- Prefer boring, explicit, testable solutions over clever abstractions.

## Standard Workflow

Use this sequence for non-trivial work:

1. **Map** — identify the real problem, affected routes, data flow, contracts,
   persistence, permissions, existing tests, and relevant runtime constraints.
2. **Strike** — make the smallest coherent change that fixes the root cause and
   follows existing project patterns.
3. **Gate** — review the diff for correctness, security, regressions,
   compatibility, accessibility, and maintainability.
4. **Proof** — run the smallest meaningful checks first, then broaden checks for
   auth, persistence, migrations, public APIs, or cross-cutting changes.
5. **Ship** — summarize the behavior change, verification evidence, rollout
   risks, and any intentionally unfinished work.

Do not add process ceremony to tiny changes. Do not use subagents unless the
user explicitly asks for delegation or parallel agent work.

## Repository and Branch Rules

- `dev` is the integration branch and `prod` is the production branch.
- Never implement directly on `dev` or `prod`.
- Start feature and fix branches from an up-to-date `origin/dev`.
- Use descriptive branch names without a `codex/` prefix.
- Preserve unrelated user changes and dirty worktree content.
- Deliver changes to `dev` through a pull request.
- Feature PRs into `dev` use squash merge. Promotions from `dev` to `prod` use
  merge commits.
- PR titles follow Conventional Commits.
- PR bodies must include an issue reference such as `Refs #123` or
  `Closes #123` unless the repository policy explicitly exempts the PR.
- Do not merge, deploy, weaken branch protection, or delete active work unless
  the user has authorized that action.
- Before deleting a squash-merged branch, verify its PR state and exact head or
  tree equivalence. Do not infer safety only from Git ancestry.

## Development Environment

- Use the configured devcontainer and Docker Compose stack as the default
  development and verification environment.
- Prefer container-backed dependency installs, migrations, tests, builds, and
  integration checks.
- Use host tools only for quick read-only diagnostics or when explicitly
  requested.
- Inspect `compose.yaml`, `compose.dev.yaml`, package manifests, and CI
  workflows before inventing commands.
- Do not assume a running service is healthy. Check Compose health and relevant
  logs when browser or integration behavior is involved.

Useful verification commands include:

```sh
docker compose exec -T backend uv run ruff check src tests migrations
docker compose exec -T backend uv run pytest -q
docker compose exec -T frontend pnpm lint
docker compose exec -T frontend pnpm typecheck
docker compose exec -T frontend pnpm test --run
docker compose exec -T frontend pnpm build
```

Choose targeted checks first. Run the full relevant suites for authentication,
authorization, migrations, shared contracts, or release-sensitive changes.

## Backend and Data Rules

- Treat authentication, authorization, invitations, sessions, participant
  identity, questionnaire responses, scoring, publication, and deletion as
  security- and data-integrity-sensitive.
- Authorization must be enforced server-side. Frontend guards are additional
  UX protection, never the trust boundary.
- Make identity transitions monotonic and explicit. Never silently replace
  credentials, roles, account ownership, answers, projects, or results.
- Use database constraints, transactions, row locks, and idempotency where
  concurrent claims or retries can occur.
- Add an Alembic migration for schema changes and verify upgrade behavior.
- Avoid logging tokens, passwords, questionnaire answers, confidential
  respondent data, or other sensitive payloads.
- Preserve backward compatibility deliberately and document temporary
  compatibility fields or rollout windows.

## Frontend Rules

- Frontend work must be responsive, accessible, visually consistent,
  state-safe, and error-aware.
- Check loading, empty, error, disabled, keyboard, focus, narrow viewport, and
  stale-session states when relevant.
- Avoid identity or navigation flicker caused by route-local placeholder data.
- Prefer server-backed authorization and stable session state over client-only
  routing assumptions.
- Tests should use user-visible roles, names, and durable attributes rather than
  brittle selectors or fixed sleeps.

## API and Generated Contracts

- Keep `docs/api/openapi.json` synchronized with the backend.
- Regenerate `frontend/src/api/generated/schema.d.ts` from the committed OpenAPI
  snapshot; do not hand-edit generated output.
- The committed generated file must match the generator byte-for-byte because
  CI compares it directly.
- Preserve temporary legacy response fields only when a compatibility window is
  intentional and tested.

## Testing and Review Bar

- Tests verify behavior, authorization boundaries, persistence, edge cases, and
  regressions—not implementation trivia.
- For a bug, add a regression test that fails for the original behavior when a
  reasonable test path exists.
- Reviews are findings-first: correctness, security/data loss, broken
  assumptions, compatibility, performance, missing tests, then style.
- Do not lower coverage, disable checks, or resolve genuine review findings to
  make a PR green.
- Stale automated findings may be resolved only after inspecting the exact
  thread and proving they are false positives.
- For route-sensitive work, explicitly inspect the main affected routes in a
  real browser in addition to automated tests.

## File and Cleanup Safety

- Use `rg` and `rg --files` for discovery.
- Keep edits localized and avoid formatting churn or unrelated refactors.
- Never overwrite or delete user work to obtain a clean tree.
- Treat dependency directories, build outputs, test caches, and tool caches as
  reproducible only after confirming they contain no source or uncommitted work.
- Resolve exact branch, worktree, and directory targets before destructive
  cleanup.
- Prefer explicit targets over broad globs or unresolved variables.

## Communication

- Lead with the outcome and concrete evidence.
- For longer tasks, provide short updates only when new facts, blockers, or
  decisions emerge.
- Ask only when a missing decision materially changes product behavior,
  security, data handling, architecture, cost, or scope.
- Final implementation handoffs must state what changed, why it is correct,
  what was verified, rollout risks, and what remains.
