# Tasks: Auth token-target issuer guard (#4755)

**Mission**: token-target-issuer-guard-01M319HS
**Branch**: `issue-4755-token-target-issuer-guard` (planning base + local merge target; PR lands on `main`)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/issuer-target-helper.md](./contracts/issuer-target-helper.md)

Completion is event-sourced — record subtasks with `spec-kitty agent tasks mark-status Txxx --status done`.
The rows below are reference rows, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `IssuerTargetMismatchError(AuthenticationError)` in `auth/errors.py` | WP01 | |
| T002 | Issuer decision + `resolve_token_endpoint(session)` in `auth/server_target.py` | WP01 | |
| T003 | Helper unit tests (all branches) | WP01 | |
| T004 | Refresh: consume endpoint; guard at TokenManager boundary | WP02 | |
| T005 | saas_client: add error to `_dead_session_errors`; held-token non-demotion; guard consumes shared decision | WP02 | |
| T006 | Rehydrate: thread session; fail-closed no-op + specific warning | WP02 | |
| T007 | `me_fetch`: strip-less rstrip → canonical normalizer | WP02 | |
| T008 | Red-first repro: consequence 1 (self-hosted) refresh | WP02 | |
| T009 | Red-first repro: consequence 2 (hostile env) refresh + held-token | WP02 | |
| T010 | Rehydrate mismatch unit test (token-free) | WP02 | |
| T011 | Revoke: `RevokeOutcome.ISSUER_MISMATCH`; guard before try | WP03 | [P] |
| T012 | `_auth_logout`: local teardown proceeds + warn revoke skipped | WP03 | [P] |
| T013 | Red-first repros: logout consequence 1 + consequence 2 | WP03 | [P] |
| T014 | Revoke/logout unit tests (token-free) | WP03 | [P] |
| T015 | WS: guard before URL/get_access_token; wrap `WebSocketProvisioningError` | WP04 | [P] |
| T016 | WS direct-invocation tests (mismatch / match / legacy) | WP04 | [P] |
| T017 | WS chained pre-connect-refresh refusal propagation | WP04 | [P] |
| T018 | Arch fence: forbid `get_saas_base_url` in the four token-send modules + allowlist floor + self-mutation | WP05 | |
| T019 | Arch fence: second direction — allowlist excludes the four token-send modules | WP05 | |
| T020 | `format_saas_mismatch_warning` consumes shared decision (keeps returning); `config.py` docstring | WP05 | |
| T021 | Fold #4053: dead `except ConfigurationError` branch/import/label in `_auth_saas_target.py` | WP05 | |
| T022 | Fold #4265: `auth login` mismatch exit code + canonical-URL comparison | WP05 | |
| T023 | Fence-both-directions + display-still-renders + positive-membership + fold unit tests | WP05 | |

## Work Packages

### WP01 — Shared issuer-target authority (foundation)
**Goal**: one canonical decision (resolve target → compare issuer → verdict) + the new typed error, with
the single normalizer. **Priority**: P1 (blocks all). **Independent test**: helper unit tests cover
match / mismatch / legacy-null / null-session / split-brain. **Subtasks**: T001–T003. **Deps**: none.
**Est**: ~250 lines. **Prompt**: [tasks/WP01-shared-issuer-target-authority.md](./tasks/WP01-shared-issuer-target-authority.md)

### WP02 — TokenManager wiring (refresh + rehydrate) + held-token non-demotion
**Goal**: wire refresh + rehydrate to the issuer, guard at the TokenManager boundary, and close the
held-token swallow re-leak; unify the `saas_client` guard. **Priority**: P1. **Independent test**: two
red-first refresh repros + rehydrate unit. **Subtasks**: T004–T010. **Deps**: WP01. **Est**: ~460 lines.
**Prompt**: [tasks/WP02-tokenmanager-refresh-rehydrate-wiring.md](./tasks/WP02-tokenmanager-refresh-rehydrate-wiring.md)

### WP03 — Revoke + logout teardown
**Goal**: revoke targets the issuer or refuses (`ISSUER_MISMATCH`) with local teardown preserved.
**Priority**: P1. **Independent test**: logout red-first repros. **Subtasks**: T011–T014. **Deps**: WP01.
**Est**: ~320 lines. **Prompt**: [tasks/WP03-revoke-logout-teardown.md](./tasks/WP03-revoke-logout-teardown.md)

### WP04 — WS provisioning (defence-in-depth)
**Goal**: close the dormant ws leak via the guard, wrapped into `WebSocketProvisioningError`.
**Priority**: P2. **Independent test**: direct-invocation tests. **Subtasks**: T015–T017. **Deps**: WP01.
**Est**: ~200 lines. **Prompt**: [tasks/WP04-ws-provisioning-guard.md](./tasks/WP04-ws-provisioning-guard.md)

### WP05 — Arch fence + display unification + campsite folds
**Goal**: non-vacuous fence (both directions) so the class cannot recur; unify the display consumer;
fold #4053/#4265. **Priority**: P1 (recurrence prevention). **Independent test**: fence self-mutation
both directions + positive-membership + display-renders. **Subtasks**: T018–T023. **Deps**: WP01, WP02,
WP03, WP04 (the fence goes green only once all flows are rewired). **Est**: ~420 lines.
**Prompt**: [tasks/WP05-arch-fence-and-campsite-folds.md](./tasks/WP05-arch-fence-and-campsite-folds.md)

## Dependencies

```
WP01 ──┬── WP02 ──┐
       ├── WP03 ──┤
       └── WP04 ──┴── WP05
```

## MVP scope
WP01+WP02+WP03 close both **live** consequences (refresh, logout, rehydrate). WP04 is defence-in-depth
(dormant path); WP05 hardens against recurrence and folds the campsite findings.
