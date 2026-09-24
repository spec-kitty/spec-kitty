# Contract — Terminus Reconciliation Gate

The invariant contract every terminus command must satisfy. Expressed as pre/post-conditions the
Tier-0 property test asserts.

## `MergeOutcomeVerifier.verify(target_ref, approved_wp_set) -> VerifyResult`

**Preconditions**
- `target_ref` resolves to a commit.
- `approved_wp_set` is derived **fail-closed and non-vacuously**, once per transaction:
  - approved commit SHAs come from **lane-branch git tips**, never from status rows/derived
    envelopes (forbids the vacuous `_assert_merged_wps_done_on_target` pattern);
  - WP membership (which WPs are approved / canceled) is read through the **Lamport** reduction
    wrapper (`status/reducer.py:371` `materialize`/`reduce_shared_state`), never LWW `reduce_parsed`
    — an in-`specify_cli` routing choice that does not touch `spec_kitty_events` (C-002 preserved);
  - if the coord surface is unresolved/unmaterialized, or the derived claim is empty while the
    manifest lists WPs, `verify` refuses (fail-closed) rather than passing vacuously.

**Postconditions / guarantees**
1. Returns `PASS` iff, for the tree at `target_ref`:
   - every approved WP's approved commit shas are reachable from `target_ref`, AND
   - no excluded (canceled/removed) commit is reachable — matched by **patch-id equivalence**, not
     SHA alone, so cherry-picked / rebased / re-lettered copies of canceled code are caught.
2. Returns `FAIL(divergence)` otherwise, naming the specific divergence (missing approved shas
   and/or present excluded patch-ids). `FAIL` never mutates anything.
3. The excluded-commit check is **non-vacuous even when the canceled set is empty** — the test
   suite plants a canceled commit to prove the check fires (no silent no-op).
4. Complexity is O(#approved-WP-commits), not O(repo history).

## Terminus entry points the gate must cover (NFR-005 allowlist)
The non-vacuous call-site gate enumerates **all six** terminus paths and a self-mutation test proves
a seventh, unrouted path fails the gate: `merge`, `merge --resume`, `merge --abort`, `upgrade`,
`agent issue-verdict`, `doctor coordination --fix`.

## Terminus command contract (wraps the verifier)

**Invariant (the epic)**: after the command returns, *if* exit code is 0 *then* `verify(...) == PASS`
held before any teardown ran. Contrapositive: `verify == FAIL` ⇒ non-zero exit, no teardown, no
ref/worktree mutation beyond what already landed, and a recovery instruction printed.

**Ordering guarantee**: teardown (branch `-D`, worktree remove) executes only after `verify == PASS`.

**Legacy guarantee (FR-012)**: if pre-fix in-flight state is detected, the command refuses with a
recovery instruction rather than proceeding under the new gate against unknown-shape state.

## CAS advance contract (`advance_branch_ref`)
- `advance(ref, new_sha, expected_old_sha)` performs `git update-ref ref new_sha expected_old_sha`.
- If the ref's value ≠ `expected_old_sha` at write time, the advance **fails closed** (raises); it
  never falls back to a 2-arg write and never retries silently.

## Surface write contract (`SurfaceAuthority.resolve_for_write`)
- Returns the authoritative coord directory only when the coord worktree/branch is resolved and
  materialized; otherwise returns a refusal. A terminus WRITE never degrades to the primary dir.

## Property test (Tier-0)
> For any terminus command invocation that exits 0, `verify(target, approved_wp_set) == PASS`.

- Drives the **real CLI entry point** — `_run_git`/subprocess is NOT mocked, so the test exercises
  `ref_advance.py:410`'s 2-arg→3-arg CAS for real.
- Must be RED against pre-fix behavior for the in-scope children (#4945, #4969, #4977, #4981, #4982,
  #4991, #4996, #4997) and GREEN after.
- #4990 is out of scope for the reducer fix; the gate's success message is scoped to
  **"approved-WP commit reachability"** (not verdict integrity), and #4990 stays named-open in the
  docs (FR-013), so a green run is not mistaken for verdict-integrity the mission does not claim.
  Because the claim is Lamport-sourced (see Preconditions), a wall-clock-later approval cannot
  green-wash a committed rejection *in the gate's own claim*.
