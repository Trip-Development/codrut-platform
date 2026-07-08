# Authorization Policy Matrix

Baseline captured during CP0002 data-integrity and authorization hardening.
This document describes the intended policy surface and the current enforcement
points found in the codebase. It is deliberately workflow-based; it is not a
generic RBAC model.

## Actors

| Actor | How it appears today | Intended trust boundary |
| --- | --- | --- |
| Trainer | `SessionPrincipal.role == trainer`; often paired with company membership role `owner` or `trainer`. | May manage only companies/projects/campaign data they own or are assigned to manage. A global trainer role is not enough for object access. |
| Participant | `SessionPrincipal.role == participant` with current terms accepted for participant-only flows. | May read/write only their own workspace, assigned questionnaires, and eligible scoring results. |
| Secure-link participant | Participant session created from a valid assignment invite token, usually for low-member invite flows. | May access only the respondent profile and assignment IDs embedded in the invite token, subject to invite/project windows and normal participant terms. |
| Anonymous public user | No `codrut_session`; public endpoints, campaign tracking links, unsubscribe links, login/register/reset, health. | May use only explicit public endpoints and signed tokens/codes. Must not infer private resource IDs. |
| System | CLI seed/import/migration code, background-like email sending helpers, test providers, deployment checks. | May mutate data only through explicit operational commands or server-side orchestration, never through unauthenticated public HTTP routes. |

There is no admin role in the current model. If an operation is truly global,
it must be treated as a temporary trainer-admin behavior and tested as such.

## Enforcement Surfaces

| Surface | Current code | Notes |
| --- | --- | --- |
| Session identity | `codrut.api.dependencies.current_principal` | Requires `codrut_session`, resolves a non-expired session, returns `SessionPrincipal`. |
| Participant terms | `codrut.api.dependencies.require_current_terms` | Applies only to participant flows; trainers bypass it. |
| Trainer role | `companies.policies.require_trainer_principal`; local `_require_trainer` helpers in `forms.router` and `communications.router` | Checks role only, not object ownership or company membership. |
| Company manager | `CompanyService._require_company_manager`; `AssignmentService._require_company_manager` | Requires target-company membership role `owner` or `trainer`. |
| Participant assignment ownership | `FormsRepository.get_assignment_for_user` through `FormsService.get_assignment_response` and `save_assignment_response` | Enforces assignment ownership before questionnaire reads/writes. |
| Scoring result access | `scoring.router.get_assignment_scoring_result` | Trainers require company membership for the assignment company; participants require own assignment. |
| Campaign owner scoping | `owner_id` parameters in `CommunicationsService` and repository methods | Authenticated communications routes pass `principal.user_id`; public tracking/unsubscribe resolves recipients by signed token. |
| Signed public links | Task-link tokens and campaign tracking/unsubscribe tokens | Tokens bind claims to resource IDs and expiry; tests cover tampering/expiry for campaign tracking. |
| CSRF for cookie-auth unsafe requests | `codrut.core.csrf.CsrfMiddleware` | Protects authenticated unsafe requests; public unsafe endpoints are deliberate exceptions. |

## Resource Matrix

