# Tasks: Placement fixture must be a real git repo (#7055)

**Mission**: `placement-fixture-real-git-01M6EJXH` · **Branch**: `issue-7055-placement-fixture-real-git` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Capture the red baseline of the module (1 failed, 8 passed) and the probe evidence for both fixture shapes | WP01 | |
| T002 | Replace `_init_bare_git_marker` with a real `git init` helper; update its docstring and the six call sites' comments | WP01 | |
| T003 | Re-run the module: the mismatch test raises `PlacementMismatchError` again with its assertion unchanged | WP01 | |
| T004 | Add the seam-distinction regression test (unusable anchor → `TRACKED_META_UNAVAILABLE` skip, nothing written, no raise) | WP01 | |
| T005 | Run the neighbouring #6673 suite and ruff/mypy on the module; record results | WP01 | |

## Phase 1 — One module, two fail-safe seams

### WP01 — Real-repo fixture and the seam-distinction pin

**Goal**: the placement module is green on `main`'s product code, with its central fail-close genuinely exercised and the tracked-meta refusal explicitly pinned as a different, deliberate path. **Priority**: P1. **Prompt**: [tasks/WP01-real-repo-fixture.md](tasks/WP01-real-repo-fixture.md)
**Independent test**: `uv run --frozen pytest -q -p no:randomly -n0 tests/specify_cli/migration/test_runtime_state_cutover_placement.py` → 10 passed, plus `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` unchanged.

T001 Capture the red baseline of the module (1 failed, 8 passed) and the probe evidence for both fixture shapes (WP01)
T002 Replace `_init_bare_git_marker` with a real `git init` helper; update its docstring and the six call sites' comments (WP01)
T003 Re-run the module: the mismatch test raises `PlacementMismatchError` again with its assertion unchanged (WP01)
T004 Add the seam-distinction regression test (unusable anchor → `TRACKED_META_UNAVAILABLE` skip, nothing written, no raise) (WP01)
T005 Run the neighbouring #6673 suite and ruff/mypy on the module; record results (WP01)

Dependencies: none. Risk: a call site left on the marker shape would silently keep a test on the wrong seam — T002 enumerates all six; T003 proves the mismatch one; T005 proves the rest.

## Parallel opportunities and MVP

One work package, one file: no parallelisation is available or needed. WP01 is the whole MVP.
