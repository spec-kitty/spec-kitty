---
affected_files: []
cycle_number: 1
mission_slug: coord-closeout-leftovers-01M78FRR
reproduction_command:
reviewed_at: '2026-11-12T22:13:38Z'
reviewer_agent: claude-reviewer
wp_id: WP04
---

# WP04 review, cycle 1 (claude-reviewer): changes requested

The core safety property holds: I could not get reclaim to delete a coordination branch whose
commits the recorded landing does not cover. Late commit past the landed ref, missing ref, missing
`merged_at` and a reopened Mission (`is_mission_merged` reads the reopen events) all refuse with the
branch kept. The branch delete is a compare-and-swap on the live tip read before the proof, and the
unique tip is kept under `refs/spec-kitty/discarded/`. Red to green is confirmed: at `b4353cf7`
the run fails with `No such command 'reclaim'`. The gates and suites below are green.

Two findings block approval. Both are small.

## F1 (required): a checkout off the target branch half-reclaims, and the printed remedy cannot succeed

**Reproduction.** Use the fixture from `test_archive_reclaim.py`: `_landed_coord_mission`, then
`archive create`. Then:

```
git -C <repo> checkout -q -b side      # operator is on any branch other than target_branch
spec-kitty archive reclaim <slug>
```

**Observed.** The command exits 1 with `RECLAIM_MARKER_NOT_COMMITTED`, after:

- the coordination worktree has been removed;
- the coordination branch has been deleted (tip kept in `refs/spec-kitty/discarded/...`);
- the landed-coordination ref has been cleared;
- `kitty-specs/<slug>/meta.json` has been flattened as an uncommitted change in the `side` checkout,
  which is the wrong branch (`git status`: ` M kitty-specs/<slug>/meta.json`).

The remedy says `Re-run from the project root to commit it: spec-kitty archive reclaim <slug>`.
Re-running from the project root refuses the same way, again and again. This breaks SC-003: a
followed remedy must reach exit 0 or a different named state. If the operator later runs
`git commit -a` on `side`, the flatten lands on the wrong branch.

**Cause.** `commit_merge_bookkeeping` goes through `safe_commit`, which requires the repository
root checkout's HEAD to be the placement destination (`target_branch`). Nothing checks this
before steps 3 to 5 mutate anything.

**Fix.** Before the first mutation, check that the commit destination can be written. That means
the repository root checkout is on the Mission's resolved PRIMARY destination (the same
resolution `commit_merge_bookkeeping` / `safe_commit` uses; do not add a new placement path).
When it is not, refuse with nothing changed. Use a named code (a new one, or reuse
`RECLAIM_MARKER_NOT_COMMITTED` with a precondition message), and give a remedy that names the
branch to check out: `git checkout <target_branch>`, then re-run.

Also correct the `RECLAIM_MARKER_NOT_COMMITTED` remedy for the post-mutation case. It should say
what actually unblocks the commit, not only "re-run from the project root".

Add a CLI cell (or a service cell) for the off-target checkout that asserts the triple and the
`meta.json` bytes are unchanged.

## F2 (required): the reported keep-record ref can be wrong

**Reproduction.** Use the same fixture, plus one extra step before reclaiming:
`git update-ref refs/spec-kitty/discarded/<coord branch> <target tip>`. This is a stale earlier
discard record, for example from a previous `mission close --discard` of a branch with the same
name. Then run reclaim.

**Observed.** Reclaim prints:

```
deleted: <branch> (tip kept as refs/spec-kitty/discarded/<branch>)
```

The guard actually wrote `refs/spec-kitty/discarded/<branch>@<short-sha>`. The plain ref the
output names points at an unrelated commit (the target tip in my probe). An operator who restores
from the printed ref restores the wrong commit.

**Fix.** `_delete_branch` hard-codes the ref name. Name it through the guard's own authority,
`destructive_guard.discarded_ref(repo_root, branch, kept_tip)`, or have the guard return the ref.
Pin the `@<sha>` case in a test.

## Non-blocking (record, or fold if cheap)

- **N1.** When the coordination worktree is already gone, `_remove_worktree` skips
  `teardown_coordination_topology`. That also skips its `COORDINATION_LEDGER_UNREPAIRED` guard,
  which protects the *branch* when it holds the only copy of the decisions ledger. In that
  partial state, the branch is then deleted without that check. The keep-record keeps the tip
  reachable, and a legacy Mission would normally refuse anyway for lack of a landed ref, so the
  risk is low. Still, the guard should not depend on step order. Consider running the ledger
  check (or the seam) whenever the branch is about to be deleted.
- **N2.** Exceptions from `flatten_coordination_metadata` (for example a Mission write-lock
  timeout) are not rendered as a named refusal; they surface as a traceback after the branch is
  gone. A re-run finishes the work, so this is cosmetic.
- **N3.** The dirty-worktree CLI cell asserts exit 1 and the kept triple, but not the error code
  (`COORDINATION_WORKTREE_KEPT_ONLY_COPY` / the seam's code). Add the assertion.

## Verified (no action)

- Exactly one new `_OPERATOR_INTENT_CALLERS` entry (`archive_reclaim.py::_delete_branch`).
  `_archive.py` is untouched. The dead-symbol allowlist only shrank (`is_mission_archived`
  removed, nothing added).
- `archive reclaim` is classified in `ADOPTED`.
- The `landed_coordination.__all__` addition was pre-agreed with WP02 (approach.md).
- ruff, ruff format `--force-exclude` and mypy are clean on the changed files; C901 is at or under
  15 everywhere.
- Every commit carries its trailers. Mission terminology is used throughout; there is no `--feature`.
- The help text has an example.
- The two extra codes are justified: `RECLAIM_WORKTREE_KEPT` is a seam no-op the operator must
  see, and `RECLAIM_MARKER_NOT_COMMITTED` reports a partial state after mutation. Add both to
  `contracts/cli-refusals.md` (WP07 or here).

## Tests run (reviewer)

- WP04 suites (`test_archive_reclaim.py`, `test_archive_reclaim_service.py`,
  `test_mission_archiving.py`, `test_archive_locked_append.py`): 55 passed.
- Gates (`test_destructive_op_routing`, `test_json_contract_enumeration`,
  `test_no_worktree_name_guess`, `test_git_path_listing_owner`, `test_no_dead_symbols`,
  `test_layer_rules`, `test_no_read_side_bypass`, `test_single_mission_surface_resolver`,
  `tests/coordination/test_flatten_primitive_single_source.py`): 408 passed.
- Red at `b4353cf7`: 1 failed, `No such command 'reclaim'`.
- The reviewer probes for F1, F2 and the late-commit refusal ran in a scratch worktree and were
  not committed.
