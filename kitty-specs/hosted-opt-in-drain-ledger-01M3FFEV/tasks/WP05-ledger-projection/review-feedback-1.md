# WP05 review — cycle 1 — CHANGES REQUESTED

Reviewer: reviewer-renata (claude). Reviewed: lane-e `900c81ae` (red-first) + `ada45ce7` (impl), HEAD `77dba47d`.

What is solid (keep it): the T021 red-first commit fails on its own for the right reason (the stale tracked `status.json` gets rewritten, not an import error). The single-writer `snapshot=` refactor is correct and only adds behaviour: `spec-kitty materialize` and `normalize_mission_lifecycle` still call without `snapshot=`. `materialize_if_stale` and `refresh_execution_projection` use `materialize_snapshot`. The mutation that swaps it for the writing `materialize()` turns case (a) red. The `_defer_fan_out` hook runs after commit through `txn.defer_outbound`, and removing it turns (e) red. Ledger on and ledger off give the same coord commit count, commit file set and event-log bytes (ignoring volatile fields). Diff coverage of touched src is 52/52 lines over the owning suites. C901 is clean, and whole-repo `ruff check` and `ruff format --check` are clean.

## Blocking

### B1 — Coord fallback arm refreshes the projection before commit, inside L1, and leaves a phantom projection on rollback

`_fallback_emit_single._coord` and `_fallback_emit_batch._coord` run the flat shell (`emit_status_transition(..., fan_out=False)`) inside `_emit_on_coord_then_commit`'s bounded L1, before `_commit_status_artifacts_to_coord`. The new flat hook `_refresh_projection_if_ledger_on` runs whether or not `fan_out` is set, so it fires there, before the commit.

Reviewer probe: force `_transaction_topology_available=False` as `tests/specify_cli/coordination/test_phantom_fanout.py` does, and record the refresh calls:

- commit succeeds: `['refresh(locked)', 'commit', 'refresh(unlocked)']`. The projection is refreshed twice, and the first refresh runs under the L1 that spans safe_commit.
- commit fails (injected): `['refresh(locked)', 'commit']`. `.kittify/derived/<slug>/status.json` shows WP01 as `claimed`, but that event was truncated away. This is the same phantom shape that SC-002 / `test_phantom_fanout.py` forbids for SaaS fan-out.

**Fix:** give the flat shells a separate opt-out, for example `refresh_projection: bool = True` on `emit_status_transition` / `emit_status_transition_batch`, and pass `False` from both coord `_flat_shell`s. The coord tail already refreshes after commit. Do not key the opt-out on `fan_out`, because FR-009 requires the refresh to run whatever `fan_out` is set to.

Add a regression test next to `test_coord_fallback_holds_lock_through_commit_and_restore_but_not_fanout`. It should cover both cases:

- `commit_fails=True`: no refresh happens and no derived file is written.
- `commit_fails=False`: exactly one refresh happens, outside L1.

### B2 — Three of the six hook paths have no behavioural test, and (e) does not prove the refresh runs after commit

- **Removing hooks goes undetected.** Mutation M5 removed the `_fan_out_committed_coord_tail` hook and the `emit_inner_state_changed_transactional` hook. Afterwards `tests/status/test_execution_projection.py`, `test_ledger_floor.py`, `tests/specify_cli/coordination/` and `tests/coordination/` still pass: 638 passed, 10 skipped.
- **(e) cannot tell before-commit from after-commit.** Mutation M3b made the `_defer_fan_out` refresh synchronous inside the transaction, and (e) stays green. It only asserts `lane == "claimed"`, which is true either way.
- **Batch and ordering gaps.** Nothing tests the transactional batch door. The flat-batch test does not check that the refresh runs once per batch.

The WP Risks section asks for tests on every real call path: flat single, flat batch, transactional single, transactional batch, coord-tail and inner-state.

**Fix:** add these tests:

- **Coord-tail:** forced fallback. The derived file lands under the MAIN repo root, not under `.worktrees/...`.
- **Inner-state door:** call `emit_inner_state_changed_transactional`.
- **Transactional batch:** call `emit_status_transition_batch_transactional`.
- **Ordering in (e):** assert the refresh runs after commit, either by recording the call order or by showing that an injected commit failure leaves no derived file.

### B3 — The ledger-floor guard's self-mutation check does not do what T024 step 9 and the DoD require

1. **Removing a permitted hook-site reference does not turn the gate red.** The real test only asserts at least one reference and that none fall outside the allow-list, so deleting two of the three hook sites stays green (M5). `test_removing_a_permitted_hook_site_reference_would_go_red` only checks a synthetic module and never exercises the real assertion.
   - **Fix:** assert that each function in `_ALLOWED_STATUS_TRANSITION_FUNCTIONS` references `ledger_posture` (set equality between the referencing functions and the allow-list). Make the self-mutation test run the same assertion helper on a synthetic module that is missing one site, and expect it to fail.
2. **A module alias gets past the AST scan.** This contradicts the docstring's claim that a rename cannot. In `status/reducer.py`, both of these alias forms stay green: `import specify_cli.core.hosted_posture as _hp` followed by `_hp.ledger_posture(None)` (M6), and `from specify_cli.core import hosted_posture as _hp2` followed by `_hp2.ledger_posture(None)` (M6b). Only the canonical `hosted_posture.ledger_posture` form (M6c) is caught.
   - **Fix:** follow `Import` / `ImportFrom` `asname` bindings of the `hosted_posture` module, or simply flag any import of `hosted_posture` in the forbidden files. Add a planted-alias case to `TestGuardBites`.

## Non-blocking (fix while you are in there)

- **N1:** `refresh_execution_projection` calls `git_operation_in_progress(repo_root)` outside its `try`. The "never raises" contract then depends on a filesystem probe never raising, for example a `PermissionError` on the gitdir. Move the call inside the guarded block.
- **N2:** `derive_mission_lifecycle(snapshot=...)` changes the snapshot it is given (`snapshot.mission_slug = ...`), and `refresh_execution_projection` shares that snapshot across all three generators. It is harmless today because `materialize_snapshot` already stamps the slug, but avoid changing the caller's object.
- **N3:** The derived slug comes from `snapshot.mission_slug or feature_dir.name` (inside `write_derived_views`), not from `_stale_check_slug` as T023 step 2 asks. It matches `spec-kitty materialize` output, so this is acceptable. Record the deviation.
- **N4:** The `tests/status/test_views.py` fakes accept `snapshot=` but never assert it was passed. Consider asserting that all three generators receive the same snapshot object.
- **N5 (shared-file coordination):** The following files are outside the WP05 `owned_files` map and need a coordination note:
  - `pyproject.toml`: format-exclude entry removed. The ratchet is green.
  - `src/specify_cli/core/hosted_posture.py`: docstring only (WP01-owned).
  - `src/specify_cli/status/__init__.py`: export added.
  - `tests/status/test_views.py`: fakes updated and file reformatted.

  Each change is justified; put that note in the move-task reason on resubmission.

## Pre-existing reds (classified, not yours)

Both of these fail the same way on base `c7b74b26` (scratch worktree):

- `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported`
- `tests/architectural/test_archive_root_byte_identical.py::test_no_preexisting_archived_file_was_modified` (shallow-history blob missing)
