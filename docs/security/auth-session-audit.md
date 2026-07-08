# Auth, Session, and Public Endpoint Audit

Baseline captured during CP0002 security hardening before behavior changes.

## Session Cookie

Source: `backend/src/codrut/modules/identity/session_cookie.py`.

| Attribute | Current value |
| --- | --- |
| Cookie name | `codrut_session` |
| Max age | 90 days (`7776000` seconds) |
| Path | `/` |
| HttpOnly | `true` |
| Secure | `true` only when `CODRUT_ENV=production` |
| SameSite | `lax` |
| Domain | not set |

Session rows store `sha256(raw_token)` in `sessions.token_hash`; the raw token is
only sent to the browser as the cookie value. Current session lookup reads
`request.cookies["codrut_session"]` and requires a matching, unexpired row.

Cookie deletion uses `response.delete_cookie("codrut_session", path="/")`.

## Session Entry And Exit Points

| Flow | Endpoint | Cookie effect | Notes |
| --- | --- | --- | --- |
| Login | `POST /api/auth/login` | Sets session cookie | Password login for existing users. |
| Leadership invite registration | `POST /api/auth/register` | Sets session cookie | Requires invite token, matching email, accepted terms, and leadership membership. |
| Low-member secure-link verification | `GET /api/auth/invite/verify?token=...` | Sets session cookie when the invitee is not leadership | This GET is state-changing: it may create a shadow participant user/session and set the cookie. |
| Leadership secure-link verification | `GET /api/auth/invite/verify?token=...` | No session cookie | Leadership users must register or login. |
| Logout | `POST /api/auth/logout` | Deletes session cookie and deletes current session row | Requires existing session. |
| Password reset request | `POST /api/auth/reset-password` | No cookie effect | Unknown emails return success without sending email. |
| Password reset confirm | `POST /api/auth/reset-password/confirm` | Deletes all sessions for the user | Consumes a one-hour reset token and requires password policy. |
| Password change | `POST /api/auth/change-password` | Deletes all sessions for the user | Requires current session and current password. |
| Terms consent | `POST /api/auth/consent` | No new cookie | Requires current session; updates terms metadata. |

## Frontend Cookie Handling

- Browser API calls use same-origin `/api/...` and `credentials: "include"`.
- `frontend/next.config.mjs` rewrites `/api/:path*` to the backend when the
  frontend serves requests directly.
- Compose/Traefik routes `/api` to the backend directly; the dev dynamic config
  gives the API router higher priority than the frontend router.
- Server-rendered frontend API calls manually forward
  `Cookie: codrut_session=<value>` from Next `cookies()`.
- Frontend middleware protects `/trainer/*` and `/participant/*` by checking for
  a `codrut_session` cookie unless demo fallback is enabled. It does not validate
  the cookie; backend `/auth/me` validation still gates server-rendered data.
- Public frontend pages include `/login`, `/trainer/login`, `/reset-password`,
  `/update-password`, `/invite/[token]`, and the public home page.

## Public Backend Endpoints

These endpoints do not depend on `current_principal`.

| Method | Path | State-changing | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/health/live` | No | Health check. |
| `GET` | `/api/health/ready` | No | Health check. |
| `GET` | `/api/auth/invite/verify` | Yes | May create low-member shadow account/session and set cookie. |
| `POST` | `/api/auth/register` | Yes | Creates leadership participant account and session. |
| `POST` | `/api/auth/login` | Yes | Creates session. |
| `POST` | `/api/auth/reset-password` | Yes | Creates reset token and sends email when eligible. |
| `POST` | `/api/auth/reset-password/confirm` | Yes | Changes password, consumes reset token, deletes sessions. |
| `POST` | `/api/companies/access-code-registration` | Yes | Creates/registers access-code account when enabled by service policy. |
| `GET` | `/api/communications/campaigns/track/calendly/{token}` | Yes | Tracks campaign calendly click and redirects. |
| `GET` | `/api/communications/campaigns/track/opened/{token}` | Yes | Tracks campaign open pixel. |
| `GET` | `/api/communications/campaigns/track/{event_type}/{token}` | Yes | Tracks campaign click-like events. |
| `GET` | `/api/communications/campaigns/unsubscribe/{token}` | No | Confirmation page data. |
| `POST` | `/api/communications/campaigns/unsubscribe/{token}` | Yes | Unsubscribes campaign recipient. |
| static | `/api/campaign-assets/*` | No | Mounted public static campaign assets. |
| docs | `/api/openapi.json`, `/api/docs` | No | Public when docs are enabled. |

## Authenticated State-changing Endpoint Groups

All endpoints below depend on `current_principal`; most are unsafe methods and
will need CSRF treatment if cookie auth remains the browser credential.

- Auth/session: `POST /api/auth/change-password`, `POST /api/auth/consent`,
  `POST /api/auth/logout`.
- Companies/projects: company create/delete, project create/update/delete.
- Participants/roster: participant create/update, roster import, invite send,
  invite resend, reporting-relationship import.
- Access codes: `POST /api/companies/{company_id}/access-codes`.
- Communications: test email, campaign asset upload, template create/update/
  activate/delete, campaign recipient bulk/update/delete/event recording,
  campaign create/update/delete, membership replace, campaign send.
- Teams: team create and team membership create.
- Assignments: assignment create, default-plan save, assignment status update,
  company invitation create/invalidate.
- Forms: questionnaire definition create/update/activate/delete, assignment
  response save, assignment response submit.

Authenticated reads also rely on the session cookie and should keep no-store or
private-cache behavior where user-specific data is involved.

## Current Gaps To Address In Follow-up Tasks

1. There is no CSRF token or Origin/Referer enforcement for cookie-authenticated
   unsafe requests. `SameSite=Lax` lowers cross-site risk for most POSTs, but it
   is not a complete CSRF strategy.
2. `GET /api/auth/invite/verify` is state-changing for low-member secure links
   because it can create a user/session and set `codrut_session`.
3. Public unsafe endpoints have no visible rate limiting: login, password reset,
   reset confirm, registration, access-code registration, unsubscribe, campaign
   event recording, and tracking endpoints.
4. Low-member secure-link sessions use the normal 90-day session lifetime. The
   invite token expiry gates link reuse, while assignment/project windows enforce
   questionnaire access after session creation.
5. Cookie deletion does not explicitly mirror all set-cookie attributes. Browser
   deletion is based on name/path/domain, but matching attributes would make the
   intent clearer.
6. General JSON/body size limits are not centralized. Campaign asset upload has
   a dedicated content-length and stream-size check.
7. Security headers are not currently installed by backend middleware. Frontend
   has `poweredByHeader: false`, but no app-level CSP or related headers are
   defined in this audit.

## Verification Commands

Route inventory was produced with:

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm --workdir /workspace/backend backend uv run python -c '...router inventory...'
```

Targeted checks for this audit:

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm --workdir /workspace/backend backend uv run pytest tests/test_identity_security.py tests/test_api_dependencies.py
git diff --check
```
