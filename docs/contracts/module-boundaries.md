# Module Boundaries

Codrut is structured as a modular monolith. Modules live in one deployable backend, but each
module should keep a clear public surface so it can be changed or extracted later without a
large rewrite.

## Backend Module Shape

New backend modules belong in `backend/src/codrut/modules/<module_name>/`.

Use this default shape unless a module is intentionally tiny:

- `models.py`: SQLAlchemy persistence models owned by the module.
- `schemas.py`: Pydantic request and response contracts exposed by the module.
- `repository.py`: database reads and writes for the module's own tables.
- `service.py`: domain behavior and orchestration.
- `policies.py`: authorization and permission decisions.
- `router.py`: FastAPI routes.

## Dependency Rules

- Routes call services.
- Services call repositories and explicit cross-module contracts.
- Repositories should not call services or routers.
- Modules should not reach into another module's repository directly.
- Shared infrastructure belongs in `backend/src/codrut/core/`.
- Cross-module data contracts belong in `backend/src/codrut/contracts/`.

These rules are enforced incrementally by
`backend/tests/architecture/test_module_boundaries.py`. The tests are
intentionally narrower than the ideal contract so they match the current code
without false positives. New direct cross-module repository imports or
router-to-service imports must be documented in that test file.

Current documented cross-module repository imports:

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

Current documented router-to-service imports across modules:

| Source | Target | Owner | Reason |
| --- | --- | --- | --- |
| `assignments.router` | `identity.service` | assignments | Task-link endpoints verify or create invite sessions. |
| `assignments.router` | `scoring.service` | assignments | Assignment report endpoints reuse scoring aggregation behavior. |

See `backend/src/codrut/modules/README.md` for module ownership and the
standard layer responsibilities.

## Cross-Module Communication

Prefer explicit contracts for work that crosses module boundaries:

- Use service methods for synchronous application behavior.
- Use event contracts for asynchronous behavior handled by workers.
- Use email contracts for communication jobs.
- Keep contract payloads stable and version them when external behavior depends on them.

This gives the codebase the simplicity of a monolith while preserving a path to split a module
into a separate service if that becomes necessary.
