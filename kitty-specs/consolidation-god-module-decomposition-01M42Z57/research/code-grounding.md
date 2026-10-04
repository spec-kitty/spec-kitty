---
type: reference
updated: 2026-10-04
audience: software-engineer (maintainers and agents changing consolidation)
---

# Code grounding: consolidation god-module decomposition

Read-only grounding run for epic #2026 (2026-10-04 re-scope), #2600 and #3457,
taken on `origin/main` @ `43b66f60`. Every claim below names the file and line
it was read from. Line numbers are for that commit.

## 1. Sizes and responsibility map

### 1.1 Module sizes (`src/specify_cli/consolidation/` and the command)

| Module | LOC | Role |
|---|---|---|
| `consolidation/executor.py` | 4,603 | everything between the CLI and the git primitives (see 1.2) |
| `consolidation/reconciliation.py` | 1,962 | claim build, `MergeOutcomeVerifier`, squash content axis, canceled-content axis |
| `consolidation/drivers.py` | 1,348 | merge-driver bodies (subprocess and in-process replay) |
| `cli/commands/consolidate.py` | 1,178 | Typer command, `--abort`/`--resume` dispatch, re-export surface |
| `consolidation/preflight.py` | 1,022 | git / target / mission-branch / review-artifact preflights |
| `consolidation/baseline.py` | 938 | #1827 baseline record + assert, mission_number read-back |
| `consolidation/ordering.py` | 911 | dependency merge order (~135 LOC) + mission_number bake cluster (~775 LOC) |
| `consolidation/git_probes.py` | 877 | git read primitives |
| `consolidation/state.py` | 853 | `ConsolidationState`, lock, resume anchors |
| `consolidation/done_bookkeeping.py` | 781 | done emission and asserts |
| `consolidation/wp_attribution.py` | 729 | mixed-lane per-WP attribution, closed world |
| `consolidation/rollback.py` | 413 | the single rollback authority |
| `consolidation/mission_number.py` | 30 | stdlib-only leaf: `is_assigned_mission_number` |
| others | < 660 each | conflict classifier/resolver, forecast, resolve, workspace, retention, ... |

`ruff check --select C901` is clean on all of them (ceiling 15). The debt is
size and cohesion, not complexity, as the #2026 re-scope comment says.

### 1.2 `executor.py` responsibility map (by phase)

Top-level definitions and their line spans (AST, `executor.py`):

