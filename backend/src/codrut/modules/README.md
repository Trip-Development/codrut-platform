# Backend Modules

The backend is a modular monolith. Modules share one FastAPI process and one
database, but each module owns its domain model and should expose a clear local
surface.

## Module Ownership

- `assignments`: questionnaire assignments, teams, team membership, assignment
  planning, assignment links, and saved assignment state.
- `communications`: campaign recipients, campaign assets, email templates,
  delivery state, reminder logic, tracking events, and task-link tokens.
- `companies`: companies, projects, participants, project membership, hierarchy
  helpers, manager matching, anonymous names, and trainer-facing company flows.
- `forms`: questionnaire definitions, questionnaire responses, response save
  and submit behavior, and form policies.
- `health`: health/readiness routes.
- `identity`: users, sessions, invite verification, password reset, consent,
  session cookies, and role/session policies.
- `participants`: participant workspace summaries and participant-facing task
  aggregation.
- `scoring`: scoring results, aggregate reports, and scoring/reporting policies.

## Standard Shape

Use this shape for non-trivial modules:

- `models.py`: persistence models owned by the module.
- `schemas.py`: request/response contracts owned by the module.
- `repository.py`: database reads and writes for the module.
- `service.py`: domain behavior and orchestration.
- `policies.py`: authorization and permission decisions.
- `router.py`: FastAPI route adapters.

Small helper files are acceptable when they have a narrower responsibility than
the standard layers, such as `hierarchy.py`, `task_links.py`, or
`password_policy.py`.

## Dependency Direction

- Routers adapt HTTP to application services and policies.
- Services orchestrate domain behavior and may use repositories.
- Repositories perform persistence operations and must not call services or
  routers.
- Policies must stay lightweight and must not depend on repositories, services,
  or routers.
- Schemas define module-owned API contracts and should not perform persistence
  or request orchestration.

## Cross-Module Imports

Prefer importing another module through stable service, policy, schema, helper,
or explicit contract surfaces. Direct cross-module repository imports are
allowed only when they are documented in
`backend/tests/architecture/test_module_boundaries.py`.

The current documented repository edges are:

| Source | Target | Owner | Reason |
| --- | --- | --- | --- |
| `assignments.service` | `companies.repository` | assignments | Assignment planning needs project membership, hierarchy, and participant data. |
| `assignments.service` | `forms.repository` | assignments | Assignment save/response flows need questionnaire response state. |
| `assignments.service` | `scoring.repository` | assignments | Assignment completion views need existing scoring-result state. |
| `companies.service` | `communications.repository` | companies | Company invite and campaign actions coordinate recipient/email state. |
| `companies.service` | `identity.repository` | companies | Roster and account flows create or connect user identities. |
| `scoring.router` | `companies.repository` | scoring | Report endpoints currently perform access lookups before service calls. |
| `scoring.router` | `forms.repository` | scoring | Report endpoints currently fetch response state before service calls. |
| `scoring.service` | `companies.repository` | scoring | Scoring aggregation needs hierarchy and project membership data. |

The current documented router-to-service cross-module edges are:

| Source | Target | Owner | Reason |
| --- | --- | --- | --- |
| `assignments.router` | `identity.service` | assignments | Task-link endpoints verify or create invite sessions. |
| `assignments.router` | `scoring.service` | assignments | Assignment report endpoints reuse scoring aggregation behavior. |

Adding a new edge is not a local convenience decision. Update the architecture
test allowlist and explain why the boundary is still acceptable.

## Architecture Tests

Architecture boundaries are enforced by:

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm --workdir /workspace/backend backend uv run pytest tests/architecture/test_module_boundaries.py
```

The tests intentionally encode the current modular monolith instead of a future
ideal. If they fail, either remove the new dependency or make the new exception
explicit and review it as architecture debt.
