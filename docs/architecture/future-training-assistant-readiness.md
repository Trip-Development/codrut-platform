# Future Training Assistant Readiness

Date: 17 July 2026

Scope: architecture audit only. This document does not authorize or implement a chatbot,
roleplay workflow, AI provider, microphone access, or new navigation.

## Verdict

The application is reasonably prepared for a new independent backend domain, but it is not yet
prepared for trainer-assigned roleplays to behave like first-class participant work.

| Addition | Readiness | Reason |
| --- | --- | --- |
| Participant-only text assistant | Moderate | A protected route and backend module fit the current architecture, but provider, persistence, streaming, limits, and privacy contracts do not exist. |
| Trainer-authored scenarios | Moderate | Company, project, trainer, and participant ownership already exist, but capability controls and roleplay policies do not. |
| Assigned roleplays with participant progress | Low to moderate | Assignment and participant task contracts are questionnaire-specific from database to UI. |
| Trainer review and reporting | Low to moderate | A separate evaluation contract and explicit visibility policy are needed; scoring cannot safely be reused by default. |
| Voice roleplay | Low | Microphone access is intentionally disabled, and audio consent, storage, retention, transcription, and realtime transport are undefined. |

Overall readiness is **B for adding a normal product module** and **C for a production AI
roleplay feature**. The gap is bounded architectural work, not a reason to redesign the product
now.

## Existing Strengths

- The backend is a modular monolith with explicit router, service, repository, policy, schema,
  and model layers.
- Architecture tests reject undocumented cross-module repository and service coupling.
- Company, project, trainer, participant, membership, and reporting relationships provide the
  ownership context a roleplay feature would need.
- Participant terms are enforced on protected participant APIs.
- The frontend already separates trainer and participant route trees and protects both audiences.
- OpenAPI generation provides a stable path for typed frontend contracts.
- Redis and an ARQ worker are deployed, so asynchronous evaluation can be added without a new
  process topology.
- Request IDs, CSRF, CSP, security headers, request limits, and rate-limit infrastructure provide
  useful defaults.

## Current Constraints

### Activity composition

`QuestionnaireAssignment`, backend `InviteTask`, participant workspace aggregation, and frontend
task grouping all assume that every assigned task is a questionnaire. A roleplay must not be
stored as a fake questionnaire or added to `QuestionnaireAssignment` with nullable AI fields.
That would couple two different lifecycles, validation rules, retention policies, and result
visibility rules.

When assigned roleplays are implemented, keep questionnaire and roleplay persistence separate.
Compose them for the participant through a small discriminated activity contract such as:

```text
LearningActivitySummary
  kind: questionnaire | roleplay
  id, title, status, href, dueAt, estimatedMinutes
```

Each domain should own how that summary is produced. The participant module should aggregate the
summaries without importing another module's repository.

### Navigation and route metadata

Top-level navigation labels live in `components/shell/nav.ts`, icons are inferred separately from
URL fragments in `app-shell.tsx`, and project tabs have another static array. Adding a roleplay
surface is possible, but easy to implement inconsistently.

Before exposing the feature, move route label, icon, audience, active-match behavior, and optional
capability key into one typed navigation registry. Loading and error shells should consume the
same metadata. This is a focused shell refactor, not a new plugin system.

The current `/participant/chat` route is a hidden support page, not a conversation product. It
should either retain an explicit support name or be replaced deliberately when the real feature
exists. It must not be treated as evidence that chat infrastructure is already present.

### Capabilities and rollout

There is no company, project, or participant capability model. An AI feature needs an explicit
entitlement so it can be enabled for selected customers, disabled during incidents, and hidden
consistently in both UI and API authorization. Environment flags alone are insufficient because
they cannot express tenant ownership.

Start with a small server-owned capability check. Do not build a general billing or feature-flag
platform before the rollout model is known.

### Provider and streaming boundary

No AI provider adapter or structured streaming contract exists. The frontend fetch wrapper can
consume a streamed response, but the product has not defined event shapes, cancellation,
reconnection, partial persistence, retries, or duplicate-turn protection.

The roleplay module should own a provider port rather than importing a vendor SDK into routes:

```text
RoleplayProvider
  stream_turn(context, participant_message) -> typed events
  evaluate_session(transcript, rubric) -> structured evaluation
```