| Phase / concern | Definitions (start line) | ~LOC |
|---|---|---|
| Run state + shared messages | `_CONSOLIDATE_ABORT_COMMAND` :208, `_NOTHING_TORN_DOWN` :212, `CoordinationTeardownError` :215, `LaneNamingSlugMismatch` :224, snapshot capture `_merge_snapshot_roots/_files`, `_capture_merge_snapshots` :235-268, `_MergeRunState` :345 (152 LOC), `_P` :499, `_moved_by_this_run` :502, `_records_post_mutation_tips` :507, `_CoordCheckpoint` :972, `_capture_coord_checkpoint` :988, topology probes `_stored_topology_for` :2861, `_is_coord_topology_mission` :2884 | 330 |
| Pre-mutation gates (in-lock) | `_assert_mission_terminal_ready` :547, `_planning_only_notice` :599, `_phase_gates_and_state` :615 | 125 |
| Claim + resume anchors | `_resolve_pre_mutation_target_sha` :2055, `_persist_executed_strategy` :2085, `_capture_pre_interrupt_lane_tips` :2111, `_resolve_pre_mutation_coord_sha` :2145, `_unanchored_lane_branches` :2173, `_refuse_unanchored_resume` :2196, `_enforce_resume_anchor_integrity` :2222, `_clear_fresh_record_on_pre_mutation_exit` :2276, `_capture_reconciliation_claim` :2309, `_capture_snapshot_and_begin_attempt` :2369, claim refusal exits :2384-2425 | 375 |
| Lane advance + mission->target | gate-artifact guard :289-341, `_lane_branch_ref_exists` :672, `_lane_completed_but_branch_gone` :683, `_created_lane_worktree` :710, `_phase_merge_lanes` :725, status-surface resolution :787-830, `_phase_baseline_and_surface` :833, `_phase_bake_and_pre_target_done` :870, `_reanchor_baseline_past_primary_tree_bake` :941, mission->target result handling :1252-1348, `_phase_mission_to_target` :1401, `_switch_write_checkout_after_single_branch_landing` :1533 | 520 |
| Coord strand (mark / heal / restore) | `_capture_pre_target_coord_ref_sha` :1014 ... `_restore_pre_target_if_at_baseline` :1232 (9 functions) | 235 |
| Projection + bookkeeping | `_run_has_code_wps` :1350, mission_number on target :1442-1531 and :2014, `_phase_capture_and_baseline` :1543, `_phase_record_done_and_project` :1607, birth cutover :1692-1853, `_phase_porcelain_invariant` :1855, `_phase_commit_and_assert` :1918 | 650 |
| Reconciliation gate | `_reconciliation_claim_for_gate` :2428, `_resume_reconciliation_already_passed` :2464, `_record_reconciliation_pass` :2494, `_phase_reconcile_before_teardown` :2510, `_reconciliation_pass_message` :2562, `_rollback_target_after_failed_reconciliation` :2585, squash projection proof :2630-2716 | 290 |
| Teardown | flatten :2751, mission-branch tip/delete :2905-2985, late coordination landing :2987-3094, `_teardown_coord_worktree` :3096, `_teardown_coordination_triple` :3173, single_branch clear :3210, `_cleanup_mission_branch_and_coordination` :3247, lane worktrees :3288, lane branches :3346, `_phase_cleanup_worktrees_and_branches` :3390 | 660 |
| Finalize | `_phase_dossier_and_stale` :2718, `_phase_push` :2732, `_phase_finalize_and_summary` :3404, stale findings render :3417-3455 | 90 |
| Unlocked entry preflight | `_resolve_coord_worktree_for_preflight` :3457, `_pre_mutation_safety_preflight` :3489, ledger refusal :3583, `_synthesize_no_lane_manifest` :3898, protected-target refusal :4201-4234, lanes.json naming :4301, `_resolve_run_status_dir` :4339 | 360 |
| Resume recovery (refusal advice + behind-own-HEAD reset) | `_LagCheckout` :3957 ... `_recover_behind_head_primary_on_resume` :4135, `_pre_mutation_safety_preflight_with_recovery` :4237 | 330 |
| Orchestration (the rollback door) | `_record_operator_attestations` :3610, `_run_lane_based_consolidation_locked` :3659 (205 LOC, the door `try` :3829-3859), `_report_rollback` :3866, `_run_lane_based_consolidation` :4385 (213 LOC, lock at :4570) | 500 |

Phase order in the locked driver (`executor.py:3781-3863`): attestations ->
review-artifact gate -> load/create state -> resume heal -> [pre-mutation:
persist strategy, `_phase_gates_and_state`, `_capture_reconciliation_claim`] ->
[door: merge lanes -> baseline/surface -> bake + pre-target done -> gate
artifacts -> mission->target -> single_branch switch -> capture/baseline ->
record done + project -> porcelain invariant -> commit + assert -> reconcile
gate] -> stale scan -> push -> cleanup/teardown -> finalize.

There is no module-level mutable state (no caches, registries or mutable
globals). The import-time state is the six `@_records_post_mutation_tips`
decorations (:724, :869, :1203, :1400, :1606, :1917) and module constants.

### 1.3 `ordering.py` (911 LOC)

- Ordering concern (stays): `MergeOrderError` :57, `has_dependency_info` :63,
  `get_merge_order` :75 (to :135).
