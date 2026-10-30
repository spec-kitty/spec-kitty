# Bounded reproduction and validation

Audience: software-engineer. Updated: 2026-10-30.

Work in temporary fixtures only; never damage this checkout's own charter state.

1. Reproduce on the current tree: create a temporary repo root with
   `.kittify/charter/` and `.kittify/charter-packs/`, then call
   `StagingDir.create(root, run_id)` followed by `commit_to_failed("...")` six
   times with distinct run ids. Baseline leaves six `.staging/*.failed/`
   directories (recorded in [research.md](research.md)).
2. Write the failing-first tests before the production change:
   `tests/charter/synthesizer/test_staging_retention_6723.py` covering
   (a) six refusals leave 3, (b) the newest is present with its `cause.yaml`
   reason, (c) an overflowing pre-existing tree is reduced, (d) a live
   non-`.failed` staging directory with content survives byte-identical,
   (e) equal mtimes resolve deterministically, (f) a removal failure does not
   raise and leaves the directory in place, (g) the real CLI refusal names a
   directory that still exists. Run it and commit the red state.
3. Implement the retention in `src/charter/activation/synthesizer/staging.py`:
   a module constant `DEFAULT_KEEP_FAILED_RUNS = 3` and a helper that lists
   `.staging/`, filters `*.failed`, orders newest-first by mtime with a name
   tiebreak, removes the surplus through `PathGuard.rmtree`, and never removes
   the preserved run. Call it at the end of `commit_to_failed`.
4. Re-run the new tests plus `tests/charter/synthesizer/` (owning subsystem
   directory) and the CLI files that exercise the refusal text. Then
   `make test-fast`.
5. Quality and docs: `uv run --frozen ruff check`, `ruff format --check` on the
   changed files, `uv run --frozen mypy` on the changed module,
   `tests/architectural/test_no_legacy_terminology.py`, and the docs freshness
   check if the ADR inventory changes. Add the `[Unreleased]` changelog entry.
6. Independent review of the integrated diff: the reviewer reads the actual
   red→green commits and the complete diff; findings are fixed in this PR.
7. Draft PR to `main` with the five-section body, `taken-by-human`, follow CI on
   the head SHA to green, flip to ready for review, add `ready-for-squad`.
   Never merge, never arm auto-merge, never push `main`.
