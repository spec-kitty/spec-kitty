# Work Packages: Per-Project Sync Consent Ledgers

**Mission**: `per-project-sync-consent-ledgers-01KZKMQZ`
**Planning branch**: `feat/per-project-sync-consent`
**Merge target branch**: `feat/per-project-sync-consent`
**Generated**: 2026-08-09T17:05:36Z
**Post-tasks revision**: 2026-08-09

## Execution contract

This mission replaces shared hosted-sync state with one canonical-UUID-owned
`sync.db`, one connection-owning unit of work, one layout-generation writer
authority, and one explicit local consent writer. WP01 is deliberately green: it
ships census, instrumentation, positive controls, and self-tests for the mutation
harness only. Every behavior-changing WP commits its own public-entry-point test
that is red on the planning base before implementation.

The mission preserves #3030's consent-bearing selection, SQL identity filtering,
final transmit recheck, terminal parking, and explicit purge. It does not absorb
#3108/PR #3135. No WP may inspect or mutate the historical 1,322 SaaS events,
mutate production `team.spec-kitty.ai`, publish, open a PR, integrate to a protected
branch, release, or deploy without separate Human-in-Charge authorization.

SaaS WP04 must provide an explicit candidate checkout/ref and canonical-contract
digest before core WP05 starts. Coordinated acceptance starts only after core
WP06-WP10 and reviewed SaaS WP02/WP08 are ready. Core owns conforming
client bytes, local isolation, stale-generation parking, and the core benchmark;
SaaS owns bypass refusal, zero server effects, tombstone proof, hosted admission
performance, and any authorized Upsun canary.

## Dependency graph

```text
WP01 Green census and evidence harness
  -> WP02 ProjectSyncStore + layout authority
       -> WP03 Consent epochs/history/hints
            -> WP04 Project-owned repositories + all current-writer permits
            -> WP05 Pinned target/admission contract  <- SaaS WP04
                 -> WP06 Attempt + lease protocol
                      -> WP07 Interactive transports
                           -> WP08 Daemon/background
                                -> WP09 Aggregate revoke/crash proof
                           -> WP10 WAL-aware migration/cutover
WP09 + WP10 + reviewed SaaS WP02/WP08 -> WP11 coordinated core evidence
```

WP10 may progress after WP07 while WP08/WP09 continue, but this is not a claim of
source-level disjointness: WP04 owns every current writer and must already have
made each one consume WP02's layout permit, while WP07 sequentially releases the
shared CLI surface before WP10. WP10 owns only migration/cutover orchestration and
proof.

## Subtask index

