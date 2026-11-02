# Tasks: Golden dry-run rendering is order-independent

**Mission**: golden-dry-run-order-independence-01M6EJX3
**Branch**: `kitty/mission-golden-dry-run-order-independence-01M6EJX3`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · issue #7030

Make `tests/upgrade/test_upgrade_outcome_rendering.py::test_golden_applied_dry_run` pass
identically when its node is selected alone and when the module runs whole, by removing the one
environment-derived input it still read live (the supporting-repair preview count) and keeping the
exact-match golden text unchanged. No `src/` change (FR-004).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: reproduce the node-selected failure on the branch and record command + output | WP01 | — |
| T002 | Stub `upgrade_module._supporting_repair_preview` in the dry-run golden from one module constant, recording calls | WP01 | — |
| T003 | Assert the stub was consulted exactly once so the preview line cannot silently drop out | WP01 | — |
| T004 | Verify: node-selected run, whole-module run, repeated runs, neighbouring upgrade suites, ruff | WP01 | — |

## Wrap-up (outside the WP lanes)

- Changelog fragment `docs/changelog/unreleased/<pr>.internal.md` is authored once the PR number
  exists (the fragment name carries it), per the mission brief and
  `docs/changelog/unreleased/README.md`.
- Issue-matrix row for #7030 is set to its terminal verdict at wrap-up.

---

## WP01 — Deterministic dry-run preview input for the golden

**Prompt**: [tasks/WP01-deterministic-dry-run-preview-input.md](tasks/WP01-deterministic-dry-run-preview-input.md)

**Summary**
- **Goal**: Stop the golden reading the isolated home's repair inventory; keep it a whole-output
  rendering oracle over a complete-preview run.
- **Priority**: P1 — the only work package.
- **Independent test**: `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q`
  passes from a clean process, then the whole module passes with the same pinned text.

**Tracking**
- [ ] T001 Red-first: reproduce the node-selected failure on the branch and record command + output (WP01)
- [ ] T002 Stub `upgrade_module._supporting_repair_preview` in the dry-run golden from one module constant, recording calls (WP01)
- [ ] T003 Assert the stub was consulted exactly once so the preview line cannot silently drop out (WP01)
- [ ] T004 Verify: node-selected run, whole-module run, repeated runs, neighbouring upgrade suites, ruff (WP01)

**Implementation sketch**
- `tests/upgrade/test_upgrade_outcome_rendering.py`: add one module constant next to
  `_PREVIEW_NOTICE` holding the complete-preview sentence the pinned golden already contains
  (`"Would repair 1 supporting surface paths (including 0 manifests). Use --plan-json for full
  repair details."`); in `test_golden_applied_dry_run`, replace the live preview by a recording
  stub over that constant and assert `len(calls) == 1`; leave `_GOLDEN_APPLIED_DRY_RUN`,
  `_stub_incomplete_preview` and the matrix rows byte-identical.
- Negative scope: NO change to `src/specify_cli/cli/commands/upgrade.py`, NO change to
  `tests/conftest.py`, NO new test file, NO skip/xfail/marker.

**Dependencies**: none.
**Estimated prompt size**: ~150 lines.
