# Tasks — Refuse a `--target` override onto a protected branch

**Mission**: `protected-target-override-refusal-01M68JPV` · **Issue**: spec-kitty/spec-kitty#6464
**Planning base / merge target**: `issue-6464-protected-target-override-refusal`

Three work packages, ordered red-first: the regression and its controls land first (and are red on
`main`), the guard makes them green, the design record and the changelog follow.

## Subtask Index

| T-id | Description | WP | Parallel |
|------|-------------|----|----------|
| T001 | Red-first e2e: `consolidate --target <protected>` refuses before any branch moves | WP01 | |
| T002 | Same-fixture controls: in-bounds `--target` consolidates; operator hatch stands the guard down | WP01 | [P] |
| T003 | `--dry-run --json` reports the same refusal code and remedy | WP01 | [P] |
| T004 | `orchestrator-api consolidate-mission --target <protected>` refuses in its envelope | WP01 | [P] |
| T005 | The decision seam: `refuse_protected_target_override` beside `refuse_protected_status_target` | WP02 | |
| T006 | Wire the seam into the pre-lock CLI door, after the #5385 probe | WP02 | |
| T007 | Wire the seam into the `--dry-run` forecast | WP02 | |
| T008 | Wire the seam into `orchestrator-api consolidate-mission` | WP02 | |
| T009 | Record the decision in ADR `2026-09-19-1` (follow-up) | WP03 | |
| T010 | Changelog entry under `[Unreleased]` | WP03 | [P] |

## Phase 1 — The regression (red first)

### WP01 — Red-first regression and controls

- **Summary**: Pin the defect through the real `spec-kitty consolidate` CLI and the real
  `orchestrator-api consolidate-mission` entry, on real git. The refusal test must fail on current
  `main` (the squash lands on `main`); the controls must pass before and after the fix.
- **Priority**: P1 (blocks WP02 — the guard is written against these assertions).
- **Independent test**: `pytest tests/terminus/test_protected_target_preflight.py tests/orchestrator_api/test_consolidate_mission_protected_target.py -q`
- **Included subtasks**: T001, T002, T003, T004
- **Prompt**: [tasks/WP01-red-first-regression-and-controls.md](./tasks/WP01-red-first-regression-and-controls.md)
- **Dependencies**: none
- **Risks**: the fixture must leave the checkout on the override branch; otherwise the pre-existing
  `MERGE_UNSAFE_PRIMARY_OFF_TARGET` guard refuses first and the new assertion proves nothing.

## Phase 2 — The guard

### WP02 — The protected-target override refusal

- **Summary**: One seam function that asks `ProtectionPolicy` whether the effective target is
  protected and differs from the recorded target, and three call sites (pre-lock CLI door, dry-run
  forecast, orchestrator-api) that refuse before any mutation with `PROTECTED_BRANCH_REFUSED`.
- **Priority**: P1.
- **Independent test**: WP01's tests go from red to green, and every pre-existing control stays green.
- **Included subtasks**: T005, T006, T007, T008
- **Prompt**: [tasks/WP02-protected-target-override-refusal.md](./tasks/WP02-protected-target-override-refusal.md)
- **Dependencies**: WP01
- **Risks**: reading the recorded target from the retargeted manifest makes the guard vacuous; the
  seam must sit after #5385's probe so that refusal's pinned text is unchanged.

## Phase 3 — The record

### WP03 — Design record and changelog

- **Summary**: Extend ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (the follow-up
  section that documents the recorded-target preflight as reading "the recorded meta target, not
  `--target`") with the new override guard and its residual, and add the `[Unreleased]` changelog entry.
- **Priority**: P2.
- **Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
  the changelog guard passes.
- **Included subtasks**: T009, T010
- **Prompt**: [tasks/WP03-design-record-and-changelog.md](./tasks/WP03-design-record-and-changelog.md)
- **Dependencies**: WP02
- **Risks**: the ADR is a historical record — amend by appending a dated follow-up, never by rewriting
  the original decision text.

## Parallel opportunities

- T002, T003 and T004 run against the same fixture shape and touch different files/test functions;
  a single WP carries them so the shared fixture cannot drift.
- T010 (changelog) is independent of T009.

## MVP scope

WP01 + WP02: the defect is closed and pinned. WP03 is the durable record a maintainer needs to review
the change against ADR `2026-09-19-1`.
