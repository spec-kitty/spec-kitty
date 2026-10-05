# Grounding: test-suite remediation analysis for `implement.py` decomposition (#5635, #5232)

> Mission research note for `implement-degod-01M44488`: the verbatim report of the pre-spec
> test-suite remediation lens (profile `python-pedro`, procedure `test-suite-quality-assessment`).
> The orchestrator's synthesis and decisions live in [`code-grounding.md`](code-grounding.md) §2.
> `scratchpad/...` references name session-local working files that are not committed; every
> count here is reproducible from the commands quoted next to it.


Revision: origin/main `9adc6880`. Read-only grounding; no repo file edited.
`src/specify_cli/cli/commands/implement.py` = 2304 lines; sibling `implement_cores.py` = 854 lines
(already the pure-core half of an earlier trio decomposition, coord-authority-trio-degod).

## 0. Governance applied

- Profile: `python-pedro` (implementer; TDD, pytest/ruff/mypy gate; no architectural decisions).
  `researcher-robbie` checked: its findings-synthesis focus fits, but this is a pytest-corpus
  remediation lens, so Pedro's test-design expertise was applied with Robbie's evidence discipline
  (exact reproducible commands, measured not estimated).
- `spec-kitty charter context --action plan --json` loaded (DIRECTIVE set incl. 030/034/036/041/043;
  USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY; NO_FULL_HEAVY_SUITES_IN_MISSION).
- Procedure `test-suite-quality-assessment` (packs/internal) followed: scope fixed, static triage via
  asset `packs/internal/assets/test-quality-scan.py` (runs no tests), per-file verdicts against Test
  Desiderata, planted-break requirement carried into the plan (section 5). Toolguide
  `test-quality-triage` flags used as candidates only, never verdicts.
  Static scan output: `scratchpad/tq/` (summary.md, files.json, tests.json, ledger/).
  Command:
  `python3 packs/internal/assets/test-quality-scan.py --paths <66 files> --out <scratch>/tq --top 70 --no-git`
  -> scanned 66 files, 673 tests, 157 flagged (mostly provenance-tokens).

## 1. Inventory

Command (as specified):
`grep -rln "commands.implement\|commands import implement\|from specify_cli.cli.commands.implement" tests`
-> 68 hits = 65 .py + 3 data files (`tests/architectural/dead_symbol_allowlist.yaml`,
`tests/release/coverage_breadth_baseline.json`,
`tests/architectural/tool_artifact_enrolment/registry/_is_self_write_only_diff.md`).
One extra path-pinned gate the grep misses: `tests/architectural/test_wp_integrity_partition_call_shape.py`
(`_IMPLEMENT = ... "implement.py"`). A further 17 files mention `implement.py` only in prose/docstrings
(not load-bearing).

The files fall in five relationship classes (this is what matters for the decomposition):

| Class | What it couples to | Files |
|---|---|---|
| A. Orchestrator-through-`implement()` with string patches | module globals of implement.py | agent/test_implement_command.py (54 patch strings), integration/test_status_emit_on_alloc_failure.py (9), specify_cli/lanes/test_lane_base_honoring.py (8), cli/test_implement_bulk_edit_planning.py (6), cli/commands/test_implement_base_flag.py (5), specify_cli/cli/commands/test_implement_vcs_lock_claim.py (5), .../test_implement_runtime_frontmatter_claim.py (5), specify_cli/test_specify_topology_flag.py (2) |
| B. Orchestrator-through-`implement()` with object patches / CliRunner | module alias attrs | agent/cli/commands/test_implement_preflight.py, .../test_implement_json_safe_output.py, .../test_implement_writeside.py, .../test_wp06_sc2_paused_mission_blockers.py, .../test_implement_coord_idempotency.py, integration/test_wp_integrity_crash_recovery.py, .../test_single_branch_implement_refusals.py, .../test_implement_bulk_edit_flag.py, agent/test_mission_handle_json_errors.py, agent/test_context_validation_unit.py, agent/test_implement_programmatic_call.py, specify_cli/test_operational_context_wiring.py, specify_cli/cli/commands/test_implement.py, .../test_implement_placement_routing.py, .../test_coordination_remedy_5113.py, cli/commands/test_resolve_lanes_dir.py |
| C. Direct imports of private helpers (seam-unit already, wrong home) | `from ...implement import _helper` | 40 distinct symbols imported across ~30 files (see `scratchpad/imports.txt`); top: `_ensure_planning_artifacts_committed_git` (8 files), `_commit_planning_artifacts_transaction` (4), `_protected_branch_status_commit_error` (3), `_feature_dir_file_paths` (3) |
| D. Source-path / source-text census pins | the literal path `src/specify_cli/cli/commands/implement.py` or its text | architectural: test_trio_seam_only, test_wp_integrity_partition_call_shape, test_no_write_side_rederivation (line-scoped allow-list keyed on implement.py), test_exemption_registry_ratchet, test_safe_commit_import_boundary, test_planning_lane_branch_requires_target, test_git_matrix_paths_resolve; contract: test_terminology_guards, test_feature_alias_scope; specify_cli: status/test_cutover_byte_stability, test_mid8_contract_sensitive_routing, test_meta_fail_closed_full_census_contract, regression/test_issue_1615_1616_1617_1618, lanes/test_lane_context_single_writer, bulk_edit/test_diff_check; data: dead_symbol_allowlist.yaml, coverage_breadth_baseline.json |
| E. Real-git integration / e2e via helpers | real repos, real lanes | integration/test_wp_integrity_{p0_repro,cross_partition_scan,checkout_identity,crash_recovery}, test_issue_3784_..., lanes/test_issue_2993_..., lanes/test_lane_allocation_integrity_e2e, coordination/test_ledger_topology_less_callers, specify_cli/coordination/test_flat_legacy_none_seam_success_arms, git/test_guard_capability_regression, git/test_protection_policy_mission_scope, specify_cli/test_meta_fail_closed_full_census_contract |

