# codrut-platform

Codrut Platform is a Next.js + FastAPI application for trainer-led company
assessment workflows: company setup, roster import, assignment planning,
secure participant links, email invitations, questionnaire completion, scoring,
and aggregate reporting.

## Current Production State

As of 2026-06-11, the active release flow remains:

```text
feature branch -> PR into dev -> release PR from dev into prod
```

Production is deployed from `prod` by the `VPS Production Deployment` workflow.
The current public host is:

```text
https://codrut.andreivacaru.ro
```

The latest verified production checkpoint passed:

- GitHub release PR from `dev` to `prod`.
- VPS production deployment.
- Public health checks for `/api/health/live` and `/api/health/ready`.
- Public landing and login page smoke checks.
- Protected trainer and participant routes redirecting to `/login` without
  server-side exception digests.

## Core Workflow

The trainer workflow for the current client-ready build is:

1. Create or open a company.
2. Import the roster first.
3. Review or generate the default assignment plan.
4. Save assignments.
5. Generate secure links or send email invites explicitly.
6. Participants complete questionnaires through account or secure-link access.
7. Reports aggregate submitted/scored responses with confidentiality thresholds.

The default assignment plan is generated from roster role groups, reporting
relationships, and teams:

- Lencioni for the leadership team and manager teams.
- Distress Drivers self-assessment for managers/leadership only.
- 360 iCARE for managers, including self-review, peer manager feedback, and
  direct-report feedback.

Roster import must not send access automatically. Access delivery is a separate
action so trainers can review assignments before links or emails are created.

## Local Verification

Use the Docker Compose dev stack as the source of truth:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend uv run pytest
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend pnpm typecheck
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend pnpm lint
docker compose -f compose.yaml -f compose.dev.yaml exec -T frontend pnpm build
```

Focused checks for the current core workflow live in:

- `backend/tests/test_company_service.py`
- `backend/tests/test_assignment_service.py`
- `backend/tests/test_assignment_invites.py`
- `backend/tests/test_questionnaire_response_service.py`
- `backend/tests/test_scoring_service.py`
- `frontend/src/app/trainer/companies/[companyId]/invitations/InvitationsWorkspace.test.tsx`
- `frontend/src/app/trainer/roster/roster-importer.test.tsx`
- `frontend/src/components/questionnaires/questionnaire-runner.test.tsx`

See `docs/ops/local-development.md` for local accounts, Mailpit, and the
two-person roster smoke test.
