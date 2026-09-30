---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T20:21:08Z'
reviewer_agent: claude
wp_id: WP12
---

# WP12 review feedback, cycle 1 (reviewer-renata)

Verdict: **CHANGES REQUESTED**. One blocking defect: a fail-closed violation that the WP's mandated pin test would have caught. Everything else is close to approvable.

## Blocking

### [HIGH-1] src/specify_cli/core/worktree_topology.py:104-118, 197: the coordination-mission repository-root WP gets a claim commit from another branch as its base, not `None`

`_planning_claim_commit(status_feature_dir, wp_id)` is handed the STATUS_STATE read dir. For a coordination-topology mission that dir is the **coordination worktree's** mission dir (`resolve_read_dir_or_degrade(..., STATUS_STATE)` at :172-179). `claim_commit_for_wp` runs `git log -S<id> HEAD` with `cwd=mission_dir`, so `HEAD` is the **coordination branch**, and the claim event *is* committed there. The helper therefore returns that coordination-branch SHA instead of failing closed.

The value then becomes the WP's `base_branch`. `_count_commits_ahead` (:200-201) evaluates it as `claim..HEAD` in the repository root checkout (`workspace.worktree_path`), where the commit is not an ancestor. Before WP12 the result was `None`, because the subject matcher ran in R.

The docstring at :105-111 claims the opposite ("which is not on this checkout's HEAD: the shared authority reports that as unresolved"), and that claim is false.

Reproduced with a scratch probe. R is on `main`, and a linked worktree on branch `coord` commits the claim event. `claim_commit_for_wp(coord/kitty-specs/m, "WP01")` returns the coord SHA; `merge-base --is-ancestor <sha> R.HEAD` is False, and `rev-list --count <sha>..HEAD` in R is 1.

T069's edge case required exactly this pin ("Coordination-topology missions with repository-root planning WPs ... The helper returns `no_commit`, and the path fails closed ... Pin it with one test."). No such test exists: no test file for worktree_topology changed in this WP.

**Required fix:** resolve the claim against the checkout whose HEAD is counted and reported. Two acceptable options:
- run the helper on the PRIMARY `feature_dir`, which is the checkout the base is used in (it then fails closed with `no_claim_event`/`no_commit` for coordination missions);
- or make the owner reject a claim that is not an ancestor of `workspace.worktree_path`'s HEAD.

Do not add a parallel matcher. Fix the docstring. Add the mandated coordination-topology pin: a coordination mission with a repository-root/lane-planning WP whose claim is committed on the coordination branch gives `base_branch is None` and `commits_ahead == 0`. The pin must be red on the current head and green after the fix, as a separate red commit. For comparison, `workflow.py:1648` passes the WORK_PACKAGE_TASK (PRIMARY) dir to `review_context_for_repo_root_workspace`, which runs git in R and is correct.

## Non-blocking (fix in this cycle if cheap, otherwise file)

- [MEDIUM-2] src/runtime/next/prompt_builder.py:334. When `owned` is set and the workspace is a lane workspace (an owned coordination-topology mission, reached via `_lanes_manifest_workspace`, which always has `context=None`), the base falls back to `get_feature_target_branch(repo_root, ...)`. That reads the repository root checkout's meta.json on an owned arm. This is pre-existing, and the spec marks the lane arm "unchanged", but it breaks the "owned arms read `owned.*`" standard. Either use the fact (or the P-read lanes manifest's `mission_branch`) when `owned` is set, or file it for WP18 with a pin.
- [MEDIUM-3] FR-009 (Deviation 3). The FR-009 marker test now pins the project-local mission-type governance tier (`.kittify/doctrine/mission_types/...`). It is a faithful test that `prompt_builder` routes `governance_root = owned.owned_root`, and it is red-then-green. However, the **charter** half of prompt governance still comes from R: `ensure_charter_bundle_fresh` canonicalises to the repository root checkout. So a P-only `charter.md` never reaches an owned prompt. That is a gap against FR-009's "prompt governance from P". Record an operator decision (charter is repo-wide by design) or file a follow-up. Do not leave it implicit.
- [LOW-4] src/mission_runtime/claim_commit.py:43. `_CLAIMED_LANE = "claimed"` is a parallel literal where the canonical `Lane.CLAIMED` exists. It is reachable through the same lazy `specify_cli.status` import, so compare against the enum.
- [LOW-5] tests/runtime/test_bridge_decision_builder.py:261,267. The `"OWNED_REVIEW_BASE_UNAVAILABLE"` literal appears twice. The DoD says codes are imported from `OwnedRefusalCode`, with no `OWNED_*` literal in new tests.
- [LOW-6] The DoD grep `claimed for implementation` still hits `src/specify_cli/cli/commands/implement.py:1677`. That line is a commit-message *writer*, not a matcher, so it is acceptable. Say so in the hand-back so WP18 does not trip on it.

## Verified OK

- Red-first: at 82b42abea (the last commit before the fixes) 7 rows are red for the stated reasons, and the 2 WP19 strict xfails are still xfail. `test_claim_commit.py` fails with ImportError at 192510bb1. The campsite commit 5f537f3e4 precedes the signature change.
- Non-vacuity was checked with mutations:
  - Making the helper ignore ambiguity turns `test_two_commits_introducing_the_claim_fail_closed` and the AS5 `ambiguous` row red.
  - Re-routing `_task_board_dir`'s owned arm through `mission_context_for` turns `test_owned_prompt_reads_no_resolver_and_no_repository_root_walk` red with the forbidden-call assertion.
- Deviation 1 is valid. Every non-owned `ResolvedWorkspace` carries a lane id (`lane-planning` at context.py:908/997). Only the owned kinds have `lane_id=None`, so the lane-less non-owned arm is unreachable through `next`. It is unit-covered in `tests/next/test_prompt_builder_review_base.py`, and the `agent action review` repo_root row is red-then-green.
- Deviation 2 (the `runtime_bridge_cores._blocked_from_step_envelope` `error_code` carry): a one-line change, declared, and red-then-green.
- No subject matcher remains in src. `effective_root` is gone from prompt_builder. `bridging: WP12` returns nothing. 0 `TRANSITIONAL(WP18)` markers were added. No xfail is left in the mission test files. No debug test is tracked. Out-of-map edits are declared. The Co-authored-by trailer is on 4de618cd2.
- mypy --strict --explicit-package-bases: 21 errors at base == 21 at head, with an identical error set. ruff check/format are clean. C901 is at most 15 (`_review_command_lines` = 5).
