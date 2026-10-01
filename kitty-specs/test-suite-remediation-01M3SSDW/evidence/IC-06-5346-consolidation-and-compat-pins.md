# IC-06 — #5346 pins: consolidation trio + compat surface and copied literals (WP06 + WP07)

Per tasks.md closeout step 1 (analysis C5), this concern merges WP06's reported evidence
(scratchpad `WP06-evidence-5346-consolidation-trio.md`, cycle-1 commit `49c48466f7`, and the
cycle-2 fold `WP06-cycle2-evidence.md`, commit `b96bb33355`) with WP07's reported evidence
(scratchpad `wp07/evidence.yaml`), and both WPs' full approval notes (`status.events.jsonl`,
`review_ref: auto-approval:WP06:20260930` and `auto-approval:WP07:20260930` — considerably
more itemized than the one-line `review-cycle-*.md` files). WP06 cycle 1 was rejected on one
blocking issue (row 6's `mission_branch` threading gap); the fold in cycle 2 closed it, and
the cycle-2 approval note itself (not just the review-cycle file, which was a plain
one-liner) itemizes the reviewer's re-run of that fold. WP07 was approved cycle 1.

## Row #5346-3 — RETIRE `TestWorktreeTeardownSeamRouting` (WP06)

```yaml
id: EV-IC06-03
item: "#5346-3"
kind: RETIRE
planted_break:
  target: "src/specify_cli/consolidation/executor.py::_created_lane_worktree"
  description: >
    made _created_lane_worktree compose its own diverging path
    (Path(path).with_name(Path(path).name + "-PLANT")) instead of returning the allocator's
    predict_lane_worktree(...) output unchanged.
  reverted: true
command: >
  uv run --frozen pytest
  tests/consolidation/test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output
  tests/consolidation/test_mid8_embedded_preflight.py::TestWorktreeTeardownSeamRouting -n0 -q
results:
  old_form_under_break: "pass — the two retired tests stayed GREEN under the break (they never call _created_lane_worktree; they guard nothing the covering guard misses)"
  new_form_under_break: n/a   # RETIRE: no new form; the class is deleted
  neutral_plant: "pass — src/specify_cli/lanes/branch_naming.py::worktree_dir_name changed to f'{mission_slug}--{lane_id}' (double-hyphen): covering guard stayed GREEN (1 passed), the two retired tests went RED (2 failed) — proving the toll"
  clean_tree: pass
covering_guard:
  node_id: "tests/consolidation/test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output"
  under_break: fail   # AssertionError: ...-lane-a-PLANT != ...-lane-a
counts:
  executed_before: 81   # named-file run: test_mid8_embedded_preflight.py + test_executor_lane_naming.py + test_branch_naming_seam.py
  executed_after: 79    # RK-1 sanctioned drop of 2 (the retired tests)
reviewer_rerun: true
notes: >
  Reviewer re-run (WP06 cycle-1 "Verified" section): "Violation (_created_lane_worktree
  returns ...-PLANT): the covering guard ... is RED (1 failed), and the retired class ...
  is GREEN (2 passed). Neutral (worktree_dir_name -> f'{slug}--{lane}'): the guard is GREEN
  (1 passed), and the retired class is RED (2 failed). It was a toll. RK-1 drop sanctioned."
  Tallied as one of the SC-005 RETIRE re-runs in evidence/README.md.
```

## Row #5346-4 — FIX (rename + re-scope) unreachable-primary test (WP06)

```yaml
id: EV-IC06-04
item: "#5346-4"
kind: FIX
planted_break:
  target: "src/specify_cli/consolidation/ordering.py::_bake_mission_number_into_mission_branch"
  description: "Violation A: added `if not wrote: return None` before the final `return next_number`, reinstating the pre-#4900 fail-open discard of the computed mission_number on the unreachable-primary path"
  reverted: true
command: >
  uv run --frozen pytest
  tests/consolidation/test_issue_4474_topology_aware_bake.py::test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it
  -n0 -q
results:
  old_form_under_break: "n/a — FIX is a rename/re-scope, not a value change; the OLD test body (same assertions) also reds under Violation A"
  new_form_under_break: "fail — AssertionError at `assert result == 1 ...`: assert None == 1"
  clean_tree: pass
counts:
  executed_before: 12
  executed_after: 12
reviewer_rerun: true
notes: >
  Second planted break (Violation B, proving the covering guard for the refusal half named
  in the renamed test's docstring): ordering.py::_bake_mission_number_onto_target_tree edited
  so `if meta is None:` sets `meta = {}` instead of raising MissionNumberVerificationError.
  Command: `uv run --frozen pytest
  tests/consolidation/test_mission_number_truthful_4900.py::test_absent_target_meta_refuses_instead_of_fabricating -n0 -q`.
  Result: RED — "Failed: DID NOT RAISE <class 'click.exceptions.Exit'>" (the executor silently
  proceeds instead of refusing). Both ordering.py edits reverted independently with
  `git checkout --` before the real commit. Test renamed to
  test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it; docstring rewritten
  to state the actual seam contract and name the covering guard. No value change:
  `assert result == 1` unchanged. Message-fragment tightening evaluated and NOT applied
  (the only f-string field, mission_slug, is already asserted independently; the rest is
  plain prose, not a named constant). Reviewer re-run (cycle-1 "Verified"): "Violation A ...
  turns the renamed test RED at assert result == 1 (None == 1). The docstring names the 4900
  refusal guard." Tallied as one of the SC-005 FIX re-runs in evidence/README.md.
```

## Row #5346-6 — FIX identity asserts instead of full-signature pins (WP06, cycle 1)

```yaml
id: EV-IC06-06
item: "#5346-6"
kind: FIX
planted_break:
  target: >
    src/specify_cli/consolidation/executor.py::_report_pre_mutation_refusal (~:3897),
    _recover_behind_head_primary_on_resume (~:3971), and their call sites in
    _pre_mutation_safety_preflight_with_recovery (~:4059-4090)
  description: >
    Neutral (M2): added a new defaulted keyword-only parameter `strategy: str | None = None`
    to BOTH functions, passed `strategy=None` explicitly at all three call sites.
  reverted: true
command: "uv run --frozen pytest tests/consolidation/test_behind_head_recovery_coverage.py -n0 -q"
results:
  old_form_under_break: "fail — 6 failed / 15 passed under the M2 neutral plant: the 5 full-signature assert_called_once_with(...) pins on _report_pre_mutation_refusal, plus the 1 on _recover_behind_head_primary_on_resume, all tripped by the new strategy=None kwarg appearing in call_args even though nothing else about the call changed"
  new_form_under_break: "pass — 21 passed, 0 test edits needed once the FIX (identity asserts) was in place"
  neutral_plant: pass
  clean_tree: pass
counts:
  executed_before: 21
  executed_after: 21
reviewer_rerun: true
notes: >
  VIOLATION plant (separate, reverted independently): first _report_pre_mutation_refusal call
  site's `base_sha=state.pre_mutation_target_sha if state else None` hardcoded to `base_sha=None`.
  Command: `uv run --frozen pytest
  tests/consolidation/test_behind_head_recovery_coverage.py::test_preflight_with_recovery_threads_persisted_pre_mutation_target_sha_as_base_sha -n0 -q`.
  Result: RED — AssertionError: assert None == 'cafef00d...' at the kept threading assertion
  (proves the #4933 contract is still enforced). Reviewer re-run (cycle-1 "Verified"): "Row 6:
  Threading plant (base_sha=None at :4066): the kept assertion is RED (1 failed, 20 passed).
  M2 neutral plant: the new form is GREEN (21 passed). The old form is RED (6 failed), and
  GREEN again after reverting src." Tallied as one of the SC-005 FIX re-runs in evidence/README.md.
```

## Row #5346-6 fold — `mission_branch` threading guard (WP06, cycle 2; C-002)

```yaml
id: EV-IC06-06b
item: "#5346-6 (cycle-2 fold)"
kind: FIX
planted_break:
  target: "src/specify_cli/consolidation/executor.py::_pre_mutation_safety_preflight_with_recovery call sites at :4060, :4066, :4077"
  description: >
    reviewer's cycle-1 plant, reproduced one call site at a time: replaced
    mission_branch=lanes_manifest.mission_branch with
    mission_branch=lanes_manifest.target_branch at each of the three call sites.
  reverted: true
command: >
  uv run --frozen pytest
  tests/consolidation/test_behind_head_recovery_coverage.py::test_preflight_with_recovery_recovers_and_retries_successfully
  tests/consolidation/test_behind_head_recovery_coverage.py::test_preflight_with_recovery_reports_and_exits_when_not_recovered
  tests/consolidation/test_behind_head_recovery_coverage.py::test_preflight_with_recovery_reports_and_exits_when_still_refused_after_recovery
  -n0 -q
results:
  old_form_under_break: "n/a — cycle-1 form had no assertion to red at these call sites; that was exactly the gap the reviewer found"
  new_form_under_break: "fail — each of the 3 single-site plants reds its corresponding new assertion: AssertionError: assert 'main' == 'kitty/mission-m', one failure per site"
  neutral_plant: "pass — M2 strategy=None re-run: 21 passed, 0 further test edits"
  clean_tree: pass
counts:
  executed_before: 21
  executed_after: 21
reviewer_rerun: true
notes: >
  Correction (coordinator-flagged undercount): the one-line `review-cycle-2.md` file is not
  the full record — the underlying `status.events.jsonl` approval event
  (`review_ref: auto-approval:WP06:20260930`) carries the reviewer's full itemized re-run:
  "Re-runs, one plant at a time, all reverted, git diff --stat empty:
  mission_branch=lanes_manifest.target_branch at executor.py:4060 -> RED (1 failed:
  recovers_and_retries_successfully); at :4066 -> RED (1 failed:
  reports_and_exits_when_not_recovered); at :4077 -> RED (1 failed:
  reports_and_exits_when_still_refused_after_recovery). M2 neutral plant (strategy=None
  defaulted kwarg on both callees, passed at all 3 call sites) -> GREEN 21 passed, 0 test
  edits." This is exactly this record's three single-site plants plus its neutral plant,
  reproduced independently by the reviewer. Tallied in evidence/README.md. Added one
  keyword-lookup value assertion per call site (never a full-signature pin): recovers test
  asserts `mock_recover.call_args.kwargs["mission_branch"] == manifest.mission_branch`;
  both report tests assert the equivalent on `mock_report.call_args.kwargs["mission_branch"]`.
  Named-file re-run (6 files): 130 passed, 1 pre-existing warning, unchanged from cycle 1.
  Optional base_sha threading guard at the second _report_pre_mutation_refusal call site
  (:4077/exc_after) left unaddressed: reviewer marked it non-blocking, pre-existing, out of
  row-6 scope.
```

## Named-file verification (WP06, 6 files, after both cycles)

`uv run --frozen pytest tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_behind_head_recovery_coverage.py tests/consolidation/test_executor_lane_naming.py tests/consolidation/test_mission_number_truthful_4900.py tests/lanes/test_branch_naming_seam.py -n0 -q` -> `130 passed, 1 warning` (pre-existing legacy-branch-grammar DeprecationWarning, unrelated).

---

## Row #5346-2 — RETIRE copy pin (`== 196`) + floor/superset guards (WP07)

```yaml
id: EV-IC06-02
item: "#5346-2"
kind: RETIRE
planted_break:
  target: "tests/specify_cli/cli/commands/agent/tasks_move_task.py + test_tasks_compat_surface.py::_TASKS_MOVE_TASK"
  description: "neutral plant: add _mt_new_helper + tuple entry + tasks.py re-export (registered consistently across all three registries)"
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py -n0 -q"
results:
  old_form_under_break: "RED — test_guard_covers_full_167_symbol_surface: assert 197 == 196"
  new_form_under_break: "GREEN — 397 passed (0 additional test edits beyond the inherent tuple registration)"
  clean_tree: "GREEN — 395 passed"
counts: {executed_before: 395, executed_after: 395}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP07:20260930): "T028 neutral (_mt_new_helper
  def+tuple+re-export) new form 397 passed, old form RED 197==196; V1 drop tuple entry RED
  superset :465; V2 non-native name RED :455+:432; V3 cross-tuple duplicate collection ERROR
  (disjoint raise); V4 drop tasks.py re-export RED :432; floor (empty _TASKS_FINALIZE) RED the
  new floor test plus :465" — the neutral plant and all 4 violation plants plus the floor
  plant recorded here, reproduced independently and reverted clean. Tallied in
  evidence/README.md. 4 violation plants, each reverted independently, all against the covering-guard battery:
  (1) drop tuple entry, keep native def -> RED (test_guard_keyset_is_superset_of_all_six_seams_native_defs:
  missing=['_mt_apply_owned_targets']); (2) register a name the seam does not define -> RED,
  2 failed (test_guard_symbol_is_genuinely_native_to_its_seam + test_tasks_binding_is_seam_object);
  (3) duplicate symbol across two seam tuples -> COLLECTION ERROR (module-level SYMBOL_TO_MODULE
  construction raises AssertionError: claimed by both seams); (4) drop tasks.py re-export, keep
  tuple+native def -> RED (test_tasks_binding_is_seam_object: tasks._mt_apply_owned_targets no
  longer resolves). Floor plant: empty one seam tuple (_TASKS_FINALIZE = ()) -> RED
  (test_every_seam_group_declares_at_least_one_symbol). All reverted; GREEN (395 passed) each time.
```

## Row #5346-5 — `:481` FIX / `:490` RETIRE / `:494` FIX (WP07)

Split into 3 records matching WP07's own `evidence.yaml` granularity (it lists `:481`,
`:490` and `:494` as three distinct items under the shared pin id `#5346-5`), so each can
carry its own `kind` for the SC-005 tally.

