---
affected_files: []
cycle_number: 1
mission_slug: lane-cleanup-landing-proof-01M81KHJ
reproduction_command:
reviewed_at: '2026-11-23T22:27:41Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review — cycle 1 (claude::reviewer-renata)

**Verdict: changes requested.** One finding. Everything else holds; see "Verified" below.

## F1 (blocking): old git now refuses a released lane that landed by a real merge

`_landed_on` (`src/specify_cli/workspace/landed_worktrees.py:866`) raises `AbsorptionUnsupported`
before any ancestry check whenever `merge_tree_write_tree_available` is False. On git < 2.38,
a released Mission lane whose tip is an ancestor of `<remote>/<primary>` therefore became
`UNPROVEN / ABSORPTION_UNSUPPORTED`, and the guard's `_absorption_proof` returns False for it.

Before WP02 the same lane was `LANDED` and prunable. Plain `lane_tip.is_absorbed` runs
`merge-base --is-ancestor` first and raises only after that leg fails. The shared predicate
`is_absorbed_but_for_mission_bookkeeping` also returns True on ancestry before it needs merge-tree.
The pre-check is what introduced the regression. A literal T010 (call the predicate) would not
have had it.

Reproduction: take the `landed` fixture from `test_landed_worktrees_mission_bookkeeping.py`, then
`git merge --no-ff -X ours <lane>` into `main`, push, fetch, set `merged_at`, and monkeypatch
`merge_tree_write_tree_available` to False in both `landed_worktrees` and `lane_tip`.
- At af207714 the lane is `landed`.
- At 6364d35a it is `unproven ABSORPTION_UNSUPPORTED`.

The failure is fail-closed (no wrong prune), but it is a behaviour regression this WP adds. A
commit-to-target or merge-strategy landing on an older git loses the prune it had.

**Fix:** in `_landed_on`'s Mission branch, decide ancestry before you gate on merge-tree. Either:
- call the predicate, return True when it holds, and raise `AbsorptionUnsupported` only when it
  is False *and* merge-tree is unavailable; or
- run an explicit `merge-base --is-ancestor` first.

Add a unit test for the ancestor-landed released lane on old git: it is `LANDED`, and
`_absorption_proof(root, slug)` returns True. Keep `test_an_old_git_leaves_a_released_lane_unproven`
for the squash case.

## Verified (no action)

- **Red first.** At af207714 source, 5 of 8 new tests fail.
  - The behavioural tests fail for the right reason: `NOT_LANDED / CONTENT_NOT_ON_PRIMARY` on the
    unit fixture and on the real-CLI acceptance, and prune removed nothing.
  - The other two fail on missing attributes (monkeypatch target and `_lane_mission_slug`). Those
    attributes were introduced with the fix.
- **Slug derivation.**
  - A detached HEAD (no branch) uses the plain proof.
  - A non-lane branch, or a Mission branch without a lane id, uses the plain proof.
  - A Mission directory that is missing or unreadable gives no slug, so the plain proof applies.
  - A legacy slug is matched by exact directory name, so similar slugs cannot cross.
  - Two Mission directories that share a mid8 give no match. I tested this: it is not `LANDED`.
  - The slug passed to the predicate is the matched directory name, so Mission A's lane cannot get
    Mission B's exemptions unless its branch name carries B's mid8.
- **Released status drift.** If the released status changes between assessment and prune, the guard
  falls back to the plain proof, which fails closed.
- **Guard routing.** The guard is unchanged and `_prune_one` still goes through it.
  `test_destructive_op_routing.py` and `test_landed_removal_obligations.py` are green.
- **Scope.** No WP03 content (`LANDING_PROOF_UNAVAILABLE` absent). Only owned files are touched.
  `released_mission_lane` keeps its contract.

## Commands and counts (at 6364d35a)

- `pytest tests/specify_cli/workspace/ tests/doctor/ tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py tests/architectural/test_destructive_op_routing.py tests/specify_cli/git/test_landed_removal_obligations.py tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py -n auto --dist loadfile`: 375 passed, 2 skipped
- `make test-fast`: 3222 passed, 7 skipped
- `ruff check`, `ruff format --check --force-exclude` (3 files) and `mypy src/specify_cli/workspace/landed_worktrees.py`: clean
- Diff coverage against af207714 on `src/specify_cli/{lanes,workspace,doctor}/*`: 96.6%. The one missed line is 509, the no-`mission_id` return.
