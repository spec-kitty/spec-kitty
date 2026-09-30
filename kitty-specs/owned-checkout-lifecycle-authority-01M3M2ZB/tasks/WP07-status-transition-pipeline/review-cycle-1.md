---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T01:53:53Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 1: CHANGES REQUESTED

Reviewer: reviewer-renata. Commits reviewed: d79da407d..235e0e521. Base: 55610f516.

## Blocking

**1. [HIGH] tests/status/test_transition_request_owned.py:601: the move-task ratchet is vacuous.**
- The test asserts `len(claim_counter) >= 1`.
- I measured the count with the same fixture: 5 on the base 55610f516 and 5 on the head 235e0e521.
- Fix: pin the count exactly with `assert len(claim_counter) == 5`. Add a comment saying that WP16 (tasks_move_task.py / tasks_mark_status.py converting to `owned=`) must tighten it to `== 1`, and that any other drift is a regression.
- Update the docstring and the Activity Log with the base count, which is 5.

**2. [HIGH] T036 has no tests.**
- Commit 2ebac258e adds `MissionHandle.owned`, the `__post_init__` mismatch guard, `_placement_for`'s owned arm and `_owned_kwargs`. It ships no test for any of them. `grep MissionHandle tests/status/test_transition_request_owned.py` finds only the module docstring.
- Add the tests the prompt requires:
  - `RealFsReader().planning_read_dir(MissionHandle(R, slug, owned=fact), kind=TASKS_INDEX) == fact.mission_dir`;
  - `RealCoordCommitRouter().feature_write_dir(...owned=fact)` returns P's STATUS dir;
  - `commit_artifact` passes `owned=fact` to the injected `commit_fn`, and passes no `owned` kwarg for a non-owned handle;
  - the same-fixture legacy control `MissionHandle(R, slug, effective_root=P)`;
  - the `__post_init__` mismatch raises `TypeError`.
- Add these tests as a red commit before any fix. They must hit the owned arms with the legacy/resolver functions patched to raise.

**3. [HIGH] New mypy --strict error: src/specify_cli/cli/commands/agent/mission_finalize.py:2753.**
- The error: `Argument 9 to "commit_for_mission" has incompatible type "**dict[str, Path]"; expected "OwnedCheckout | None"`.
- Cause: adding `owned=` to `commit_for_mission` makes the untyped `**effective_root_kwargs(...)` splat ambiguous.
- Evidence: 15 errors on the base and 16 on the head, from the same 16-file invocation. The implementer's list omitted this caller.
- Fix without a suppression. For example, make `effective_root_kwargs` return a `TypedDict(total=False)` with `effective_root: Path`, declared out-of-map in `core/owned_mission.py`. Then re-run the diff with the callers included.

**4. [MEDIUM] status_transition.py:1693-1745: `emit_inner_state_changed_transactional` is only half converted.**
- (a) `fact = request.owned_fact()` is computed **before** `_identity_for_request`. A legacy caller that passes only `effective_root` now skips the `OWNED_TRANSACTION_UNAVAILABLE` refusal, which the base raised on `effective_root is not None`.
- (b) Two checks still key on the bare `effective_root` keyword, not on `identity.owned`:
  - the `_uncommitted_emit` short-circuit at :1712;
  - the `BookkeepingWorktreeMissing` re-raise at :1740.

  A caller that passes only `owned=` therefore degrades silently to an uncommitted write, which fails open. The prompt said to use `request.owned_fact()` / `identity.owned` for all three checks.
- Fix: key all three on `identity.owned`. Add tests for an `owned=`-only call and an `effective_root`-only call covering the refusal and the re-raise.

**5. [MEDIUM] Unmarked dual or legacy parameters.** The 12 markers you added match the DoD list, but these sites carry legacy parameters with no marker:
- `commit_router._resolve_group_placement(effective_root=)` at :292;
- `commit_router._commit_partition_group(effective_root=)` at :439;
- `write_seam._probe_write_target(effective_root=)` at :245;
- `emit_inner_state_changed_transactional(owned_mission=)` at :1636;
- `transaction._acquire_locked(primary_root=)` at :331, still read at :499 (`primary_root or repo_root`). The prompt said that `owned=` **replaces** `primary_root=`, and that the grep for `primary_root` in transaction.py must find only comments.

