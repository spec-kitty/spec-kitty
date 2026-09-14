---
work_package_id: WP05
title: Pinned target-scoped admission and canonical refusal contract
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-004
- FR-007
- FR-009
- FR-016
- FR-017
- FR-020
- FR-027
- FR-031
- FR-033
- NFR-007
- C-004
- C-005
- C-007
- C-010
planning_base_branch: feat/per-project-sync-consent
merge_target_branch: feat/per-project-sync-consent
branch_strategy: Planning artifacts for this mission were generated on feat/per-project-sync-consent. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/per-project-sync-consent unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
history:
- at: '2026-08-09T17:05:36Z'
  actor: planner
  action: Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/sync/admission_operations.py
create_intent:
- src/specify_cli/sync/admission_operations.py
- src/specify_cli/sync/project_store.py
- src/specify_cli/saas_client/admission.py
- tests/sync/test_admission_operations.py
- tests/sync/test_project_store.py
- tests/sync/test_saas_admission_compatibility.py
- tests/sync/test_target_admission_audience.py
- tests/contract/test_project_sync_admission_contract.py
execution_mode: code_change
owned_files:
- src/specify_cli/sync/admission_operations.py
- src/specify_cli/sync/project_store.py
- src/specify_cli/sync/target_authority.py
- src/specify_cli/delivery/interfaces.py
- src/specify_cli/delivery/targets.py
- src/specify_cli/delivery/__init__.py
- src/specify_cli/saas_client/admission.py
- src/specify_cli/saas_client/endpoints.py
- src/specify_cli/saas_client/errors.py
- tests/sync/test_admission_operations.py
- tests/sync/test_project_store.py
- tests/sync/test_saas_admission_compatibility.py
- tests/sync/test_target_admission_audience.py
- tests/contract/test_project_sync_admission_contract.py
- tests/delivery/test_targets.py
role: implementer
tags: []
tracker_refs:
- Priivacy-ai/spec-kitty#3262
- Priivacy-ai/spec-kitty-saas#585
---

## ⚡ Do This First: Load Agent Profile

Load the assigned implementation profile first:

```text
/ad-hoc-profile-load python-pedro
```

Then read research Decisions 4, 5, 12, and 13 plus the ProjectTargetAdmission/ProjectAdmissionOperation data model. Obtain the explicit SaaS WP04 candidate checkout path, expected commit, and expected SHA-256 digest from the orchestrator. Read `contracts/cli-saas-current-api.yaml` from that checkout only. It is authoritative and read-only in this WP.

## Objective

Implement the core half of target-scoped SaaS admission against one attested candidate contract. Move delivery target interfaces, concrete registry, public exports, and their existing tests into the ProjectSyncStore boundary so targets cannot retain a component-owned database or connection. A local project consent decision remains project-wide, while remote admission is valid only for the exact normalized server origin, authenticated account/canonical Private Teamspace, project UUID, and opaque generation. Persist admit/revoke/readmit operation identity before I/O and consume stable per-write proof/refusal shapes without inventing a parallel protocol.

## External gates

WP04 now sequentially owns `sync/project_store.py` after WP02 to mint/thread the
verified active-UoW store capability required by repository/status isolation.
WP05 consumes that reviewed seam and then applies its already planned admission
operation/target changes; it must not replace, structurally clone, or bypass the
capability when merging the approved WP04 boundary.

SaaS WP04 must expose the candidate checkout/ref and generated contract digest before this WP starts. Fail if the checkout HEAD or digest differs; do not fall back to `../spec-kitty-saas`, an ambient workspace name, branch name, or package version. Repository-sharing `admissions/` or `RepositoryShareMembership` is a different domain and must not be reused, inherited, or backfilled as ProjectSyncAdmission.

Use local/test SaaS only. A dynamically discovered Upsun branch environment may be used later with authorization; `team.spec-kitty.ai` is production and must receive no mutating request. Reviewed SaaS WP02 recorded-UUID anti-rematerialization authority must be real—not mocked—before coordinated acceptance. PR #609's full residue-safe purge remains separate and is not a substitute or prerequisite for this core prevention package.

## Subtask T021 — Select and attest the candidate contract

Require explicit inputs for SaaS checkout path, expected commit, and expected contract SHA-256. Resolve/realpath the checkout, verify its Git HEAD, read its canonical `contracts/cli-saas-current-api.yaml`, verify the digest, and record sanitized path/ref/digest in test evidence. Refuse dirty generated-contract drift, missing inputs, ambient relative lookup, and a digest from another checkout. The proof must identify SaaS WP04 as the producing gate.

## Subtask T022 — Project-owned delivery target boundary

Refactor `delivery/targets.py` so the concrete target registry is a connection-free repository over ProjectSyncStore rather than its own database/connection. Update `delivery/interfaces.py` and `delivery/__init__.py` exports together, and re-pin the existing `tests/delivery/test_targets.py` suite to the project-owned unit of work. Target URL/account/team data remains audience metadata inside one project's store and can never choose storage identity or grant consent. Add rollback and A/B isolation coverage.

## Subtask T023 — Normalize exact admission audience

Extend target authority so it returns a stable audience containing:

- normalized server origin (scheme/host/port/path policy from canonical contract);
- authenticated account identity from trusted auth metadata, never token material;
- auth-derived canonical Private Teamspace identity;
- canonical source project UUID;
- local target configuration generation.

