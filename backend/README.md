# Codrut Backend

FastAPI modular monolith for Codrut Platform.

## Module Rules

- Routers handle HTTP concerns only.
- Services hold business logic.
- Repositories own database access.
- Policies own authorization decisions.
- Modules communicate through service interfaces or contracts, not by importing each other's persistence internals.
