---
affected_files: []
cycle_number: 2
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T11:38:32Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review cycle 2 — changes requested (reviewer-renata)

Cycle-1 items 1–3 are all resolved:
- The remedy line is pinned in the primary-arm and aggregation tests.
- The worktree arm asserts the worktree path and the remedy, with `COLUMNS=400`.
- The regression marker is removed.

The executor fix (78a4c385) behaves correctly. I probed `_report_pre_mutation_refusal` directly against real git repos:
- Pure behind-own-HEAD lag with a persisted `base_sha`: the reset guidance IS printed.
- The same lag with `base_sha=None` (a fresh consolidation): NOT printed.
- The lag plus a genuine user edit, with `base_sha`: NOT printed.

The edit is confined to `_report_pre_mutation_refusal` and its two call sites in `_pre_mutation_safety_preflight_with_recovery`. No other part of executor.py was reformatted, and the whole-file format drift and the 4 mypy errors also exist on base. 106 tests pass across the WP04 tests, test_behind_head_recovery_coverage, test_behind_head_remedy, test_repro_4997, test_resume_phantom_only and the ratchet/destructive-op-routing gates.

**Issue 1 — the new positive branch of `_report_pre_mutation_refusal` has no test** (`src/specify_cli/consolidation/executor.py`, `proven_behind_head = ... and is_pure_behind_head_lag(main_repo, base_sha=base_sha)`).

Only the negative branch is exercised: the #4933 CLI test asserts that "reset --hard HEAD" is absent. Nothing asserts that a proven pure lag still gets the #4982 reset-to-HEAD guidance. `test_behind_head_recovery_coverage.py` mocks `_report_pre_mutation_refusal` out, and test_repro_4997 / test_resume_phantom_only take the auto-recovery path, not this printer. If someone over-gated this branch, for example by dropping `base_sha` at a call site so every call passes `None`, the #4982 guidance would disappear silently with every test still green. The charter requires tests for every new branch, and the diff-cover ≥90% gate applies.

Add a focused real-git test, e.g. in `tests/consolidation/test_behind_head_remedy.py` or the WP04 test file. Build the repo like this:
- commit A on `main`
- a lane branch with commit B (adds `f.txt`)
- `git update-ref refs/heads/main B` while the checkout stays at A's tree (a pure lag)

Then call `_report_pre_mutation_refusal(exc, repo, mission_branch=<lane>, base_sha=A)` with a `MERGE_UNSAFE_PRIMARY_DIRTY` `DestructiveOpRefused` and assert:
- (a) with `base_sha=A`, the output contains "reset --hard HEAD";
- (b) with `base_sha=None`, it does not;
- (c) after an extra user edit to a tracked file (lag plus genuine edit), with `base_sha=A`, it does not.

Also add one assertion that the call sites thread the persisted sha: with a saved `ConsolidationState` carrying `pre_mutation_target_sha`, the mocked `_report_pre_mutation_refusal` in `test_behind_head_recovery_coverage.py` receives `base_sha=<that sha>`, not `None`.

Non-blocking residual, to record in the PR description rather than fix here: when the checkout genuinely lags its own HEAD AND also holds a user edit, the refusal now shows only the generic "Commit, stash, or revert". The #4982 "Do NOT stage or record these changes" warning is gone in that case. That is strictly safer than advising `reset --hard` over a user edit, but the case deserves its own guidance (stash the genuine edit, then reset) as a follow-up issue.
