# Code grounding: `implement.py` decomposition (#5635) and C-004 removal (#5232)

Pre-spec brownfield grounding squad, run read-only against `origin/main` `9adc68803` on 2026-10-04.
Four profile-loaded delegates were dispatched in parallel:

| Lens | Profile loaded | Report |
|---|---|---|
| Architect | `architect-alphonso` | Appendix A |
| Code archaeologist | `researcher-robbie` | Appendix B |
| Gates | `reviewer-renata` | Appendix C |
| Test-suite remediation | `python-pedro` (+ `test-suite-quality-assessment` procedure) | [`test-remediation.md`](test-remediation.md) |

All four verdicts: **GO, with conditions.** This page is the orchestrator's synthesis. It lists the
facts the spec rests on and the decisions taken from them. The appendices keep each delegate's
evidence verbatim.

## 1. Facts the spec rests on

### 1.1 Size, churn and coupling (re-measured)

- `src/specify_cli/cli/commands/implement.py`: **2,304 LOC**, **53 commits in 90 days, 18 of them fixes**.
  `implement()` sits at mccabe **15**, exactly the C901 / Sonar S3776 ceiling.
- Hotspots by hunk count: `implement()` 41, `_commit_planning_artifacts_transaction` 21,
  `_ensure_planning_artifacts_committed_git` 19, `_commit_wp_claim_status` 9.
- Test coupling: **94 string patch targets** (`specify_cli.cli.commands.implement.<name>`, 15 distinct
  names, 8 files) plus **18 object patches** on the module (7 names, 6 files), so **112 patch sites
  into the module namespace**. There are also 5 console couplings and 40 private names that tests
  import directly. `tests/agent/test_implement_command.py` alone holds 54 string targets.
- Reproducible count command (the one used for the before/after report):
  `grep -rnoE "[\"']specify_cli\.cli\.commands\.implement\.[A-Za-z_]+" tests --include='*.py' | wc -l`.
- A first decomposition already exists: `implement_cores.py` (854 LOC) holds the pure git-porcelain and
  placement cores behind a `GitPort`. `implement.py` re-exports them through a `# noqa: F401` shim.

### 1.2 The real phases (corrects the issue's list)

#5635 lists "auto-rebase" as a phase. **No auto-rebase code runs on the `spec-kitty implement` path.**
`attempt_auto_rebase` is reached only from `lanes/lifecycle_sync.py`, `lanes/consolidation.py` and
`agent/workflow_executor.py`. All three delegates found this independently. The actual ordered
phases inside `implement()` are:

1. **Context**: `--mission` guard (exit 2) → recover mode → repo root → charter preflight → mission
   handle, feature dir, WP file, declared dependencies.
2. **Claim preflight**: target branch → protected status-commit check → status surface + lanes dir →
   **dependency gate** (unseeded/genesis rejection + `dependency_readiness_for_wp`).