Required fixes:
- Delete `_acquire_locked`'s `primary_root` and derive the value from `owned.repository_root`.
- For the three private helpers, the deviation itself is justified: without a fact, `resolve_placement_only` / `placement_seam` still need the legacy root. Mark each legacy parameter `# TRANSITIONAL(WP18): delete with the dual keywords`.
- Mark `owned_mission=` on the inner-state door.
- Amend the WP07 DoD marker list, the count and the Activity Log in the same PR. WP18 T096 deletes only what the grep finds.

**6. [MEDIUM] status_transition.py:931: the legacy branch is no longer byte-identical, and the batch door regresses.**
- `request.owned = fact` mutates the caller's request as a side effect.
- The batch door resolves identity only from `requests[0]`, so only the first request is mutated. For `requests[1:]` that carry only an `effective_root`, `_infer_review_gates` now passes `owned=None` to the subtasks resolver. On the base, each request's `effective_root` was threaded.
- The only pipeline test that covered the legacy `effective_root` threading (`test_effective_root_is_threaded_to_the_resolver`) was replaced rather than kept as a legacy control.
- Fix: do not mutate the input. Bridge the legacy root for `has_owned_root_only()` requests inside the pipeline's default resolver path, or pass the identity's fact into `prepare_transition` explicitly.
- Keep a legacy-shape resolver test and a batch test with two effective_root-only requests.

**7. [MEDIUM] Red-first commit discipline.**
- Only T032 has a separate red commit: d79da407d, 8 failing, then green at 2cca090c4.
- The T033, T034 and T035 tests were committed in the same commit as their fixes. I confirmed they are red against each parent's src (4, 1 and 1 failing respectively), but the DoD requires the red test commit to precede its fix commit.
- T037 was committed **after** all the fixes, so it was never a red commit. On the base it is red: finalize-tasks counts 2.
- For the rework, the new T036 tests (item 2) and the item 4 and item 6 fixes must land test-first as separate commits. Record the T037 base counts (finalize 2, move-task 5) in the Activity Log.

## Non-blocking

8. [LOW] transition_pipeline.py:97/106 and transaction.py:845-847: the `# bridging: WP17 converts` markers sit in a docstring or on a preceding comment line, not on the `effective_root=` line. The Risks-section grep (`grep -rn "effective_root=" src | grep -v "TRANSITIONAL\|bridging"`) therefore still flags them. Move each marker onto the call line. Also list that grep's remaining sites in the Activity Log, with their owning WPs.
9. [LOW] bootstrap.py:143: `fact = owned or owned_mission` is a second collapse rule that does not check for disagreement. Build a `TransitionRequest`-style collapse, or reuse `owned_fact()` semantics (raise `TypeError` when both are set and differ). write_seam.py:566 forwards both `owned` and `effective_root` to `commit_for_mission` without checking that they agree.
10. [INFO] The Activity Log misattributes `tests/architectural/test_no_dead_symbols.py`.
    - That test is red **identically on the base 55610f516**: the same 5 symbols, and the same src reference sites on the base and the head.
    - WP07 did not cause it. On the base, status_transition.py's `TYPE_CHECKING` import already names `OwnedCheckout`.
    - The symbols are consumed by later WPs (WP08: adopt_owned_checkout and resolve_owned_create_root; WP11/WP19: NEXT_OWNED_TOPOLOGIES; WP16: OwnedCheckoutPathRefused; WP18: deletes OwnedMission).
    - Not blocking. Correct the note.

## Verified OK

- **Lock path:** unchanged. `lock_root = owned.owned_root` is the same path the base used (`effective_root = identity.repo_root = owned_root`), and it resolves through `feature_status_lock_path` under the git common dir. The NFR-001 r_snapshot test is green.
- **Zero re-validation on the fact path:** the tripwire tests are non-vacuous. The finalize-tasks CLI count is 2 on the base and 1 on the head.
- **Complexity:** ≤ 15 on the touched functions. The campsite commit precedes the conversion.
- **ruff:** check is clean. The format drift predates this WP; it is present on the base in the same three src files and one test file.