- mission_number cluster (moves, #2600): `assign_next_mission_number` :138,
  `_already_baked` :217, `_mark_mission_number_baked` :227,
  `_is_assigned_mission_number` :241, `_compute_next_mission_number_or_none` :254,
  `_surface_unbaked_mission_number` :327, `_bake_mission_number_on_primary_tree` :357,
  `_write_mission_number_to_branch` :491, `_refuse_unassignable_mission_slug` :670,
  `_bake_mission_number_into_mission_branch` :688,
  `_assign_planning_only_mission_number_if_needed` :821,
  `_bake_mission_number_onto_target_tree` :851, `_read_target_tree_mission_number` :891.
- Callers: `consolidation/__init__.py:22`, `forecast.py:43`, `executor.py:144`,
  `cli/commands/consolidate.py:200`.
- `ordering` sits in the mypy transitional quarantine (`pyproject.toml:2694`,
  `ignore_errors = true`); code moved out of it is held to strict mypy.

**Target module tension.** The #2600 refresh (2026-10-04) asks for the cluster
to move "into the existing leaf `consolidation/mission_number.py`". That module
is a declared stdlib-only leaf (`mission_number.py:1-15`) precisely so the
merge-driver body module `drivers.py:87` (run inside git's merge-driver
subprocess) can import it without pulling `ordering`'s dependency graph. Moving
~775 LOC with `console`, git, worktree and `mission_metadata` imports into that
file would break its documented contract. Resolution is recorded in plan.md.

#3926 (listed as a blocker on #2600): its fix items 1-3 are on main already
(worktree-first triple order and fail-loud at `executor.py:3173-3207`;
mission_number written to and verified on the target tree by #4900 at
`executor.py:1487-1531`, `:2014-2052`). The move is no longer a rebase hazard
for that fix.

### 1.4 `cli/commands/consolidate.py` (1,178 LOC)

- ~265 LOC of re-export imports kept "byte-stable" for test importers
  (`consolidate.py:24-55` header rule, `__all__` :1124).
- `consolidate()` :801 takes **19 parameters**, all `typer.Option(...)`
  defaults. A direct Python call that omits one receives the `OptionInfo`
  sentinel, which is the #3457 failure mode (`_validated_attestation_flags`
  :1077 already has to defend against it).
- Direct call sites: `tests/consolidation/test_merge_preflight_mission_branch.py`
  (7 x `merge_mod.consolidate.__wrapped__`, lines 98, 242, 311, 363, 428, 480,
  543; 16 kwargs each) and `tests/consolidation/test_executor_coverage.py:1274`
  (1 x `merge_mod.consolidate(`, 16 kwargs). All 8 omit `skip_lanes`,
  `attest_canceled_superseded`, `attest_reason`, which is exactly the latent
  `OptionInfo` trap.
- `tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py:202` binds
  captured kwargs against `inspect.signature(consolidate)`, so the Typer
  signature must keep its 19 named options.

## 2. Invariants that must survive (with enforcement and pins)

"In E" = the enforcing code lives in `executor.py` and must move intact.

