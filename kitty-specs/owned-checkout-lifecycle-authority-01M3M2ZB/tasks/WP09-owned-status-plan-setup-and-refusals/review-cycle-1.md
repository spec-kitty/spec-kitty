---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T06:25:26Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review — cycle 1 — CHANGES REQUESTED

Reviewed: 432968d0b, 13bcedc18, de26c58eb, ca1ec188f, 6f1811e67, 39f052461, 17e1e5bc5, bb6e56546, b3297e262 and the late b3dc01fff. Base: d61da95c8.

## What is solid

- Red-first order holds. The red commits were run in a scratch detached worktree:
  - 432968d0b: 10 failed;
  - de26c58eb: 7 failed, 2 passed (the 2 passes are the controls);
  - ca1ec188f: 24 failed, 47 passed (the status and setup-plan rows).
- Goldens:
  - `status.help` and `_group.help` were regenerated with the T048 script at head and are byte-identical to the committed fixtures;
  - `move-task.help` and `mark-status.help` are unchanged;
  - the flag sets for `setup-plan` and `status` were updated in the same commits as the surface change.
- The T049 R row is non-vacuous. A source mutation made `resolve_owned_or_adopt` fall back to `None` for R, and `refuse_owned_action` skip validation for R. With the mutation, all 5 commands went red on the R row.
- mypy `--strict --explicit-package-bases`: 0 errors on the base and 0 on the head (11 files, one invocation).
- ruff check is clean. Complexity: every touched function is ≤ 11.
- 0 `TRANSITIONAL(WP18)` markers were added and no `bridging: WP09` markers remain. Both match the DoD.
- The status owned arm is clean. A probe made `get_main_repo_root`, `candidate_feature_dir_for_mission`, `resolve_handle_to_read_path` and `committed_status_dir` raise after minting, and it passed from cwd R and from cwd P.
- b3dc01fff is fine. The compat guard's own contract (`test_guard_keyset_is_superset_of_all_six_seams_native_defs`) requires every native def to be registered, so the re-exports are the convention, not a guard-appeasement.

## Issues (all must be fixed)

**Issue 1 [HIGH] `mission_setup_plan.py:937-938` (`_run_documentation_wiring`) — the declared deviation is not covered by the spec's fallback.**

The T046 fallback allows leaving these helpers un-wired only for software-dev owned missions. A documentation-type owned single_branch mission is legitimate and does reach both helpers. I probed it with a documentation meta, `gap_filling`, P containing `docs/` and `pyproject.toml`, and `--owned-checkout P`:
- `_run_documentation_gap_analysis` and `_detect_and_configure_generators` call `commit_for_mission(repo_root=P, owned=None)`;
- they resolve `ProtectionPolicy` from **P**, so the linked checkout's config governs protection.

The outcome depends on R's stale copy:
- **No R copy:** both return `no_op_wrong_surface`. This is silently suppressed by `contextlib.suppress`, and P is left dirty (`meta.json` modified, `gap-analysis.md` untracked), while the payload still reports `gap_analysis` and `generators_detected`.
- **With `stale_root_copy`:** both "commit", because placement consulted R's copy.

That is exactly the fact-less, stale-copy-dependent routing FR-005 and FR-007 forbid.

Required fix:
- thread `owned=` into both helpers and on into `commit_for_mission(..., owned=owned)`;
- resolve protection from `owned.repository_root`, as `_commit_to_branch` now does;
- add a test with a documentation-type owned mission asserting the gap-analysis and generator commits land on P's branch (P `HEAD` advances, R unchanged), with and without `stale_root_copy`;
- remove the "untested here" docstring claim.

**Issue 2 [HIGH] T045 step 5 tests are missing, and the owned staleness/workspace wiring is untested.**

bb6e56546 adds no tests. Nothing asserts either of these:
- an owned WP in `in_progress` (via `move-task --owned-checkout P`) renders `workspace_kind == "owned_checkout"` with no error;
- with `stale_root_copy` where R's WP01 lane differs, status reports P's lane.

The `owned=None` pin added in b3dc01fff (`test_tasks_status_cmd_seam.py`) is correct for the non-owned call. The owned counterpart assertion is the missing piece: `_st_resolve_execution_mode(..., owned=<fact>)` → `resolve_workspace_for_wp(..., owned=<fact>)`, and `check_doing_wps_for_staleness(owned=st.owned)`.

Add the two T045 rows. Also add a unit test for `_st_status_read_dir` on both arms. The owned arm must return `owned.mission_dir` without calling `committed_status_dir`; pin that with a raising monkeypatch.

**Issue 3 [HIGH] No raising pins for the "fact is the only representation" rule.**

Add tests where these functions RAISE once the fact is minted (wrap `resolve_owned_or_adopt` to arm the pins):
- **status:** `get_main_repo_root`, `_find_mission_slug`, `_ensure_target_branch_checked_out`, `resolve_handle_to_read_path`, `candidate_feature_dir_for_mission`, `committed_status_dir` and `get_status_read_root`. My probe shows these pass today, so this only pins the behaviour.
- **setup-plan:** `_resolve_setup_plan_feature_dir`, `_show_branch_context`, `_mission._planning_read_dir` and `resolve_checkout_identity`.