```yaml
id: EV-IC06-05a
item: "#5346-5 (:481)"
kind: FIX
planted_break:
  target: "scripts/ci/recapture_charter_shard_timings.py::PR_BODY_TEMPLATE"
  description: "drop the {after} placeholder from PR_BODY_TEMPLATE"
  reverted: true
command: "uv run --frozen pytest tests/ci/test_recapture_charter_shard_timings.py -n0 -q -k test_pr_body_template_renders_substitutions_and_names_timings_file"
results:
  new_form_under_break: "RED — test_pr_body_template_renders_substitutions_and_names_timings_file: assert '105' in body (fails)"
  clean_tree: "GREEN — 79 passed"
counts: {executed_before: 79, executed_after: 79}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP07:20260930): "T029: drop {after} RED new
  PR-body test" — exactly this record's planted break, reproduced independently. Tallied in
  evidence/README.md.
```

```yaml
id: EV-IC06-05b
item: "#5346-5 (:490)"
kind: RETIRE
planted_break:
  target: "scripts/ci/recapture_charter_shard_timings.py::_push_and_open_pr"
  description: "--title receives a different string than COMMIT_MESSAGE"
  reverted: true
command: "uv run --frozen pytest tests/ci/test_recapture_charter_shard_timings.py -k test_push_and_open_pr_runs_git_and_gh_with_expected_arguments -n0 -q"
covering_guard:
  node_id: "test_push_and_open_pr_runs_git_and_gh_with_expected_arguments:341"
  under_break: fail   # assert calls[3][...] == recapture.COMMIT_MESSAGE (fails)
results:
  neutral_plant: "GREEN — 78 passed under a wording-tweak-only plant (the retired verbatim test would have reded here; the covering guard does not)"
  clean_tree: "GREEN — 79 passed"
counts: {executed_before: 79, executed_after: 79}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "--title != COMMIT_MESSAGE RED :341; git commit -m !=
  COMMIT_MESSAGE RED :336; COMMIT_MESSAGE reworded new 79 passed, old RED" — both the
  covering-guard violation (:341 and the related :336 assertion) and the neutral
  wording-tweak plant recorded here, reproduced independently. Tallied in evidence/README.md.
```

