---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T16:38:31Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP07
---

# WP07 review cycle 1 (lane-g 68dccc137e): REJECT

Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

No integrity hole was found. Three LOW findings are folded in below.

## Binding DoD item (INCORPORATE_MERGE_ATTRIBUTES_REFUSED): PASS

- **Guard paths** are changed(base,HEAD) ∪ changed(base,stamp). An unreadable base refuses.
- **Placement:** the guard runs in the lane checkout before run_committing_op. The merge runs under merge_probe_env, and the window-merge probe gets attributes_source.
- **Red-first:** the union test was red at the base.
- **Real-git probes**, each refused with HEAD unchanged:
  - info/attributes filter plus renormalize
  - registered driver on *.py
  - untracked src/.gitattributes union
  - custom driver
  - merge.default=union
- **Residuals for WP13 (no change needed):**
  - The attribute source is the Mission branch tip rather than the pre-run target tip.
  - A Mission-branch move between the read and the merge only affects honouring an already-reviewed union.

## #7861 refusal removal: sound

- The flag is set only when a -coord worktree exists on a protected target. lanes, single_branch and --commit-to-target leave it false.
- **Probes:**
  - detached -coord: exit 1, target unchanged, no review-cycle written
  - -coord on another branch: exit 1
  - deleted coordination branch: exit 1
  - no coordination surface: _protected_branch_status_commit_error fires first
- **WP13 ADR:** record the T050 reversal. Rationale: REVIEW_CYCLE is a COORD-partition kind, and the path with no coordination surface still fails closed.

## Also verified

- Reuses main's SiblingLane / refine_stale_result.
- --agent appears on every implement line. No git merge, no cd .worktrees.
- T036 runs each printed line.
- FR-009 writes lane_rebase_moves only for the exact shape, never WP02's durable ref. A halted auto-rebase merge is therefore rolled back, never exempted.
- The test-leeway edits are justified.

## Must fix (LOW)

1. **Durability matrix pins coord_protected evidence on main** (tests/integration/test_review_durability_matrix.py:600-602).
   - Problem: `_assert_exact_blob_at_ref(repo, "main", evidence_ref)` runs for the coord_protected cells too. Their fixture has no real coordination branch, so a regression that sends REVIEW_CYCLE to protected main would pass.
   - Fix, either:
     - (a) a real coordination topology for those cells, asserting the blob on the coordination branch and main unchanged; or
     - (b) assert the destination only for single_branch, and state in the docstring that coord_protected placement is pinned by test_main_reopen_line_runs_on_a_protected_coordination_target and T036.
2. **Weak negative assertion in the renamed T050** (test_move_task_durability.py). `assert signal.skip_reason != _DURABILITY_REASON_PROTECTED_TARGET_BRANCH` appears twice. Assert the concrete outcome instead: the refusing router's typed non-durable reason, or durable with destination_ref.
3. **Dead constant.** `_DURABILITY_REASON_PROTECTED_TARGET_BRANCH` (tasks_verdict_persistence.py:116) and its text-map entry (:548) have no producer left. Remove both, or keep them with a comment naming the remaining producer.

## Evidence

- Red-first: 29 failed / 166 passed / 2 skipped.
- Post-fix: 195 passed / 2 skipped.
- Blast radius: 8334 passed / 26 skipped / 3 xfailed.
- Terminus subset: 32 passed.
- 8 arch gates: 326 passed.
- no_dead_symbols: 37 passed.
- ruff, C901, format, mypy: clean.
