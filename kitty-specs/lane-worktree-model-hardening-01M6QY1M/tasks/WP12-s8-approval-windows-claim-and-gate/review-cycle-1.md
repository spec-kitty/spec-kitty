---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T15:40:13Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP12
---

# WP12 review, cycle 1 (reviewer-renata): changes requested

## Blocking

1. **The dead-symbol gate is red for three new symbols.** `tests/architectural/test_no_dead_symbols.py`, run serially on the lane, fails `test_no_public_symbol_in_all_is_unimported` with:
   - `specify_cli.consolidation.write_branch_bound::ApprovalWindow`
   - `specify_cli.consolidation.write_branch_bound::approval_windows`
   - `specify_cli.consolidation.write_branch_bound::commits_outside_windows`

   No src/ module imports any of them. `commits_outside_windows` is called only by tests, so it is test-only code. Fix:
   - Remove `ApprovalWindow` and `approval_windows` from `__all__`. They stay as module internals that `check_write_branch` uses.
   - Delete `commits_outside_windows`, or make it private, and rewrite its two unit tests (`test_missing_open_stamp_degrades...` and `test_stamped_open_excludes...`) to go through `check_write_branch`.

   Do not add allowlist entries. The fourth symbol the gate lists, `approved_bound::stamp_refusal`, is WP11's and is already red on the lane base (identical on ce8c06e4a4), so it is not WP12's. The WP prompt does say "tier 1 via WP11's stamp_refusal", though, so importing it in `write_branch_bound` would legitimately clear that red as well. Optional.

## Non-blocking (please fold in while you are there)

2. **ADR residual text, missing `O_k`.** The amendment says the degrade "is not a new refusal". The degrade also hides a commit. I reproduced it: WP01 is claimed with a stamp and approved, commit X follows, then WP02 is claimed WITHOUT a stamp and approved. `check_write_branch` returns `()`, so X, which sits between the two approvals, passes. The residual should say that a missing `O_k` covers every commit before `S_k`, including a commit between the preceding approval and that WP's claim. It should also say that the degrade is logged only at INFO.
3. **ADR residual text, rebase plus re-approval.** After a rebase, the old `O_k` is no longer on the branch. `reach(O_k)` then holds only pre-rebase SHAs, so the window widens to `(claim_base, S_k]`, the same as a missing `O_k`. Tier 1 still forces re-approval or attestation first, which is a recorded operator act. Name it next to the missing-`O_k` residual. The same applies to an attestation when the claim is unstamped: the attestation stamp is the tip at that moment, so the attested window covers the whole branch before it.
4. **NFR-007, refusal path.** `_preceding_wp` runs one `git rev-list` for each refused commit. The pass path is batched and measured, but a branch with many out-of-window commits costs O(n) subprocesses. Acceptable on a refusal path. Note it, or reuse the `reach` sets you already have.
5. **orchestrator-api call.** The new `_refuse_post_approval_lane_content` call in the planning-only path also runs for a `lanes` planning-only Mission. There it is a no-op, but it now reads the status log and resolves the target, and either can raise. That is harmless and fail-closed. Mention it in the PR as part of the out-of-map justification.