Client-provided team selectors, repo slug, active checkout, API-key labels, and route aliases cannot establish or mutate the authority tuple. A change to any tuple member invalidates remote eligibility without changing local consent or selecting old epochs.

Test case/default ports, trailing slashes, loopback development URLs, account switch, team switch, and same project against two servers. Diagnostics expose pseudonymous IDs/categories only.

## Subtask T024 — Durable control-operation receipts and CAS

Create ProjectAdmissionOperation repository/service over the ProjectSyncStore unit of work. Before any admit, revoke, or readmit network call, persist:

- immutable operation key and action;
- exact audience tuple and project UUID;
- expected prior generation/CAS value;
- request payload hash/version and created timestamp;
- state `prepared`, `sent`, `acknowledged`, `refused`, or `unknown`;
- original server result/error category.

Operation keys cannot be reused for a different action/audience/payload. Server results are immutable evidence; never overwrite a first success/refusal with a later retry response.

Retrying the same operation after timeout must reuse the same key and return/reconcile the original result. Revoked-to-admitted requires a new explicit key plus expected-generation compare-and-set. A delayed retry of an older admit must never revive a later revoked generation.

Separate operation idempotency from admission generation. Model remote revocation truthfully:

- local opt-out complete + remote acknowledged;
- local opt-out complete + remote revocation pending/unknown;
- remote refusal with typed reason.

Do not claim server revocation because local consent changed.

## Subtask T025 — Canonical contract compatibility and refusal tests

Build a narrow client adapter from the SaaS-owned OpenAPI shapes. Verify:

- admit/revoke/readmit request/response headers and bodies;
- expected-generation and idempotency fields;
- Event, mixed-batch item, WebSocket Event, LocalCommit, dossier/body, and history/preflight each carry source UUID plus their own admission generation/audience proof;
- WebSocket uses the contract's Authorization header, not stale query-token prose;
- `project_not_admitted` has stable correlation and refusal metadata.

WP07 wires interactive senders. This WP owns target interfaces/registry, schemas, typed values, and compatibility tests. Never edit the SaaS contract from core to make a failing consumer test pass. Commit red-first tests for contract attestation, same-key retry, delayed-old-admit after revoke, expected-generation mismatch, target/account/team switch, and offline remote revocation. Test correlated refusal for each per-write shape and ensure no credential/payload enters diagnostics.

Prove repository-share membership, tracker Channel 2, configured host, and authenticated session never grant ProjectSyncAdmission. Keep #3108/PR #3135 out of scope; only verify it cannot widen.

## Branch Strategy

Run `spec-kitty agent action implement WP05 --agent <name>` after WP02/WP03 approval and SaaS WP04 candidate attestation. This lane can run beside WP04 because its ownership is distinct. Use only the computed worktree and merge via the mission workflow into `feat/per-project-sync-consent`. Do not publish or mutate any hosted environment.

## Test strategy

Use the explicit candidate contract and a local fake transport; no production calls. Commit a contract-attestation/operation-CAS test red-first. Run all five owned admission/contract tests plus `tests/delivery/test_targets.py`, target-authority tests, ruff, and strict mypy. Retain exact sanitized request/response fixtures with candidate commit and digest for review.

## Definition of Done

- Admission audience is exact and auth-derived.
- Delivery targets, interfaces, and exports use the project-owned unit of work with no component connection.
- Candidate checkout HEAD and canonical contract digest are explicit and verified.
- Every control operation is durable before I/O and immutable afterward.
- Same-key retry and expected-generation semantics prevent stale revival.
- Core consumes the SaaS-owned contract without defining a rival shape.
- Remote revocation state is truthful and separate from local consent.
- Every project-bearing write type has a per-write proof schema ready for WP06
  protocol work and downstream adapter convergence.

## Risks and reviewer guidance

Reviewers must independently verify the candidate checkout/ref/digest, race delayed admit against revoke, and inspect database evidence. Verify target storage and audience identity cannot be selected by request parameters. Reject ambient sibling lookup, a target registry that still connects/commits, inference from event-channel success/repository sharing/login/tracker permission, and mutating tests aimed at `team.spec-kitty.ai`.

## Activity Log

- 2026-08-10T01:45:55Z – codex – shell_pid=1091 – WP05 source green at 9dc5fd9ad: 71 focused tests passed; strict mypy and diff-scoped ruff passed. Submission is intentionally held in_progress until WP04 is approved and merged. Read-only architecture probe: 41 passed, 2 xfailed, 2 expected failures in WP04-owned ratchets (removed legacy target sqlite connect/commit floors; new authorized ProjectDeliveryTargetRegistry/admission_operations SQL sites). After WP04 approval, sequentially transfer the two architecture tests WP04→WP05, repin only those exact sites, and require the architecture gate green before for_review.
- 2026-08-10T01:48:31Z – codex – shell_pid=1091 – Broader compatibility planning gap for arbitration: all 22 legacy-consent setup errors arise in tests/delivery/test_dispatcher.py at its autouse _consent_to_the_test_project fixture (line 80), calling approved WP03-owned src/specify_cli/sync/consent.py and now receiving LegacyConsentMigrationRequiredError. No mission WP owns tests/delivery/test_dispatcher.py. Later WP07 owns src/specify_cli/delivery/dispatcher.py but only its three new tests/sync convergence files, not this legacy test. Do not edit until arbitration assigns sequential ownership, likely WP03→WP07 for the fixture migration.