| Resource or workflow | Allowed actors | Intended policy | Current enforcement | Test anchor |
| --- | --- | --- | --- | --- |
| Health readiness | Anonymous, system | Public read-only operational status. | `health.router` has public `GET /live` and `GET /ready`. | Existing health/API smoke tests. |
| Session login/logout/password reset | Anonymous for login/reset; authenticated user for logout/change-password/consent. | Public entrypoints create or recover sessions; authenticated mutations require current session and CSRF. | `identity.router`, `IdentityService`, password policy, CSRF exceptions for public entrypoints. | `tests/test_identity_security.py`, `tests/test_csrf.py`. |
| Invite verification and secure-link session bootstrap | Anonymous with valid task-link token; secure-link participant after session creation. | Token must identify company, respondent, assignment IDs, and expiry. Low-member verification may create a participant session only for scoped assignments. | `IdentityService.verify_invite_token_and_create_session`, task-link parsing, project access-window validation. | Assignment invite and task-link tests; add cross-company/token-scope deny tests if missing. |
| Company list and summaries | Trainer only, scoped to managed companies. | Trainers should see only companies they own/manage unless the product intentionally adds a named global operator mode. | `companies.router` requires trainer role and passes `principal.user_id` into scoped company, summary, project list, and project get service calls. | `tests/test_companies_router.py`; add broader second-trainer visibility tests as route coverage grows. |
| Company create/delete | Trainer; delete only owner/trainer membership for target company. | Create assigns owner membership. Delete requires company manager of target company. | Create uses `principal.user_id`; delete calls `CompanyService.delete_company`, which now requires target-company membership. | Add cross-company trainer delete deny test. |
| Company projects | Trainer owning/managing target company. | Project list/create/update/delete must be scoped by company membership and project-company match. | Company service checks company/project existence and membership; top-level project list/get routes pass `principal.user_id`. | Add unowned-company project read/write deny tests. |
| Participant profiles, roster import, invitations, reporting relationships | Trainer owning/managing target company. | Participant PII, roster updates, invite sends, and hierarchy imports are company-scoped trainer operations. | Router checks trainer role; `CompanyService` checks target-company manager membership. | Add unowned-company participant list/update/import/invite deny tests. |
| Access code creation | Trainer owning/managing company. | Only company manager may mint access codes. | Router checks trainer role; service uses current company-manager logic. | Add cross-company access-code creation deny test. |
| Access code registration | Anonymous with valid active code. | Public registration may create/connect a participant account only to the code's company and the submitted identity. | `CompanyService.register_with_access_code`; public CSRF exception; sets session cookie. | Existing identity/company registration tests; add inactive/wrong-code and cross-company assertions if missing. |
| Teams and team memberships | Trainer owning/managing company. | Teams and memberships must belong to the target company; team members must be company participants. | `AssignmentService._require_company_manager` checks membership owner/trainer and participant/team company membership. | Assignment service tests; add route-level unowned-company deny test. |
| Assignment planning and status updates | Trainer owning/managing company. | Assignment respondent, target person/team, project, and questionnaire definition must be scoped and valid. Status reopen must unlock response and clear scoring state only for scoped assignment. | `AssignmentService` validates company manager, project, participants, teams, assignment target shape, and status side effects. | `tests/test_assignment_service.py`; add cross-company assignment status deny test. |
| Assignment invitation create/invalidate | Trainer owning/managing company. | Caller must manage the company; invite token must include only assignments for the respondent/company/project. | Router checks trainer role and company-manager membership before calling `IdentityService`; invite service checks respondent and assignment scope. | Add unowned-company invite create/invalidate deny tests. |
| Questionnaire definitions | Active definitions: authenticated trainer/participant reads. Retired/writes: trainer only. | Participants may fetch active definitions needed to render assigned forms; definition lifecycle is trainer-only. | `forms.router` allows authenticated reads; `include_retired` and write routes require trainer role. | `tests/test_forms_router.py`; add participant write deny if not covered. |
| Questionnaire responses | Participant assigned to the questionnaire. | Only the respondent user may read/save/submit their response; submitted responses are locked unless trainer reopens the assignment. | `FormsService` resolves assignment through `get_assignment_for_user`, validates windows, locks submitted responses. | `tests/test_forms_service.py`; add other-participant assignment deny test if missing. |
| Participant workspace | Participant with current terms. | Workspace may show only the participant's profile, assignments, projects, teams, and released results. | `participants.router` checks participant role and terms; service queries by `user_id`. | `tests/test_participant_workspace_service.py`; add trainer/other-user deny tests if missing. |
| Scoring result by assignment | Trainer managing assignment company; respondent participant for own assignment. | Trainers need company membership; participants need exact assignment ownership. | `scoring.router` performs explicit membership or assignment ownership checks before compute/read. | `tests/test_scoring_router.py`; add cross-company trainer/participant deny tests if gaps remain. |
| Aggregate company reports | Trainer owning/managing company. | Aggregate reports must not expose another company's participant or scoring data. | `assignments.router.get_company_report_aggregate` calls `AssignmentService.require_company_manager`, which uses membership-scoped logic. | Add route-level cross-company aggregate deny test. |
| Email templates and ops summary | Trainer, scoped to owner where custom templates or send state exist. | Catalog templates may be shared read-only; owner-specific templates and send state are scoped. | Authenticated routes pass `owner_id=principal.user_id`. | Add second-trainer template/campaign visibility tests. |
| Campaign recipients | Trainer owning the recipient set; anonymous token links for tracking/unsubscribe. | Recipient PII, status, and memberships must be owner-scoped. Public writes must be token-bound. | Authenticated recipient routes pass `owner_id=principal.user_id`; manual event recording is trainer-authenticated and CSRF-protected; tracking/unsubscribe stay signed-token public flows. | Add owner-scope deny tests and public-token tamper tests. |
| Campaign assets | Trainer only. | Uploaded content must pass size/type/path checks and not allow path traversal. | Router requires trainer role, central request limit, asset-specific declared and actual size checks in storage helper. | Existing security middleware tests plus asset upload tests. |
| Campaign create/update/delete/send/memberships | Trainer owning campaign and recipient set. | Campaign mutations and sends must be owner-scoped and must not mix recipients across owners or segments. | Authenticated routes pass `owner_id=principal.user_id`; service/repository enforce owner filters. | Add second-trainer campaign update/send/delete deny tests. |
| Campaign tracking and unsubscribe | Anonymous with signed token. | Token must bind action/recipient/event/target and expiry; unsubscribe confirmation is public, POST mutates only token-bound recipient. | `campaign_tracking` token helpers and service parsers; unsubscribe reads recipient by token claim. | `tests/test_campaign_tracking.py`, `tests/test_campaign_policy.py`; add token-recipient mismatch if not covered. |
| System seed/migrations/deploy checks | System only. | Operational commands must require explicit environment controls and never be exposed through public HTTP. | Seed docs mention production guard; migrations run out of band. | Deployment and migration verification tasks in this Festival. |

