# Tasks: Upgrade must not rewrite healthy Mission history

**Mission**: `upgrade-preserves-mission-history-01M49D3A` · **Branch**: `issue-5811-upgrade-preserves-mission-history`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | #5811 CLI repro: no-op `upgrade --yes` leaves history byte-identical | WP01 | [P] |
| T002 | #5811 repro: no audit manifest; `auto_commit` commit has no `kitty-specs/` path | WP01 | |
| T003 | #5812 CLI repro: residue directory raises no blocker and gets no files | WP01 | [P] |
| T004 | Prove both repros red on the base commit; record the evidence | WP01 | |
| T005 | Campsite: extract helpers from `_repair_mission` (behaviour-preserving) | WP02 | |
| T006 | Public row-to-line function in `status/store.py`; store uses it | WP02 | |
| T007 | Lane rows round-trip through `StatusEvent`; delete allowlist; byte-preserve non-lane rows | WP02 | |
| T008 | Remove the `_row_sort_key` re-sort; prove lane state unchanged | WP02 | |
| T009 | Derived files only when the log changed and the file is tracked | WP02 | |
| T010 | Field-list-driven parity test; re-pin fixtures that pinned null keys | WP02 | |
| T011 | Repair outcome carries errored Missions with reasons; characterize `errors=52` | WP02 | |
| T012 | Public `is_mission_dir` predicate (tracked `spec.md` or `meta.json`) | WP03 | |
| T013 | `_select_mission_dirs` uses the predicate; residue directories skipped | WP03 | |
| T014 | Audit uses the predicate; non-blocking `RESIDUE_DIRECTORY` finding | WP03 | |
| T015 | Identity backfill still runs for real legacy Missions | WP03 | |
| T016 | Turn the #5812 repro into a regular test | WP03 | |
| T017 | Gate evaluates readiness only under drain; report-only, never repairs | WP04 | |
| T018 | `upgrade.py` stops passing repair consent; doctor renders errored Missions, exits non-zero | WP04 | |
| T019 | Sole-caller pin: only doctor calls `repair_repo` | WP04 | [P] |
| T020 | Retire or re-pin upgrade-consent tests that assert `--yes` repairs | WP04 | |
| T021 | ADR `2026-10-07-1`; turn the #5811 repro into a regular test | WP04 | |

## Phase 1: Red-first

### WP01: Red-first CLI reproductions (#5811, #5812)
- **Prompt**: [tasks/WP01-red-first-repros.md](tasks/WP01-red-first-repros.md) (~250 lines)
- **Goal**: prove both defects through the real CLI entry points before any fix.
- **Priority**: P0. **Independent test**: both files fail on base under `SPEC_KITTY_RUN_P0_REPRO=1`.
- **Subtasks**:
  T001 #5811 CLI repro (WP01)
  T002 #5811 manifest and auto_commit assertions (WP01)
  T003 #5812 CLI repro (WP01)
  T004 Red-on-base evidence (WP01)
- **Dependencies**: none.
- **Risks**: a mocked repro is vacuous. The repro must use a real scratch git repository, real writer-produced logs, and drain on (the default autouse fixture).

## Phase 2: Fixes

### WP02: Repair keeps writer-shaped history byte-identical
- **Prompt**: [tasks/WP02-repair-row-parity.md](tasks/WP02-repair-row-parity.md) (~400 lines)
- **Goal**: lane rows round-trip through `StatusEvent` and the store's serializer; physical order is kept; derived files are written only when needed; the outcome names errored Missions.
- **Subtasks**:
  T005 Campsite extraction (WP02)
  T006 Store row-to-line function (WP02)
  T007 Lane-row round trip (WP02)
  T008 Remove re-sort (WP02)
  T009 Derived-file guard (WP02)
  T010 Parity test and fixture re-pins (WP02)
  T011 Errored-Missions outcome (WP02)
- **Dependencies**: WP01.
- **Risks**:
  - `_repair_mission` is at complexity 15, so extract first.
  - Legacy rows must still be normalized.
  - The #4897 non-lane registry must hold.

### WP03: One is-a-Mission predicate (#5812)
- **Prompt**: [tasks/WP03-is-mission-dir-predicate.md](tasks/WP03-is-mission-dir-predicate.md) (~280 lines)
- **Goal**: residue directories are not Missions in the audit or the repair.
- **Subtasks**:
  T012 Predicate (WP03)
  T013 Repair selection (WP03)
  T014 Audit selection and finding (WP03)
  T015 Legacy identity backfill (WP03)
  T016 Unmark #5812 repro (WP03)
- **Dependencies**: WP02 (shares `mission_state.py`; same lane).
- **Risks**:
  - The walker gate requires `_iter_mission_dirs` to stay the single enumeration primitive.
  - A Mission that is untracked but genuine, such as a fresh scaffold with no `spec.md` committed, must still count. Accept a `meta.json` that exists on disk with a `mission_id`; see the prompt.

### WP04: Upgrade becomes report-only under drain
- **Prompt**: [tasks/WP04-upgrade-report-only.md](tasks/WP04-upgrade-report-only.md) (~350 lines)
- **Goal**: `upgrade` never repairs; it reports under drain and points to `doctor mission-state --fix`.
- **Subtasks**:
  T017 Drain-gated, report-only gate (WP04)
  T018 Upgrade consent removal and doctor outcome (WP04)
  T019 Sole-caller pin (WP04)
  T020 Consent test retire or re-pin (WP04)
  T021 ADR and unmark #5811 repro (WP04)
- **Dependencies**: WP01. Runs in parallel with WP02 and WP03.
- **Risks**: deliberately breaks tests that assert `--yes` repairs; each gets a KEEP, RE-PIN or RETIRE verdict.

## Parallelism

WP02 and WP03 run in sequence in one lane. WP04 runs in its own lane in parallel with them.

## MVP

WP01 plus WP04 alone removes the P0 trigger. WP02 and WP03 make the explicit repair safe.
