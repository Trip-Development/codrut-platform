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

## Cross-Module Communication

Prefer explicit contracts for work that crosses module boundaries:

- Use service methods for synchronous application behavior.
- Use event contracts for asynchronous behavior handled by workers.
- Use email contracts for communication jobs.
- Keep contract payloads stable and version them when external behavior depends on them.

This gives the codebase the simplicity of a monolith while preserving a path to split a module
into a separate service if that becomes necessary.