Per-file test count, runtime and kind: see section 6 (baseline table, measured per file).

## 2. Patch-target census (re-measured; the issue said 93)

### 2a. String targets
Reproducible:
```
grep -rnoE "[\"']specify_cli\.cli\.commands\.implement\.[A-Za-z_]+" tests --include='*.py' | wc -l   # -> 94
grep -rhoE "[\"']specify_cli\.cli\.commands\.implement\.[A-Za-z_]+" tests --include='*.py' \
  | sed -E "s/^[\"']specify_cli\.cli\.commands\.implement\.//" | sort | uniq -c | sort -rn
```
**94 occurrences, 15 distinct targets, 8 files.** (93 + 1 drift since the issue was filed.)

| count | target | defined in | seam it belongs to |
|---:|---|---|---|
| 15 | find_repo_root | task_utils (imported) | shell: repo-root discovery |
| 15 | detect_feature_context | implement.py | context resolution (mission handle) |
| 14 | resolve_feature_target_branch | implement.py | context resolution (target branch) |
| 12 | create_lane_workspace | lanes.implement_support (imported) | allocate/reuse lane |
| 12 | _ensure_planning_artifacts_committed_git | implement.py | planning-artifact commit phase |
| 8 | _ensure_vcs_in_meta | implement.py | VCS lock (mission_metadata.set_vcs_lock) |
| 6 | start_implementation_status | status (imported) | record claim (status pipeline) |
| 3 | resolve_workspace_for_wp | workspace.context (imported) | resolve workspace |
| 2 | find_wp_file | implement.py | context resolution |
| 2 | _resolve_placement_ref | implement_cores (re-exported shim) | C-004 fallback -> removed by #5232 |
| 1 | get_current_branch | core.git_ops (imported) | status-commit destination |
| 1 | _report_workspace_created | implement.py | presenter |
| 1 | _print_workspace_ready_banner | implement.py | presenter |
| 1 | _commit_wp_claim_status | implement.py | record claim (commit) |
| 1 | ProtectionPolicy | git.protection_policy (imported) | protected-branch policy |

Per-file: test_implement_command.py 54 | test_status_emit_on_alloc_failure.py 9 | test_lane_base_honoring.py 8 |
test_implement_bulk_edit_planning.py 6 | test_implement_vcs_lock_claim.py 5 | test_implement_runtime_frontmatter_claim.py 5 |
test_implement_base_flag.py 5 | test_specify_topology_flag.py 2.

### 2b. Object-style patches (AST, script `scratchpad/objpatch.py`)
`monkeypatch.setattr(<alias>, "x", ...)` / `patch.object(<alias>, "x", ...)` where `<alias>` is bound to
the implement module (import-as, from-import, import_module): **18 occurrences, 7 distinct, 6 files**.
find_repo_root 6, detect_feature_context 4, create_lane_workspace 2, _load_primary_anchored_mission_meta 2,
_run_planning_artifact_commit 2, resolve_topology 1, _commit_planning_artifacts_transaction 1.
Files: test_implement_preflight.py 6, test_implement_json_safe_output.py 6, test_implement_writeside.py 2,
test_wp_integrity_crash_recovery.py 2, test_wp06_sc2_paused_mission_blockers.py 1, test_implement_coord_idempotency.py 1.
Plus **5** `patch.object(impl_mod.console, "print", ...)` / `impl_mod.console.capture()` output-capture
couplings (test_implement_base_flag x2, test_lane_base_honoring, test_issue_610, test_implement_writeside).

### 2c. Totals
**112 patch sites into implement.py's namespace (94 string + 18 object), 19 distinct targets**
(union), + 5 console couplings, + 40 distinct private symbols imported directly from implement.py
(9 of them are only re-exported there from implement_cores via a `# noqa: F401 -- shim re-export`).
Inbound seam-level patching today is near zero: `specify_cli.lanes.implement_support.*` 0,
`workspace.context.*` 5, `core.dependency_graph.*` 2, `implement_cores.*` 1.