3. **Planning-artifact commit** (largest block, about 890 LOC, 39% of the file; the #5232 site): placement
   ref → structural refusal → staging decision → meta.json demotion guard → `BookkeepingTransaction`
   commit(s).
4. **Bulk-edit gate** (FR-006 gate + FR-009 inference) → operational context (FR-017).
5. **Workspace + lane selection**: `resolve_workspace_for_wp(write_intent=True)` → lanes.json lane
   lookup.
6. **Allocate**: single_branch write-checkout refusals → VCS lock → `--base` resolution →
   `create_lane_workspace`.
7. **Record claim**: `start_implementation_status` (with claim policy metadata) → claim auto-commit.
8. **Present**: tracker, banner, or `--json` payload.

### 1.3 Behaviour that must survive byte-for-byte

- Side-effect order (the archaeologist's phase table): the planning-artifact commit (it can land a
  commit) runs *before* the bulk-edit, operational-context, checkout-identity and write-checkout
  refusals. The refusals run *before* `_ensure_vcs_in_meta`; this is pinned
  (`test_single_branch_implement_refusals.py:480,488`).
- Exception contracts: detect catches a fixed tuple → exit 1. Validate catches `Exception` → tracker
  error + exit 1. Create distinguishes `workspace_created` (#4888) and prints `next_step` for three
  allocator errors. The claim commit re-raises `SafeCommitPathPolicyError`, `SafeCommitHeadMismatch` and
  `PlacementResolutionRequired`, and downgrades everything else to a warning with exit 0.
- `--json` error text is the last 20 captured console lines, so reordering prints changes it.
- `agent/workflow.py:1620` calls the Typer command `implement(...)` programmatically. Its
  `json_output`/`recover` defaults are `typer.Option` objects (the #5650 `OptionInfo` bug class), so
  the signature and decorators must stay byte-identical.
- Refusal codes and texts: the WRITE_CHECKOUT_* codes come from `lanes/implement_support.py`;
  MissingLanesError comes from `lanes/persistence.py`; DESTROYED_LANE and LANE_WORK_TIP_UNKNOWN come
  from `lanes/worktree_allocator.py`. Those raise sites are **not moved** by this mission. The
  dependency gate and the genesis rejection are raised in `implement.py` today.
- Pinned only by substring or code, never byte-for-byte. Two paths are **not pinned at all**: the
  genesis "is not finalized" rejection, and the #4888 "Workspace was created but starting the WP status
  failed" message.

### 1.4 #5232: when does the C-004 fallback actually run?

`_resolve_placement_ref` (`implement_cores.py:766`) returns `None` only when the **read-shaped**
`resolve_action_context` raises `ActionContextError`. When that happens,
`_ensure_planning_artifacts_committed_git` / `_commit_planning_artifacts_transaction` fall back to
`coordination_branch` read from meta.json. The fallback has three `None` arms: flat single commit;
"narrow triple" raise; meta-derived partition commit. The architect's reachability analysis gives
three groups:

- **Already refused earlier, so no change:** a deleted coordination branch, and probably an
  unmaterialized coordination worktree. Both are inferences that need a characterization test.
- **Likely still reach the fallback:** an empty coordination branch, topology/invariant mismatches,
  WP-bearing resolution failures, and flat/legacy missions whose context does not resolve.
- INV-7 (`test_flat_legacy_none_seam_success_arms.py`) pins that `placement_ref=None` on a flat
  mission still reaches the success arm.

Precedent for a seam-owned, fail-closed resolution already exists: `agent/mission_record_analysis.py`
resolves through `placement_seam(...).write_target(kind)` and wraps the failure in
`PlacementResolutionRequired` (#5113 / D11). The write-shaped leg composes the coord ref for an
unmaterialized worktree, resolves flat/primary topologies to the target ref, and fails only on real
breakage. `_resolve_claim_commit_target` (`implement_cores.py:796`) is dead in production and carries a
byte-duplicate of the `PlacementResolutionRequired` remedy at `implement.py:1238`.

### 1.5 Gates that move with the code

- **Silent-narrowing risk.** Several gates scan fixed file lists that name `implement.py`, and code
  moved out of the file leaves their scan while they stay green. Each needs the new module added; that
  widens the gate and does not loosen it. The lists are `test_exemption_registry_ratchet.CHURN_SURFACE_MODULES`,
  `test_trio_seam_only._TRIO_FILES/_CORE_FILES`, `test_no_write_side_rederivation._WRITE_DIR_CONSUMER_MODULES`,
  `test_mid8_contract_sensitive_routing`, `test_cutover_byte_stability`,
  `test_meta_fail_closed_full_census_contract`, `test_terminology_guards` and `test_feature_alias_scope`.
- **Loud pins to re-point.** These fail visibly when the code moves:
  - the WS#3 allow-list entry `implement.py::_status_commit_destination_branch` and its twin guard;
  - `test_wp_integrity_partition_call_shape._IMPLEMENT` with its non-vacuity floor of at least 3
    `_run_planning_artifact_commit` calls;
  - `dead_symbol_allowlist.yaml` rows for `_ensure_vcs_in_meta` and `find_wp_file`;
  - source-text pins: `test_implement_placement_routing.py:97,125,307`, `test_operational_context_wiring.py:254`
    and `test_issue_1615…:85`.
- **Patch liveness.** No gate covers it for implement today. The existing gate
  `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py` (#5629/#5684) covers only the
  `agent/tasks*` family.
- **mypy.** `implement.py` is quarantined (`ignore_errors`, `pyproject.toml:2675`). It hides 5 strict
  errors, 4 of them in functions that may move. Moved code must be strict-clean. `core/dependency_graph.py`
  has 2 pre-existing strict errors.
- **CI routing.** `tests/specify_cli/cli/commands` is out of the CI matrix, and a diff to implement.py
  routes only the `cli` shard. The implement test files must therefore run locally, with the counts
  recorded in the PR.
- **Layering.** `lanes/`, `workspace/` and `coordination/` import nothing from `specify_cli.cli` today.
  Decisions moved there must return typed results or raise typed errors, and the CLI renders them.
  The cold-import and status-boundary gates require status/workspace imports in
  `core/dependency_graph.py` to stay lazy and to go through the status facade.

### 1.6 Related issues

| Issue | State | Location | Disposition |
|---|---|---|---|
| #5232 | open P2 | `implement.py` C-004 fallback | **Fold in, close with this PR** |
| #5673 | open P1 | `implement.py:1695,1715` (`_commit_wp_claim_status` sweeps `.kittify/config.yaml` into the claim commit) | **Shape the seam**: extract a pure claim-commit path bundle so the fix becomes one line plus one test. Not fixed here, because changing the committed content is a behaviour change. |
| #5676 | open P2 | `core/mission_creation.py:524-592`, not implement.py | **Out of scope.** Sibling mission #5634 owns the file. Overlap: the single_branch write-checkout policy (dirty/occupied predicates). Not extracted here, to avoid two owners. |
| #5550, #5663/#5459, #5680/#5685 | closed | `lanes/implement_support.py` | Context only. The refusal seam is already in implement_support. |
| #5669 | open | runtime `next` dependency wedge | Out of scope. Keep the dependency-gate seam clean for it. |
| #3931 | open P0 | move-task remedy text | Out of scope. Move-task modules untouched. |
| #5634 | sibling mission | `mission_creation.py` | Coordinate through code. Shared surface is small (`ProtectionPolicy`, `get_current_branch`, `GitCommandError`, `Lane`). |

Found during grounding, to file as follow-ups rather than fix:
- The planning-artifact commit lands before late validation (`resolve_workspace_for_wp`, lane lookup),
  so a validate failure leaves a landed commit behind.
- An unmaterialized coordination worktree surfaces as a misleading "WP not finalized" refusal.
- Three entry points (`implement`, `agent action implement`, `orchestrator_api`) duplicate the claim and
  dependency-gate glue, which suggests a shared implement application service. That would be a new
  subpackage and needs an ADR.
- Pre-existing red on main: `tests/specify_cli/cli/commands/test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src`
  (flags `_commit_message.py`).

## 2. Decisions taken from the findings

| # | Decision | Traces to |
|---|---|---|
| D1 | Phases are *context → claim preflight + dependency gate → planning-artifact commit → bulk-edit gate + operational context → workspace/lane selection → allocate → record claim → present*. "Auto-rebase" is dropped: it is not on this path. | §1.2 |
| D2 | Slice like the precedents (#5650/#5664/#5679/#5695). Move code verbatim first and adjust callers second. Pure decisions go into the **existing** seams with typed results/errors, and printing stays in the CLI. No module becomes a package, and no new top-level package is added. | Appendix A §3 |
| D3 | Seam homes: dependency-gate core → `core/dependency_graph.py`; lane selection + `--base` resolution + repo-root refusal + VCS lock → `lanes/implement_support.py`; WP-file / lanes-dir / target-branch reads → `workspace/context.py`; planning-commit pure decisions → `coordination/planning_commit.py`, a new module beside `BookkeepingTransaction` in the existing package; claim-policy metadata → status facade. Effect adapters that print stay in `cli/commands/` siblings. | Appendix A §3; brief |
| D4 | **Patch liveness:** widen the existing `test_tasks_patch_targets_live.py` gate to the `cli/commands/implement*.py` family as its **first** change, before anything moves. Do not add a second gate. A moved name loses its `implement` re-export in the same work package unless production imports it, so stale patches fail loudly. | §1.5; test-remediation §2 |
| D5 | **#5232:** the C-004 fallback goes and the `placement_ref` `None` default is deleted. Resolution moves to the **write-shaped placement seam**, and the remaining failure is wrapped in `PlacementResolutionRequired`, as `mission_record_analysis` does. This needs a characterization test first: the write-shaped ref must equal the read-shaped `placement_ref` for every topology where the latter resolves. **If that equality fails in a reachable case, stop and ask the operator** (behaviour-change decision). INV-7 is re-pointed to "a flat mission resolves a non-None ref and commits to the planning branch". It is not silently deleted. | §1.4 |
| D6 | #5673 is shaped, not fixed. #5676 is out of scope (sibling mission). | §1.6 |
| D7 | Signature and decorators of the Typer `implement()` stay byte-identical; `agent/workflow.py` keeps calling it. | §1.3 |
| D8 | Every census or scan list gains the new module(s) in the work package that moves code. Pins are re-pointed, never loosened, and no new size or ratchet gate is added. | §1.5; operator ruling |
| D9 | Characterization pins land first and are tests only. They cover phase order with no mutation per refusal family, the genesis rejection, the #4888 message, the claim-commit propagate/soften table, and the #5232 equality and reachability. The vacuous tests are fixed or retired with planted-break proofs. | test-remediation §5 WP-T0 |
| D10 | Moved code is mypy-strict-clean and leaves the quarantine. Complexity stays ≤ 15. | §1.5 |

---

# Appendix A: Architect lens (architect-alphonso), verbatim

### Grounding: `implement.py` decomposition (#5635) + C-004 fallback removal (#5232)

Lens: **architect-alphonso** (builtin profile: system architecture, component boundaries; directives 001/003/031/032/041/043/044/051; tactics dependency-hygiene, development-bdd). Avoidance boundary respected: no implementation code, read-only.
Charter context loaded: `spec-kitty charter context --action plan --json` (bootstrap). The principles applied are single canonical authority, architectural alignment (enforced layer pair), DDD with tiered rigour, ATDD-first, `change-apply-smallest-viable-diff`, DIRECTIVE_024 Locality of Change and DIRECTIVE_025 Boy Scout. Paradigm: brownfield-onboarding (treat the legacy code as a record of constraints).
CLAUDE.md sections read: Modularity SSOT (enforced pair = pyproject inventory + `tests/architectural/{conftest.py,test_layer_rules.py}`; chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`), Execution Workspace Strategy (implement is the only workspace-preparation path; `resolve_workspace_for_wp`; single_branch refusals in `lanes/implement_support.py`).

Ground truth: `origin/main` = branch `issue-5635-implement-degod`. File is 2,304 LOC. A mission scaffold already exists: `kitty-specs/implement-degod-01M44488/` (topology `lanes`, target `issue-5635-implement-degod`; `spec.md` is still the unfilled template).

---

## 0. Headline findings

1. **There is no auto-rebase phase in `implement.py`.** #5635 lists "handle the auto-rebase" as a phase. No auto-rebase code runs on the `spec-kitty implement` path. Auto-rebase lives in `lanes/auto_rebase.py` (`attempt_auto_rebase`). Its callers are `lanes/lifecycle_sync.py:158`, `lanes/consolidation.py:223` and `agent/workflow_executor.py:325` (`auto_rebase_lane_after_commit`). Lane re-entry self-heal is in `worktree_allocator.py` / `implement_support.reenter_lane_self_heal`, which `agent/workflow.py:1632` calls, not `implement.py`. **The spec should drop this phase or re-scope it.**
2. **The largest cohesive block is a phase the issue does not name.** The pre-claim **planning-artifact commit** (L400–1292, about 890 LOC, 39% of the file) is the C-004 area. It is coordination/bookkeeping behaviour: `BookkeepingTransaction`, partition guard, demotion guard.
3. **`implement()` is at mccabe 15, which is exactly the ceiling** (C901 / Sonar S3776). Adding any branch to the entry point reds the gate.
4. **A first decomposition already happened.** `implement_cores.py` (854 LOC, WP03 #2173) holds the pure git-porcelain cores and the placement cores behind a `GitPort`. `implement.py` re-exports them (`# noqa: F401` shim, L75–91).
5. **The test coupling is very high.** About 100 dotted-string patch targets on `specify_cli.cli.commands.implement.*` (top: `find_repo_root` 15, `detect_feature_context` 15, `resolve_feature_target_branch` 14, `create_lane_workspace` 12, `_ensure_planning_artifacts_committed_git` 12, `_ensure_vcs_in_meta` 8, `start_implementation_status` 6). There are also about 50 private names imported directly by tests, and four **source-text pins** on `implement.py` (§6).
6. **`_resolve_claim_commit_target` is dead in production.** It is imported via the shim, and only tests call it (`test_coordination_remedy_5113.py`, `test_implement_writeside.py`). It is the natural fail-closed helper for #5232.
7. **Precedent for #5232 already exists.** `agent/mission_record_analysis.py:100–140` resolves placement through `placement_seam(...).write_target(kind)` and fails closed with `PlacementResolutionRequired` through `_require_record_analysis_placement`. This is the same shape #5232 asks for.

---

## 1. Responsibility map

Complexity values are measured mccabe numbers (`ruff C901`, threshold 3). Functions with no number are below 4.

| Lines | LOC | cc | Symbol | Responsibility | Phase / target seam |
|---|---|---|---|---|---|
| 1–112 | — | — | imports, implement_cores re-export shim, `_WP_ID_RE`, `_RED_ERROR_PREFIX`, `_BANNER_*` | module plumbing | facade |
| 114–125 | 12 | | `_protected_branch_status_commit_error` | protected-branch refusal text for the pre-lane status commit | claim preflight (ProtectionPolicy) |
| 128–130 | 3 | | `_status_commit_destination_branch` | predicts the status-commit branch (`get_current_branch or fallback`). **Allow-listed WS#3 in `test_no_write_side_rederivation.py` by rel_path+qualname** | claim preflight |
| 133–185 | ~45 | | `_json_wrapper_*` (6 fns) | `--json` console capture / error payload | CLI presentation |
| 188–209 | 22 | 5 | `_json_safe_output` | decorator: mutates the global `console.file/quiet` and resets `console._file=None` | CLI presentation |
| 212–240 | 29 | | `detect_feature_context` | `--mission` handle → slug (`resolve_mission_handle`) | CLI parse / mission resolution |
| 243–276 | 34 | 4 | `find_wp_file` | locate the WP prompt via `placement_seam.read_dir(WORK_PACKAGE_TASK)` | workspace resolution (read) |
| 279–288 | 10 | | `resolve_feature_target_branch` | target branch via `core.git_ops.resolve_target_branch` | workspace resolution |
| 291–359 | ~70 | | `_BASE_REF_UNRESOLVED_MSG`, `_raise_base_ref_unresolved`, `_rev_parse_ref`, `_is_ancestor`, `_resolve_base_ref`, `_validate_base_ref` | `--base` origin-preferred resolution (#4969) | lane allocation (base) |
| 362–374 | 13 | | `_git_stdout` | git subprocess helper | misc (duplicate of `implement_cores._SubprocessGitPort`) |
| 377–397 | 21 | | `_resolve_lanes_dir` | `lanes.json` dir via `placement_seam.read_dir(LANE_STATE)` (#3371) | lane allocation |
| 400–432 | ~31 | | `_print_uncommitted_planning_artifacts`, `_print_planning_artifact_commit_instructions` | planning-commit refusal/instructions (`typer.Exit`) | planning-artifact commit (presentation) |
| 435–581 | ~147 | | `_load_primary_anchored_mission_meta`, `_load_fallback_mission_meta`, `_extract_mission_identifiers_from_meta`, `_compute_effective_bookkeeping_ids`, `_BookkeepingTransactionIdentifiers` (NamedTuple, **C-006 frozen 5-tuple**), `_resolve_bookkeeping_transaction_identifiers` | meta cascade → `(coord_branch, mission_id, mid8, eff_id, eff_mid8)` | planning-artifact commit (identity). **The C-004 fallback source** |
| 584–639 | ~54 | 7/4 | `_feature_dir_file_paths`, `_planning_artifact_source_dir` | candidate file enumeration, `.worktrees/` guard (#1887) | planning-artifact commit |
| 642–656 | 15 | | `_print_structural_planning_refusal` | #1598 refusal text | planning-artifact commit (presentation) |
| 659–778 | ~120 | 6 | `_META_JSON_FILENAME`, `_DEMOTION_*`, `_read_json_at_ref`, `_meta_json_demotion_refusal`, `_meta_json_repo_relative_path`, `_refuse_if_meta_json_demotion` | #4979 coord-demotion guard | planning-artifact commit (guard) |
| 781–795 | 15 | | `_refuse_on_unreadable_planning_status` (ctx mgr) | GitCommandError → `typer.Exit(1)` | planning-artifact commit (adapter) |
| **798–907** | 110 | 5 | **`_ensure_planning_artifacts_committed_git`** | staging executor; **#5232 fallback at L833–838** | planning-artifact commit (orchestrator) |
| 910–930 | 21 | | `_partition_files_for_commit` | PRIMARY vs COORD-residue split | planning-artifact commit (pure) |
| 933–982 | 50 | 5 | `_guard_planning_commit_partition` | Seam-A guard (FR-002/C-008) | planning-artifact commit (pure guard) |
| 985–1045 | 61 | 5 | `_run_planning_artifact_commit` | one `BookkeepingTransaction` commit | planning-artifact commit (effect) |
| **1048–1292** | **245** | **11** | **`_commit_planning_artifacts_transaction`** | 4-arm destination decision + commit; **meta-derived arm + narrow-triple raise** | planning-artifact commit (decision+effect) |
| 1295–1325 | 31 | 4 | `_ensure_vcs_in_meta` | write the VCS lock to meta.json | lane allocation (prep) |
| 1328–1445 | ~118 | 4 | `_recover_resolve_context`, `_recover_emit_no_action_result`, `_recover_print_scan_table`, `_recover_emit_report`, `_run_recover_mode` | `--recover` mode (delegates to `lanes.recovery`) | CLI presentation over lanes.recovery |
| 1456–1489 | 34 | | `_detect_wp_context` | auto_commit default, slug, feature_dir (SPEC seam), wp_file, deps | workspace resolution (detect) |
| 1492–1500 | 9 | | `_raise_if_status_commit_protected` | protected-branch preflight (raises ValueError) | claim preflight |
| 1503–1532 | 30 | | `_ensure_wp_claim_preconditions` | read+reduce events, genesis rejection, `dependency_readiness_for_wp` | **dependency gate** |
| 1535–1587 | 53 | 5 | `_run_bulk_edit_gate_and_inference` | FR-006 gate + FR-009 inference (Panels, Exit) | bulk-edit gate (not in #5635's phase list) |
| 1590–1604 | 15 | | `_resolve_execution_lane` | repo-root vs lane; `require_lanes_json`; tracker | lane allocation |
| 1607–1641 | 35 | 4 | `_resolve_active_lanes_manifest` | `--base` validation + planning-lane warning (#3571) | lane allocation (base) |
| 1644–1663 | 20 | | `_primary_surface_status_paths` | #2155/#3784 `.worktrees/` filter | claim recording (commit bundle) |
| 1666–1762 | 97 | 8 | `_commit_wp_claim_status` | claim auto-commit via `safe_commit` to `write_target(WORK_PACKAGE_TASK)`; imports `cli.commands.agent.tasks._collect_status_artifacts` | **claim recording** (effect) |
| 1765–1809 | 45 | | `_build_implement_json_payload` | `--json` success payload | CLI presentation |
| 1812–1830 | 19 | | `_claim_policy_metadata` | shell_pid/baseline triple (**duplicate** of `workflow_executor._claim_policy_metadata`) | claim recording |
| 1833–1866 | 34 | | `_start_wp_implementation_status` | `start_implementation_status` + error translation to Exit | **claim recording** (transition) |
| 1869–1884 | 16 | 5 | `_report_workspace_created` | tracker + branch lines | CLI presentation |
| 1887–1903 | 17 | | `_refuse_repo_root_checkout_if_unavailable` | single_branch write-checkout refusals (delegates to `implement_support._ensure_repo_root_checkout_available`) | lane allocation (preflight) |
| 1906–1922 | 17 | | `_planning_commit_branch` | `single_branch_write_ref` over primary meta | planning-artifact commit |
| 1925–1972 | 48 | 5 | `_print_workspace_ready_banner` | banners + lane-test-env export | CLI presentation |
| **1975–2301** | **327** | **15** | **`implement`** (`@_json_safe_output @require_main_repo`) | Typer command + orchestration of all phases | CLI + orchestrator |
| 2304 | | | `__all__ = ["_ensure_vcs_in_meta","find_wp_file","implement"]` | | facade |

Size per phase (approximate): CLI presentation/JSON/recover ~420 · workspace resolution/detect ~110 · base ref/lane prep ~200 · **planning-artifact commit ~890** · dependency gate ~30 · claim recording ~170 · bulk-edit ~53 · entry point 327.

## 2. Call graph of `implement()` (entry L1977)

```
implement(wp_id, --mission, --auto-commit, --json, --recover, --base, --acknowledge-not-bulk-edit, --actor)
 ├─ [guard] mission is None → Exit(2)
 ├─ [recover] _run_recover_mode → lanes.recovery.scan_recovery_state / run_recovery → _recover_* (presentation)
 ├─ tracker "detect"   (except: TaskCliError|FileNotFoundError|FrontmatterError|ValidationError|Exit → Exit(1))
 │   ├─ find_repo_root()                       [patched 15x]
 │   ├─ charter_runtime.preflight.hook.run_preflight_or_abort (lazy)
 │   └─ _detect_wp_context → get_auto_commit_default, detect_feature_context [patched], placement_seam.read_dir(SPEC),
 │                            find_wp_file, parse_wp_dependencies
 ├─ tracker "validate" (except Exception → tracker.error + Exit(1))   ← PlacementResolutionRequired lands here today
 │   ├─ resolve_feature_target_branch [patched]
 │   ├─ _raise_if_status_commit_protected → _status_commit_destination_branch, _protected_branch_status_commit_error
 │   ├─ coordination.surface_resolver.resolve_status_surface_with_anchor (lazy) → status read dir
 │   ├─ _resolve_lanes_dir → placement_seam.read_dir(LANE_STATE)
 │   ├─ [DEPENDENCY GATE] _ensure_wp_claim_preconditions → status.read_events/reduce, dependency_readiness_for_wp
 │   ├─ [C-004] _resolve_placement_ref (implement_cores) → mission_runtime.resolve_action_context(action="implement") | None
 │   ├─ [PLANNING COMMIT] _ensure_planning_artifacts_committed_git(placement_ref=…)
 │   │     ├─ _planning_artifact_source_dir, detect_structural_planning_changes (cores) → refusal
 │   │     ├─ placement_ref? _placement_coord_filter : _resolve_bookkeeping_transaction_identifiers()[0]   ← #5232
 │   │     ├─ _feature_dir_file_paths, resolve_planning_artifact_staging (cores)
 │   │     ├─ _refuse_if_meta_json_demotion, _print_* (auto_commit off)
 │   │     └─ _commit_planning_artifacts_transaction → _resolve_bookkeeping_transaction_identifiers,
 │   │           _partition_files_for_commit, _run_planning_artifact_commit → _guard_planning_commit_partition,
 │   │           coordination.transaction.BookkeepingTransaction
 │   │     (planning_branch = _planning_commit_branch → mission_runtime.single_branch_write_ref)
 │   ├─ _run_bulk_edit_gate_and_inference → bulk_edit.gate / bulk_edit.inference
 │   ├─ runtime.next.runtime_bridge.build_operational_context_for_claim (lazy) + require_active_role   [source-pinned]
 │   ├─ [WORKSPACE] resolve_workspace_for_wp(write_intent=True)  [patched 3x]
 │   └─ _resolve_execution_lane → lanes.compute.is_repo_root_lane, require_lanes_json
 ├─ tracker "create"  (except Exit → render+raise; except Exception → workspace_created-aware message, next_step, Exit(1))
 │   ├─ [LANE] _refuse_repo_root_checkout_if_unavailable → implement_support._ensure_repo_root_checkout_available
 │   ├─ _ensure_vcs_in_meta [patched 8x] → set_vcs_lock
 │   ├─ _resolve_active_lanes_manifest → _resolve_base_ref / _raise_base_ref_unresolved
 │   ├─ [LANE] create_lane_workspace (lanes.implement_support) [patched 12x]
 │   ├─ [CLAIM] _start_wp_implementation_status → status.start_implementation_status [patched 6x] + _claim_policy_metadata
 │   └─ _report_workspace_created; "Using explicit base ref" line
 ├─ [CLAIM COMMIT] _commit_wp_claim_status → agent.tasks._collect_status_artifacts, _primary_surface_status_paths,
 │     placement_seam.write_target(WORK_PACKAGE_TASK), git.safe_commit
 │   (outer: re-raise SafeCommitPathPolicyError | SafeCommitHeadMismatch | PlacementResolutionRequired; else soft warning)  [source-pinned]
 └─ json? print(_build_implement_json_payload) : _print_workspace_ready_banner
```

Ordering hazard: the planning commit (a durable git side effect) runs **before** `resolve_workspace_for_wp(write_intent=True)` and `_resolve_execution_lane`. A later validate failure therefore leaves a landed planning-artifact commit behind. This is current behaviour. Keep it in the tidy pass, and record it as a follow-up.

## 3. Proposed target layout

### Constraints discovered
- **Layering inside `specify_cli` is convention, not gate**, except for one rule: `consolidation/**` must not import `specify_cli.cli` other than `cli.console` (`test_layer_rules.py:575–675`). `lanes/`, `workspace/` and `coordination/` import no `specify_cli.cli` today. One sanctioned-by-practice leak exists: `implement_support.py:400` lazily imports `cli.console`. Known leaks: `status/doctor.py → cli.commands.review`, `core/tool_checker.py → cli.StepTracker`. **Moved code must not add `cli`/typer imports to lower packages.** Decisions return typed results or raise `StructuredError`s, following the `WriteCheckout*Error` pattern in `implement_support.py`. The CLI renders the exact current strings.
- `runtime` must not import `specify_cli.cli` (ledger in `test_layer_rules.py`). Do not route anything through `runtime.next` beyond the existing lazy `build_operational_context_for_claim` call.
- **External importers (compat surface):** in production, only `cli/commands/__init__.py:273` (`implement_module.implement`) and `agent/workflow.py:83` (`implement as top_level_implement`, called programmatically with kwargs at L1620). Every other importer is a test: about 75 test files. `__all__` is only `_ensure_vcs_in_meta`, `find_wp_file` and `implement`, but tests import about 50 private names. Every moved name must stay importable from `implement` **by identity**, following the precedent rule.

### Precedent pattern (what to copy)
| Slice | Shape | Where the pieces went | Friction recorded |
|---|---|---|---|
| #5650/#2026 consolidation | facade keeps entry+lock+rollback door; phases → sibling `consolidation/phase_*.py`, `run_state`, `entry_preflight`… | same package, siblings | 2nd commit re-pointed **every** patch to "the module that looks the name up"; shared-mock helper `tests/consolidation/executor_family.py`; gates "re-pointed or widened, never loosened" (`test_layer_rules`, `test_no_write_side_rederivation`, `test_exemption_registry_ratchet`) |
| #5664/#5628 orchestrator_api | facade keeps app + registry; verbs → `wp_lifecycle`, `consolidation`, …; shared helpers → `_common` | siblings | patched helpers reached as `_common.<name>` so **one patch reaches every caller** |
| #5679/#5627 mission_finalize | facade (~1,420) + 7 `mission_finalize_*` siblings, verbatim bodies | siblings in `cli/commands/agent/` | phase modules call patched names via **lazy in-function import of the facade** (`tasks_shared` seam-bridge idiom); new seam tests pin re-exports, no module-scope cycles, patch interception; a guard scan had to **add moved call sites it would otherwise silently drop** |
| #5661/#5695 move-task | `tasks_move_task_gates.py`, `_hops.py`, `_executor.py` | siblings | ~70 private patch sites needed repointing; `untrusted_path_audit/inventory.md` pins file:line; `ruff --select I001 --fix` exploded re-export blocks (use only F401,F811,F841); added **patch-target liveness gate** (`test_tasks_patch_targets_live.py`) |
| earlier WP03 #2173 (this file) | `implement_cores.py` with `GitPort` | sibling | shim re-export with `noqa: F401` |

None of the precedents converted a module into a package, and none moved code into a lower-layer package in the same commit. The verbatim move and the seam lifting were separate steps.

### Recommended layout (two-step: verbatim move first, then lift into existing seams)

**Step A: verbatim sibling split (behaviour-identical, precedent-shaped)**

| New module (sibling in `cli/commands/`) | Receives | ~LOC |
|---|---|---|
| `implement.py` (facade) | `implement()` Typer signature unchanged, `_json_safe_output`+wrappers, tracker orchestration, presentation (`_report_workspace_created`, `_print_workspace_ready_banner`, `_build_implement_json_payload`, `_BANNER_*`), `detect_feature_context`, re-exports | ~650 |
| `implement_planning_commit.py` | L400–1292 + `_planning_commit_branch` (planning-artifact commit executor, demotion guard, bookkeeping identifiers, partition/guard/run/transaction) | ~900 → ~700 after #5232 |
| `implement_workspace.py` (or `implement_lane.py`) | `find_wp_file`, `resolve_feature_target_branch`, `_detect_wp_context`, `_resolve_lanes_dir`, base-ref family, `_resolve_execution_lane`, `_resolve_active_lanes_manifest`, `_refuse_repo_root_checkout_if_unavailable`, `_ensure_vcs_in_meta` | ~330 |
| `implement_claim.py` | `_protected_branch_status_commit_error`, `_status_commit_destination_branch` (**move the WS#3 allow-list descriptor with it**), `_raise_if_status_commit_protected`, `_ensure_wp_claim_preconditions`, `_claim_policy_metadata`, `_start_wp_implementation_status`, `_primary_surface_status_paths`, `_commit_wp_claim_status`, `_run_bulk_edit_gate_and_inference` | ~330 |
| `implement_recover.py` | `_recover_*`, `_run_recover_mode` | ~120 |

Names that tests patch on `implement.*` and that moved code calls must be reached through `implement.<name>` (lazy facade import, finalize idiom), or the patches must be re-pointed (consolidation idiom). **Decide one rule up front and gate it with a liveness test** (§6).

**Step B: lift decisions into the existing seams (pure core + effect adapter, typed errors, CLI renders)**

| Decision | Existing seam to receive it | Notes |
|---|---|---|
| Dependency gate (`_ensure_wp_claim_preconditions`) | `status/dependency_verdict.py` (already the pure verdict seam: `readiness_from_snapshot`, `wp_lanes_from_snapshot`) + `core/dependency_graph.py` stays the authority | Add a pure `claim_precondition_verdict(snapshot, wp_id, deps)` covering genesis rejection and readiness. **Subtle diff:** implement builds lanes with `_state.get("lane", Lane.GENESIS)`, while the seam uses `str(state.get("lane") or GENESIS.value)`. These differ for a present-but-falsy lane. Pin this before switching. The same snapshot→readiness glue is duplicated in `workflow_executor.py:684`, `orchestrator_api/wp_lifecycle.py:489` and `orchestrator_api/commands.py:453`. Exception types (`WorkPackageStartRejected`, `ValueError("dependencies_not_satisfied: …")`) must survive |
| Workspace / lane selection (`_resolve_execution_lane`, `_resolve_lanes_dir`, base-ref family, repo-root refusal) | `lanes/implement_support.py` (already owns `create_lane_workspace`, `_ensure_repo_root_checkout_available`, `guard_repo_root_claim`) and `workspace/context.py` (`resolve_workspace_for_wp`) | Base-ref resolution is pure git. Its docstring says it is "coordinated with WP04's `workspace/context.py` / `lanes/compute.py`", so `lanes/compute.py` or `implement_support` fits. Replace the `typer.Exit` in `_raise_base_ref_unresolved` with a typed error |
| Claim recording (`_start_wp_implementation_status`, `_claim_policy_metadata`) | `status/work_package_lifecycle.py` (`start_implementation_status`) + `status.build_claim_policy_metadata` | Dedupe `_claim_policy_metadata` with `workflow_executor._claim_policy_metadata`. `_commit_wp_claim_status` **cannot** move below `cli` yet: it imports `cli.commands.agent.tasks._collect_status_artifacts`. Move that collector to `status/` first, or keep the claim commit in the CLI layer |
| Planning-artifact commit | `coordination/` (next to `transaction.BookkeepingTransaction`, `commit_router._group_files_by_partition`, `coherence`) | `_partition_files_for_commit` mirrors `commit_router._group_files_by_partition`, which makes it a dedupe candidate. `_guard_planning_commit_partition` raises `commit_router.PrimaryKindReachedCoordStagingError` and belongs beside it. Bookkeeping identifiers (`resolve_mid8`/`resolve_transaction_mid8` live in `lanes/branch_naming.py`) could become an identity helper there |
| Bulk-edit gate | `bulk_edit/gate.py` | Return a verdict (pass / informational / blocked). CLI renders the Panels |
| Auto-rebase | n/a | **Not in implement.py**, see §0.1 |

Do **not** create a new top-level `specify_cli/implement/` package unless the team wants an "implement orchestrator" application service shared with `agent action implement` (`workflow_executor`) and `orchestrator_api.wp_lifecycle`. That would be a real DDD win, because three entry points duplicate the claim/gate glue. It is a new subpackage, though, and it widens scope beyond "tidy-first, existing seams". Record it as an option for an ADR, not for this mission.

## 4. Relevant docs and ADRs
- `docs/architecture/execution-lanes.md` §Workspace Resolution Contract (L28+): implement → `resolve_workspace_for_wp`, `require_lanes_json` fail-closed.
- `docs/architecture/artifact-placement-seam.md` L265–280: #3371 lesson (`implement._resolve_lanes_dir` straggler; **only the e2e `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence` caught it**). Run that e2e for any planning-commit or lanes_dir move.
- `docs/architecture/04_implementation_mapping/README.md` L216 (lists `implement.py` in the workflow command set; update after the split).
- ADR `docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md`: ExecutionContext owner and CommitTarget atomicity (C-PLACE-1 basis).
- ADR `docs/adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md`. **Note: "C-004" is overloaded.** Here C-004 = "the coordination-worktree mechanism stays". In `implement.py` C-004 = the meta-derived strangler. Name the sense in the spec.
- ADR `docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md` (stored topology; its own C-004 = "structural, not symptomatic").
- ADR `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md` (planning commit ↔ lane base; #2993 test exercises both placement arms).
- ADR `docs/adr/3.x/2026-07-08-1-mission-resolver-port.md` (resolver port threading through `resolve_action_context`).
- `docs/context/orchestration.md#routing` / `#primary-*` for terminology (placement vs branch-target sense).
- CLAUDE.md Execution Workspace Strategy (single_branch refusals `WRITE_CHECKOUT_*` in `implement_support.py`).

## 5. #5232: the C-004 fallback

### Current code
`implement.py:827–838` (inside `_ensure_planning_artifacts_committed_git`):
```python
if placement_ref is not None:
    coord_branch_for_filter = _placement_coord_filter(repo_root, mission_slug, placement_ref)
else:
    coord_branch_for_filter = _resolve_bookkeeping_transaction_identifiers(feature_dir, mission_slug, repo_root)[0]
```
`_commit_planning_artifacts_transaction` (L1137–1292) has **four** arms. When `placement_ref is not None`, it re-derives `coord_branch` from the placement and runs a partition commit. When it is `None` there are three cases:
- (a) No `coord_branch` in meta: one commit to `planning_branch` (flat/legacy).
- (b) Meta `coord_branch` present and `planning_branch` protected: raise `PlacementResolutionRequired` (the #2648 narrow triple). Its message is a byte-duplicate of `implement_cores._resolve_claim_commit_target`.
- (c) Meta `coord_branch` present and `planning_branch` unprotected: partition commit with COORD files sent to the **meta-derived** coord branch.

The caller is `implement.py:2091`: `_placement_ref = _resolve_placement_ref(...)`, inside the validate `try/except Exception`.

`_resolve_placement_ref` (`implement_cores.py:766–793`) calls `resolve_action_context(repo_root, action="implement", feature=slug, wp_id=wp_id)`. It returns `context.artifact_placement.placement_ref`, and it **returns `None` only on `ActionContextError`** (narrow catch, so `CheckoutIdentityError` is never swallowed). On the WP-bearing path `artifact_placement` is never `None` (`_assemble_artifact_placement_fragment` always builds it from `branch_ref.destination_ref`), so `None` means "context resolution raised".

### When does resolution fail in practice?
`resolve_action_context` uses the **read-shaped** status-surface leg (`_resolve_status_surface_dir`, `for_write=False`). It raises `ActionContextError` for:
- `CoordinationWorktreeUnmaterialized`: the branch is present but the worktree is absent (fresh clone, CI, removed worktree). Confirmed by `test_coordination_remedy_5113.py:242`, which asserts `None` on a real fresh unmaterialized mission.
- `CoordinationBranchDeleted`, never-created, or EMPTY coord.
- mid8 not derivable.
- `TOPOLOGY_INPUT_MISMATCH`, `CONTEXT_INVARIANT_VIOLATION`, `MISSION_AMBIGUOUS_SELECTOR`.
- WP-bearing failures: `WORK_PACKAGE_UNRESOLVED`, `CANONICAL_STATUS_UNREADABLE`/`NOT_FOUND`, and errors from `resolve_workspace_for_wp(write_intent=False)` that `_resolve_wp_bearing_fields` wraps.

Earlier steps in `implement()` already fail some of these cases closed. These are **inferences to pin with a characterization test before deciding**:
- DELETED: `resolve_status_surface_with_anchor` raises `CoordinationBranchDeleted`, so validate exits 1 before `_resolve_placement_ref`.
- UNMATERIALIZED: the anchor resolver *composes* the coord path. `read_events` on a missing file returns `[]`, so the WP reads as genesis. `_ensure_wp_claim_preconditions` then raises `WorkPackageStartRejected("…not finalized…")`, so validate exits 1 with a misleading message, also before the fallback.
- Likely still reaching the fallback today:
  - coord-EMPTY (the anchor resolver's Option B returns the primary surface, while the read-shaped context leg may refuse);
  - topology/invariant mismatches;
  - WP-bearing failures, where the fallback **commits planning artifacts and then** validate fails at `resolve_workspace_for_wp(write_intent=True)`, a partial side effect;
  - genuinely legacy/flat missions whose context does not resolve, which today get arm (a), a successful commit.

### Is fail-closed an operator-visible behaviour change?
Yes, but narrowly:
- Cases that already exit 1 earlier (DELETED, likely UNMATERIALIZED): **no change**.
- Coord-EMPTY / mismatch / WP-bearing: today implement may auto-commit to a meta-derived ref (arm c) or the planning branch (arm a) and continue or fail later. After the change it exits 1 at the "validate" tracker step with the `PlacementResolutionRequired` remedy (`spec-kitty doctor coordination --mission <slug> --fix`). The validate `except Exception` already renders `PlacementResolutionRequired` this way (arm b today), so the **output shape is not new**.
- Flat/legacy missions that hit `ActionContextError`: **newly refused**. `tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py` explicitly pins "placement_ref=None for a flat mission must still reach the success arm" (#2463 None-overload / INV-7). That invariant must be consciously retired or preserved.

### Options
- **A. Fail closed with a typed error.** `placement_ref: CommitTarget` becomes required. The caller runs `_resolve_claim_commit_target(_resolve_placement_ref(...), mission_slug=...)`, which is dead today and would become live, and arms (a), (b) and (c) are deleted. Simple and C-PLACE-1-pure. Risk: it newly refuses the UNMATERIALIZED window wherever that is reachable, and it refuses legacy/flat missions whose context fails (INV-7).
- **B. Seam-owned resolution (degrade owned by the placement seam).** Replace the read-shaped `resolve_action_context` call with the **write-shaped** seam `placement_seam(repo_root, slug).write_target(<COORD-partition kind>)`, which is `resolve_placement_only(..., for_write=True)`. Per the #5113 classification in `test_coordination_remedy_5113.py:46–55`, that leg composes the coord ref for UNMATERIALIZED instead of raising, resolves flat/primary topologies to the target ref, and hard-fails only for DELETED and similar breakage. Wrap the remaining failure in `PlacementResolutionRequired`, as `mission_record_analysis._require_record_analysis_placement` already does. The `None` overload disappears, the meta-derived arm is deleted, and the commit transaction collapses to two arms (coord topology: partition; flat: single).

### Recommendation: **B**, fail-closed shape, record-analysis precedent
It satisfies #5232's first bullet (required ref, typed, operator-actionable error), and the degrade it keeps is owned by the placement seam, as the second bullet requires. It does not newly refuse the unmaterialized window, and it reuses an already-landed, already-tested pattern (#5113 / D11).

Prerequisites, all test-first (ATDD):
1. **Equality characterization:** for coord, lanes_with_coord, lanes, single_branch (incl. a minted mission branch) and flat-legacy fixtures, `write_target(kind)` must equal `resolve_action_context(...).artifact_placement.placement_ref` wherever the latter resolves. Choose the COORD-partition kind whose ref equals `branch_ref.destination_ref`. Note that `artifacts.py:357–371` returns `placement_ref` as the commit_target for both partitions, so verify the kind choice empirically.
2. Characterize which states actually reach the fallback today (§above) through the real `implement` CLI.
3. Decide INV-7 explicitly. Rewrite `test_flat_legacy_none_seam_success_arms.py` to "flat mission resolves a non-None ref and commits to the planning branch".

Tests to rewrite or delete when the arms go:
- `test_implement_writeside.py` (placement_ref=None at L209, 248, 302, 353, incl. `test_protected_planning_branch_raises_placement_resolution_required`, `test_no_coord_branch_collapses…`)
- `test_precondition_ref_unification.py` L237, 302
- `test_issue_2993_lane_planning_ancestry.py` (the `legacy-fallback` param)
- `test_flat_legacy_none_seam_success_arms.py`
- `test_coordination_remedy_5113.py` `implement_claim_commit_target` case (it asserts `_resolve_placement_ref` returns None)
- `tests/agent/test_implement_command.py:710` and `tests/specify_cli/lanes/test_lane_base_honoring.py:260` (patch `_resolve_placement_ref → None`)
- `test_implement_bookkeeping_identifiers.py::test_consumer_contract_five_tuple_positions_match_fixture` (C-006: the `[0]` consumer disappears)
- `tests/architectural/test_wp_integrity_partition_call_shape.py` (asserts **≥3** `_run_planning_artifact_commit` calls **in implement.py's file text**. The count drops when the meta arm is removed (2 coord-partition + 1 flat = 3 only if the flat arm keeps its own call), and it goes to 0 when the code moves.)

Also dedupe the `PlacementResolutionRequired` message (inline SC-002/T041 follow-up) and drop the C-004 wording from docstrings.

## 6. Risks
| Sev | Risk | Mitigation |
|---|---|---|
| HIGH | **Dead intercepts.** About 100 `patch("specify_cli.cli.commands.implement.<name>")` targets. Once a caller moves to a sibling, patches on the facade name stop intercepting. The real function then runs, and the test either reds or, worse, **stays green vacuously**. | Before moving anything, add an implement-family patch-target liveness gate cloned from `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py`. Then choose one rule: re-point patches to the looking-up module (consolidation) or a lazy facade bridge (finalize). |
| HIGH | **Source-text pins on implement.py:** (1) `test_implement_placement_routing.py:97,125` uses `inspect.getsource(implement)` and requires `except PlacementResolutionRequired:` / `except SafeCommitHeadMismatch:` before the soft-warning print. (2) Same file L307: forbidden-ternary scan of the whole module. (3) `test_operational_context_wiring.py:254`: `implement` source must contain `build_operational_context_for_claim` and `require_active_role`. (4) `test_wp_integrity_partition_call_shape.py` reads the `implement.py` file. | Re-point each to the receiving module in the same commit. Never loosen (precedent rule). The except-ordering pin effectively freezes the claim-commit `try` in `implement()`. |
| HIGH | **Architectural scan lists name `implement.py`/`implement_cores.py` by path:** `test_no_write_side_rederivation.py:96–109` (scan) + `:256–268` (WS#3 allow-list by rel_path+qualname `_status_commit_destination_branch`), `test_exemption_registry_ratchet.py:99,116`, `test_trio_seam_only.py:98–125` (trio/core files; cores must stay pure), `tests/contract/test_terminology_guards.py:53`, `test_feature_alias_scope.py:60`, `test_safe_commit_import_boundary.py`, `test_git_matrix_paths_resolve.py`, `test_planning_lane_branch_requires_target.py`, `tool_artifact_enrolment/registry/_is_self_write_only_diff.md`. If a moved function leaves the scanned set, the gate goes **vacuously green**. | Add every new sibling to each scan list in the same commit. Verify the per-file contribution count is non-zero, as the move-task landing did. |
| HIGH | **Complexity ceiling.** `implement()` is at cc 15 and `_commit_planning_artifacts_transaction` at 11. | Any new branch must be extracted. The #5232 collapse lowers cc. |
| MED | **Global console mutation.** `_json_safe_output` swaps `console.file`/`quiet` and resets `console._file=None`. Moved code that prints must use the same `specify_cli.cli.console.console` singleton and must never cache `console.file`. Under `--json`, `print()` vs `console.print` placement is significant. The recover paths `print(json.dumps…)` directly. | Keep all printing in the CLI layer, and keep `--json` golden tests (`test_implement_json_safe_output.py`). |
| MED | **Programmatic Typer call.** `agent/workflow.py:1620` calls `implement(...)` with kwargs. `json_output` and `recover` use non-Annotated `typer.Option(...)` defaults, so an omitted kwarg is a truthy `OptionInfo`. This is the exact #5650 `'OptionInfo' object has no attribute 'strip'` class. | Keep the signature byte-identical, or convert to `Annotated` with real defaults as a deliberate, tested tidy. Better: have workflow call the orchestrator function, not the Typer command. |
| MED | **Upward import.** `_commit_wp_claim_status` imports `cli.commands.agent.tasks._collect_status_artifacts`, which blocks any move into `status/`. | Relocate the collector first, or keep the claim commit in the CLI layer. |
| MED | **Exception-shape contracts.** Validate catches `Exception` → Exit(1); create distinguishes `workspace_created` (#4888) and prints `next_step` for the three allocator errors; the outer claim commit re-raises three types and softens the rest. Typed errors introduced in seams must flow through the same handlers unchanged. | Characterization tests on the stdout/exit code for each handler before moving. |
| MED | **Shim layering.** Names re-exported from `implement_cores` via `implement` (`# noqa: F401`). A second shim layer (facade → sibling → cores) must re-export **by identity**. `test_precondition_ref_unification::test_helper_is_module_private` pins privacy. | Pin identity re-exports with a seam test, as all precedents did. Use `ruff --select F401,F811,F841 --fix` only, never I001 (move-task friction). |
| LOW | Dependency-gate lane-map derivation differs subtly from `status.dependency_verdict.wp_lanes_from_snapshot`. | Pin before deduping. |
| LOW | **Partial side effect.** The planning commit lands before the later validate failures (`resolve_workspace_for_wp`, lane lookup). | Out of scope for tidy-first. File a follow-up to reorder. |
| LOW | #3371 lesson: partition/reader moves are only caught by `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`. | Include it in the blast radius. |
| LOW | Duplicate `_git_stdout` vs `implement_cores._SubprocessGitPort`; duplicate `_claim_policy_metadata` vs workflow_executor; duplicate `PlacementResolutionRequired` text. | Boy-scout candidates, each in its own commit. |

## 7. Verdict
**Go, with a re-scoped spec.** Slice in the order the precedents proved:
1. Liveness gate + characterization tests (CLI exit codes and messages per handler; #5232 reachability; write_target ≡ placement_ref equality).
2. Verbatim sibling split (`implement_planning_commit`, `implement_workspace`, `implement_claim`, `implement_recover`), with identity re-exports and gates re-pointed or widened.
3. #5232 via Option B (write-shaped seam + `PlacementResolutionRequired`), collapsing the commit transaction to two arms.
4. Lift the pure decisions into `status/dependency_verdict.py`, `lanes/implement_support.py`, `coordination/` and `bulk_edit/gate.py` with typed errors and CLI rendering; move tests onto those seams.

Drop "auto-rebase" from the phase list, and add "planning-artifact commit" and "bulk-edit gate" as named phases.

---

# Appendix B: Code archaeologist lens (researcher-robbie), verbatim

# Grounding: code archaeologist lens: `implement.py` degod (#5635) and C-004 removal (#5232)

Read-only. Base: `origin/main` @ `9adc68803` (2026-10-04). The clone was shallow (50 commits), so I deepened it with `git fetch --shallow-since=2026-06-20`. No repo files were edited.

## 0. Profile and governance applied

- Profile: `researcher-robbie`. Investigate, synthesize and recommend. No production code and no final decisions.
- Charter context (`--action plan`, bootstrap) applied:
  - single canonical authority
  - tidy-first / smallest-viable-diff (`change-apply-smallest-viable-diff`)
  - DIRECTIVE_024 locality of change
  - DIRECTIVE_025 Boy Scout rule. Opportunistic fixes are licensed, but they must be labelled as behaviour changes and not hidden inside a move.
  - ATDD / red-first
  - canonical sources

## 1. Churn (last 90 days)

| File | LOC | Commits | `fix` commits |
|---|---|---|---|
| `src/specify_cli/cli/commands/implement.py` | 2304 | 53 | 18 |
| `src/specify_cli/lanes/implement_support.py` | 852 | 26 | 13 |
| `src/specify_cli/workspace/context.py` | 1353 | 17 | 4 |
| `src/specify_cli/cli/commands/implement_cores.py` (the earlier degod's cores) | 854 | 18 | n/a |

The fix ratio in `implement_support.py` is 50%. All of its last 10 commits are about the single_branch write checkout: #5100, #5459, #5680, #5550.

### Hotspot functions inside `implement.py`

Counted by hunk header over 90 days, so the counts are approximate (a hunk is attributed to the enclosing def that precedes it).

| Function | Hunks | Notable fixes that landed there |
|---|---|---|
| `implement()` (L1977-2301, ~325 LOC) | 41 | #3571 `--base` (7fd312f54), #3371 lanes.json PRIMARY read (0d471bbe5), #5100 side-effect-free refusals (32ee4006e), #3937 leave WP planned on alloc failure (f64650f2d), json-mode threading (3b9423dd9) |
| `_commit_planning_artifacts_transaction` (L1048-1292, ~245 LOC) | 21 | #2533 partition-aware commit (e4644c234), #2648/9/50 commit-path hardening (c10a94dc5), #5108 lane naming (af8759bf5) |
| `_ensure_planning_artifacts_committed_git` (L798-907) | 19 | FIX-M2-08 (3599c0599), #4979 demotion guard (18c54db8e), idempotency read surface (055465e49) |
| `_commit_wp_claim_status` (L1666-1762) | 9 | #3784 `.worktrees/` exclusion (a94c27692), #2155, #610. This is where **#5673** lives. |
| `_resolve_bookkeeping_transaction_identifiers` | 7 | #2648, json mode |
| `_run_recover_mode`, `_ensure_wp_claim_preconditions` | 5 each | #2464 squad |

**Conclusion.** Two clusters carry the risk:

1. The planning-artifact commit family, about 500 LOC (L584-1292).
2. The `implement()` body.

The claim/refusal logic already lives mostly in `implement_support.py`.

## 2. Bugs landing in this code

| Issue | State | Where | Notes |
|---|---|---|---|
| #5550 | closed by PR #5696 | `lanes/checkout_occupancy.py::_writes_to_another_branch` | Occupancy is now scoped to the branch. |
| #5459 / #5663 | closed by PR #5659 (471ca83e2) | `implement_support.py:203 guard_repo_root_claim` | This is now the one claim seam both verbs share. `agent action implement` calls it directly (`workflow.py:1640`). |
| #5680 / #5685 | closed (5b71c1955, 64a52450c) | `implement_support.py:169-185` | #5685 is a duplicate. The remedy text was changed again in a1f43379a, today. |
| **#5673** | **open, P1** | `implement.py:1695,1715-1716` and `implement_support.py:75` | See 2a. |
| **#5676** | **open, P2** | `core/mission_creation.py:524-592` (**not** in implement.py) | See 2b. |
| #5669 | open | `runtime/next/discovery.py:152` | It shares `dependency_readiness_for_wp` but is not in implement.py. It is out of scope for this mission. |
| #3931 | open (remedy text reworked in d68f555a9) | move-task family | Not in implement.py. |
| #5232 | open, P2 | `implement.py:806,833-838,1056,1154-1292`, `implement_cores.py:766-793` | Claimed by mission `implement-degod-01M44488`. See section 3. |
| Related open issues | open | n/a | #5151 (one dirty repo-root file blocks WPs), #3471 (auto-commit-off churn), #5099 epic (one writer per checkout), #5675 (for_review gate counts foreign commits). |

### 2a. #5673: the claim commit sweeps the operator's `.kittify/config.yaml` edit

There are two cooperating causes.

1. **Bundle.** `implement.py:1695` sets `config_file = repo_root / ".kittify" / "config.yaml"`. Then `:1715-1716` runs `if config_file.exists(): files_to_commit.append(config_file.resolve())` unconditionally.
   - `safe_commit(paths=...)` therefore commits whatever the working tree holds.
   - Nothing in `implement` writes `config.yaml`. The VCS lock goes to `meta.json` via `_ensure_vcs_in_meta`. So the bundle entry is legacy residue: `-S` traces it back through the 2026-06/07 degods, and it predates the 90-day window.
   - **The bundle is topology-independent.** On lanes and coord missions there is no dirty check on the repository root checkout either. So any `config.yaml` edit is also swept into the primary claim commit whenever `auto_commit` is on and the status changed. That is broader than the issue title (`single_branch`). Mark it "likely" until a red test confirms it.
2. **Dirty-scan exemption.** `implement_support.py:55-77 _owned_status_prefixes` exempts the whole `.kittify/` prefix.
   - It mirrors `_RUNTIME_STATE_DENY_LIST` in `agent/tasks_shared.py:114`.
   - As a result, `WRITE_CHECKOUT_DIRTY` (`:194-199`) never sees `config.yaml`.

**Seam shape that makes it small.** Extract a pure `claim_commit_paths(wp_file, status_paths, meta_file) -> tuple[Path, ...]` out of `_commit_wp_claim_status`.

- The fix is then a one-line deletion plus a unit test on the pure function, with no git needed.
- Optionally, narrow the dirty-scan exemption to `.kittify/` minus `config.yaml`. Note that this changes refusal behaviour: an operator `config.yaml` edit would now refuse a single_branch claim. That is a product decision, and the issue lists both outcomes as acceptable. Dropping the bundle alone yields "a claim commit that touches only the claim metadata".

**Free inside a pure move? No.** Dropping the path changes committed content, so it is a behaviour change. Do it as its own labelled, red-first slice: after the extraction, or before it as a tiny separate PR. It must not ride inside a "behaviour-preserving" move commit.

### 2b. #5676: `mission create` switches an occupied root checkout

- Cause: `core/mission_creation.py:524-592 _mint_protected_single_branch_mission_branch`. It refuses only on dirty paths (`:559-580`), then runs `git checkout -b` (`:588+`). It never consults occupancy.
- The rule it needs already exists: `lanes/checkout_occupancy.py:139 in_progress_wps_in_write_checkout(repo_root, write_root, exclude=None)`.
  - After #5680, the scan counts only missions whose write branch is the branch the checkout is on (or whose write branch is unknown).
  - At create time the checkout is on alpha's mission branch, so alpha's in-progress WP would be counted as-is.
- **This is not in implement.py**, so it is not fixable by the #5635 move.
- The natural seam is a public "write-checkout policy" in `lanes/`: wrong-branch, occupied and dirty predicates, plus the refusal errors. Today they are private (`_ensure_repo_root_checkout_available`, `_owned_status_prefixes`).
- With that seam, `mission_creation` calls one function and the fix is about five lines plus a test.
- **The two dirty scans differ:**
  - `mission_creation` uses a bidirectional `GitPath.overlaps` over `.kittify` and its own scaffold.
  - `checkout_occupancy.dirty_paths` uses a one-directional `_is_owned_path`.
  - This is a canonical-authority smell to note, not to fix silently.
- It belongs to sibling #5634 (`mission_creation.py` degod), so coordinate there.

## 3. C-004 meta-derived fallback (#5232): history and current need

- Origin: the "C-004 strangler" is defined in `106531095` (2026-06-20, canonical mission-surface resolver). It was later carried through:
  - `9be0ef6d4` and `620e7cb82` (#2056)
  - `ed336e034` (#2464, which created `implement_cores.py`)
  - `e4644c234` (#2533, partition-aware)
  - `3dd223029` (2026-09-03, commit_router fail-loud on silent primary fallbacks)
- Current sites:
  - `implement_cores.py:766-793 _resolve_placement_ref` returns `None` only on `ActionContextError`. The catch is deliberately narrow, so a `CheckoutIdentityError` is never swallowed. On success `artifact_placement` is always populated (`mission_runtime/resolution.py:480,3141`).
  - `implement.py:833-838`: the `else` arm uses `_resolve_bookkeeping_transaction_identifiers(...)[0]` (meta-derived coord).
  - `implement.py:1154-1292`: three `placement_ref is None` arms:
    - (a) flat/legacy: commit to `planning_branch`
    - (b) protected: fail closed with `PlacementResolutionRequired` (#2648)
    - (c) meta-derived coord: partition-aware commit
- **Something still pins the None path. Do not delete it blindly.**
  - `tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py` pins INV-7 (the #2463 "None-overload guard"): a genuinely flat/legacy mission with `placement_ref=None` must reach the success arm.
  - Other tests that pass `placement_ref=None`, or patch `_resolve_placement_ref`:
    - `test_implement_writeside.py`
    - `test_precondition_ref_unification.py`
    - `test_coordination_remedy_5113.py`
    - `test_wp_integrity_p0_repro.py`
    - `test_issue_2993_lane_planning_ancestry.py`
    - `test_lane_base_honoring.py`
    - `tests/agent/test_implement_command.py`
    - `tests/mission_runtime/test_self_bookkeeping_allowlist.py`
    - `test_gate_read_two_surface_behavioral.py`
  - In production, `None` means "context resolution raised". Callers that pass `None` directly are tests only. The only production caller is `implement.py:2096`.
  - `test_wp_integrity_partition_call_shape.py` AST-scans `implement.py` by path for `_run_planning_artifact_commit` calls.
- **Recommendation.** Make `placement_ref: CommitTarget` required, and have `_resolve_placement_ref` raise a typed `PlacementResolutionRequired` (with the existing remedy text) instead of returning `None`.
  - Arm (c) is the one #5232 targets, and it becomes dead.
  - Arm (b) folds into the new raise.
  - Arm (a): a flat mission's resolved `placement_ref` already names the target ref, so `_placement_coord_filter` returns `None` and the same success arm runs.
  - Re-point INV-7 to "flat mission with a resolved placement_ref reaches the success arm" instead of deleting it.
  - **This is a behaviour change.** A context fault turns from a silent degrade into a refusal (exit 1). It needs its own red-first slice and an explicit decision on whether a context-resolution fault on a flat/legacy mission may refuse.

## 4. Sibling mission #5634

- `origin/issue-5634-mission-creation-degod` (2b7ad857f) and `origin/issue-5635-implement-degod` (fc05f136e) both exist. Each holds **only a scaffold commit** on top of `9adc68803`; neither has code yet.
- Symbol-level import overlap is small:
  - `ProtectionPolicy`
  - `get_current_branch`
  - `kernel.git.GitCommandError`
  - `mission_runtime` (`classify_topology` vs `single_branch_write_ref`)
  - `specify_cli.status.Lane`
- The real **semantic** overlap is the single_branch write-checkout policy:
  - dirty scan
  - occupancy (#5676)
  - the protected-target mission branch (`single_branch_write_ref` / `resolve_single_branch_write_ref` / `meta.mission_branch`)
- Agree with #5634 on who owns a public `lanes` write-checkout-policy seam, so the two missions don't each extract their own.

## 5. Hidden behaviour a move can break

### 5.1 Side-effect order in `implement()` (L2021-2301)

1. `mission is None` → print, then `Exit(2)`. This runs **before** `--recover` (SC-003).
2. `--recover` → `_run_recover_mode` (returns early).
3. `StepTracker` steps `detect`/`validate`/`create`, then a leading `console.print()`.
4. **detect**: `find_repo_root`, then the charter preflight `run_preflight_or_abort(consumer="implement")`, then `_detect_wp_context`. Failure → `tracker.error`, render, `Exit(1)`.
5. **validate**, in this order:
   1. `resolve_feature_target_branch`
   2. `_raise_if_status_commit_protected`
   3. status surface (`resolve_status_surface_with_anchor`)
   4. lanes dir (PRIMARY)
   5. `_ensure_wp_claim_preconditions` (genesis / deps)
   6. `_resolve_placement_ref`
   7. **`_ensure_planning_artifacts_committed_git` (can COMMIT)**
   8. bulk-edit gate
   9. `build_operational_context_for_claim` + `require_active_role`
   10. `resolve_workspace_for_wp(write_intent=True)`
   11. `_resolve_execution_lane` (`MissingLanesError` here)

   Any exception (blanket `except Exception`) → `Exit(1)`.

   Note: the planning auto-commit happens **before** the bulk-edit, operational-context, checkout-identity and write-checkout refusals. So a later refusal can leave a planning commit behind. This is existing behaviour; preserve it, and don't "fix" it in a move.
6. **create**, in this order:
   1. `_refuse_repo_root_checkout_if_unavailable` (single_branch wrong-branch / occupied / dirty). It runs **before** `_ensure_vcs_in_meta` writes `meta.json` (#5100 A3).
   2. `_resolve_active_lanes_manifest` (`--base` validation)
   3. `create_lane_workspace`. This step:
      - repeats the guard with `occupancy_verified` (claim base on the repo-root arm)
      - allocates the worktree (`DESTROYED_LANE` / `LANE_WORK_TIP_UNKNOWN` are raised in `worktree_allocator`)
      - installs the hook (prints the backup line)
      - writes frontmatter `base_*`
      - writes context
   4. `_start_wp_implementation_status` (status events / commit)
   5. `_report_workspace_created`
   6. the `→ Using explicit base ref` line (printed only after success, and not on a planning lane)

   On failure:
   - `typer.Exit` re-raises after rendering.
   - Anything else prints `tracker.error("create", "workspace allocation failed: …")` and then one of two messages:
     - `Error: Workspace allocation failed: {exc}`, or
     - the `workspace_created` variant naming a possibly-landed commit sha (#4888).
   - It then prints `Next step:` for 3 conflict types and exits 1.
7. `_commit_wp_claim_status`. Only three exceptions propagate: `SafeCommitPathPolicyError`, `SafeCommitHeadMismatch` and `PlacementResolutionRequired`. Everything else becomes the yellow `Warning: Could not update WP status` and **exit 0**.
8. `--json` → `print(json.dumps(payload))`. Otherwise the ready banner.

Decorators are `@_json_safe_output @require_main_repo`. In `--json` mode the console is captured, and on a non-zero `typer.Exit` the payload carries the **last 20 captured lines** as `error`. Any reordering of prints changes the JSON error text.

### 5.2 Refusal producers and what pins them

`StructuredError.__str__` is the message only. `implement`'s broad `except` drops `error_code`, so the CLI output never shows codes; the test file itself says so at `test_single_branch_implement_refusals.py:273-278`. The codes are pinned only at the exception level.

| Refusal | Produced at | Pinned by |
|---|---|---|
| `WRITE_CHECKOUT_WRONG_BRANCH` | `implement_support.py:40` (class), raised `:161-167` | `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py:286-333` (substrings "Check out 'trunk'"); `tests/specify_cli/orchestrator_api/test_single_branch_repo_root_workspace.py` |
| `WRITE_CHECKOUT_OCCUPIED` | `:46`, raised `:170-185` | same file `:382-411`. **Near byte-exact**: the full `move-task … --to blocked --mission … --note "<reason>"` remedy and "use --to canceled instead if the work is abandoned". Also `tests/integration/test_single_branch_write_checkout_e2e.py`. |
| `WRITE_CHECKOUT_DIRTY` | `:52`, raised `:194-199` | same file `:467-530` ("Commit or stash them", the listed path, the lock dir excluded); also `meta.json` must have no `vcs` after a refusal (`:480,488`), which pins the refusal-before-VCS-lock order |
| `MissingLanesError` | `lanes/persistence.py:168` (`require_lanes_json`), reached via `implement.py:1590-1604` | `tests/lanes/test_persistence.py`, `tests/agent/test_implement_command.py`, `tests/architectural/test_workspace_resolution_doc.py` and ~10 integration tests |
| `DESTROYED_LANE` | `lanes/worktree_allocator.py:216` (class), raised `:491,498,539,543` | `tests/lanes/test_destroyed_lane_guard_*.py`, `test_issue_4889_destroyed_lane_guard.py`, `tests/orchestrator_api/test_issue_4889_caller_independence.py` |
| `LANE_WORK_TIP_UNKNOWN` | `worktree_allocator.py:281`, raised `:525,535` | `tests/lanes/test_destroyed_lane_guard_tip_rows.py` |
| not finalized | `implement.py:1520` (`WorkPackageStartRejected`), duplicated at `status/work_package_lifecycle.py:214` | `tests/agent/test_implement_command.py` and others |
| deps gate | `implement.py:1532` (`ValueError("dependencies_not_satisfied: {wp} depends on {…}; all dependencies must be approved or done before implementation can start")`) | `tests/agent/test_implement_command.py:387` (substring) |
| `--mission` required | `implement.py:2026` exit **2** | SC-003 tests |
| base ref unresolved | `implement.py:291` `_BASE_REF_UNRESOLVED_MSG` | `tests/cli/commands/test_implement_base_flag.py` |

The dependency gate is one of six call sites of `dependency_readiness_for_wp`:

- `implement.py:1529`
- `workflow_executor.py:684`
- `runtime/next/discovery.py:152`
- `orchestrator_api/{commands.py:453, wp_lifecycle.py:489}`
- `status/dependency_verdict.py:56`
- `tasks_status_view.py:235`

The comment says the authoritative gate is `GuardContext.dependency_ready`. The implement copy is "pre-flight UX only".

### 5.3 Structural pins a move will trip

- **Source-inspection tests on `implement()`'s own body:**
  - `test_implement_placement_routing.py:97,125` needs `except PlacementResolutionRequired:` and `except SafeCommitHeadMismatch:` to appear before the `Could not update WP status` print, inside `inspect.getsource(implement)`.
  - `:307` scans the whole module for the forbidden `coord_branch if coord_branch else planning_branch`.
  - `test_operational_context_wiring.py:254` needs `build_operational_context_for_claim` and `require_active_role` inside `implement`'s source.
  - Moving the orchestration out of `implement()` breaks all three. Re-point them; don't weaken them. The precedent is workflow_executor T013 "moved AST-anchor target".
- **Architectural gates keyed by file path and qualname:**
  - `test_no_write_side_rederivation.py:260` allow-list descriptor for `implement.py::_status_commit_destination_branch` (staleness twin-guard)
  - `test_wp_integrity_partition_call_shape.py:47` (`_IMPLEMENT` path)
  - `test_trio_seam_only.py:98-99` (`implement.py` / `implement_cores.py` shells)
- **Monkeypatch targets:**
  - 93 string targets on `specify_cli.cli.commands.implement.*`, across 58 test files.
  - Top targets: `find_repo_root` 15, `detect_feature_context` 15, `resolve_feature_target_branch` 14, `create_lane_workspace` 12, `_ensure_planning_artifacts_committed_git` 12, `_ensure_vcs_in_meta` 8, `start_implementation_status` 6.
  - There are about 11 more object-style `setattr(implement_module, ...)` patches.
  - After a verbatim move, a patch left on `implement.*` silently stops intercepting.
  - The precedent is `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py` (the #5629/#5684 patch-liveness gate). Clone it for `implement*` modules **before** moving anything.
- **Canonical-path coupling:**
  - `agent action implement` calls the Typer function directly: `workflow.py:83` imports `implement as top_level_implement`, and `:1620` calls it with keyword args. That goes through both decorators.
  - Four tests patch `workflow.top_level_implement`.
  - Keep `implement()`'s signature and decorator stack, or switch `workflow.py` to call the new orchestrator in a separate, labelled step.
- `__all__ = ["_ensure_vcs_in_meta", "find_wp_file", "implement"]` (L2304) must keep re-exporting.

### 5.4 Scoping correction for #5635's phase list

**Auto-rebase is not in implement.py.** The re-entry self-heal and auto-rebase run in:

- `agent/workflow.py:1630-1636` (`reenter_lane_self_heal`)
- `lanes/implement_support.py:521,832-852`
- `lanes/lifecycle_sync.py:158`

Dependency-lane merges happen inside `worktree_allocator.allocate_lane_worktree`. The real phases of `implement.py` are:

1. detect / charter preflight
2. validate: target, protection, status surface, deps gate, **planning-artifact commit**, bulk-edit, operational context, workspace resolution, lane
3. write-checkout refusal
4. VCS lock
5. allocate/reuse
6. status start
7. claim commit
8. render

---

# Appendix C: Gates lens (reviewer-renata), verbatim

# Grounding: gates that touch the implement.py decomposition (#5635) + C-004 removal (#5232)

Delegate: reviewer-renata, read-only. HEAD = origin/main `9adc68803`.
Profile loaded: `spec-kitty agent profile show reviewer-renata` (reviewer; directives 001/024/030/032/041/051; tactics code-review-incremental, reverse-speccing, delete-the-assertion-not-the-test). Charter context: `spec-kitty charter context --action review --json` (bootstrap). Applied: DIRECTIVE_041 (stale allow-list rows are deleted or re-pointed, never kept as dead weight), DIRECTIVE_043 (non-vacuity: a scan that silently loses its subject is a regression), "re-point, never loosen", and no new size or ratchet gates (operator ruling).

## 0. Current baseline on main (all green)

```
uv run --frozen pytest -q -p no:randomly -n0 \
  tests/architectural/test_trio_seam_only.py tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_wp_integrity_partition_call_shape.py tests/architectural/test_exemption_registry_ratchet.py \
  tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_status_module_boundary.py \
  tests/architectural/test_safe_commit_import_boundary.py tests/architectural/test_cold_import_status_boundary.py \
  tests/architectural/test_planning_lane_branch_requires_target.py tests/architectural/test_git_matrix_paths_resolve.py \
  tests/architectural/test_workspace_resolution_doc.py tests/lanes/test_lane_context_single_writer.py
# -> 165 passed in 70.95s

uv run --frozen pytest -q -p no:randomly -n0 \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_ratchet_baselines.py tests/architectural/test_ruff_format_exclude_ratchet.py \
  tests/architectural/test_layer_rules.py tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py
# -> 179 passed in 218.39s

uv run --frozen ruff check <implement.py implement_cores.py workspace/context.py lanes/implement_support.py core/dependency_graph.py status/transition_pipeline.py>
# -> All checks passed
uv run --frozen ruff check --select C901 --config 'lint.mccabe.max-complexity=15' <same 6 files>
# -> All checks passed. At threshold 10: implement() = 15 (AT the ceiling), _commit_planning_artifacts_transaction = 11
uv run --frozen ruff format --check --force-exclude <same 6>      # 5 formatted (implement_cores.py excluded)
uv run --frozen ruff format --check src/.../implement_cores.py    # Would reformat (format-debt ratchet entry, pyproject.toml:525)
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check   # rc=0
mypy --strict (narrow): workspace/context.py, lanes/implement_support.py, status/transition_pipeline.py, implement_cores.py -> clean
mypy --strict core/dependency_graph.py -> 2 PRE-EXISTING errors (:90, :123 no-any-return)
mypy --strict implement.py -> "clean" only because it is quarantined (ignore_errors, pyproject.toml:2675).
  Unquarantined (temp config copy) -> 5 errors: :175 _json_wrapper_handle_typer_exit, :288 resolve_feature_target_branch,
  :1830 _claim_policy_metadata, :1902 _refuse_repo_root_checkout_if_unavailable, :1976 implement (untyped decorator).
```

## 1. Gates that scan a FIXED file list containing implement.py. Moved code silently leaves the scan (false green)

These are the most dangerous ones: moving code out of implement.py leaves them green while the moved code is no longer scanned. The precedent (#2026 executor split, #5629/#5695 move-task split, coord-authority-trio-degod) is to add the successor module to the scope list in the same PR. That widens the scope; it does not loosen the gate.

| Gate | List | What it checks | Required action when code moves |
|---|---|---|---|
| tests/architectural/test_exemption_registry_ratchet.py:79 (`CHURN_SURFACE_MODULES`, implement.py at :116) | R-014 filename-exemption collections in dirty-state/churn predicates | Add every new sibling module, and any seam that receives a dirty-state/churn predicate, to `CHURN_SURFACE_MODULES` (comment: "folded here by the WP that introduces it"; #5629 precedent). |
| tests/architectural/test_trio_seam_only.py:104 (`_TRIO_FILES`), :119 (`_CORE_FILES`) | T027 seam-only read-path imports; T028 no I/O in pure cores | Add the new `cli/commands/implement_*.py` siblings to `_TRIO_FILES`. A new PURE core goes in `_CORE_FILES` too. Do NOT move I/O code into implement_cores.py, because T028 reds (only the allowlisted `_SubprocessGitPort` sites are exempt). |
| tests/architectural/test_no_write_side_rederivation.py:88 (`_PRE_WRITE_DIR_ADOPTED_MODULES`, frozen historical) / :126 (`_WRITE_DIR_CONSUMER_MODULES`) | root_walk / mid8 recompute / HEAD-selector grammars | Add successors to `_WRITE_DIR_CONSUMER_MODULES` (NOT the frozen `_PRE_` tuple; #5629/#5695 precedent). lanes/implement_support.py, workspace/context.py and core/dependency_graph.py are currently NOT in scope, so code moved there exits the scan unless added. |
| tests/specify_cli/test_mid8_contract_sensitive_routing.py:59 | negative `mission_id[:8]` scan | add successors |
| tests/specify_cli/status/test_cutover_byte_stability.py:63 (`_WP04_OWNED_SRC`) | zero predicate refs | add successors |
| tests/specify_cli/test_meta_fail_closed_full_census_contract.py:86 | WP09-owned files retain only silent sites | add successors (the always-on twin test_lifted_root_meta_fail_closed_census is whole-tree, so it is safe) |
| tests/contract/test_terminology_guards.py:53 and tests/contract/test_feature_alias_scope.py:60 (`FORBIDDEN_SCAN_ROOTS`) | `--feature` alias / terminology | new cli/commands siblings are already covered by the `CLI_COMMAND_GLOBS` glob for some checks, but the explicit de-aliased list is per-file. Add successors that carry user-facing strings. |

## 2. Gates that pin implement.py by path, symbol or content. They go RED loudly on a move, so re-point them

- tests/architectural/test_no_write_side_rederivation.py:259-268 `_ALLOW_LIST_SEED` (rel_path implement.py, qualname `_status_commit_destination_branch`, implement.py:128-130) plus the twin guard at :484 `_seed_and_key_for("src/specify_cli/cli/commands/implement.py")`. If the function moves, re-point both `rel_path` and the literal at :484 (the workflow -> workflow_cores re-point is the precedent, with a rationale line). If C-004/#2453 work ROUTES the selector, DELETE the entry and the twin test (it is shrink-only, and the twin's message says so). Never leave a vacuous entry.
- tests/architectural/test_wp_integrity_partition_call_shape.py:47 `_IMPLEMENT` plus the non-vacuity floor at :157 (`>= 3` `_run_planning_artifact_commit` calls). Moving `_commit_planning_artifacts_transaction` (implement.py:1048) reds the floor, so re-point `_IMPLEMENT` to the new home (or scan both files). Keep the floor at 3.
- tests/architectural/dead_symbol_allowlist.yaml:652-657 `category_b_grandfathered_legacy` rows for `specify_cli.cli.commands.implement::_ensure_vcs_in_meta` and `::find_wp_file` (both in implement.py `__all__`, :2304). Moving or deleting them makes the rows go STALE (GONE verdict), which reds test_no_dead_symbols. Re-key them to the new module, or delete them if the symbol gains a src caller or is removed. The baseline count in `_baselines.yaml` `test_no_dead_symbols` warns on shrink and does not fail.
- tests/architectural/test_owned_checkout_single_authority.py:89 G6 pins `workspace/context.py::resolve_workspace_for_wp` as a contract-s7 consumer. Keep that def in place. Moving more code INTO workspace/context.py is fine.
- Source-shape pins outside tests/architectural (`getsource`/`read_text` of implement.py): tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py:86-89 (asserts that implement.py references `resolve_mission_read_path`), tests/specify_cli/test_operational_context_wiring.py, tests/specify_cli/cli/commands/test_implement_placement_routing.py, test_implement_writeside.py, test_precondition_ref_unification.py, tests/integration/test_wp_integrity_checkout_identity.py, tests/agent/test_implement_programmatic_call.py. These red loudly when a pinned substring moves, so re-point them to the new module. Do not delete the assertion.
- Import-site tests that import private helpers from implement (e.g. `_partition_files_for_commit`, `_load_fallback_mission_meta`, `_feature_dir_file_paths`, `_run_bulk_edit_gate_and_inference`, `_load_primary_anchored_mission_meta`). They red with ImportError and must be re-pointed.

## 3. Patch-target liveness. NOT covered by any gate today (HIGH, silent)

- The gate from #5629/#5684/#5695 is tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py. Its scope is DERIVED as `agent/tasks_*.py` plus the `tasks` bridge (:58), so it does not apply to implement.py. Its rule: a patched `(module, name)` is live only if that module reads the name as a module-global `Name` load outside the name's own def (or lazily imports it inside a function). Re-export `ImportFrom` lines never count. Unresolvable targets are counted against a baseline (1).
- Exposure: tests patch `specify_cli.cli.commands.implement.<name>` 94 times as string targets over 15 names, plus about 13 `monkeypatch.setattr(implement_mod, "...")` sites. The top targets are find_repo_root 15, detect_feature_context 15, resolve_feature_target_branch 14, create_lane_workspace 12, _ensure_planning_artifacts_committed_git 12, _ensure_vcs_in_meta 8, start_implementation_status 6, resolve_workspace_for_wp 3, find_wp_file 2, _resolve_placement_ref 2, plus single uses of get_current_branch, _report_workspace_created, _print_workspace_ready_banner, _commit_wp_claim_status, ProtectionPolicy and _load_primary_anchored_mission_meta. The full list is at scratchpad/impl_targets.txt.
- When a caller moves to a seam and still calls `find_repo_root` etc. through the seam's own globals, every patch on `implement.find_repo_root` stops intercepting and the test stays green against the real function. That is the exact #5629 failure class.
- Honest options (operator decision):
  - (a) generalize the EXISTING liveness gate's derived module set to cover `cli/commands/implement*.py` (this is a scope widening of an existing correctness gate, not a size or ratchet gate);
  - (b) without a gate, do a per-move manual audit: for every moved function, grep `implement\.<callee>` patch targets for each global it calls and re-point them to the new module, then record the audit in the PR.
  - Recommend (a), or at minimum (b) plus a red-first proof per re-pointed patch (temporarily break the patched collaborator and see the test go red).

## 4. Re-export shims in implement.py

- implement.py:69-91 already carries a `# noqa: F401 -- shim re-export` block from implement_cores, and `__all__` at :2304.
- test_compat_shims.py only governs `compat/_adapters/`, and test_unregistered_shim_scanner only governs `__deprecated__ = True` modules. NO gate counts or forbids re-export lines in implement.py.
- BUT test_no_dead_symbols counts a `from new_mod import name` in implement.py as a src caller. A moved public symbol that is re-exported only so that tests can patch or import it therefore looks live, which masks dead code. Re-exports also defeat the liveness rule (an `ImportFrom` does not make a patch intercept).
- Recommendation: re-point tests to the new home. Do not add new re-exports kept only for tests. Keep `implement` (the Typer command) and real cross-module callers.

## 5. Layer, import and boundary gates (green on main; constraints for where code may land)

- test_layer_rules.py: specify_cli is the top layer, so intra-package moves add no ledger edges. TestMergeCliBoundary forbids only `consolidation/**` from importing `specify_cli.cli`. Moving code into lanes/workspace/core/status is not layer-gated against cli imports, but a seam importing `specify_cli.cli.*` is an architectural smell and a circular-import risk, so pass `console` and callables in rather than importing cli.
- test_cold_import_status_boundary.py:36-49: `task_utils.support`, `core.owned_mission` and `cli.commands.charter` must not transitively load `specify_cli.status*` or `specify_cli.workspace*`. Do not add module-level status/workspace imports to core/dependency_graph.py (or any core leaf) reachable from those roots. Keep them lazy.
- test_status_module_boundary.py SR-2 (whole tree): no `specify_cli.status.<submodule>` imports outside the exempt files. implement.py uses the facade, and new modules must too. workspace/context.py is a permanent cycle-breaker exemption (:145) for `status.wp_metadata` only, so do not widen what it imports from status submodules.
- test_safe_commit_import_boundary.py (whole tree; the implement mention at :105 is a comment): no new `safe_commit(destination_ref=...)` callers, and `core.commit_guard.evaluate` importers are blessed-only.
- tests/lanes/test_lane_context_single_writer.py: `save_context` is called ONLY from `lanes.worktree_allocator.persist_lane_context`, so do not move any save_context call into workspace/context.py callers.
- test_planning_lane_branch_requires_target.py (whole tree, floor 5): every `lane_branch_name` call must pass `target_branch=`.

## 6. Dead modules / dead symbols for new modules

- test_no_dead_modules: every new module needs a non-test src importer (implement.py importing it is enough).
- test_no_dead_symbols: every new public module-level name needs a src `from mod import name` caller or intra-module use. Prefer `_private` names for helpers that are used only inside the module.

## 7. Lint, type and format

- Complexity: `implement()` (implement.py:1977) is exactly 15 = the ceiling, and there is no per-file C901 ignore for implement.py (ruff.toml has none; pyproject only has ignores for agent/*). The C-004 fallback removal should drop it; any added branch reds C901.
- mypy: implement.py is in the transitional quarantine (pyproject.toml:2675, ignore_errors). New sibling modules are NOT quarantined. CLAUDE.md requires new code to be strict-clean, and adding a new module to the quarantine list would be loosening (forbidden). So the 4 latent errors move with their functions and must be FIXED on move: `_json_wrapper_handle_typer_exit` (getattr default type), `resolve_feature_target_branch` (Any return), `_claim_policy_metadata` (Any return), `_refuse_repo_root_checkout_if_unavailable` (Any return). core/dependency_graph.py already has 2 strict errors on main (:90, :123), so a narrow check there is red at baseline. Fix them in passing (campsite) or record them as pre-existing.
- mypy is NOT a CI job (no `mypy` in .github/workflows; `make typecheck` covers 2 files only). It is policy, not a gate, so it must be run and recorded manually.
- Format: implement.py is NOT in `[tool.ruff.format].exclude`. implement_cores.py IS (pyproject.toml:525) and is unformatted. test_ruff_format_exclude_ratchet.py enforces count <= 2808, no dangling entries, and that every entry still genuinely reformats. If you touch implement_cores.py and format it, you MUST delete its exclude entry (and likewise for the many tests/... implement test files listed at pyproject.toml:811-1890 if they get reformatted or renamed). New files must be formatted, and the exclude list may not grow.

## 8. CI routing and coverage (no red on main, but material to "keep green honestly")

- Router (scripts/ci/gate_selection.py, simulated):
  - implement.py or a new cli/commands/implement_*.py -> only module `cli` (tests/cli);
  - lanes/implement_support.py -> `lanes`;
  - core/dependency_graph.py -> core_misc + specify_cli_runtime;
  - status/transition_pipeline.py -> core_misc, execution_context, status, unit;
  - workspace/context.py -> unmatched src -> RUN-ALL (fail-closed; no registry row roots workspace/**).
- .github/ci-module-registry.yml:484 lists `tests/specify_cli/cli/commands` as OUT-OF-MATRIX. Most `test_implement*.py` files live there (about 12 files), so per-PR CI does not run them, and tests/agent (the agent row) is not selected for an implement.py-only diff. The per-PR safety net for this refactor is thin. The mission must run those directories locally and record the counts in the PR. (Context: coverage_breadth_baseline.json shows implement.py at 260/647 statements in-matrix.)
- The diff-cover >= 90% gate is scored only over `CRITICAL_PATHS` (scripts/ci/aggregate_source.py:19). These include `src/specify_cli/status/*` and `src/mission_runtime/*` but NOT cli/lanes/workspace/core. Any lines moved INTO status/transition_pipeline.py count as new critical lines and need >= 90% coverage from IN-MATRIX tests (status, unit, core_misc, execution_context, ...). Coverage from the out-of-matrix tests/specify_cli/cli/commands does not count. Moving code into the status pipeline therefore requires matching tests under tests/status or tests/unit in the same PR.
- New modules need no registry or router registration while they stay under existing rooted dirs (cli/**, lanes/**, core/**, status/**). A new top-level package would need wheel `packages` (test_pyproject_shape) plus a registry row; avoid that.
- scripts/ci/derive_pinning_inventory.py is unrelated: it derives rules that pin the retired Sonar job (subjects `sonarcloud` / `ci-quality.yml` / `make test-fast`, hard-coded at :131). It has no implement subject and was not affected (`--check` rc=0).

## 9. Docs and prose (no gate; stale after a move)

- docs/architecture/wp-runtime-state-eviction.md:37,80 cite `implement.py:1730` and `implement.py:1328` (raw line numbers, ungated, and already drifting).
- docs/development/reference/read-side-seam-classification.md:603-606 lists `implement.py :: find_wp_file / _load_primary_anchored_mission_meta / _planning_artifact_source_dir / _build_implement_json_payload`. It is a referenced ledger but not cross-checked by a test. Update it if those functions move.
- The comments in test_safe_commit_import_boundary.py:105, test_planning_lane_branch_requires_target.py:10 and test_git_matrix_paths_resolve.py:79 mention implement.py. Only the matrix doc table is checked, and only for file existence (implement.py stays, so it stays green).
- CLAUDE.md names lanes/implement_support.py (WRITE_CHECKOUT_* refusals) and workspace/context.py::resolve_workspace_for_wp. Both stay valid if those homes are kept. CLAUDE.md does not cite implement.py line numbers.

## Verdict

Baseline is GREEN on main (344 gate tests passed, ruff clean, pinning check rc=0). The decomposition is feasible without loosening anything. The PR must, in the same change:

1. widen the fixed-list scans to follow the code: CHURN_SURFACE_MODULES, _TRIO_FILES (and _CORE_FILES if a pure core is added), _WRITE_DIR_CONSUMER_MODULES, and the 5 non-architectural per-file negative scans;
2. re-point the path/symbol pins: the WS#3 descriptor and its twin, the `_IMPLEMENT` partition gate, the 2 dead-symbol allowlist rows, and the source-shape and import tests;
3. solve patch-target liveness for about 107 implement patch targets. No gate covers it today, so an operator decision is needed between extending the existing liveness gate and a manual red-first audit;
4. make moved code mypy-strict-clean, since the quarantine must not grow;
5. run the out-of-matrix tests/specify_cli/cli/commands and tests/agent locally, because per-PR CI will not.

Moving code into status/* additionally triggers the diff-cover 90% critical-path gate.
