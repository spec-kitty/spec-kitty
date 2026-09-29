# Work Packages: Consolidation claim, rollback and teardown integrity

**Inputs**: Design documents from `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rollback-authority.md, quickstart.md

**Tests**: Required (charter ATDD-first, C-003 red-first real-CLI repros, NFR-002 ≥90% diff coverage).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Every WP is `code_change`; there is deliberately **no** `planning_artifact` WP — in this LANES mission a planning WP depending on code WPs would itself trip #5296 on the target branch. ADR/CHANGELOG/CLAUDE.md edits happen at closeout on the aggregate branch.

## ⛔ HARD RULE (every implementer and reviewer)

No heavy full suites during the mission: no whole `tests/architectural/`, no e2e/full-integration, no performance/stress/timing suites, no `make test-full`, no whole-repo pytest. Per WP run only the test files covering touched files, the owning module's fast tier, and the specific NAMED architectural gate files listed in the WP. (`NO_FULL_HEAVY_SUITES_IN_MISSION`.)

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Tidy-first + claim-time refusal (#5338) (Priority: P0)

**Goal**: A consolidation whose approved-work claim fails its integrity check exits non-zero before any mutation.
**Independent Test**: `tests/terminus/test_repro_5338.py` — resume scenario B refuses with target/mission/lane SHAs, bookkeeping and event logs unchanged; the PASS-anchor control still exits 0.
**Prompt**: `tasks/WP01-claim-time-refusal.md`
**Requirement Refs**: FR-001, FR-002, NFR-003, NFR-004, C-001, C-003

### Included Subtasks

T001 Red-first real-CLI repro for #5338 (resume scenario B) + FR-002 control, committed before the fix (WP01)
T002 [P] Tidy-first: hoist the repeated "Nothing was torn down…" executor literal to a constant; extract the claim GitProbeError exit helper (behaviour-preserving) (WP01)
T003 Pure `claim_integrity_refusal(claim)` in reconciliation.py composing `MergeOutcomeVerifier._refusal_reason` + vacuous check, with unit tests (WP01)
T004 Act on it at the end of `_capture_reconciliation_claim` (inside the fresh-record guard), exempting `_resume_reconciliation_already_passed` (WP01)
T005 Re-pin stale tests that expected a refused claim to reach later phases (rationale per test); run targeted gates (WP01)

### Dependencies

- None.

---

## Work Package WP02: Single snapshot + CAS rollback authority (core) (Priority: P0)

**Goal**: One persisted pre-mutation snapshot, per-phase post-mutation tips, and one compare-and-swap rollback authority with a truthful report — no executor wiring yet.
**Independent Test**: `tests/consolidation/test_rollback_authority.py` + `tests/git/test_restore_branch_ref_resync.py` on real git repos: restore, already-at-snapshot, CAS conflict (not restored, not overwritten), missing post tip (not restored), verified-landing guard, dirty checkout, idempotence, bookkeeping clear only on full restore.
**Prompt**: `tasks/WP02-rollback-authority-core.md`
**Requirement Refs**: FR-003, FR-007, FR-010, FR-011, NFR-001, NFR-003, NFR-004, C-007

### Included Subtasks

T006 Extract `_resync_checkouts` from `advance_branch_ref`; re-key the destructive-op census allowlist entry (behaviour-preserving) (WP02)
T007 `restore_branch_ref(..., resync_checkouts=False, is_residue=None)` opt-in resync + docstring amendment + tests (WP02)
T008 [P] `ConsolidationState.pre_mutation_refs` / `post_mutation_refs` (back-compat load) + pure `reconciliation_passed_for_tip(state, tip)` (WP02)
T009 New `consolidation/rollback.py`: `capture_pre_mutation_snapshot` (reads legacy anchors as seeds), `begin_attempt` (per-attempt restore targets), `record_post_mutation_tips`, `rollback_to_snapshot` → `RollbackReport` (incl. UNCHANGED_BY_RUN), `render` (WP02)
T010 Unit tests for the authority on real temp repos (all outcomes + guard + idempotence) (WP02)
T011 [P] LANES real-CLI fixture builder `tests/terminus/lanes_fixture.py` (from the verified reference) + a smoke test (WP02)

### Dependencies

- None (parallel with WP01).

---

## Work Package WP03: Wire the authority into consolidation (#5318, #5332) + truthful text (Priority: P0)

**Goal**: Every gate FAIL/REFUSE and projection refusal restores every snapshotted branch and prints the rollback report; snapshot captured once before mutation; post tips recorded after each mutating phase.
**Independent Test**: `tests/terminus/test_repro_5318.py` (coord + LANES), `tests/terminus/test_repro_5332.py` (coord), fresh-run "all lanes folded" REFUSE now restores and never prints "no refs/worktrees were mutated"; `tests/consolidation/test_single_rollback_authority.py` AST pin.
**Prompt**: `tasks/WP03-wire-rollback-into-consolidation.md`
**Requirement Refs**: FR-003, FR-004, FR-006, FR-009, FR-010, SC-002, SC-004, C-001, C-002, C-003

### Included Subtasks

T012 Red-first real-CLI repros: #5318 coord (FAIL → coord/mission branch left moved; `--abort`+fresh self-refuses/ships), #5318 LANES (mission branch left moved), #5332 coord (projection refusal, no rollback), fresh "all lanes folded" gate REFUSE (target left advanced + false text) (WP03)
T013 Capture the snapshot once (fresh) inside the pre-mutation guard after the claim; resume reuses (WP03)
T014 Record post-mutation tips at the end of each mutating phase and immediately before the gate (WP03)
T015 Driver call-site wrapper around `_phase_reconcile_before_teardown`: non-zero `typer.Exit` → `rollback_to_snapshot` → print report → re-raise; `_resume_reconciliation_already_passed` delegates to `reconciliation_passed_for_tip` (WP03)
T016 AST pin `tests/consolidation/test_single_rollback_authority.py` (caller floor 1 in WP03, raised to 2 by WP04; self-mutation) (WP03)
T017 Re-pin tests encoding FOLD-5 "no rollback on projection refusal" / REFUSE-leaves-target (stale product direction, rationale) and golden output; run named gates (WP03)

### Dependencies

- Depends on WP01, WP02.

---

## Work Package WP04: `--abort` restores through the authority (#5318) (Priority: P1)

**Goal**: `--abort` restores every snapshotted branch (under the consolidation lock) before clearing the record; keeps the record and names branches it cannot restore; keeps a verified landing.
**Independent Test**: `tests/terminus/test_repro_5318_abort.py` — failed run → `--abort` → all branches at pre-run SHAs and fresh run passes after removing the cause; SC-005 (branch moved by plain git → not restored, not overwritten, exit 1, record kept); verified-landing record kept; pre-fix record without snapshot → today's behaviour + notice.
**Prompt**: `tasks/WP04-abort-restores-through-authority.md`
**Requirement Refs**: FR-005, FR-007, FR-011, SC-005, SC-006

### Included Subtasks

T018 Red-first real-CLI repros for `--abort` from a real in-phase exit (#5385 shape): restore, SC-005 CAS control, operator fix kept, verified landing, pre-fix record, live lock (WP04)
T019 Extract `_abort_restore_or_keep_record(...)` and call it in `_dispatch_abort` before workspace cleanup/coord teardown/clear_state, under the existing lock API (WP04)
T020 Exit codes + truthful abort messages (report render); keep `_dispatch_abort` ≤ 15 complexity (Sonar) (WP04)
T021 Unit tests for the helper branches; run targeted gates (WP04)

### Dependencies

- Depends on WP03.

---

## Work Package WP05: Planning self-heal never merges onto the target checkout (#5296) (Priority: P1)

**Goal**: A planning-lane claim whose repository root checkout HEAD is the target branch waives code-lane ancestry and never merges code lanes onto the target; consolidation later lands the code through attribution.
**Independent Test**: `tests/terminus/test_repro_5296.py` (LANES fixture): claim the planning WP → target SHA unchanged, no code file in root checkout; approve; consolidate → rc 0, gate passes. Control: root checkout on another branch keeps today's self-heal.
**Prompt**: `tasks/WP05-planning-self-heal-skip.md`
**Requirement Refs**: FR-008, SC-003, C-007

### Included Subtasks

T022 Red-first real-CLI repro (LANES fixture) for #5296 claim + consolidate (WP05)
T023 Waiver in `_approved_dependency_lane_refs` scoped to "root checkout HEAD == manifest target branch" + operator notice (WP05)
T024 Keep the existing off-target controls in test_planning_claim_self_heal.py; add on-target and protected-on-target contract tests (WP05)
T025 Unit tests for the scoping predicate; run lanes + terminus targeted tests and named gates (WP05)

### Dependencies

- Depends on WP02 (LANES fixture builder).

---

## Execution order & parallelism

- Wave 1: WP01 ∥ WP02
- Wave 2: WP03 (needs WP01+WP02) ∥ WP05 (needs WP02)
- Wave 3: WP04 (needs WP03)

MVP if time runs out: WP01 (#5338) alone, then WP02+WP03 (#5318/#5332). WP04/WP05 are cut in that order.
