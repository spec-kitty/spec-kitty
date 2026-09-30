---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T07:03:55Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 1: REJECTED (reviewer-renata)

The operator decision above T072 stands and is not relitigated here. The write-then-restore mechanism is accepted **only** under three conditions:
- every T070 refusal row leaves P and R unchanged;
- no finalize commit lands before the single final commit;
- no xfail remains.

Two of these conditions are violated in ways I reproduced with real, unpatched runs. The guard also makes one existing case worse than it is on base.

## Blocking

1. **[HIGH] `mission_finalize.py:4146` / `:4163`, with the flag set at `:3184`. The guard unwinds an already-durable finalize commit.**
   - The byte-restore guard and `_restore_owned_head` both gate on `meta_commit_progress.committed`.
   - That flag means "meta.json's delta rode the commit". It does not mean "the finalize commit landed".
   - When meta.json is excluded from the commit, the flag stays False after a successful commit. The exclusion happens through `_meta_json_delta_is_finalize_attributable` whenever a foreign field is pending, for example the `vcs`/`vcs_locked_at` fields from `implement --no-auto-commit` (SK3466-REV-001).
   - In that state, any post-commit exception reverts the mission directory, and in owned runs it also runs `git reset <pre-run sha>` on P. The exception can come from `_emit_success_report` or from anything else after `_commit_finalize_artifacts`.
   - The result: the finalize commit is orphaned. That directly contradicts the code comment at `:4144`: "a LATER, unrelated failure after a real commit must never unwind an already-durable finalize".
   - Repro: owned `under_worktrees` fixture, add an uncommitted `vcs` field to P's meta.json, and patch `_emit_success_report` to raise. P's HEAD then goes back from the finalize commit (`a276f88…`) to the pre-run SHA (`33f3084…`).
   - **Fix:** give the new guards their own "finalize commit landed" marker. Set it the moment `_commit_finalize_artifacts` returns with a commit. Keep SK3466's meta-attribution flag for the meta.json revert only. Add a regression test for exactly this scenario, owned and non-owned.

2. **[HIGH] `mission_finalize.py:3759` → `_scaffold_issue_matrix_if_present` (`:908`). The issue-matrix scaffold makes its own commit before the refusal gates. This violates "no commit before the single final commit", and the guard makes it worse than base.**
   - `scaffold_issue_matrix(..., repo_root=…)` goes through `write_issue_matrix`, which commits ("chore: update issue-matrix for …").
   - This happens before `_validate_ownership_manifests`, the stale-canceled check, and the lane-cycle check.
   - Repro: the non-owned `test_finalize_atomicity` ownership-overlap fixture, with `#4242` added to spec.md. After the refusal:
     - HEAD has advanced by the issue-matrix commit;
     - the byte guard then deletes the newly committed file, so the working tree shows ` D kitty-specs/<slug>/issue-matrix.json`.
   - On base, the commit was stranded but the tree was clean. It is now stranded **and** dirty.
   - This is the same defect class you already closed for the acceptance matrix in 9ef5c4263, and the fix should match: when the issue matrix's declared home is `planning_dir`, take the bare-write path so it rides the single final commit. Otherwise defer the scaffold until after the gates.
   - Every existing fixture has no issue refs in spec.md, which is why this was missed. Add a refusal row whose spec.md references an issue, non-owned and owned.

3. **[MEDIUM] Writes outside the mission directory under non-owned `coord` / `lanes_with_coord` topologies are neither guarded, tested nor documented.**
   - Repro: a real lane-cycle refusal, created via `create_mission_core`, with no patches. It leaves:
     - commits on `kitty/mission-<slug>-<mid8>`, from the transactional emitter's bootstrap;
     - a newly materialized `.worktrees/<slug>-<mid8>-coord` worktree;
     - `R/.kittify/derived/<slug>/*` residue.
   - These are pre-existing, and the operator deferred this class to #5343. But the code comments and the Activity Log currently claim the refusal leaves the checkout unchanged.
   - **Fix:** state the residual precisely in the `finalize_tasks` guard comment and the Activity Log, and add it to #5343: coordination-branch commits, coordination-worktree materialization and non-owned `.kittify/derived`. If you prefer to close it, the non-owned `.kittify/derived/<slug>` snapshot is a one-line generalisation of the owned one.