| # | Invariant | Enforced at | Pinned by | In E |
|---|---|---|---|---|
| I1 | Claim-integrity refusal exits before the first mutation (ADR 2026-09-19-1 A1, #5338); order inside the claim: legacy check -> checkpoint -> resume anchors -> claim build -> refusal -> snapshot | `_capture_reconciliation_claim` :2309-2366, `reconciliation.claim_integrity_refusal` :1517 | `test_claim_integrity_refusal.py`, `test_executor_phase_boundary.py`, `terminus/test_claim_refusal_before_mutation.py` | yes |
| I2 | One pre-mutation snapshot, never recaptured on resume (A2) | `_capture_snapshot_and_begin_attempt` :2369 -> `rollback.capture_pre_mutation_snapshot` :228 (early return :246) | `test_executor_rollback_wiring.py::test_snapshot_is_captured_once_and_reused_by_a_resume`, `test_state_snapshot_fields.py` | call site |
| I3 | Post tips recorded per phase, only for target/mission/coord branches that changed; never after a CAS refusal, always after `RefResyncError`; best-effort on the error path | `_moved_by_this_run` :502, `_records_post_mutation_tips` :507-544 on six phases | `test_executor_rollback_wiring.py` (:102-215) | yes; all six stay decorated |
| I4 | ONE rollback door over the whole post-mutation span; non-zero `Exit`/exception/interrupt -> `_report_rollback` then bare `raise`; `Exit(0)` passes; `typer.Exit` clause first | `_run_lane_based_consolidation_locked` :3828-3859, `_report_rollback` :3866 | `test_single_rollback_authority.py::test_every_span_phase_call_sits_inside_the_one_rollback_door` (reads executor.py text), `test_executor_phase_boundary.py::test_locked_driver_calls_phases_in_frozen_order`, `test_reconciliation.py:961-982` | yes; driver + door + `_report_rollback` stay in executor.py |
| I5 | Single rollback authority: `rollback_to_snapshot` called only from `executor._report_rollback` and `consolidate._abort_restore_or_keep_record`; no per-phase `git revert`; resume heal called only from the driver | `rollback.py:397` | `test_single_rollback_authority.py` `_ALLOWED_CALLERS` :85 (floor 2), revert-argv scan :252 (**executor.py only**), heal pin :272 | yes |
| I6 | Rollback authority semantics (restore only at recorded post tip, lanes report-only, never undo an earlier verified landing, resync) | `rollback.py` | `test_rollback_authority.py`, `test_consolidate_abort_rollback.py`, `terminus/test_abort_restores_snapshot.py` | no |
| I7 | CAS ref advance / restore (3-arg `update-ref`, fail closed, no 2-arg fallback); `RefResyncError` subclasses `RefAdvanceError`, `RefRestoreError` does not | `git/ref_advance.py:82-96`, `advance_branch_ref` :588, `restore_branch_ref` :689, `_resync_checkouts` :565 | `tests/git/test_ref_advance_cas.py` | no (I3 depends on the hierarchy) |
| I8 | Gate FAIL/REFUSE restores the target and tears nothing down; PASS records the CAS anchor; `route_terminus` reached | `_phase_reconcile_before_teardown` :2510-2559, `_rollback_target_after_failed_reconciliation` :2585 | `test_refuse_restores_target.py`, `test_merge_state_authority.py`, `terminus/test_repro_5021.py` | yes |
| I9 | Squash content axis fail-closed (#5013) + squash projection proof | `reconciliation._unattributable_content_squash` :846; `_assert_squash_projected_content_landed` :2651 | `terminus/test_repro_5022.py`, `test_repro_5038.py`, `test_repro_5051_clean_3way.py` | proof only |
| I10 | Canceled-content axis + closed world (ADR 2026-09-29-1, FR-013) | `reconciliation._canceled_content_divergence` :632, `wp_attribution.py` :578-620 | `test_reconciliation.py`, `terminus/test_mixed_lane_closed_world.py`, strict xfails in `test_canceled_content_residuals.py` | no (E only resolves `excluded_canceled_wp_ids` :3703 and records attestations :3708 before the claim) |
| I11 | Resume anchors read-persisted-first (`pre_mutation_target_sha`, `pre_mutation_coord_sha`, `pre_interrupt_lane_tips`, strategy) | :2055-2272 | `terminus/test_repro_4982.py`, `test_repro_4997.py`, `test_resume_strategy_authority.py` | yes |
| I12 | `ProjectionTeardownGate` re-checks the coord tip with CAS before destroying the triple; triple is worktree -> branch (CAS at approved tip) -> flatten | `_teardown_coord_worktree` :3139-3164, `_teardown_coordination_triple` :3197-3207; enforcement `coordination/teardown.py:187` | `tests/coordination/test_projection_teardown.py`, `test_coord_teardown_order_3926.py`, `terminus/test_coord_teardown_cas_branch_delete.py` | construction |
| I13 | Protected-target (`PROTECTED_BRANCH_REFUSED`) preflight before the lock, no record written | `_refuse_protected_status_target_or_continue` :4201, called :4554 | `terminus/test_protected_target_preflight.py`, `test_preflight_seam.py` | yes |
| I14 | Global consolidation lock with owner token, released in `finally` | `_run_lane_based_consolidation` :4570-4597 | `test_merge_state_authority.py` | yes |
| I15 | INV-5 #1827 order: baseline RECORD -> bookkeeping commit -> baseline ASSERT | `_phase_capture_and_baseline` :1594, `_phase_commit_and_assert` :1955-2009 | `test_executor_phase_boundary.py::test_record_then_commit_then_assert_ordering` | yes |
| I16 | Fresh run's own record cleared on any pre-mutation exit (#5111) | `_clear_fresh_record_on_pre_mutation_exit` :2276 | `test_fresh_record_cleared_on_pre_mutation_exit.py` | yes |

A pure move preserves every row as long as (a) function bodies are byte-identical,
(b) decorators move with their functions, (c) the driver, the door `try`, the
inline phase calls and `_report_rollback` stay in `executor.py` under their
names, and (d) every patch/pin that named `executor` is re-pointed to the module
where the name is now looked up.

## 3. Gates, pins and ledgers that reference the moved code

Keep each one green honestly: re-point, never loosen. "Vacuous risk" = the gate
would stay green but stop scanning moved code.

| Gate / ledger | What it pins | Honest action |
|---|---|---|
| `tests/consolidation/test_single_rollback_authority.py` :44-89, :232-272 | allowed callers `(executor.py, _report_rollback)`; door scan of `executor.py`; heal only from the driver; **revert-argv scan reads executor.py only** (vacuous risk) | keep driver/door/`_report_rollback` in executor.py; widen the revert-argv scan to every executor-family module (tightening) |
| `tests/consolidation/test_executor_phase_boundary.py` :76-118 | executor does not import the shim; frozen phase-call order via `inspect.getsource` | driver stays; shim-import check extended through `test_merge_compat_surface.py::_SEAM_IMPORT_TARGETS` |
| `tests/consolidation/test_reconciliation.py` :961-982 | claim -> gate -> push -> cleanup order in the driver source | driver stays |
| `tests/consolidation/test_merge_compat_surface.py` :97-310 | `_ORDERING_SYMBOLS` identity re-export; `_SEAM_IMPORT_TARGETS` one-way-import list (vacuous risk for new modules) | map the bake symbol to its new home; add every new module to `_SEAM_IMPORT_TARGETS` |
| `tests/consolidation/test_ordering_bake_seam.py` :32-40 + attribute access | lazy-import AST guard on `ordering`'s source; `ordering._already_baked` etc. | re-point to the new bake module |
| `tests/architectural/test_destructive_op_routing.py` :235-237, :258-270, :426-438 | census keys `(rel, qualname)` for `_recover_behind_head_primary_on_resume` (reset_hard) and two ordering `worktree_remove_force` sites; `guarded_worktree_remove(` substring in executor.py | re-point `rel` / file to the new modules |
| `tests/architectural/_load_meta_census.py` :208-210 | `ACCOUNTED_SITES` for three ordering functions | re-point to the bake module |
| `tests/specify_cli/test_meta_fail_closed_full_census_contract.py` :62-66 | `_WP09_OWNED_FILES` includes executor.py, ordering.py (vacuous risk) | add the modules that receive `load_meta*` sites |
| `tests/architectural/test_no_write_side_rederivation.py` :1363-1364, :135/:159 | `_COORD_WRITER_CENSUS` `(executor.py, _phase_baseline_and_surface)`, `(executor.py, _run_lane_based_consolidation)`; `_WRITE_DIR_CONSUMER_MODULES` scan scope (vacuous risk) | re-point the moved pair; add modules that receive write-dir code |
| `tests/architectural/test_coord_read_residuals_closeout.py` :232-235, :573 | `_STATUS_BEARING_MODULES` (executor.py) for `read_events` feeds (vacuous risk) | add the modules that receive `read_events` calls; keep executor.py (asserted at :573) |
| `tests/architectural/test_exemption_registry_ratchet.py` :79-99 | `CHURN_SURFACE_MODULES` includes executor.py, ordering.py (vacuous risk) | add the receiving modules |
| `tests/architectural/tool_artifact_enrolment/registry/_GATE_ARTIFACT_FILENAMES.md` :20 | `module: .../executor.py`, `symbol: _GATE_ARTIFACT_FILENAMES` | re-point `module:` |
| `tests/architectural/test_status_events_writes_gate.py` :140 | `("specify_cli.consolidation.executor", "write_bytes", "path")` | re-point the dotted module |
| `tests/architectural/test_layer_rules.py` :588-600, :649, :658 | `_MERGE_CLI_CONSOLE_IMPORTERS` allowlist with unlisted-importer and stale-entry guards | list each new `console` importer; drop a stale one |
| `tests/architectural/test_mission_resolver_walker_gate.py` :26 | `_LEGACY_WALKER_ALLOWLIST` file entry for ordering.py | re-point (no second row) |
| `tests/architectural/dead_symbol_allowlist.yaml` :1099-1104 | `specify_cli.consolidation.ordering::_already_baked`, `::_is_assigned_mission_number` | re-point `module:` |
| `tests/architectural/untrusted_path_audit/inventory.md` :65-66, :103, :170 | rows keyed `(rel, qualname, token)` for `_compute_next_mission_number_or_none` | re-point the locator; record the relocation in the rationale |
| `tests/specify_cli/cli/commands/test_commit_recipes.py` :74-77 | `("consolidation/ordering.py", "git commit failed on the primary checkout")` | re-point |
| `pyproject.toml` :2694 | mypy quarantine for `specify_cli.consolidation.ordering` | do not quarantine new modules; make moved code strict-clean |
| Package-level globs (`ci-router.yml:156`, `scripts/ci/aggregate_source.py:24`, coverage guards, `test_single_blob_reader.py`, `test_merge_state_authority.py:628`) | glob `consolidation/**` | none; new modules are picked up |

No gate requires per-module registration of a new consolidation module.
Observed but out of scope: `test_coord_read_residuals_closeout.py` :108-112/:568
still names the retired `specify_cli/merge` path (pre-existing; reported, not fixed here).

## 4. Test seams and their cost

Unit/seam files per phase (test counts by `def test_`):

- **Claim:** `test_claim_integrity_refusal.py` (10), `test_executor_phase_boundary.py` (12), `test_executor_terminus_integrity.py` (17), `test_fresh_record_cleared_on_pre_mutation_exit.py` (15), `test_executor_rollback_wiring.py` (28).
- **Lane advance:** `test_executor_coverage.py` (57), `test_issue_4764_terminus_safety.py` (6), `test_merge_canceled_wp.py` (3), `test_canceled_dependency_lane.py` (26), `tests/specify_cli/consolidation/test_single_branch_mission_to_target.py` (13), `test_single_branch_bookkeeping_only.py` (12).
- **Gate:** `test_reconciliation.py` (120), `test_refuse_restores_target.py` (5), `test_merge_state_authority.py` (31), `test_squash_reconcilers_2709.py` (11).
- **Rollback door:** `test_rollback_authority.py` (29), `test_single_rollback_authority.py` (19), `test_executor_rollback_wiring.py` (28), `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py` (16).
- **Projection/bookkeeping:** `test_bookkeeping_projection_seam.py` (17), `test_done_bookkeeping_seam.py` (44); birth cutover is thin (`tests/specify_cli/migration/test_backfill_migration_coexistence.py`, 5).
- **Teardown:** `tests/coordination/test_projection_teardown.py` (29; the only unit for `_land_late_coordination_commits`), `test_coord_teardown_order_3926.py` (2), `test_coordination_flatten_on_branch_delete.py` (3), `test_executor_lane_naming.py` (28).
- **Resume:** `test_resume_coord_lag.py` (30), `test_behind_head_recovery_coverage.py` (21), `test_resume_strategy_authority.py` (24), `test_user_meta_json_dirty_4933.py` (8), `test_executor_ledger_preflight.py` (7).

Slow e2e that only replays unit-pinned behaviour (ledger in #5618, with
planted-break evidence B1-B9): `terminus/test_abort_restores_snapshot.py`
(9 tests, 251 s), `test_canceled_dependency_content_refused.py` (150 s),
`test_rollback_restores_refs.py` (125 s), `test_mixed_lane_canceled_content_controls.py`
(94 s), `test_claim_refusal_before_mutation.py` (61 s),
`test_mixed_lane_canceled_content_verdicts.py` (51 s). Keeps:
`test_mixed_lane_closed_world.py`, `test_planning_claim_never_lands_code_on_target.py`,
the `test_repro_*` files. `tests/lanes/` contains no executor replay.

**Biggest move risk: monkeypatch targets.** About 493 patches across 48 test
files target `specify_cli.consolidation.executor.<name>` (top:
`test_executor_coverage.py` 82, `tests/integration/test_merge_lane_planning_data_loss.py` 41,
`test_executor_phase_boundary.py` 34, `test_behind_head_recovery_coverage.py` 30,
`tests/integration/sparse_checkout/test_merge_refresh_and_invariant.py` 29). A
patch on `executor.X` no longer intercepts a call made from a function that
moved to another module; it fails loudly only if `X` vanished from `executor`,
and otherwise the test silently runs the real collaborator. Each patch must be
re-pointed to every module that now looks `X` up (computed mechanically from
the AST, so the re-pointed set is exactly the old interception set). 129 patches
in 34 files target `cli.commands.consolidate.<name>` and 41 (one file) target
`consolidation.ordering.<name>`.

## 5. Interaction with #5613 (open P0) and PR #5633

PR #5633 (the #5613 fix, open) edits `executor.py` (+283/-87),
`reconciliation.py` (+715), `wp_attribution.py`, `preflight.py`,
`coordination/`, `git/ref_advance.py`, `orchestrator_api/commands.py`. Its
executor hunks fall in: the error classes after `CoordinationTeardownError`
(:220), `_mission_branch_tip` / `_tip_moved_teardown_error` (:2905-2932),
`_pre_mutation_safety_preflight` (:3489-3580), and the refusal/recovery family
`_synthesize_no_lane_manifest` .. `_pre_mutation_safety_preflight_with_recovery`
(:3898-4298).

Mapping of the five #5613 gaps onto the planned split:

| #5613 gap | Code it touches | Home after the split |
|---|---|---|
| 1 presence axis (`APPROVED_CONTENT_MISSING`) | `reconciliation.py` + gate wiring | `reconciliation.py` (unchanged) + the gate module |
| 2 coord status-surface write guard | `coordination/` | outside consolidation (unchanged) |
| 3 lag recovery for every checkout | lag classifier, refusal advice, behind-HEAD reset, entry preflight | the resume-recovery module + the entry-preflight module |
| 4 superseded canceled dependency | `wp_attribution.py` / `reconciliation.py` | unchanged |
| 5 stable refusal codes | `_constants.py`, teardown refusal text | `_constants.py` + the teardown module |

So gaps 3 and 5 land in two small, separately testable modules instead of a
4,600-line file. The split will textually conflict with #5633's executor hunks;
the resolution is mechanical (apply each hunk to the function's new module, no
logic change). Merge order is the operator's call; the PR says so. This mission
does not touch the `p0_repro` marker or any #5613 reproduction.

## 6. Churn and fix history (90 days, GitHub API; local clone is shallow)

| File | Commits | Notes |
|---|---|---|
| `executor.py` (incl. former `merge/executor.py`) | 93 | 57 fix, 14 feat, 9 refactor; ~45 in the last week |
| `ordering.py` | 15 | |
| `consolidate.py` (incl. former `merge.py`) | 31 | |

Most-cited issues in executor commits: #5100 x7 (single_branch landing),
#5570 x5 (teardown tip CAS), #5111 x5 (transaction record), #5353 x3, then
#5572, #5001, #4933, #4900, #4753, #3086, #2709, #2711 x2 each. Hottest
functions by commits touching their hunks: `_MergeRunState` 17, the locked
driver 11 (+12/+13 under its former `_run_lane_based_merge*` names),
`_phase_commit_and_assert` 9, `_pre_mutation_safety_preflight` 8,
`_phase_cleanup_worktrees_and_branches` 8, `_phase_bake_and_pre_target_done` 8,
`_report_pre_mutation_refusal` 7, `_phase_merge_lanes` 7,
`_handle_mission_merge_result` 7, `_flatten_coordination_metadata_after_branch_delete` 7.
The seams keep breaking at: rollback/transaction-record coherence, teardown and
the coordination lifecycle, single_branch topology, claim integrity, resume.
Those are exactly the phase boundaries the split follows.
