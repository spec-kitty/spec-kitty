# WP04 review feedback (cycle 1) — reviewer-renata

The production wiring is correct and the red-first evidence holds: the regression file run
against the pre-fix src (26761b3a) is 9 red (each for the right reason: 4 land at exit 0, the
lanes arms refuse with PROTECTED_BRANCH_REFUSED / TARGET_BRANCH_NOT_SYNCHRONIZED instead of
ORIGIN_STATUS_STALE, `--origin-check` is unknown, `--resume` hits the pre-fix-state refusal)
and 3 controls green; at 032b1ec5 all 86 targeted tests pass, ruff/format clean, the 7 mypy
errors on the touched files all exist at 26761b3a; `tests/terminus/ -k "not slow"` is 190 passed, 10 deselected. The rejection is about two binding
Definition-of-Done items that no test pins.

## 1. [HIGH] Placement "before `_resolve_run_status_dir`" is not pinned (DoD item 2)

Mutation run: swapping the two lines in `src/specify_cli/consolidation/executor.py:705-706`
(`check_origin_before_status_dir` AFTER `feature_dir = _resolve_run_status_dir(seam)`) leaves
`tests/terminus/test_consolidate_sees_teammate_rejection.py` + `tests/consolidation/test_origin_gate.py`
fully green (31 passed). The DoD says "Refusal happens before `_resolve_run_status_dir` ...; no
branch, worktree or remote moved on refusal" — nothing fails if that ordering regresses.

A real-CLI arm that pins it (verified by the reviewer in a scratch copy: green at 032b1ec5,
RED under the swap mutation): on the `coord` fixture, B pushes the WP02 rejection on the
coordination branch, A removes its coordination worktree
(`git worktree remove --force <CoordinationWorkspace.worktree_path(...)>`, local branch kept),
then A runs `consolidate --mission <m>`; assert `ORIGIN_STATUS_STALE` in the output, refs
unchanged, AND the coordination worktree path still does not exist (under the mutation
`_resolve_run_status_dir` materializes it before the refusal). Add it to the regression file.

## 2. [MEDIUM] Coordination `local_missing` pass-through is tested only through stubs (binding fold "test it")

`test_coordination_evidence_only_on_the_remote_passes_through` stubs `_routes_through_coordination`
and the freshness check, so it cannot detect a wiring/topology-read regression on the
production path (acceptance-criteria-non-vacuity: exercise the production entry point). Add a
real-CLI arm on the same `coord` fixture: A removes its coordination worktree, deletes its
local coordination branch and `refs/remotes/origin/<coord>`; `consolidate --mission <m>` must
exit non-zero with NO `ORIGIN_` code and the existing COORDINATION_WORKTREE_UNMATERIALIZED
remedy ("Create the local coordination branch from its remote" / "unmaterialized"), refs
unchanged. (Reviewer-verified green at 032b1ec5; it goes red if `_evidence_for_gate` stops
passing the verdict through.) Pair it with a lanes-topology positive control already present
(arm 3) or the unit test `test_non_coordination_evidence_missing_locally_refuses`.

## Non-blocking notes (no change required in this WP; record for WP08 / follow-up)

- [MEDIUM] `src/specify_cli/git/origin_freshness.py::_status_remedy` (WP03 text, reached via this
  gate): when no checkout holds the evidence branch (e.g. coordination worktree removed),
  the remedy prints `git pull origin <coordination-branch>` with no `-C`, i.e. run in the
  repository root checkout it merges the coordination branch into whatever is checked out
  there (normally `main`). Prefer `git fetch origin <b>:<b>` (fast-forward the local branch)
  when `evidence_checkout is None`. Observed in the reviewer's probe output.
- [LOW] Arm 10 asserts the abort line is present, not that the remedy STARTS with it
  (fold wording); the rendering unit test has the same shape. Consider asserting order.
- [LOW] Arm 5 asserts only `"WP02" in out`; the WP prompt names "missing review approval: WP02".
  A tighter substring would make the control less permissive.
