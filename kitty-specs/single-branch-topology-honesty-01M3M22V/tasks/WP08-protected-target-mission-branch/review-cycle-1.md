---
affected_files: []
cycle_number: 1
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-29T08:48:59Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The mint, the protection query, the write-target arm and the consolidation hunks are correct and minimal (see "Verified"). Four test-honesty and coverage gaps block approval.

## Blocking

**Issue 1: the `context/resolver.py` `authoritative_ref` edit is untested.**

- **Mutation W2.** I changed `target_branch=authoritative_target` to `target_branch=target_branch` in `resolve_context` (`src/specify_cli/context/resolver.py:~281`) and ran the four WP08 files plus the #5100 integration file: **33 passed**.
- **Required fix.** Add a test of `resolve_context(...)` for a single_branch mission whose `meta.mission_branch` is set. It must assert that `authoritative_ref == mission_branch` and that `context.target_branch` stays the real target. Add the unprotected control, where `authoritative_ref == target_branch`. W2 must go red.

**Issue 2: `test_status_transition_commits_to_mission_branch_no_head_mismatch` passes for the wrong reason.**

- **Mutation W1.** I forced `_resolve_single_branch_write_ref` to return `target_branch`. This test **stayed green**. The mutation was caught only by `test_implement_wrong_branch_refused_naming_mission_branch` and the #5100 `test_protected_target_mints_mission_branch`, both via finalize's `PROTECTED_BRANCH_REFUSED`.
- **Why it is vacuous.**
  - It calls the flat `status.emit.emit_status_transition`. For a coord-less topology that is the uncommitted plain door (C-008), so it never commits.
  - Its assertion (`"WP01" in subject or "status" in subject.lower()`) is satisfied by whatever commit already sits on the minted branch.
- **Required fix.**
  - Drive the committing path: `coordination.status_transition.emit_status_transition_transactional`, or `agent status emit` / `move-task` through CliRunner.
  - Assert that the **new** commit (the tip SHA changed) is on `mission_branch` and carries this transition's event, that `main` did not move, and that no `SafeCommitHeadMismatch` was raised.
  - W1 must turn this test red.

**Issue 3: the recovery/doctor classification test that the brief required is missing.**

- **What the brief asked for** (T036 Risks: "Add explicit tests for recovery and doctor"). A minted `kitty/mission-<slug>-<mid8>` single_branch `mission_branch` must not be classified as a lane, a coordination branch or an orphan by:
  - `lanes/recovery.py` (`_list_mission_branches` globs `kitty/mission-{slug}*`, then `parse_lane_id_from_branch`);
  - the doctor/workspace scans.
- **Status.** The code likely handles it: `parse_lane_id_from_branch` needs a `-lane-<id>` suffix. But nothing pins that.
- **Required fix.** Add a test on a real repo with a minted mission branch:
  - `scan_recovery_state` (or the relevant recovery entry point) yields no recovery state for it;
  - the doctor topology or orphan scan reports no orphan or coord finding for it.

**Issue 4: the consolidate path is not exercised end to end, and the retention test is tautological.**

- **Manual sequencing, not the executor.** `tests/specify_cli/consolidation/test_single_branch_mission_to_target.py` calls `_phase_mission_to_target`, `_switch_write_checkout_after_single_branch_landing` and `_delete_mission_branch` by hand. It never runs the executor's own ordering (`_run_lane_based_consolidation_locked`), and never runs the reconciliation gate with the new `sb_window` authorship source. A real protected single_branch consolidate goes through the fail-closed squash blob-attribution gate. If `authorship_window` / `_collect_authored` were wrong, every protected consolidate would CAS-revert, and no test would notice.
- **The retention test decides the outcome itself.** It runs `ex._delete_mission_branch(run) if run.delete_branch else None`, so it cannot fail for any product reason.
- **Required fix.** Add one end-to-end consolidate test: `spec-kitty consolidate` via CliRunner, or `_run_lane_based_consolidation` on a real repo. Build the protected single_branch mission by create, finalize, implement WP01, commit, approve. Assert:
  - `main` contains the work;
  - the reconciliation gate passed;
  - the checkout is on `main`;
  - the mission branch is deleted;
  - with `--keep-branch` / `retain_branches: true`, the mission branch is retained.

  Replace the tautological retention assertion with one of these.

## Non-blocking

**Nit 5: red-first.**
- Assertion-level reds, as required:
  - mint + checkout (`'main' == kitty/mission-…`);
  - existing branch refused (`DID NOT RAISE`);
  - US3.2 wrong-branch (`PROTECTED_BRANCH_REFUSED` assertion);
  - status transition (mint precondition assertion).
- Acceptable for brand-new symbols: the `ImportError` / `TypeError` reds on `read_commit_to_target`, `CommitToTargetMetaError`, `expected_write_branch` and the new `commit_to_target=` kwarg, and on `is_protected_target`.
- Not acceptable: the three consolidation behaviour tests are red only on `AttributeError` (a new private helper). The end-to-end test from Issue 4 fixes that.

**Nit 6.** `authorship_window` returns `None` when the fork point is unresolvable. `_collect_authored` then silently falls back to `(coord_base_ref, _lane_branch_for(lane-planning))`, and `_lane_branch_for` for the planning lane is the target branch. Confirm that this still refuses (fail-closed) rather than attributing against the target. Otherwise raise explicitly.

## Verified

- **Hunk sizes.** `executor.py` is +9 (one call plus a 6-line helper). `reconciliation.py` is +17/−6. `git_probes.py` is untouched. The logic lives in `lanes/single_branch_landing.py`. The diffs of `executor.py`, `paths.py`, `protection_policy.py`, `resolver.py` and `git_probes.py` carry no unrelated reformatting.
- **Protection and naming.**
  - The protection query is `ProtectionPolicy.is_protected_target(branch, primary_branch=...)`: primary plus configured, with the operator hatch honoured.
  - The mint uses the existing `mission_branch_name(...)`; there is no second composer.
  - Dirty-checkout refusal and `MISSION_BRANCH_EXISTS` both run before any mission file is committed.
  - `read_commit_to_target` fails closed on a non-bool.
- **#5100 xfails flipped.** `test_protected_target_mints_mission_branch` and `test_commit_to_target_overrides` pass for the right reason.
- **Tests.** 209 passed (`-m "not timing"`, empty `GIT_CONFIG_GLOBAL`) across:
  - the WP08 files (create/mint, protection, consolidate);
  - the #5100 integration file;
  - `test_protection_policy`, `test_commit_router`, `test_owned_single_branch_ssot`, `test_status_transition`;
  - the retention files (`test_mission_create_retention`, `consolidation/test_retention`, `core/test_retention_resolver`);
  - `context/test_resolver`, and the WP05 single_branch lane tests.
- **Gates.** `test_layer_rules` 74, `test_no_dead_symbols` 34, `test_mission_runtime_surface` 7.
- ruff is clean.
