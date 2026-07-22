# Scaffold Architecture

Codrut Platform starts as a modular monolith: one FastAPI backend with strict internal module boundaries, one Next.js frontend, one PostgreSQL database, one Redis-backed worker, and one Traefik edge gateway.

## Boundary Rules

- FastAPI owns domain behavior, authentication, authorization, persistence, background jobs, and integration boundaries.
- Next.js owns UI, routing, rendering, and generated API client usage.
- Traefik owns edge routing and TLS, not application authentication.
- Modules communicate through services or explicit contracts, not through arbitrary cross-module database queries.

## Backend Modules

- `identity`: users, sessions, roles, and auth policies.
- `companies`: companies, projects, participants, memberships, and hierarchy.
- `assignments`: questionnaire assignments, teams, planning, and assignment links.
- `forms`: questionnaire definitions, responses, save, and submit behavior.
- `participants`: participant workspace aggregation and participant-facing tasks.
- `scoring`: scoring results, aggregate reports, and reporting policies.
- `communications`: campaigns, contacts, templates, delivery, reminders, and tracking.

The standard module shape, documented dependency exceptions, and architecture test command live in
`backend/src/codrut/modules/README.md` and `docs/contracts/module-boundaries.md`.

## Extraction Path

The service boundary is in-process now. If a module needs to become a separate service later, its service interface and contracts become the transport boundary without rewriting product behavior.

The future training-assistant assessment is recorded in
`docs/architecture/future-training-assistant-readiness.md`. It deliberately keeps questionnaire
and roleplay persistence separate while defining the small activity contract needed to compose
both for participants.
