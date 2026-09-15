# Tasks: CI Main Concurrency + Fleet Fan-out Cap (Stage 1)

**Mission**: `ci-main-concurrency-fanout-cap-01M2K46V` | **Branch**: `fix/ci-main-concurrency-fanout-cap`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Authority**: ADR `2026-09-15-1` (PR #4534)

> **Single work package, single lane.** The two ADR levers (1a #4347, 2a #4371) are coupled and **must land together in one PR** (NFR-004); their edits are small and share the test surface. The plan's Parallel Work Analysis established one lane. There is therefore exactly one WP; there is no parallelism to exploit and forcing a split would create overlapping `owned_files` on the shared test files.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Lever 1a — `ci-router.yml` per-SHA main concurrency (exact expression) | WP01 | |
| T002 | Lever 1a pin — exact-equality golden-YAML concurrency pin in `test_dual_mode_contract.py` | WP01 | |
| T003 | Lever 2a — `ci-fleet-verdict.yml`: trim `types:[completed]` + top-level per-SHA concurrency + refresh `report`(PR) comment (report-main UNCHANGED) | WP01 | |
| T004 | Lever 2a pins — update `test_fleet_verdict.py:125` types set + add exact-equality top-level-concurrency pin | WP01 | |
| T005 | Dedup survivor test — non-tautological double-snapshot / newer-not-suppressed test in `test_fleet_verdict.py` | WP01 | |
| T006 | Verify — actionlint+shellcheck (raw output), ci pins + never-green + reconcile green, diff-scope check, #4208 byte-identical tests green | WP01 | |

## Work Packages

### WP01 — Stage-1 concurrency + fan-out cap (levers 1a + 2a)

**Goal**: Land both coupled ADR levers — per-SHA main concurrency (1a) and the fleet-verdict fan-out cap (2a: `types:[completed]` + top-level per-SHA coalesce; `report-main` deliberately unchanged) — with exact-equality golden-YAML pins and a non-tautological dedup survivor test, verified pre-merge and (post-merge) on the merged main tip.

**Priority**: P1 (the whole mission). **Independent test**: the `ci` module shard (`tests/ci` + `tests/architectural/test_dual_mode_contract.py`) plus manual `actionlint`/`shellcheck`; real acceptance is the merged-main-tip runbook in [quickstart.md](./quickstart.md).

**Included subtasks**: T001, T002, T003, T004, T005, T006 (tracked via `spec-kitty agent tasks mark-status`, not checkboxes).

**Implementation sketch**:
1. T001 `ci-router.yml` concurrency → `group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}`, `cancel-in-progress: ${{ github.event_name != 'push' }}`.
2. T002 add exact-equality pin (see contracts/ci-yaml-shape.md C-YAML-1) in `test_dual_mode_contract.py`.
3. T003 `ci-fleet-verdict.yml`: `types:` → `[completed]`; add top-level `concurrency: {group: ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}, cancel-in-progress: true}`; refresh the `report`(PR) `cancel-in-progress:false` comment (C-YAML-6). **Leave `report-main` exactly as-is.**
4. T004 update `test_fleet_verdict.py:125` (`{"completed"}`) + add exact-equality top-level-concurrency pin (C-YAML-3). **Do NOT touch `test_fleet_main.py:166`.**
5. T005 add the dedup survivor test (contracts/verdict-invariants.md VI-1/VI-2) — drift via the in-memory `API()` stub, never by patching `snapshot`.
6. T006 verify: `actionlint`+`shellcheck` (paste raw output), run `tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/ci/test_reconcile_shards.py tests/architectural/test_dual_mode_contract.py`, the diff-scope check, confirm #4208 byte-identical policy tests green.

**Estimated prompt size**: ~380 lines (6 subtasks).

**Dependencies**: none. **Parallel opportunities**: none (single lane).

**Risks**: fakeable substring pins (mitigated → exact equality); coalescing dropping a verdict (mitigated → per-SHA keys, report-main untouched); the terminal-survivor residual wedge (detected by SC-006, self-heal deferred to Stage 3); no actionlint CI gate (mitigated → manual run + exact pins). See plan.md risk table.

**Reviewer guidance**: verify the exact concurrency expressions match the contracts verbatim; verify `report-main` and `test_fleet_main.py:166` are UNCHANGED; verify the dedup test drives drift through the stub (not by patching `snapshot`); verify the diff touches no `ci-aggregate.yml`/`reconcile_shards.py`/`aggregate_source.py`; verify raw actionlint/shellcheck output is captured.

## MVP scope

WP01 is the entire mission. There is no reduced MVP — the two levers are coupled (1a without 2a worsens the storm).
