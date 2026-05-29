# Scaffold Architecture

Codrut Platform starts as a modular monolith: one FastAPI backend with strict internal module boundaries, one Next.js frontend, one PostgreSQL database, one Redis-backed worker, and one Traefik edge gateway.

## Boundary Rules

- FastAPI owns domain behavior, authentication, authorization, persistence, background jobs, and integration boundaries.
- Next.js owns UI, routing, rendering, and generated API client usage.
- Traefik owns edge routing and TLS, not application authentication.
- Modules communicate through services or explicit contracts, not through arbitrary cross-module database queries.

## Initial Backend Modules

- `identity`: users, sessions, roles, and auth policies.
- `companies`: company and participant membership model.
- `forms`: questionnaire definitions, assignments, and submissions.
- `scoring`: scoring definitions and calculated results.
- `communications`: email templates, delivery state, reminders, and later campaign messaging.

## Extraction Path

The service boundary is in-process now. If a module needs to become a separate service later, its service interface and contracts become the transport boundary without rewriting product behavior.
