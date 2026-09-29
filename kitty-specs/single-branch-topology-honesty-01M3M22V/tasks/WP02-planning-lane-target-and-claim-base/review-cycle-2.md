---
affected_files: []
cycle_number: 2
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-28T17:18:57Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback, cycle 2 (reviewer-renata)

**Verdict: changes requested, for one narrow item.** Every cycle-1 item is resolved, and I verified the fixes independently (see "Verified" below). One test that WP02 added is flaky, and it must be fixed at the root before approval (charter: fix correctness flakes at the root, never retry-to-green).

## Blocking

**Issue 1: `tests/lanes/test_claim_base.py::test_record_reads_head_from_write_checkout_not_repo_root` passes or fails depending on wall-clock timing.**

- **What the test does.** It builds two *independent* repositories (`repo` and `other`) with `_init_repo`. It then calls `record_claim_base(repo, other_checkout, ...)`, which runs `git -C repo update-ref <ref> <other's HEAD SHA>`.
- **Why it only sometimes passes.** `repo`'s object database contains that SHA only when both seed commits hash identically: same tree, same author, same message, and the same commit **timestamp second**. When the two `_init_repo` calls straddle a second boundary, the SHAs differ. `update-ref` then exits 128 (nonexistent object) and the test errors with `CalledProcessError`.
- **Evidence.**
  - It failed once in my parallel targeted run (`-n 4`, 1 failed / 237 passed) and passed on five reruns.
  - I made it fail deterministically by inserting a 1.1 s sleep after each `_init_repo`: `CalledProcessError: git update-ref refs/spec-kitty/wp-base/claim-base-01KZZTEST/WP01 06c66a75… returned non-zero exit status 128`.
- **Required fix.** Make `other_checkout` a real linked worktree of `repo`, which is also the realistic production shape, since refs live in the common dir:
  1. `git -C repo worktree add -b other-branch <tmp>/other`
  2. Make one extra commit there, so its HEAD differs from `repo`'s HEAD.
  3. Assert that the recorded base equals the worktree's HEAD and differs from `repo`'s HEAD.

  Pinning the commit dates would also stabilise it, but the test would still model an impossible shape (a foreign repository), so prefer the worktree.

## Non-blocking (note in the Activity Log; no rework required)

**Nit 2.** The coord-fallback arm's terminal hook (`status_transition.py:577`, inside `_fallback_emit_single._coord`) has no test. I deleted that call and all 52 tests in `test_claim_base.py` and `test_status_transition.py` stayed green.

- Cycle 1 required "at least primary + transactional", so this does not block.
- The implementer's ordering claim holds: this arm clears the ref *after* `_emit_on_coord_then_commit` commits.
- A coord-fallback done/canceled test would close the last untested terminal arm. It can be folded into the WP07 hook extension.

**Nit 3.** In the missing-ref gate test, dropping the `base_sha is not None` guard is an equivalent mutant: git rejects `None..HEAD`, so the gate still refuses. That is acceptable, because the observable contract is pinned: forcing the missing-ref branch to pass is caught (verified below). The guard's safety does depend on no ref literally named `None` existing. Keep the explicit guard.

## Verified (cycle-1 items resolved)

**Mutation spot-checks.** I ran each in a throwaway detached worktree at b7ca4c05, deleting the call or flipping the condition, then restored and removed the worktree. Every one is caught:

| Mutation | Tests that fail |
|---|---|
| M1: `implement_support.py:147` `record_claim_base` removed | `test_create_lane_workspace_records_claim_base_for_planning_wp` |
| M2: `orchestrator_api/commands.py:1373` `record_claim_base` removed | `test_orchestrator_resolve_start_workspace_records_claim_base_for_planning_lane` |
| M3: primary-fallback clear (`:544`) removed | `test_primary_fallback_arm_done_transition_clears_claim_base` |
| M4: transactional clear (`:1612`) removed | the transactional done test and the canceled test (2 fail) |
| M5: gate made to PASS on a missing ref (`base_sha is None or …`) | `test_for_review_gate_refuses_when_claim_base_ref_missing_even_with_qualifying_commit` |
| M6: sparse_checkout planning-lane fix reverted | `test_expected_branch_for_returns_none_for_the_planning_lane` |

**Other checks.**
- Items 1(a) through 1(e) and Issue 2 from cycle 1 are resolved.
- Nits 3, 4 and 5 are addressed with rationale comments.
- Targeted list, re-run: 238 passed (a second run: 1 failed, which was Issue 1 above, and 237 passed).
- `ruff check` and `ruff format --check` on the cycle-2 files are clean.
- `mypy --strict` on the cycle-2 src files shows only pre-existing errors (`status_transition.py:196/795`, `engine.py`).
