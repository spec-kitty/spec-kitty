# Research: Regression-slice test cleanup

## R-01 Where do the verdicts come from?
- **Decision**: the per-file ledgers in issues #5618, #5619, #5620, #5621 and the report in #5622 are the input; they were produced by `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml` on 2026-10-04.
- **Rationale**: the operator brief names them as authoritative; re-deriving would duplicate the review.
- **Alternatives considered**: re-running the static scan (`make test-quality-scan`) — rejected; the ledgers already carry verdicts, and #5621 notes the text-search scan over-selected prose-only files.

## R-02 Does removing `regression` change what CI runs?
- **Decision**: no de-routing risk. Module shards select `not performance and not stress`, so a `regression` test already runs per-PR; unmarking only moves `fast`/`unit` tests into `make test-fast`.
- **Rationale**: verified in `scripts/ci/shard_select.py` and `Makefile` (`FAST_TIER_MARKERS`).
- **Alternatives considered**: none needed. The gates that still bind marker edits are `test_marker_job_completeness.py`, `test_ci_collection_completeness.py` and `test_fast_tier_marker_completeness.py`; run them after the marker edits.

## R-03 How are planted breaks applied safely in lane worktrees?
- **Decision**: edit `src/` inside the lane worktree, run only the named test files, `git checkout -- src/` to revert, confirm `git status --short src/` is empty before any commit.
- **Rationale**: `pytest.ini` sets `pythonpath = src`, so the worktree's own `src/` shadows the editable install for in-process tests. Tests that shell out to `spec-kitty` import from the venv's editable path (the repository root checkout), so they need `PYTHONPATH=<worktree>/src` for the break to reach them.
- **Alternatives considered**: mutation tooling (`mutmut`) — rejected as heavier than needed and not scoped to one behaviour.

## R-04 Root independence (#5622)
- **Decision**: skip under `os.geteuid() == 0` with an explicit reason unless the test's I/O seam can be patched cheaply to raise `PermissionError`; prefer the seam injection where the code under test reads through one call.
- **Rationale**: root bypasses mode bits; CI is non-root, so the skip loses no CI coverage, while seam injection keeps the coverage everywhere.