## Immediate Authorization Test Targets

These are the highest-value deny tests for the next task. They are ordered by
blast radius and current evidence, not by implementation difficulty.

1. A trainer without membership in company B cannot list, update, import,
   invite, create access codes, or delete resources under company B.
2. Assignment invitation create/invalidate denies a trainer who is not a manager
   of the target company, even though invite token creation validates assignment
   scope internally.
3. A participant cannot read/save/submit another participant's assignment
   response and cannot read another participant's scoring result.
4. Campaign recipients, campaigns, campaign memberships, sends, email templates,
   and ops summaries remain scoped by `owner_id=principal.user_id`.
5. Manual campaign event recording remains trainer-authenticated and
   CSRF-protected; anonymous tracking and unsubscribe remain signed-token public
   flows.
6. System-only commands remain unavailable through authenticated or anonymous
   HTTP routes.

## Policy Function Direction

Do not spread object checks into every router as ad hoc conditionals. The next
implementation should consolidate toward small policy/helper surfaces that are
easy to test:

- `require_trainer_principal(principal)` for role-only trainer screens.
- `require_company_manager(user_id, company_id)` for company-scoped resources;
  this must not treat every trainer as a manager.
- `require_participant_assignment(user_id, assignment_id)` through forms/scoring
  repositories or a dedicated participant policy helper.
- `require_campaign_owner(owner_id, campaign_id)` or consistent
  `owner_id=principal.user_id` propagation through `CommunicationsService`.
- `require_signed_public_token(...)` for task links, campaign tracking, and
  unsubscribe actions.
- System operations should stay CLI/internal and should not gain HTTP policy
  helpers unless there is a real authenticated system actor.

Any behavior intentionally left global must be named as such in code and tests.
The current role name `trainer` is too weak to imply global administration.