| ID | Description | Work Package | Parallel |
|---|---|---|---|
| T001 | Record the #3030 supersession and replacement boundary in an ADR | WP01 | [P] |
| T002 | Census every live SQLite connection and commit owner | WP01 | [P] |
| T003 | Census every local grant writer and implicit grant input | WP01 | [P] |
| T004 | Census all project-bearing sender, result, and current-writer paths | WP01 | [P] |
| T005 | Build green positive-control and mutation-harness self-tests | WP01 | |
| T006 | Implement canonical UUID parsing and deterministic store resolution | WP02 | [P] |
| T007 | Implement ProjectSyncStore schema and connection-owning unit of work | WP02 | |
| T008 | Implement the sole layout-generation authority and write-permit API | WP02 | |
| T009 | Implement immutable ProjectSyncContext construction and mismatch refusal | WP02 | [P] |
| T010 | Prove atomicity, layout authority, worktree sharing, and physical isolation | WP02 | |
| T011 | Replace local grant resolution with one versioned project decision writer | WP03 | |
| T012 | Implement monotonic capture sequences and consent epochs | WP03 | |
| T013 | Implement immutable previewed history-disclosure capabilities | WP03 | [P] |
| T014 | Implement atomic narrowing-only daemon deny hints | WP03 | [P] |
| T015 | Retire legacy grant writers and prove opt-in/opt-out semantics | WP03 | |
| T016 | Move event-journal capture behind the project unit of work and layout permit | WP04 | |
| T017 | Move delivery selection/results/status behind the project store and permit | WP04 | |
| T018 | Move event and body/offline outboxes behind the project store and permit | WP04 | [P] |
| T019 | Preserve project-scoped purge and terminal-selection defenses | WP04 | [P] |
| T020 | Wire every current writer/export to the layout API and prove zero cross-project access | WP04 | |
| T021 | Select and attest the exact SaaS WP04 candidate contract | WP05 | |
| T022 | Move delivery target interfaces, registry, exports, and tests into the project boundary | WP05 | [P] |
| T023 | Normalize the exact server/account/Private-Teamspace admission audience | WP05 | [P] |
| T024 | Persist immutable admit/revoke/readmit receipts with CAS semantics | WP05 | |
| T025 | Consume and prove the pinned per-write proof/refusal contract | WP05 | |
| T026 | Commit red-first durable-attempt and cross-process lease ATDD | WP06 | |
| T027 | Persist attempts and recover uncertain native-idempotency outcomes | WP06 | |
| T028 | Implement the project-scoped transport/result lease and final gate | WP06 | |
| T029 | Make opt-out settle or irrevocably terminalize orphan attempts | WP06 | |
| T030 | Prove protocol ordering, bounded deadlines, and no late success promotion | WP06 | |
| T031 | Commit red-first interactive transport convergence ATDD | WP07 | |
| T032 | Converge dispatcher, event relay, WebSocket Event, and LocalCommit | WP07 | |
| T033 | Converge body, dossier, history/preflight, final, and reconnect paths | WP07 | [P] |
| T034 | Converge generic SaaS and tracker-hosted adapters without granting | WP07 | [P] |
| T035 | Prove native correlation, terminal refusal, final-gate mutants, and no fresh retry identity | WP07 | |
| T036 | Commit red-first daemon/background isolation ATDD | WP08 | |
| T037 | Converge daemon, runtime, and background discovery on project authority | WP08 | |
| T038 | Enforce deny-only hints and layout permits on background/current writers | WP08 | |
| T039 | Prove another project remains live and no cache/layout path grants | WP08 | |
| T040 | Build the all-family deterministic synchronization harness | WP09 | |
| T041 | Prove pause-before-start and start-before-opt-out for every family | WP09 | |
| T042 | Prove kill-before-send, during-response, and before-result recovery | WP09 | |
| T043 | Prove kill-during-response then immediate opt-out rejects late recovery | WP09 | |
| T044 | Implement read-only WAL-aware legacy inventory and exact verification | WP10 | [P] |
| T045 | Implement copy-only UUID partitioning and non-deliverable quarantine | WP10 | |
| T046 | Advance the existing layout authority through verified atomic cutover | WP10 | |
| T047 | Implement recognized-daemon quiesce/restart and residue diagnosis | WP10 | |
| T048 | Expose preview/migrate/diagnose commands and hard-kill convergence proof | WP10 | |
| T049 | Verify candidate commits and canonical contract digest | WP11 | |
| T050 | Run the core-owned conforming six-project exact-byte proof | WP11 | |
| T051 | Run real stale-generation terminal parking without duplicating SaaS refusal proof | WP11 | |
| T052 | Prove deterministic cross-platform identity and physical-open isolation | WP11 | [P] |
| T053 | Run the reproducible project-discovery benchmark | WP11 | [P] |
| T054 | Emit immutable evidence manifest, checksums, retention metadata, docs, and tracker mappings | WP11 | |

## WP01 — Green baseline, architecture census, and evidence harness

**Prompt**: `tasks/WP01-baseline-architecture-census.md`
**Priority**: P1
**Dependencies**: none

**Goal**: Freeze connection, commit, grant-writer, sender, and current-writer
topology; record the #3030 supersession; and deliver a green reusable evidence
harness with live positive controls and self-tests. It does not commit a failing
feature assertion or change production behavior.

T001-T005 belong to WP01.

## WP02 — ProjectSyncStore, layout authority, schema, and identity

**Prompt**: `tasks/WP02-project-sync-store-aggregate.md`
**Priority**: P1
**Dependencies**: WP01

**Goal**: Create the UUID-owned physical aggregate, sole live transaction owner,
immutable context, and machine layout-generation/write-permit API used by every
later current writer and migration.

T006-T010 belong to WP02.

## WP03 — Sole consent writer, epochs, deny hints, and history capability

**Prompt**: `tasks/WP03-consent-epochs-history-hints.md`
**Priority**: P1
**Dependencies**: WP02

**Goal**: Reduce local consent to one explicit writer, separate capture from
egress through monotonic epochs, and make history disclosure and daemon narrowing
explicit capabilities.

T011-T015 belong to WP03.