Note: a global `get_main_repo_root` pin on setup-plan currently fires in two callees outside WP09's map:
- `status/lifecycle_events.py:340` (`_repo_root_for_lifecycle_log` → `resolve_canonical_root`, via `_emit_spec_plan_phase_events`);
- `coordination/commit_router.py:321` (`resolve_topology(repo_root, …)` runs even when `owned` is set, reading R's meta).

Pin the WP09-layer functions. Record those two residues in the Activity Log as follow-ups for the owning WP (WP07/WP18) rather than editing them here.

**Issue 4 [MEDIUM] `tasks_status_cmd.py:239-247` — sole-mission auto-select runs before owned resolution.**

The T045 edge case says: "Do not auto-select a sole mission for an explicit owned run." Probe: `status --owned-checkout P --json` with no `--mission`, while R holds one other active mission `other-…`. It returns `FEATURE_CONTEXT_UNRESOLVED` "No mission found for handle "other-01M2D9AA"". The handle came from R's auto-select, when it should be the minter's handle-required error ("--owned-checkout requires an explicit --mission.").

Separately, flagless `status --json` from cwd P in the same setup exits 0 and shows R's unrelated mission. That breaks the flagless rule ("from cwd P a flagless run equals the flagged run").

Required fix:
- apply `_sole_active_mission_slug_or_none` only on the non-owned path, after `_st_resolve_owned` returns False;
- pin the handle-required code in the T049 file, with and without an R-only sole mission.

**Issue 5 [MEDIUM] T049 per-row assertions are incomplete compared with step 3.**

Every row asserts only the exit code, the code and the worktree/branch lists. Also required:
- `result.exception is None or isinstance(result.exception, SystemExit)`;
- R snapshot unchanged (`make_r_snapshot(checkouts)`, since each row builds its own instance);
- a P snapshot unchanged (HEAD, `status --porcelain`);
- for `setup-plan` on the topology row, no `plan.md` created in P.

The valid-P control for status, setup-plan and context-resolve asserts only exit 0.

`test_fr020_mutation_check_r_row_goes_red_when_resolver_stubbed` is a test-level stub with a near-tautological assertion (`exit_code == 0 or code not in combined`) that covers `status` only. Either delete it and log the real source mutation in the Activity Log (I confirmed it: all 5 R rows go red), or make it assert the concrete mutant outcome for all 5 commands.

**Issue 6 [MEDIUM] T044 rows missing or vacuous.**

- `test_o1_flagless_status_from_p_lists_only_p_wps`: `r_snapshot.assert_unchanged(r_snapshot.take(), r_snapshot.take())` is vacuous, because both snapshots are taken after the run. Take `before` before invoking.
- Missing: O1 flagless **with** `stale_root_copy`. This was the fail-open base column (exit 0 listing R's WP01–WP05), and it is the most important FR-007 row.
- Missing: O2 flagless and O2-flag **with** `stale_root_copy` (base `SPEC_FILE_MISSING` naming R's copy).
- Missing: the setup-plan `stale_repository_root_copy` assertions:
  - JSON path equal to R's copy with the stale copy present, and `null` without it;
  - the human-mode stderr warning.
  - FR-007 is currently untested for setup-plan.
- Missing: H ∈ {slug, mid8, id}. Use the WP02 `owned_handle` fixture for O1-flag and O2-flag (FR-004 DoD item 1).
- Missing: NFR-001 (e). The owned cases are not parametrised over cwd ∈ {R, P, elsewhere}; use `owned_cwd`.
- Missing: NFR-002 (d). Owned setup-plan should count 1 and non-owned should count 0. Only owned status is counted today.
- Control (a) asserts only key absence. Capture and compare the payload shape (`_shape`). Also remove the stray unused first `_status(...)` call.
- US1-AS2: assert P `HEAD` advanced by **exactly one** (`rev-parse HEAD~1 == head_before`), not just `!=`.
- Missing T046 edge rows:
  - non-substantive spec in P → `SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED` with `spec_file` under P;
  - scaffold-only (pristine template) → no commit, P `HEAD` unchanged, R unchanged, and `plan.md` created in P, not R.

**Issue 7 [LOW] Campsite commits lack their required focused tests.**

T045 and T046 step 1 say "Add a focused unit test", but 6f1811e67 and 39f052461 add none. Add them: `_st_status_read_dir` (covered by Issue 2) and `_resolve_setup_plan_scope` (non-owned and owned arms, including the refusal → `result_error_envelope`).

**Issue 8 [LOW] `test_owned_lifecycle_acceptance_cli.py:78,123,149` — the literal `"OWNED_ACTION_UNSUPPORTED"` is repeated 3 times.**

The DoD says no `OWNED_*` literal may be repeated in new tests. Use `OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value`.

**Issue 9 [LOW] `tasks.py` `move_task` option — new format drift.**

Dropping the trailing comma after `help=(...)` makes ruff want to collapse the block: format-diff lines go from 84 to 86 against the base's pre-existing drift. Restore the magic trailing comma so WP09 adds no drift.

**Issue 10 [LOW] Commit-body accuracy.**

bb6e56546 claims "the owning subsystem dir … (2111 passed)". Yet b3dc01fff says that directory surfaced two failures introduced by bb6e56546 (the compat guard and the seam pin). Record the real per-file commands and counts in the Activity Log for this cycle.

## Coordination note

`tasks.py` is shared with WP10, WP13, WP14, WP16 and WP19 (inline `--owned-checkout` declarations). WP09 converted only `move_task` and `mark_status`, as T048 specified.