**Hazard (load-bearing for the refactor):** `unittest.mock.patch("pkg.implement.X")` patches the name
in implement.py's globals. Once the orchestrator body moves to another module that imports `X` itself,
every such patch becomes a silent no-op *while the attribute still exists* (re-exports keep it alive).
Tests then either hit real I/O and fail noisily (good), or pass for the wrong reason (bad). Mitigation
in section 5: delete re-exports in the same WP that moves a call site, so stale patches raise
`AttributeError` (mock's default `create=False`).

## 3. Classification

### Pinning internals (call graph), not behaviour
- agent/test_implement_command.py `TestImplementCommand` (7 tests, lines 162-627): every test stubs 5-9
  collaborators (repo root, context, target branch, planning commit, VCS lock, allocator, status) and
  asserts on MagicMock interactions (`create_lane_workspace.assert_called_once` etc.). These are
  orchestrator-sequencing tests written against the module namespace. Behaviours they really own:
  JSON payload shape, dependency gate precedes allocation, protected-target coord commit allowed,
  execution_mode threading, planning-lane allowance.
- cli/test_implement_bulk_edit_planning.py (3): the behaviour is `_run_bulk_edit_gate_and_inference`'s
  verdict; it is proved through `implement()` with 6 patches + `assert_called_once/not_called`.
- integration/test_status_emit_on_alloc_failure.py (2): marked integration but fully stubbed (9 patches);
  owns the F-50 "no blocked emission on alloc failure" contract.
- test_implement_vcs_lock_claim.py / test_implement_runtime_frontmatter_claim.py (5 patch strings each,
  shared helper): own the "implement writes 0 runtime bytes to WP file / VCS lock claim" contracts.
- test_lane_base_honoring.py (8 patches incl. `_resolve_placement_ref -> None`).
- specify_cli/cli/commands/test_implement_writeside.py and test_implement_coord_idempotency.py patch
  private planning-commit internals (`_load_primary_anchored_mission_meta`,
  `_commit_planning_artifacts_transaction`) via the module alias.
- Source-text pins (class D) are by design form-coupled (architectural ratchets); they are not defects
  but they are a **mandatory edit list** for every WP that moves code out of implement.py.

### Slow e2e that could become seam units
Measured (section 6): the real-git integration files dominate wall time. The decision logic they
exercise mostly sits in `_commit_planning_artifacts_transaction` / `_partition_files_for_commit` /
`_guard_planning_commit_partition` (pure partition decisions) and could be proven with pure units over
`_partition_files_for_commit` + one real-git smoke per partition family. Keep the P0 repros
(test_wp_integrity_p0_repro, cross_partition_scan) as the behaviour-family smokes.

### Vacuous / mis-attributed / duplicated
- **CONFIRMED VACUOUS** `tests/agent/test_implement_command.py:163`
  `test_implement_requires_lanes_json`: asserts only `pytest.raises(typer.Exit)`. Probe (run from
  scratchpad, repo untouched) shows it exits at the *validate* step with
  `"Could not determine current branch"` (resolve_feature_target_branch on a non-git tmp dir), and the
  WP is also unseeded (genesis). It never reaches the lanes.json check its name promises.
  `test_implement_json_error_output_is_clean` (line 246) is the real lanes.json guard (asserts
  `"lanes.json is required"`), so this test is a duplicate-in-name with no oracle -> RETIRE (guard:
  line 246 test; re-prove by planting a break in `_resolve_execution_lane`/`require_lanes_json`).
- **CONFIRMED VACUOUS** `tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py:85`
  `test_resolve_mission_read_path_used_in_implement`: asserts the string `resolve_mission_read_path`
  appears in implement.py. The only occurrence is a *comment* at implement.py:2066 explaining that the
  code no longer uses it (it now uses `resolve_status_surface_with_anchor`). The test is green because
  of prose saying the opposite of what it checks; any decomposition that moves that comment turns it red
  for no behavioural reason. FIX -> assert the real contract (implement's dependency-gate read goes
  through `resolve_status_surface_with_anchor`; better: a behavioural test that a coord-topology mission's
  dependency gate reads the coord status surface).
- `tests/specify_cli/cli/commands/test_implement.py:375` `test_implement_command_callable`
  (`assert callable(implement)`) and `:363` (`hasattr(implement, "safe_commit")`) - import smoke with no
  behavioural oracle; the second pins an import that the decomposition may legitimately move. RETIRE
  both (guard: every class-B test imports and calls `implement`).
- Bare `pytest.raises(typer.Exit)` oracles to re-check during migration (candidates, not verdicts):
  test_implement_command.py:125,158,186,277,381,733; test_implement_base_flag.py:186;
  test_implement.py:296,323; test_implement_demotion_guard_4979.py:115,183,206;
  test_implement_json_safe_output.py:127,143,173; test_wp06_sc2_paused_mission_blockers.py:222,243.
  Each must be paired with a message/code assertion when moved (DIRECTIVE_043 non-vacuity).
- Static-scan `no-assertion` flags at test_implement_demotion_guard_4979.py:310, test_implement_writeside.py:424,
  test_wp06_sc2_paused_mission_blockers.py:136, test_dependency_graph_canceled.py:205 are "must not raise"
  tests - legitimate (KEEP), but each needs a sibling negative (they have one) to stay non-vacuous.

### Missing seam coverage (decisions with no direct unit test)
Zero test references (grep of each `def` name across tests/) for:
`_detect_wp_context`, `_resolve_execution_lane`, `_raise_if_status_commit_protected`,
`_refuse_repo_root_checkout_if_unavailable` (its callee `_ensure_repo_root_checkout_available` IS unit-tested),
`_claim_policy_metadata`, `_build_implement_json_payload` (only indirectly via JSON tests),
`_compute_effective_bookkeeping_ids`, `_extract_mission_identifiers_from_meta`, `_read_json_at_ref`,
`_refuse_on_unreadable_planning_status`, `_print_structural_planning_refusal`, `_rev_parse_ref`,
`_raise_base_ref_unresolved`, the `_json_wrapper_*` family, `_recover_*` family.
Behavioural gaps:
- **Unseeded (genesis) WP rejection** `implement.py:1520`
  (`WorkPackageStartRejected("WP {wp_id} is not finalized; run ... finalize-tasks")`): no test anywhere
  asserts this text or exception on the implement path (`grep -rn "is not finalized" tests` -> 0).
- **The phase-order contract** (refusals before any mutation) is only covered piecemeal:
  dependency-before-allocation (test_implement_command.py:340, test_single_branch_implement_refusals.py:623),
  refusal-leaves-no-VCS-lock (test_single_branch_implement_refusals.py:472). No single test pins the full
  order detect -> preflight -> target-branch/protection -> claim preconditions -> placement -> planning
  commit -> bulk-edit gate -> operational context -> workspace resolve -> lane resolve -> occupancy ->
  VCS lock -> allocate -> status start -> claim commit.
- **"workspace created but status start failed" message** (#4888/T025, implement.py ~2225): grep for
  "Workspace was created but" in tests -> 0 hits; only the generic "Workspace allocation failed" path
  is pinned.
- **Auto-rebase is NOT on the `spec-kitty implement` path.** `attempt_auto_rebase` is reached only from
  `lanes/lifecycle_sync.py` (agent workflow) and `lanes/consolidation.py`; implement.py mentions
  lifecycle_sync only in a docstring (line 387). The proposed orchestrator phase "auto-rebase" has no
  current implement-side behaviour to preserve - scope it explicitly or drop it.

## 4. Refusal-text / code pins and C-004 coverage

| Refusal | Raised in | Pinned by | Pin form |
|---|---|---|---|
| WRITE_CHECKOUT_WRONG_BRANCH | lanes/implement_support.py (`_ensure_repo_root_checkout_available`) | specify_cli/cli/commands/test_single_branch_implement_refusals.py:310,332; orchestrator_api/test_single_branch_repo_root_workspace.py | `error_code ==` (code, not text) + CLI output |
| WRITE_CHECKOUT_OCCUPIED | same | test_single_branch_implement_refusals.py:406 (+586,648 negative); integration/test_single_branch_write_checkout_e2e.py | code |
| WRITE_CHECKOUT_DIRTY | same | test_single_branch_implement_refusals.py:506; test_single_branch_write_checkout_e2e.py | code |
| MissingLanesError / "lanes.json is required" | lanes/persistence.py via `_resolve_execution_lane` | agent/test_implement_command.py:246 (text "lanes.json is required"), :636 (negative + sentinel); tests/lanes/test_persistence.py (unit) | substring |
| DESTROYED_LANE | lanes/worktree_allocator.py | tests/lanes/test_destroyed_lane_guard_{tip_rows,lanes_topology,helpers}.py, test_issue_4889_destroyed_lane_guard.py, orchestrator_api/test_issue_4889_caller_independence.py | code; **not via implement()** - allocator-level only |
| LANE_WORK_TIP_UNKNOWN | lanes/worktree_allocator.py | tests/lanes/test_destroyed_lane_guard_tip_rows.py only | code; allocator-level only |
| dependencies_not_satisfied | implement.py:1533 `_ensure_wp_claim_preconditions` | agent/test_implement_command.py:387 (substring), test_single_branch_implement_refusals.py:646, specify_cli/core/test_dependency_graph_canceled.py:219 (direct call of the private helper, `match="dependencies_not_satisfied"`) | token substring, not full text |
| WP not finalized (genesis) | implement.py:1520 | **none** | gap |
| PlacementResolutionRequired (D11) | implement_cores `_resolve_claim_commit_target` | test_implement_placement_routing.py, test_implement_cores.py, test_implement.py, test_implement_writeside.py, test_coordination_remedy_5113.py | type + remedy substring |
| --mission required (exit 2) | implement.py:2023 | (SC-003 no-selector suite; not in this file set) | exit code |

Byte-for-byte text pins: none of the refusals above is pinned byte-for-byte; all are code- or
token-level. That is good for the refactor (moving raise sites cannot break them) but means a reworded
remedy would also go unnoticed - decide per refusal whether the remedy text is a contract.

C-004 / `_resolve_placement_ref` (#5232) coverage:
- Function under test directly: `test_coordination_remedy_5113.py:238-243` (asserts it returns None for
  an unmaterialized coord surface - this test **pins the fallback itself** and must be rewritten when the
  fallback is removed: the new contract is a fail-closed refusal with the doctor remedy).
- Forced-None by patch (rely on the fallback existing): `agent/test_implement_command.py:710`,
  `specify_cli/lanes/test_lane_base_honoring.py:260`.
- `placement_ref=None` arms of `_commit_planning_artifacts_transaction` (flat/legacy, coord-truthy
  narrow-triple fail-close #2648): `specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py`,
  `lanes/test_issue_2993_lane_planning_ancestry.py` (explicitly exercises the ActionContextError -> None
  path, lines 59-65, 242, 290), `test_implement_writeside.py`, `test_precondition_ref_unification.py`
  (15 `placement_ref=None` call sites across 6 files incl. 2 outside scope:
  mission_runtime/test_self_bookkeeping_allowlist.py, missions/test_gate_read_two_surface_behavioral.py).
- Downstream fail-closed: `_resolve_claim_commit_target(None)` -> PlacementResolutionRequired is pinned in
  test_implement_placement_routing.py / test_implement_cores.py; it stays valid after #5232.
- Integration: test_wp_integrity_checkout_identity.py:316 (placement read must not mark write intent),
  test_wp_integrity_p0_repro.py (coord topology threads a real placement ref).
- Architectural: test_no_write_side_rederivation.py names `_resolve_claim_commit_target` (line 519).

Important (INV-7, the #2463 "None-overload guard"): `test_flat_legacy_none_seam_success_arms.py`
pins that `placement_ref=None` with NO `coordination_branch` in meta.json must reach the flat SUCCESS
arm of `_commit_planning_artifacts_transaction`, i.e. "`placement_ref is None` is NOT unconditionally
degenerate". The helper has four outcomes (implement.py:1110-1140); only the narrow triple
(None + coord_branch + protected planning branch) raises. #5232 removes the *degrade at the resolver*
(`_resolve_placement_ref` returning None on ActionContextError) - it must decide explicitly whether the
flat arm (a) becomes unreachable from `implement()` because flat missions always resolve a real primary
ref (then INV-7 test is rewritten to feed a real primary ref, and the None arms become dead code to
delete with a planted-break proof), or (b) stays as a direct-caller contract. Do not silently delete
INV-7.

## 5. Remediation plan (maps onto phase WPs)

Principles: (1) inject collaborators through an explicit `ImplementPorts` (frozen dataclass of callables,
default-built by the CLI shell) or patch at the *seam module that owns the name*, never at implement.py;
(2) tests move with the code they test, file names mirror the source tree; (3) a retirement names its
covering guard and is proven by a planted break run on the specific files only; (4) keep >= 1 real-git
smoke per behaviour family; (5) each WP deletes the implement.py re-export of every symbol it moves, so
stale patches fail loudly.

### WP-T0 (pre-refactor, characterization, no src change)
- Add `tests/specify_cli/cli/commands/test_implement_phase_order.py`: one real-git orchestrator test per
  refusal family asserting (a) the refusal code/text, (b) *no mutation* (no new worktree, no meta.json VCS
  lock, no status event): genesis-unseeded, dependencies_not_satisfied, protected status-commit target,
  WRITE_CHECKOUT_* (reuse fixtures from test_single_branch_implement_refusals), MissingLanesError,
  PlacementResolutionRequired. This is the regression net every later WP must keep green.
- Add the missing pins: genesis rejection text; "Workspace was created but starting the WP status failed"
  message (inject a failing status port).
- FIX test_issue_1615...:85 (vacuous comment pin) and RETIRE test_implement_command.py:163 +
  test_implement.py:363/375 with planted breaks (see section 3).

### WP-1 Resolve workspace / context phase
Targets: find_repo_root (21), detect_feature_context (19), resolve_feature_target_branch (14),
find_wp_file (2), resolve_workspace_for_wp (3).
- Orchestrator takes `repo_root` as an argument (shell calls `find_repo_root()`), so 21 patches disappear
  -> tests pass `tmp_path` directly.
- Move `detect_feature_context`/`find_wp_file`/`resolve_feature_target_branch`/`_detect_wp_context` to
  e.g. `src/specify_cli/cli/commands/_implement/context.py` (or `specify_cli/implement/context.py`);
  new `tests/specify_cli/cli/commands/_implement/test_context.py` absorbs TestDetectFeatureContext /
  TestFindWpFile from agent/test_implement_command.py and test_trio_read_seam_migration's find_wp_file case.
- Tests that patched detect_feature_context/resolve_feature_target_branch to dodge meta resolution
  instead seed a real `meta.json` with `target_branch` (helper already exists: `create_meta_json`) - that
  is what the vacuous lanes.json test was missing.
- `resolve_workspace_for_wp` stays in workspace/context.py (already has tests/specify_cli/workspace/*);
  the 3 patches become a `resolve_workspace` port.

### WP-2 Dependency gate phase
Targets: `_ensure_wp_claim_preconditions` (direct import in test_dependency_graph_canceled.py).
- Move to `core/dependency_graph.py` (or `status/claim_preconditions.py`) as a public
  `ensure_wp_claim_preconditions(snapshot, wp_id, declared_deps)` that takes a reduced snapshot (pure);
  the I/O (`read_events`/`reduce`) stays in the orchestrator.
- New `tests/specify_cli/core/test_claim_preconditions.py`: genesis rejection, deps unmet, operator-canceled
  dep admits, synthetic-canceled blocks (moved from test_dependency_graph_canceled.py::TestImplementClaimGateThreadsProvenance).
- Keep one orchestrator smoke (test_single_branch_implement_refusals.py:623 already proves gate-before-occupancy).

### WP-3 Planning-artifact commit phase (largest; includes #5232)
Targets: _ensure_planning_artifacts_committed_git (12 str + 8 importing files),
_commit_planning_artifacts_transaction (1 obj + 4 files), _run_planning_artifact_commit (2 obj),
_load_primary_anchored_mission_meta (2 obj), _partition_files_for_commit, _guard_planning_commit_partition,
_meta_json_demotion_refusal/_refuse_if_meta_json_demotion, _feature_dir_file_paths,
_resolve_bookkeeping_transaction_identifiers, _planning_artifact_source_dir, _status_paths_for_commit,
_primary_surface_status_paths, _placement_coord_filter, _PorcelainEntry.
- Move to `src/specify_cli/coordination/planning_commit.py` (or `cli/commands/_implement/planning_commit.py`)
  with mirrored `tests/specify_cli/coordination/test_planning_commit.py`; the 8 files that import
  `_ensure_planning_artifacts_committed_git` switch import path only (no behaviour change).
- Orchestrator tests stop stubbing it with a no-op patch: inject `commit_planning_artifacts` port
  (a no-op fake is legitimate at that boundary).
- #5232: `_resolve_placement_ref` stops returning None -> raise `PlacementResolutionRequired`
  (or the ActionContextError's own structured refusal). Rewrite:
  test_coordination_remedy_5113.py:238-243 (assert refusal + doctor remedy instead of None);
  test_implement_command.py:710 and test_lane_base_honoring.py:260 (drop the forced-None patch; supply a
  real placement or assert the refusal); lanes/test_issue_2993_lane_planning_ancestry.py (degraded arm
  becomes a refusal test); re-examine the `placement_ref=None` arms in
  test_flat_legacy_none_seam_success_arms.py / test_precondition_ref_unification.py / test_implement_writeside.py.
  Update test_wp_integrity_partition_call_shape.py `_IMPLEMENT` path and test_no_write_side_rederivation.py
  line-scoped allow-list keys.

### WP-4 Allocate / reuse lane phase
Targets: create_lane_workspace (14), _ensure_vcs_in_meta (9), `_resolve_execution_lane`,
`_resolve_active_lanes_manifest`, `_refuse_repo_root_checkout_if_unavailable`, `_validate_base_ref` (2 files).
- Ports: `allocate_lane` (default `lanes.implement_support.create_lane_workspace`), `lock_vcs`.
- `_resolve_execution_lane` + `_resolve_active_lanes_manifest` -> `lanes/implement_support.py`
  (new `tests/lanes/test_implement_support_lane_resolution.py`: MissingLanesError, WP-not-in-manifest,
  --base on planning lane is a warned no-op).
- `_validate_base_ref` family -> keep with base-ref tests (cli/commands/test_implement_base_flag.py,
  specify_cli/cli/commands/test_implement_base_ref.py) - import path change only.
- WRITE_CHECKOUT_* / DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN pins are already seam-level (implement_support /
  worktree_allocator) - no change; keep test_single_branch_implement_refusals.py's CLI cases as the e2e smoke.

### WP-5 Record claim phase (status pipeline)
Targets: start_implementation_status (6), _commit_wp_claim_status (1 str + test_issue_610),
_start_wp_implementation_status (test_implement_compact_identity_4665), get_current_branch (1),
ProtectionPolicy (1), `_raise_if_status_commit_protected`, `_protected_branch_status_commit_error` (3 files),
`_status_commit_destination_branch` (architectural line-pin in test_no_write_side_rederivation.py:229-310,484).
- Port `start_status` defaulting to `status.start_implementation_status`; prefer real event-log assertions
  (read `status.events.jsonl`) over the 6 MagicMock patches - vcs_lock_claim / runtime_frontmatter_claim
  tests already have real-git fixtures, so only allocator needs faking.
- New `tests/specify_cli/cli/commands/_implement/test_claim.py` (or under tests/status/) absorbs
  test_issue_610_head_mismatch_not_swallowed and the "propagate SafeCommitPathPolicyError / HeadMismatch /
  PlacementResolutionRequired, soften everything else" contract (currently untested as a table).

### WP-6 Presenter / shell
Targets: _report_workspace_created (1), _print_workspace_ready_banner (1 + _BANNER_* imports),
`_build_implement_json_payload`, `_json_safe_output` + `_json_wrapper_*`, 5 console couplings.
- Presenter object with `render(result)`; tests assert on returned text/payload, not
  `patch.object(console, "print")`. test_implement_json_safe_output.py already unit-tests the wrapper -
  import path change.

### Gate/census edits required whenever code leaves implement.py (do in the moving WP)
test_trio_seam_only.py (`_IMPLEMENT_PY`, seam-only import list - new modules must join the trio set or
the guard goes dark), test_wp_integrity_partition_call_shape.py (`_IMPLEMENT`), test_no_write_side_rederivation.py
(scope list lines 96-109 + line-keyed allow-list), test_exemption_registry_ratchet.py (Surfaces list 99/116 +
registry row `_is_self_write_only_diff.md`), test_safe_commit_import_boundary.py (destination_ref note 105),
test_planning_lane_branch_requires_target.py (non-vacuity floor >= 5 call sites), test_git_matrix_paths_resolve.py
(shipped git-operations-matrix.md `Source File` cells), contract/test_terminology_guards.py:53,
contract/test_feature_alias_scope.py:60, status/test_cutover_byte_stability.py:63,
test_mid8_contract_sensitive_routing.py:59, test_meta_fail_closed_full_census_contract.py:86,
bulk_edit/test_diff_check.py:80, dead_symbol_allowlist.yaml, release/coverage_breadth_baseline.json.
Rule: a census list that enumerates files must gain the new module(s), never just lose implement.py,
or the guard silently narrows (DIRECTIVE_043).

### E2E smokes to keep (>= 1 per family)
- lane allocation: lanes/test_lane_allocation_integrity_e2e.py
- coord partition / #3371: integration/test_wp_integrity_p0_repro.py, test_wp_integrity_cross_partition_scan.py
- crash recovery: integration/test_wp_integrity_crash_recovery.py
- single_branch refusals: specify_cli/cli/commands/test_single_branch_implement_refusals.py (CLI cases)
- base ref: cli/commands/test_implement_base_flag.py (integration class)
- planning-lane ancestry: lanes/test_issue_2993_lane_planning_ancestry.py (rewritten for #5232)
- protected-target coord commit: git/test_guard_capability_regression.py
- programmatic call / JSON contract: agent/test_implement_programmatic_call.py, test_implement_json_safe_output.py

### Planted-break proofs to run before any RETIRE (specific files only)
- RETIRE test_implement_command.py:163 -> plant: make `require_lanes_json` return silently ->
  test_implement_command.py::test_implement_json_error_output_is_clean must go red.
- RETIRE test_implement.py:363/375 -> plant: rename `implement` -> class-B tests go red at import.
- FIX test_issue_1615:85 -> plant: swap `resolve_status_surface_with_anchor` for primary read -> new test red.

## 6. Baseline (origin/main 9adc6880, 2026-10-04)

Command, per file (serial, no randomisation; loop over `scratchpad/runlist.txt` = the 65 .py files + the
call-shape gate):
```
uv run --frozen pytest <file> -q -p no:randomly -p no:cacheprovider -n0
```
Result: **862 passed, 1 failed, 0 skipped/xfailed across 66 files; ~425 s warm serial wall time**
(536 s measured incl. a one-off ~110 s test-venv bootstrap on the first file).
The single failure is **pre-existing and unrelated to implement.py**:
`tests/specify_cli/cli/commands/test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src`
flags `cli/commands/_commit_message.py` (help text "Commit message. Repeat -m ...") as an unallowlisted
git-commit recipe. Red on a clean origin/main checkout -> classify as baseline-red, not WP-owned.
(Note: the test count column is the static-scan count per file; architectural parametrised gates expand
at run time, e.g. test_safe_commit_import_boundary 6 defs -> 18 runs.)

Slowest (warm): lanes/test_lane_allocation_integrity_e2e.py 47 s (2 tests), test_specify_topology_flag.py
25 s, contract/test_feature_alias_scope.py 22 s, test_safe_commit_import_boundary.py 19 s,
agent/test_context_validation_unit.py 17 s. Everything in class A runs < 5 s per file - the patch-heavy
tests are cheap, so the motivation to move them is coupling, not speed.

Suggested per-WP regression command (implement-direct subset). Verified: **450 passed in 18.3 s** (-n auto, loadfile):
```
uv run --frozen pytest -n auto --dist loadfile -p no:randomly \
  tests/agent/test_implement_command.py tests/agent/cli/commands/test_implement_preflight.py \
  tests/agent/test_implement_programmatic_call.py tests/agent/test_mission_handle_json_errors.py \
  tests/cli/commands/test_implement_base_flag.py tests/cli/commands/test_resolve_lanes_dir.py \
  tests/cli/test_implement_bulk_edit_planning.py tests/integration/test_status_emit_on_alloc_failure.py \
  tests/specify_cli/cli/commands/test_implement*.py \
  tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py \
  tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py \
  tests/specify_cli/cli/commands/test_coordination_remedy_5113.py \
  tests/specify_cli/cli/commands/test_precondition_ref_unification.py \
  tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py \
  tests/specify_cli/lanes/test_lane_base_honoring.py tests/specify_cli/core/test_dependency_graph_canceled.py \
  tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py \
  tests/lanes/test_issue_2993_lane_planning_ancestry.py tests/integration/test_wp_integrity_*.py \
  tests/architectural/test_trio_seam_only.py tests/architectural/test_wp_integrity_partition_call_shape.py \
  tests/architectural/test_no_write_side_rederivation.py
```
Full 66-file list: `scratchpad/runlist.txt`; per-file outcomes: `scratchpad/timings.tsv`.

| file | tests | markers | wall s | pass | fail | skip | xfail | err |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| tests/architectural/test_wp_integrity_partition_call_shape.py | 5 | architectural | 2.1 (148.7 cold: includes one-off test-venv bootstrap) | 5 | 0 | 0 | 0 | 0 |
| tests/agent/cli/commands/test_implement_preflight.py | 5 | fast | 3.4 | 5 | 0 | 0 | 0 | 0 |
| tests/agent/test_context_validation_unit.py | 24 | fast | 16.5 | 24 | 0 | 0 | 0 | 0 |
| tests/agent/test_implement_command.py | 18 | fast | 4.5 | 18 | 0 | 0 | 0 | 0 |
| tests/agent/test_implement_programmatic_call.py | 2 | fast | 3.6 | 2 | 0 | 0 | 0 | 0 |
| tests/agent/test_mission_handle_json_errors.py | 7 | fast,unit | 4.1 | 7 | 0 | 0 | 0 | 0 |
| tests/architectural/test_exemption_registry_ratchet.py | 11 | architectural | 3.9 | 11 | 0 | 0 | 0 | 0 |
| tests/architectural/test_git_matrix_paths_resolve.py | 2 | architectural | 2.0 | 2 | 0 | 0 | 0 | 0 |
| tests/architectural/test_no_write_side_rederivation.py | 47 | architectural | 10.0 | 81 | 0 | 0 | 0 | 0 |
| tests/architectural/test_planning_lane_branch_requires_target.py | 2 |  | 2.2 | 2 | 0 | 0 | 0 | 0 |
| tests/architectural/test_safe_commit_import_boundary.py | 6 | architectural | 19.1 | 18 | 0 | 0 | 0 | 0 |
| tests/architectural/test_trio_seam_only.py | 14 | architectural | 2.3 | 14 | 0 | 0 | 0 | 0 |
| tests/cli/commands/test_implement_base_flag.py | 4 | git_repo,integration | 3.3 | 4 | 0 | 0 | 0 | 0 |
| tests/cli/commands/test_resolve_lanes_dir.py | 4 | fast | 2.8 | 4 | 0 | 0 | 0 | 0 |
| tests/cli/test_implement_bulk_edit_planning.py | 3 | fast | 3.3 | 3 | 0 | 0 | 0 | 0 |
| tests/contract/test_feature_alias_scope.py | 9 | contract,fast | 21.5 | 9 | 0 | 0 | 0 | 0 |
| tests/contract/test_terminology_guards.py | 17 | contract,fast | 3.3 | 17 | 0 | 0 | 0 | 0 |
| tests/coordination/test_ledger_topology_less_callers.py | 5 | git_repo,unit | 7.7 | 15 | 0 | 0 | 0 | 0 |
| tests/git/test_guard_capability_regression.py | 9 | git_repo | 4.3 | 16 | 0 | 0 | 0 | 0 |
| tests/git/test_protection_policy_mission_scope.py | 10 | git_repo | 4.5 | 36 | 0 | 0 | 0 | 0 |
| tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py | 1 | git_repo,integration | 4.8 | 1 | 0 | 0 | 0 | 0 |
| tests/integration/test_status_emit_on_alloc_failure.py | 2 | integration | 3.5 | 4 | 0 | 0 | 0 | 0 |
| tests/integration/test_wp_integrity_checkout_identity.py | 10 | git_repo,integration | 3.2 | 10 | 0 | 0 | 0 | 0 |
| tests/integration/test_wp_integrity_crash_recovery.py | 1 | git_repo,integration | 3.2 | 1 | 0 | 0 | 0 | 0 |
| tests/integration/test_wp_integrity_cross_partition_scan.py | 2 | git_repo,integration | 3.8 | 2 | 0 | 0 | 0 | 0 |
| tests/integration/test_wp_integrity_p0_repro.py | 2 | git_repo,integration | 3.5 | 2 | 0 | 0 | 0 | 0 |
| tests/lanes/test_issue_2993_lane_planning_ancestry.py | 1 | git_repo,integration,regression | 3.4 | 2 | 0 | 0 | 0 | 0 |
| tests/lanes/test_lane_allocation_integrity_e2e.py | 2 | git_repo,integration,regression | 47.4 | 2 | 0 | 0 | 0 | 0 |
| tests/lanes/test_lane_context_single_writer.py | 5 | fast | 8.0 | 12 | 0 | 0 | 0 | 0 |
| tests/specify_cli/acceptance/test_trio_read_seam_migration.py | 13 | git_repo,unit | 5.0 | 31 | 0 | 0 | 0 | 0 |
| tests/specify_cli/bulk_edit/test_diff_check.py | 16 | fast,unit | 3.1 | 30 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py | 7 | integration,regression | 5.7 | 7 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_cli_git_paths.py | 27 | git_repo | 4.8 | 29 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_commit_recipes.py | 17 | fast,unit | 14.8 | 16 | 1 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_coordination_remedy_5113.py | 7 | git_repo,integration | 7.7 | 10 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement.py | 12 | git_repo,unit | 3.8 | 12 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_base_ref.py | 3 | git_repo,integration | 3.0 | 3 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_bookkeeping_identifiers.py | 10 | fast | 3.2 | 10 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_bulk_edit_flag.py | 3 | fast,unit | 3.5 | 3 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_coord_idempotency.py | 5 | git_repo,integration | 3.4 | 6 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_cores.py | 79 | unit | 3.7 | 84 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py | 9 | git_repo,regression,unit | 3.8 | 9 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_json_safe_output.py | 16 | fast | 2.9 | 16 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_placement_routing.py | 8 | git_repo,unit | 2.9 | 8 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py | 8 | git_repo,unit | 3.8 | 18 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py | 6 | git_repo,unit | 3.6 | 13 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_implement_writeside.py | 16 | git_repo,unit | 3.3 | 16 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py | 2 | git_repo,unit | 3.7 | 2 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_meta_bypass_diagnosability.py | 9 | unit | 2.9 | 15 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_precondition_ref_unification.py | 13 | git_repo,unit | 3.0 | 13 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py | 19 | git_repo,integration | 6.7 | 19 | 0 | 0 | 0 | 0 |
| tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py | 14 | git_repo,integration,unit | 6.6 | 14 | 0 | 0 | 0 | 0 |
| tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py | 1 | git_repo,integration | 3.1 | 1 | 0 | 0 | 0 | 0 |
| tests/specify_cli/coordination/test_partition_authority_characterization.py | 6 | fast,unit | 3.1 | 9 | 0 | 0 | 0 | 0 |
| tests/specify_cli/core/test_dependency_graph_canceled.py | 13 | fast,unit | 3.2 | 13 | 0 | 0 | 0 | 0 |
| tests/specify_cli/lanes/test_lane_base_honoring.py | 16 | git_repo,unit | 5.5 | 16 | 0 | 0 | 0 | 0 |
| tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py | 22 | fast | 3.5 | 22 | 0 | 0 | 0 | 0 |
| tests/specify_cli/status/test_cutover_byte_stability.py | 13 | unit | 4.3 | 13 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_change_mode_read_boundaries.py | 1 | fast,unit | 3.6 | 4 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_meta_fail_closed_full_census_contract.py | 2 | git_repo,integration | 10.9 | 21 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_meta_read_permission_denied_regression.py | 5 | unit | 3.5 | 5 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_mid8_contract_sensitive_routing.py | 5 | fast,unit | 1.7 | 5 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_operational_context_wiring.py | 14 | integration | 4.8 | 14 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_specify_topology_flag.py | 8 | git_repo | 25.4 | 8 | 0 | 0 | 0 | 0 |
| tests/specify_cli/test_worktrees_index.py | 5 | git_repo,unit | 3.3 | 5 | 0 | 0 | 0 | 0 |
| tests/status/test_actor_identity_reconciliation_4665.py | 13 | fast,regression | 3.5 | 13 | 0 | 0 | 0 | 0 |
| **TOTAL (66 files)** | | | 536 | 862 | 1 | 0 | 0 | |
