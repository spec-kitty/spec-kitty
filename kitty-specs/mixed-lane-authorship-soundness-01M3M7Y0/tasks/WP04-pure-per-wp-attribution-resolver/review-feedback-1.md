# WP04 review feedback — cycle 1 (reviewer-renata)

Verdict: **changes requested**. Tooling is green (54/54 WP tests; arch gates 167 passed, the only failure is the expected
dead-symbol flag on the 6 `wp_attribution` exports that WP05 will consume; ruff/format/C901/mypy clean, no suppressions).
The window, stamp (R8), merge (R3), R1 pre-state and probe logic are correct. One soundness hole blocks approval.

**Issue 1 (HIGH — fail-open, violates C3 "missing → REFUSE" and SC-007/R1)**: `_resolve_wp_windows(..., strict=False)`
silently skips a *sibling* window that cannot be resolved (no stamp, open window, stamp not an ancestor of the lane tip,
unreadable). Contract C1 says a missing stamp is a *legal* state (best-effort stamping), so this is reachable. When the
skipped sibling window overlaps the canceled WP's window, the sibling's commits are attributed to the canceled WP with
no contest, and that can make a real canceled change disappear.

Reproduced with real git (scratch test): WP01 (survivor) claims with no stamp, WP02 (canceled) claims at the fork point,
WP01 commits `y.py` v0→v1 (approved), WP02 commits `y.py` v1→v0, WP02 canceled (stamped). Result:
`Attributed(commits={S, X}, canceled_content=frozenset())`. The survivor commit S is in C, the oldest canceled touch
becomes S, pre_state = v0 == canceled_state, so the path is dropped as a "self-revert". The canceled WP undid the approved
work, and that undo ships silently. Correct outcome: REFUSE.

Fix: a sibling window that cannot be resolved must not be treated as "no overlap". Return `Unattributable` when a lane
sibling that entered a window has any unresolvable window. Use its own reason, or `contested_commit`. The detail must
name the sibling WP and the lane (NFR-003). You may narrow this only if you can *prove* the unresolved window cannot
overlap the canceled WP's windows. Remove the "fail-OPEN toward the sibling" wording in the docstring. Add a
red-first test for the scenario above (sibling missing its open stamp) and one for a sibling with a
rewritten-history stamp.

**Issue 2 (LOW — test non-vacuity)**: `test_merge_commit_inside_window_is_not_attributed_and_does_not_supersede`
merges an unrelated path cleanly, so the merge never lists `merge_target.py`. If you delete the merge filter in
`_canceled_content_walk`, the test still passes. Add a conflict-resolved lane-sync merge that *does* list the canceled
path in `git show --name-only`. Assert that the canceled state is still read at the canceled commit. I checked that the
current code handles this correctly; the case just needs a test that pins it.

**Issue 3 (LOW — pin append order)**: no test shows that events are consumed in append order and never sorted by
`at`. Add a `_windows` test whose `at` values run backwards relative to append order.

**Issue 4 (LOW — spec drift)**: `_entered_implementation` uses `_IMPLEMENTATION_LANES`, which includes `blocked`. Its
docstring, T016 and plan D-3 step 2 define "entered implementation" as a transition into `claimed`/`in_progress`. A WP
that went planned→blocked→canceled is therefore treated as entered. Use `{claimed, in_progress}` for this predicate.
`blocked` still counts inside windows (R6). Add a test.

**Issue 5 (NIT — document)**: `pre_state_by_survivor` counts *any* non-merge spine commit that is not in C. That
includes commits in no WP window and commits from another canceled WP. Keep it, since it is the safe direction for WP05
(it FAILs). Say so in the docstring of `CanceledPathState`.

Verified OK (no action): fork-point stamp validity (R8); rewritten-history → invalid; claimed+in_progress share a
window; rework opens a new window; `(open, close]` ∩ spine, non-merge only; `GitProbeError` → `spine_unreadable` via
the direct `first_parent_commits_in_range` (not the tolerant helper); single newest→oldest walk; R1 pre-state at the
first parent of the oldest canceled touch, including the first lane commit (pre-state at the fork point); delete then
re-add, and net-zero restore dropped; `path_state_at` absent → None, bad sha or unknown ref → raises; `is_merge_commit`
root → False; `--no-renames` on `changed_paths_of`; facade-only status imports; complexity ≤ 15.
