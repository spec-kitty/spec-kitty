# Tasks: Finalize re-pins an orphaned planning_commit_sha after a rebase (#4827)

**Mission**: `finalize-repin-orphaned-planning-commit-01M31TAT`
**Branch**: `fix/finalize-repin-orphaned-planning-commit`
**Design**: see [research.md](./research.md) (D1–D7), [data-model.md](./data-model.md), [contracts/finalize-repin-contract.md](./contracts/finalize-repin-contract.md)

Single-orchestrator, sequential mission. Four work packages; WP02 and WP03 both depend only on WP01. Tests are event-sourced — record subtask completion with `spec-kitty agent tasks mark-status Txxx --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | New shared module: object-presence + reachability git predicates | WP01 | |
| T002 | `classify_recorded_pin` → captured/advanced/orphaned/foreign (+ degrade signal) | WP01 | |
| T003 | Unit tests for the classifier (real git repo: advanced/orphaned/foreign/degrade) | WP01 | |
| T004 | Red-first finalize repro (@regression): plain preserves orphan; refresh refuses orphan | WP02 | |
| T005 | Add `--allow-orphaned` Typer option (default False), thread to the resolver | WP02 | |
| T006 | Wire classifier into `_preserve_or_capture_planning_commit_sha`: re-pin / fail-closed / degrade / keep advance-only refusal | WP02 | |
| T007 | `repinned` action + report-after-write + fix #4178 drift-WARN false-positive (FR-009/FR-010) | WP02 | |
| T008 | Golden-contract frozenset += `--allow-orphaned`; update `--refresh-planning-commit` help | WP02 | |
| T009 | Envelope `CONTRACT_VERSION` 1.5.0→1.6.0; regen `docs/api/agent-subcommands.md` | WP02 | |
| T010 | Un-mark red-first repro; confirm #4141 + #3311 suites green | WP02 | |
| T011 | Red-first allocator repro (@regression): orphaned pin → generic conflict today | WP03 | |
| T012 | `_merge_recorded_planning_commit` gains target-branch ref + classifies; orphan → orphan-specific error | WP03 | |
| T013 | New orphan-specific error class (next_step names the finalize re-pin recovery) | WP03 | |
| T014 | Reconcile `implement_support.py` reconcile-merge (:352) + `check_claim_ancestry` (:497) | WP03 | |
| T015 | Reconcile `_mt_resolve_owned_review_base` (`tasks_move_task.py:697`) — no dead-base diff | WP03 | |
| T016 | Corrected expectations: `test_lane_base_common_ancestor.py`, `test_worktree_allocator_atomicity.py` | WP03 | |
| T017 | Un-mark red-first repro; confirm `tests/lanes/` green | WP03 | |
| T018 | `[Unreleased]` Fixed CHANGELOG entry (impact-first, `(#4827)`, before→after) | WP04 | |
| T019 | Cross-check CLI-ref reflects `--allow-orphaned`; note #4178 sweep + adjacent tickets | WP04 | |

## Work Packages

### WP01 — Pin classifier (foundation)
- **Goal**: one shared authority that classifies the recorded `planning_commit_sha` against the target-branch tip, removing the duplicated ad-hoc ancestry checks. Foundation for WP02 and WP03 (C-001/C-002/C-006).
- **Priority**: P1 · **Independent test**: unit tests over a real git repo exercise all four classes + the degrade signal.
- **Subtasks**: T001, T002, T003
- **Dependencies**: none · **Requirement refs**: FR-001, NFR-005
- **Prompt**: [tasks/WP01-pin-classifier.md](./tasks/WP01-pin-classifier.md) (~250 lines)

### WP02 — Finalize re-pin surface
- **Goal**: default fails closed on a proven orphan (degrades otherwise); `--refresh-planning-commit --allow-orphaned` re-pins; bare `--refresh-planning-commit` keeps advance-only refusal; report the decision; fold the #4178 corrections; keep the CLI/JSON surface green.
- **Priority**: P1 · **Independent test**: the #4827 finalize red-first repro flips green; #4141/#3311 unchanged.
- **Subtasks**: T004, T005, T006, T007, T008, T009, T010
- **Dependencies**: WP01 · **Requirement refs**: FR-002, FR-003, FR-004, FR-005, FR-009, FR-010, NFR-001, NFR-002
- **Prompt**: [tasks/WP02-finalize-repin-surface.md](./tasks/WP02-finalize-repin-surface.md) (~450 lines)

### WP03 — Consumer detection
- **Goal**: every recorded-pin consumer (allocator merge fresh+reuse, reconcile, claim gate, owned-review base) names a stale pin + recovery instead of a false conflict, a dead-base diff, or a bare refusal — detection centralized in the shared merge helper.
- **Priority**: P1 · **Independent test**: the #4827 allocator red-first repro flips green; corrected-expectation suites pass.
- **Subtasks**: T011, T012, T013, T014, T015, T016, T017
- **Dependencies**: WP01 · **Requirement refs**: FR-006, FR-007, FR-008, NFR-003, NFR-004
- **Prompt**: [tasks/WP03-consumer-detection.md](./tasks/WP03-consumer-detection.md) (~500 lines)

### WP04 — Docs & changelog
- **Goal**: user-facing documentation of the fix once both code WPs land.
- **Priority**: P2 · **Independent test**: CHANGELOG entry present with `(#4827)`; doc-freshness gate green.
- **Subtasks**: T018, T019
- **Dependencies**: WP02, WP03 · **Requirement refs**: FR-003
- **Prompt**: [tasks/WP04-docs-changelog.md](./tasks/WP04-docs-changelog.md) (~120 lines)

## MVP scope

WP01 + WP02 close the operator-facing wedge (re-pin path + no-silent-preserve). WP03 closes the consumer-side dead-ends; WP04 documents. All four are needed for a release-grade fix, but WP01+WP02 are the minimum that un-wedges finalize.
