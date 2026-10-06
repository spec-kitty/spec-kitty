# Tasks: meta.json merge driver honours the merge base

**Mission**: `meta-driver-base-aware-01M490FF` · **Issue**: #5460
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first `p0_repro` tests: file-level `run_meta_driver(O, A, B)` on the captured #5460 blobs, real-git merge through the registered driver (exit 0 + invocation proof), `git rebase` positive control, squash-opt-out fixture | WP01 | |
| T002 | Goldens: three new hand-authored meta cases (`base-one-sided-delete`, `base-both-changed-precedence`, `base-empty-file`) red on the pre-fix driver; refresh the `base-absent` note; five existing cases untouched | WP01 | |
| T003 | Base-aware reconciliation in `drivers.py`: `_MISSING` sentinel, coupled key groups, `_reconcile_meta_two_way` extraction, per-unit three-way rule with today's precedence, `mission_number` guard regardless of ancestor, `acceptance_history` union | WP01 | |
| T004 | `run_meta_driver(base, ours, theirs, *, two_way=False)` loads `%O` through `_load_json_object`; corrupt ancestor fails loud and named | WP01 | |
| T005 | Lane-merge pipeline opt-out: `META_DRIVER_TWO_WAY_ENV` constant, shell reads it, `_make_merge_env` sets it, pipeline-ratchet and auto-rebase checks | WP01 | |
| T006 | Docstrings (`drivers.py`, `cli/commands/merge_driver.py`), CHANGELOG `[Unreleased]` Fixed entry, terminology + docs-freshness gates | WP01 | |
| T007 | Verification: remove the `p0_repro` markers in the fix commit, targeted test runs, ruff/mypy, end-to-end reproducer `kept`, tracer entries | WP01 | |

## WP01 — Base-aware meta merge driver with pipeline opt-out (IC-01 … IC-04)

**Prompt**: [tasks/WP01-base-aware-meta-merge-driver.md](tasks/WP01-base-aware-meta-merge-driver.md) · ~430 lines
**Goal**: an ordinary `git pull`/merge keeps a change made on only one side of `meta.json` (the #5460 discard survives), the consolidation pipeline's own merges stay byte-identical, and the P0 is pinned red-first. **Priority**: P0 (release blocker).
**Independent test**: `SPEC_KITTY_RUN_P0_REPRO=1 pytest tests/consolidation/test_meta_driver_base_aware_5460.py` is red on the planning base and green at the final commit; the issue reproducer reports `kept`.

T001 Red-first `p0_repro` tests through the pre-existing entry points (WP01)
T002 Goldens: three new cases red on the pre-fix driver, note refreshed, existing five untouched (WP01)
T003 Base-aware reconciliation rule in `drivers.py` (WP01)
T004 `run_meta_driver` loads the ancestor; corrupt ancestor fails loud (WP01)
T005 Lane-merge pipeline two-way opt-out (WP01)
T006 Docstrings and CHANGELOG, prose gates (WP01)
T007 Verification, marker removal, tracer entries (WP01)

**Implementation sketch**: T001+T002 are the ATDD commit (red through `run_meta_driver` and through git); T003+T004 turn them green; T005 adds the opt-out and its tests; T006 documents; T007 removes the `p0_repro` markers in the fix commit and re-runs the targeted suites.
**Parallel opportunities**: none inside the WP (single lane); T002 can be authored alongside T001.
**Dependencies**: none. **Risks**: reusing `_merge_field` (conflates `None`/absent) — use the sentinel; a post-fix `_capture.py` run would green-wash the goldens — never run it over the existing five; the real-git test must point the driver at `sys.executable -m specify_cli`, never a global binary.