Provider model names, prompt versions, safety configuration, and token usage must be persisted or
logged with the session. The browser must call Codrut, never an AI provider directly.

### Background work and events

The ARQ worker currently runs only a health-check function. Event dataclasses exist but are not
dispatched. Post-session evaluation, transcript redaction, and usage aggregation therefore need a
real enqueue boundary, retry policy, idempotency key, and failure state before the worker can be
considered application infrastructure.

Streaming a live turn should remain in the request path. Slow evaluation after a completed
session is the better first worker job.

### Privacy, safety, and cost

The current privacy and terms copy does not describe AI-generated coaching, transcript retention,
audio, automated evaluation, or external model providers. Backend and frontend also duplicate the
current terms version as constants, which increases drift risk when consent changes.

Before a customer pilot, decide and encode:

- whether transcripts, audio, and evaluations are stored;
- retention and deletion periods for each data class;
- which trainer roles can view transcripts versus aggregate evaluations;
- whether customer data may be used by a model provider for training;
- redaction of secrets and unnecessary personal data before provider calls;
- prompt-injection and data-exfiltration boundaries;
- participant disclosure that the counterpart is AI and output may be inaccurate;
- incident handling, content reporting, and human review;
- per-participant and per-company usage quotas, concurrency limits, and budget alerts.

The current IP-and-path rate limiter is not a cost-control mechanism. AI limits should key on the
authenticated user and company and account for tokens or duration.

Voice requires a separate gate. The frontend `Permissions-Policy` currently disables microphone
access, as it should until audio behavior is designed and approved.

## Recommended Domain Shape

When implementation is authorized, add a `roleplays` backend module with its own standard layers.
Likely owned records are:

- `RoleplayScenario`: trainer-authored scenario, rubric, version, and company ownership;
- `RoleplayAssignment`: project and participant assignment with status and due date;
- `RoleplaySession`: immutable scenario version, participant, lifecycle, and provider metadata;
- `RoleplayTurn`: ordered participant and assistant turns with provider request identity;
- `RoleplayEvaluation`: structured rubric result, visibility policy, model version, and review state.

Minimum API families should remain domain-oriented:

- trainer scenario and assignment management;
- participant assignment and session lifecycle;
- idempotent participant turn submission with typed streaming events;
- explicit session completion and retryable evaluation state;
- trainer review guarded by company and project authorization.

Do not reuse questionnaire scoring until a product decision proves that the same privacy,
interpretation, validation, and review semantics apply.

## Delivery Sequence

1. **Product and data decision**: text or voice, assignment model, transcript visibility,
   retention, provider processing, and pilot entitlement.
2. **Focused foundations**: typed navigation metadata, tenant capability check, server-owned terms
   version, and participant activity summary contract.
3. **Text roleplay core**: scenarios, sessions, turns, provider adapter, cancellation, persistence,
   limits, and local deterministic provider.
4. **Trainer workflow**: assignments, progress, review, and failure recovery.
5. **Evaluation**: idempotent worker job, structured rubric contract, human review, and reporting.
6. **Voice only after a separate review**: microphone permission, transcription, audio retention,
   accessibility fallback, latency, and cost controls.

## Verification Required

- Architecture tests for the new module and every permitted cross-module contract.
- Authorization tests across trainer, company, project, participant, session, and transcript IDs.
- Provider contract tests with deterministic streaming, cancellation, timeout, malformed output,
  and retry behavior.
- Persistence and idempotency tests for duplicate turns and duplicate evaluation jobs.
- Component tests for partial streaming, reconnect, retry, disabled input, and accessible status.
- Privacy tests proving transcripts and evaluations are not exposed through participant or trainer
  endpoints outside their policy.
- Load and budget tests before enabling the feature for more than the pilot entitlement.

## Do Not Do Yet

- Do not install an AI SDK or add provider secrets.
- Do not expose a chatbot navigation item.
- Do not convert the hidden support route into a simulated chatbot.
- Do not generalize `QuestionnaireAssignment` before the real roleplay lifecycle is known.
- Do not enable microphone access.
- Do not seed fake roleplay conversations into the current local preview.

These constraints keep the current overhaul focused while preserving a clear, reviewable path for
the future feature.