## WP04 — Project-owned repositories and current-writer participation

**Prompt**: `tasks/WP04-project-owned-payload-repositories.md`
**Priority**: P1
**Dependencies**: WP02, WP03

**Goal**: Move journal, ledger, event/body outboxes, retention/status, and their
runtime exports into ProjectSyncStore. Every current-version writer uses WP02's
layout permit immediately before insert; no later migration WP edits these writers.

T016-T020 belong to WP04.

## WP05 — Pinned target-scoped admission and canonical contract

**Prompt**: `tasks/WP05-target-scoped-admission-contract.md`
**Priority**: P1
**Dependencies**: WP02, WP03, external SaaS WP04 candidate

**Goal**: Attest the exact SaaS candidate contract, move delivery target
interfaces/registry/exports behind the project boundary, bind admission to the
exact audience, and persist immutable control-operation receipts.

T021-T025 belong to WP05.

## WP06 — Durable attempt and transport/result lease protocol

**Prompt**: `tasks/WP06-transport-attempt-lease-protocol.md`
**Priority**: P1
**Dependencies**: WP04, WP05

**Goal**: Establish the durable attempt, final eligibility gate, cross-process
lease, orphan settlement, and no-late-success rules before adapters converge.

T026-T030 belong to WP06.

## WP07 — Interactive transport convergence

**Prompt**: `tasks/WP07-interactive-transport-convergence.md`
**Priority**: P1
**Dependencies**: WP06

**Goal**: Thread one context/attempt/lease through every interactive HTTP,
WebSocket, LocalCommit, body/dossier, history, generic SaaS, and tracker adapter.

T031-T035 belong to WP07.

## WP08 — Daemon and background convergence

**Prompt**: `tasks/WP08-daemon-background-convergence.md`
**Priority**: P1
**Dependencies**: WP06, WP07

**Goal**: Converge daemon/runtime/background discovery on authoritative project
state, denial hints, layout permits, and independent liveness for other projects.

T036-T039 belong to WP08.

## WP09 — Aggregate revocation and crash matrix

**Prompt**: `tasks/WP09-aggregate-revocation-crash-matrix.md`
**Priority**: P1 acceptance gate
**Dependencies**: WP07, WP08

**Goal**: Use one test-only synchronization harness to prove every sender family,
both revoke orderings, every hard-kill window, and the compound
kill-during-response -> immediate opt-out -> late-recovery case.

T040-T043 belong to WP09.

## WP10 — WAL-aware layout migration, quarantine, and cutover

**Prompt**: `tasks/WP10-wal-aware-project-store-cutover.md`
**Priority**: P1
**Dependencies**: WP04, WP07

**Goal**: Consume—not create—the layout authority; copy and verify mixed shared
state into project stores; quarantine unsafe identity; atomically cut over; and
prove all already-converted writers obey both orderings.

T044-T048 belong to WP10.

## WP11 — Coordinated core acceptance and immutable evidence

**Prompt**: `tasks/WP11-cross-repository-evidence-closure.md`
**Priority**: P1 acceptance gate
**Dependencies**: WP09, WP10, reviewed SaaS WP02 anti-rematerialization and WP08 server/effect candidates

**Goal**: Prove the core-owned half of coordinated acceptance against exact
candidate commits and one contract digest, run local/cross-platform/performance
gates, and emit an immutable checksum manifest referencing—but not duplicating—
SaaS-owned server and hosted evidence.

T049-T054 belong to WP11.

## Implementation readiness notes

- WP IDs are sequential and every task ID T001-T054 appears exactly once.
- All code-changing WPs use `python-pedro`. WP01 alone uses
  `architect-alphonso` because it is a green census/review package and owns no
  production implementation. WP11 changes executable acceptance/evidence code,
  so it also uses `python-pedro`.
- `owned_files` are exact. Any shared file is sequentially owned with an explicit
  dependency (currently WP07 → WP10 for `cli/commands/sync.py`); any other
  out-of-map edit requires coordination and a recorded ownership update.
- Every behavior-changing WP commits red-first ATDD in its own lane. WP01 must be
  green and approvable.
- A pre-existing failure must be filed before baseline classification.
- The plan, ADR, contracts, and post-tasks adversarial review are the mission's
  sufficient research record; a separate optional `research/` directory is not
  required for implementation or acceptance.
- `/spec-kitty.analyze` remains mandatory before implementation.