4. **[MEDIUM] Required T070 rows are missing or vacuous.**
   - (a) The non-owned **lane-cycle** row, which is T070 step 1's primary fixture, is absent from `test_finalize_atomicity.py`. I built it: WP01→WP02, WP03→WP04, with the codebase-wide trick. It is green with the guard and red with the guard disabled, so it is cheap to add.
   - (b) The **lane-glob re-validation** row (`LaneGlobValidationError`) is absent everywhere.
   - (c) The **planning-pin** row passes on base and passes with **both** guards disabled. The refusal fires before any write on a re-finalize. Record it as "already atomic" in the Activity Log. Commit d602d5fe8's body claims it was red; that red was a fixture-signature bug, not a product red.
   - (d) There is no **owned** pre-commit-injection row. I verified one: patch `commit_for_mission` to raise in the owned `under_worktrees` fixture. It is green with the guards and red without them. Add it.
   - (e) `_take_p_oracle` is HEAD plus porcelain only. T070 requires content hashes of ignored files (`tests/_owned_tree_hash.hash_tree`). Without them, a rewrite of an existing `.kittify/derived` file, or an append to an already-dirty `status.events.jsonl`, is invisible.

5. **[MEDIUM] G5 grew from 1 to 2 offenders, and T074 step 1 was not done.**
   - `tests/architectural/_owned_checkout_scan.bare_owned_root_paths` on `mission_finalize.py`: base has 1 offender (the inline option). Head has 2: the inline option at `:3924` plus the new helper parameter `_resolve_finalize_context(owned_checkout: Path | None)` at `:3524`.
   - **Fix:** use `OwnedCheckoutOption` on the command, or `owned_checkout_option(help=...)` if the help text is golden. Make the helper parameter exempt: either annotate it with the alias, or resolve in `finalize_tasks` and pass the fact.

6. **[MEDIUM] Red-first discipline.**
   - 3372fa798 bundles the FR-021 flagless adoption and the FR-007 field with their tests, so there is no red commit for either. Split it into a red test commit followed by the fix.
   - 9eb592720 (a `src/` change) precedes the first T070 test commit. This is acceptable only as a pure refactor; say so in its body.

7. **[MEDIUM] Out-of-map edits are undeclared.**
   - `tests/status/test_transition_request_owned.py` (3372fa798) and `tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py` (a5a251528) are not in WP13's `owned_files`.
   - Neither commit body declares them.

8. **[MEDIUM] FR-007: the `stale_repository_root_copy` key is untested in the owned success and refusal payloads.** Only the validate-only payload and the non-owned absence case are tested. Add both assertions. `grep` of `tests/` finds no other test of this key.

## Non-blocking (fix in the same pass)

- **[LOW] `mission_finalize.py:201`.** The comment contains the literal `TRANSITIONAL(WP18)`. The DoD expects 0 markers, and WP18 T096's grep will count this one. Reword it.
- **[LOW] `OwnedFactContractViolation` (`mission_finalize.py:3488`).** The real defect is `resolve_owned_or_adopt`'s return type.
  - Better fix: add `@overload`s in `_owned_checkout.py`, so an explicit `Path` returns `OwnedCheckout`. This removes the unreachable branch; `context.py:260` has the same latent gap.
  - If you keep the class, move it next to `UnregisteredOwnedRefusalCode` in `_owned_checkout.py`. It is a public name for WP08's contract, not a finalize concept.
  - The monkeypatch test pins branch coverage only; that is acceptable.
- **[LOW] T074 step 2.** Owned refusals go through the generic `except Exception` envelope, not `emit_owned_refusal`, so the registry is never validated. Route the `ActionContextError` from `resolve_owned_or_adopt` through `emit_owned_refusal`, and keep the finalize envelope keys.
- **[LOW] `tests/integration/test_owned_lifecycle_acceptance_finalize.py:10-30`.** The module docstring says the lane-cycle test uses a "Rule 2" disjoint-ownership fixture and "builds exactly that fixture". The test actually uses Rule 1 with a codebase-wide exemption. Correct the docstring.
- **[LOW] Terminology.** The new helper parameter `feature` in `_resolve_finalize_context` should be renamed to `mission_handle`. The test docstring "real feature branch" in `test_finalize_atomicity.py` should say "mission branch".

## Verified OK

- **G2.** `resolve_owned_or_adopt(..., allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES, target_override=…)` is in place. G2 validator calls went from 1 to 0, and G4 identifiers from 5 to 2 (both marked bridging).
- **Ownership validation count.** Exactly 1 ownership validation, flagged and flagless (`TestExactlyOneOwnershipValidation`).
- **Bridging markers.** `# bridging: WP17 converts` and `# bridging: WP15 converts` are correct. WP17's T090 and WP15's T082 convert those callees and name these call sites.
- **Two atomicity mechanisms.** There is no double restore (meta.json is excluded from the byte guard), and the SK3466 revert runs first.
- **Complexity.** `finalize_tasks`, `_commit_finalize_artifacts` and `_run_bootstrap_loop` are all ≤ 15, and the `noqa: C901` is gone.
- **Lint and types.** ruff check and format are clean. mypy `--strict` over 11 files reports 5 errors on base and 5 on head, identical.
- **No xfail remains.**
- **#5009.** No #5009 commit maps to IC-07, and nothing was ported.