```yaml
id: EV-IC06-05c
item: "#5346-5 (:494)"
kind: FIX
planted_break:
  target: "scripts/ci/recapture_charter_shard_timings.py::run_capture_phase"
  description: "run_capture_phase passes a wrong --module argv"
  reverted: true
command: "uv run --frozen pytest tests/ci/test_recapture_charter_shard_timings.py -k test_run_capture_phase_invokes_capture_shard_timings_with_module_charter -n0 -q"
results:
  new_form_under_break: "RED — test_run_capture_phase_invokes_capture_shard_timings_with_module_charter: seen[0][:2] == ['--module','specify_cli'] != ['--module','charter']"
  neutral_plant: "GREEN — 79 passed (0 test edits) under a constant-rename-only plant (MODULE -> TARGET_MODULE)"
  clean_tree: "GREEN — 79 passed"
counts: {executed_before: 79, executed_after: 79}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "T030: --module specify_cli RED new argv recorder (sole
  guard, so FIX not RETIRE is right); MODULE->TARGET_MODULE rename new 79 passed, old RED" —
  both the violation and the neutral rename plant recorded here, reproduced independently.
  Tallied in evidence/README.md.
```

## Row #5346-7 — FIX mission_type teardown seam routing (WP07)

```yaml
id: EV-IC06-07
item: "#5346-7"
kind: FIX
planted_break:
  target: "src/specify_cli/cli/commands/consolidate.py::_teardown_coordination_for_abort"
  description: "violation plant: replaced the teardown_coordination_topology(...) seam call with an inline CoordinationWorkspace.teardown(main_for_abort, coord_slug, mid8) call"
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/coordination/test_teardown_single_seam_routing.py -n0 -q"
results:
  neutral_plant: "GREEN — 6 passed (same-module extraction of _teardown_coordination_worktree's body into an _impl, original becomes a thin delegator)"
  new_form_under_break: "RED (2 failures) — test_consolidate_abort_routes_teardown_through_the_seam (recorder never called) AND test_zero_production_teardown_calls_outside_the_seam (literal-scan guard also catches the reintroduced direct call)"
  clean_tree: "GREEN — 4 passed (test_teardown_single_seam_routing.py alone)"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP07:20260930): "T031: inline
  CoordinationWorkspace.teardown in _teardown_coordination_for_abort RED recorder + :81; the
  same in mission_type RED recorder + :81; seam imported but never called in consolidate: new
  RED, OLD literal scan GREEN (proves the trap); persist=True RED; aliased primitive
  (CW.teardown) :81 green but recorder RED; neutral same-module helper extraction green (6
  passed)." This covers both the recorded neutral/violation plants and additional reviewer-run
  variants (mission_type's own inline-teardown plant, the "seam imported but never called"
  trap, a persist=True plant, and an aliased-primitive plant) not separately itemized in the
  WP's own evidence.yaml. Tallied in evidence/README.md.
```

## Final named-file run (WP07) / quality gates

`uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/ci/test_recapture_charter_shard_timings.py tests/specify_cli/coordination/test_teardown_single_seam_routing.py tests/specify_cli/cli/commands/test_mission_close_teardown_message.py -n0 -q` -> `480 passed`.
Skip hygiene (WP07 owned files): no hits. `ruff check` -> All checks passed!; `ruff format --check` -> 2 files already formatted (the third is format-excluded). `git diff --stat src/ scripts/` empty before final commit. `make test-fast` -> `2169 passed, 5 skipped, 4 warnings in 264.67s`, exit 0.

(WP06's own quality gates: `ruff check` on the 3 owned files -> All checks passed!; `ruff format --check` -> 3 files already formatted; skip-hygiene grep 0 hits; `git diff --stat src/` empty at every commit point in both cycles.)
