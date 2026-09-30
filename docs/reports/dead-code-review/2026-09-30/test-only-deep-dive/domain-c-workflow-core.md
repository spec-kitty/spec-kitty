---
doc_status: active
updated: '2026-09-30'
---

# Test-only deep dive — Domain C: workflow core

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

Checkout: `/home/claude/spec-kitty` at bd1577a3. The checkout was unshallowed mid-run, so every history lookup below uses the full history. Every line count is a `wc -l` or an AST span.

| # | slice | symbols | src LOC | test LOC | verdict | confidence | behaviour gap? |
|---|---|---|---|---|---|---|---|
| 1 | core/worktree.py legacy workspace creation | `create_wp_workspace`, `create_feature_worktree`, `setup_feature_directory`, `_ensure_spec_kitty_exclude`, `_exclude_from_git`, `_existing_worktree_is_valid`, `_create_workspace_with_fallback`, `_compose_worktree_feature_dir`, plus collateral `GitPreflightError`/`is_deterministic`/`_DETERMINISTIC_PREFLIGHT_CODES` | ~570 + ~35 | ~1,570 | **WIRE a working FR-016 exclude into the lane allocator first, then DELETE** | High | **YES (P1 bug candidate):** FR-016 has never reached a live worktree, and the dead writer does nothing even when called |
| 2 | core/vcs `GitVCS` / `VCSProtocol` | the whole class and Protocol; `get_vcs`/`_instantiate_backend`/`_get_locked_vcs_from_feature`; most of types.py and exceptions.py | ~846 + 267 + ~250 | ~1,100 | DELETE after slice 1 (OWNER-DECISION on the abstraction) | High (dead) / Medium (scope) | minor: the allocator skips `run_git_preflight` |
| 3 | subtask checkbox writers | `count_subtask_rows`, `count_wp_section_subtask_rows`, `uncheck_wp_section_subtask_rows` | 67 | ~260 | MOVE-TESTS-THEN-DELETE | High | no |
| 4 | context_validation leftovers | `require_worktree`, `set_context_env_vars`, `get_context_env_vars` (+ DEAD `require_either`) | 116 | ~130 | DELETE | High | no |
| 5 | core path/topology/git_ops helpers | `has_tracking_branch`, `resolve_with_context`, `check_broken_symlink`, `assert_worktree_supported` + `StatusReadUnsupported`, `render_topology_text` | 122 | ~200 | DELETE | High | no |
| 6 | status write-door residue | `append_event_jsonl`, `filter_dossier_snapshots`, `coordination.status_service.append_event_log` | 43 | ~60 direct + ~40 call sites | DELETE the first two; MOVE-TESTS-THEN-DELETE `append_event_log` | High / Medium | no |
| 7 | status FSM and helper leftovers | `_run_guard`, `WPState.can_transition_to`, `findings_by_category`, `_Builder.append_to_history`/`append_dependency`, `ArtifactVerdict`/`EmissionArtifactVerdict`, `assert_birth_invariant_holds` | ~95 | ~250 | mixed (see slice) | Medium | no |
| 8 | consolidation leftovers | `is_safe`, `_print_remediation_lines`, `display_merge_order`, `_durable_done_wps_on_coordination_ref`, `_final_authored_blobs`/`_deletions`, `lane_integrated_by_tree_or_ancestry`, `progress_percent`, `set_pending_conflicts`, `RollbackReport.advanced_branches` | ~130 | ~350 | mostly MOVE-TESTS-THEN-DELETE / DELETE | Medium-High | no |
| 9 | surface_authority forward API (#2160) | `_classify_noncommit_outcome`, `_exit_code_for` | 46 | ~250 | OWNER-DECISION (wire into the CLI exit mapping, or delete) | Medium | no |
| 10 | git/gitignore/lanes helpers | `protect_selected_agents`, `get_agent_directories`, `protected_branches`, `SparseCheckoutReport.any_active`, `is_mission_branch`, `is_legacy_branch` | ~100 | ~250 | DELETE 4, KEEP 2 | Medium-High | no |
| 11 | runtime-state backfill utilities | `backfill_runtime_state_repo`, `run_backfill_and_verify`, `assert_zero_readers` + `find_field_readers` | ~157 | ~150 | MOVE-TESTS-THEN-DELETE (fix the runbook first) | Medium | no |
| 12 | mission / metadata / missions surface | `get_active_mission`, `discover_missions`, `validate_deliverables_path`, `get_template`/`get_workflow_phases`/`get_path_conventions`, `clear_coordination_metadata`, `get_change_mode`/`set_purpose_summary`, `resolve_feature_dir_for_slug`, `is_mission_archived`, the `missions/__init__` lazy shim, `clear_mission_brief` | ~390 | ~900 | mixed; `validate_deliverables_path` is an OWNER-DECISION (security) | Medium | **possible:** research deliverables path is unvalidated |
| 13 | forward contracts never wired | `policy/audit.py` (module), `acceptance/post_consolidation.py` (module), `GateExecutionContext.not_applicable_below` | 89 + 310 + 21 (+159 script) | 62 + 336 + part of 811 | OWNER-DECISION (recommend DELETE `policy.audit`; wire or retire the others) | Medium | contract/docs promise enforcement that does not run |
| 14 | upgrade / task_utils residue | `apply_text_replacements`, `exclude_paths`, `NEVER_SEED_VARS`, `WorkPackage.authored_*` | ~87 | ~300 | DELETE / KEEP-with-note | Medium | no |

**Headline.**
- **The worktree finding is worse than the first pass reported.** FR-016's `.spec-kitty/` writer was added on 2026-04-14 (976d7169d, #625). It went only into `create_feature_worktree`, which had no caller since 2026-01-11, and `create_wp_workspace`, which never had one. The lane allocator it should have gone into already existed (7d7496cae, #377, 2026-04-04). So the writer has never run in production.
- **The writer would not work even if wired.** It writes to the per-worktree git dir (`.git/worktrees/<name>/info/exclude`), and git ignores that file. I checked on git 2.43: `git rev-parse --git-path info/exclude` resolves to the *common* dir, and `?? .spec-kitty/` still shows after the writer runs. The #79 symlink excluder `_exclude_from_git` has the same defect.
- **The practical impact is real.** `.spec-kitty/review-lock.json` is written into live lane worktrees by `workflow.py:1853`. Nothing ignores it: `get_runtime_gitignore_entries()` has no `.spec-kitty/` entry, and it is absent from `_owned_status_prefixes`. Reproduced: a leftover lock makes `_validate_worktree_clean` raise `DirtyWorktreeError` on the lane REUSE and CRASH-RECOVERY routes (worktree_allocator.py:1087, :1150). `dirty_paths` also reports it for single_branch write checkouts (`WRITE_CHECKOUT_DIRTY`). A stray `git add -A` would commit it.
- **The fix is small and already in the codebase:** `core.git_ops.exclude_from_git_index(repo_root, [".spec-kitty/"])` (git_ops.py:284). It writes the common-dir exclude and is live through migration m_0_13_1. I verified that it silences the entry. The alternative is to register `.spec-kitty/` as an IGNORED state surface.
- **The cleanup behind it is large.** Once that lands, slices 1+2 delete about 1,900 src LOC and about 2,700 test LOC. The other slices are ordinary cleanup with a handful of move-tests-first cases.

---

## Slice 1: core/worktree.py legacy workspace creation (FR-016)

- **What it is.** `create_feature_worktree` created a mission-level worktree `.worktrees/<slug>-<mid8>` through the VCS abstraction, with a direct-git fallback. It wrote the FR-016 exclude and then ran `setup_feature_directory`, which did three things: scaffolded `kitty-specs/<dir>/{checklists,research,tasks}`, wrote a tasks README, and symlinked `.kittify/memory` and `AGENTS.md` into the worktree, then excluded those symlinks. `create_wp_workspace` routed a WP by `execution_mode`: `planning_artifact` went to `create_planning_workspace`, `code_change` went to `vcs.create_workspace`. The file itself is live: its lower half (`validate_feature_structure` and helpers, worktree.py:609-836) is imported by `cli/commands/agent/mission.py:63` and must stay.
- **History.**
  - `create_feature_worktree`/`setup_feature_directory`: introduced e0e002f53 (2025-12-17). `create_feature_worktree`'s only caller (`agent/feature.py`) was removed in fd82f6cb0 (2026-01-11, 0.11.0 "planning in main, no worktrees during specify"). `setup_feature_directory`'s last outside mention was removed in d1dafbaf4 (#360, 2026-04-01).
  - `create_wp_workspace`: introduced 5d2386574 (#347, 2026-03-30). **It never had a caller outside the file.**
  - `_exclude_from_git`: 9fb2c7ffd (2026-01-20, issue #79).
  - `_ensure_spec_kitty_exclude`: 976d7169d (#625, mission `legacy-sparse-and-review-lock-hardening-01KP54ZW`, WP07, FR-016). Its WP07 `owned_files` listed only `core/worktree.py`, so the live allocator was never in scope.
  - The live lane allocator `lanes/worktree_allocator.py` was added in 7d7496cae (#377, 2026-04-04). The last `vcs.create_workspace` use outside this file was removed in 87058c1d9 (#398, 2026-04-05, "Enforce lane-only worktree runtime").
- **What replaced it.**
  - `lanes/worktree_allocator.py::allocate_lane_worktree` (:959) with `_create_lane_worktree` (:1843, raw `git worktree add -b`) and `_recover_lane_worktree` (:1862). It is called from `lanes/implement_support.py:346` and `orchestrator_api/commands.py:1488`.
  - Planning-artifact routing: `implement_support.py:531-542` and `workspace/context.py:801` (both call `create_planning_workspace`).
  - Reuse validation: `_validate_worktree_clean` (:1813).
  - Mission-level worktree and feature scaffolding: dropped by design (0.11.0: planning on primary).
- **What the legacy path did that the allocator does not:**
  1. **FR-016 `.spec-kitty/` exclude.** Absent from the allocator and from everything it calls: `_create_lane_worktree`, `_recover_lane_worktree`, `_register_sparse_checkout_if_coord` → `coordination.register_lane_sparse_checkout`, `_merge_*`, `record_tip`, `_backfill_context_if_missing`. `rg '\.spec-kitty/' src` finds a writer only in the dead worktree.py. **The dead writer is also inert:** it resolves `git rev-parse --git-dir`, which gives `<common>/worktrees/<name>`, and git never reads `info/exclude` there. Reproduced in scratch on git 2.43.0: after the writer ran, `git status --porcelain` still showed `?? .spec-kitty/`. Appending the same line to the common-dir exclude (via `exclude_from_git_index`) cleared it. Consequences today:
     - lane REUSE and CRASH-RECOVERY refuse with `DirtyWorktreeError` when a review lock or empty-but-unremoved `.spec-kitty/` is present;
     - single_branch `implement` sees `.spec-kitty/` as operator dirt (`checkout_occupancy.dirty_paths`; `_owned_status_prefixes`, implement_support.py:55-72, lists only status files, `meta.json` and `.kittify/`);
     - only `move-task` filters it (`tasks_shared._RUNTIME_STATE_DENY_LIST`, :111).
  2. **#79 symlink exclude** (`_exclude_from_git`). Same inert per-worktree target. It is moot now because the allocator creates no symlinks, `.kittify/memory` is tracked (so lane worktrees are full checkouts that already contain it), and m_3_2_0rc35_unified_bundle removes legacy symlinks.
  3. **Git preflight.** `GitVCS.create_workspace` ran `run_git_preflight(check_worktree_list=True)` and surfaced typed `UNTRUSTED_REPOSITORY`/`WORKTREE_LIST_FAILED` errors with remediation commands. The allocator runs no preflight, so a safe.directory failure surfaces as a raw `RuntimeError(stderr)`. The degradation is to diagnostic quality only, not safety.
  4. The legacy git calls used `encoding="utf-8", errors="replace"` and `timeout=60`. The allocator's `subprocess.run` calls use neither. This is minor: a non-UTF-8 stderr could raise during decoding.
  5. Planning-artifact routing, reuse detection and `base_commit`: the live path has equivalents. No gap.
- **Tests that keep it alive:**
  - `tests/specify_cli/core/test_worktree.py` (475 LOC, 22 tests): all pin the dead copy, so (b) DELETE. Two classes need a note. `TestNoSparseCheckoutInVCS` pins GitVCS and goes with slice 2. `TestWorktreePreflightTypedException` pins `GitPreflightError` fallback semantics (NFR-007/#1893) that nothing live uses.
  - `tests/integration/core/test_worktree_exclude_spec_kitty.py` (208, 5): (b), with a note. Its docstring says the writer is "called from the live worktree-creation path", which is false. It asserts only file *content*, never `git status`, which is why the inert target went unnoticed. **Replace it with (a)-style tests on the allocator** that assert `git status --porcelain` is clean after `.spec-kitty/review-lock.json` is created in a freshly allocated lane.
  - `tests/core/test_worktree_symlink_fallback.py` (111, 2): (b).
  - `tests/specify_cli/core/test_cli_boundary_git_encoding.py` (36, 2: `GitVCS._get_git_dir`, `_exclude_from_git`): (b).
  - `tests/git_ops/test_worktree.py` (1,037, 45 tests): (c) SPLIT. DELETE `TestCreateFeatureWorktree`, `TestSetupFeatureDirectory`, `TestVCSAbstraction`, `TestExcludeFromGit` and `TestComposeWorktreeFeatureDir`: 31 tests, about 738 LOC. KEEP `TestValidateFeatureStructure` (14 tests, live) and `TestAssignNextMissionNumber` (3, tests the live `consolidation.ordering.assign_next_mission_number`).
  - Live coverage for the exclude: **uncovered**. Allocator tests exist (tests/lanes/*, tests/agent/test_orchestrator_lane_allocation.py), but none checks `.spec-kitty/`.
- **Open intent.** FR-016 in `kitty-specs/legacy-sparse-and-review-lock-hardening-01KP54ZW/spec.md:81` reads "When a lane worktree is created, spec-kitty writes `.spec-kitty/` to that worktree's `.git/worktrees/<lane>/info/exclude`". The requirement text itself names the inert location, so the spec needs amending too. Its status is `proposed`. The review lock module (`review/lock.py:14`) still claims the lock is "git-ignored". No open issue number is recorded; status unknown offline.
- **Risk if deleted.** No other repo imports it (spec-kitty-planning grep: 0 hits). `state/contract.py:435` names `owner_module="core/worktree"` for `worktrees_root`; point it at `lanes/worktree_allocator`. Deleting without the fix loses nothing that works today, because the writer is inert. But the FR-016 intent must be re-homed, or it is lost silently.
- **Verdict.** **WIRE, then DELETE.** High confidence.
  - Step 1 (bug fix): call `exclude_from_git_index(repo_root, [".spec-kitty/"])` in `allocate_lane_worktree` on all three routes (REUSE, CRASH-RECOVERY, FRESH), before `_validate_worktree_clean`. Add an upgrade migration modelled on `m_0_13_1_exclude_worktrees` for existing projects. Also consider adding `.spec-kitty/` to `_owned_status_prefixes` and registering it as an IGNORED `StateSurface`. Add allocator tests that assert on `git status`.
  - Step 2: delete worktree.py:37-606 (about 570 LOC) and `GitPreflightError`/`is_deterministic`/`_DETERMINISTIC_PREFLIGHT_CODES` (git_preflight.py, about 35 LOC; worktree.py is their only user). Delete the tests listed above (about 1,570 LOC).
- **Behaviour gap: YES.** FR-016 is unimplemented in production and the dead implementation is also wrong. Treat it as a bug to fix, not just cleanup.

## Slice 2: core/vcs `GitVCS` / `VCSProtocol`

- **What it is.** The VCS abstraction class covering workspace create/remove/list/info, conflicts, changes, commit and init. It was built for git plus jj; jj was removed in c2b10ce05 (#314, 2026-03-20).
- **History.** Introduced e3ed78eb8 (2026-01-17, "feat(vcs): Add VCS detection and factory function"), wired into implement in f6cc25f39 (2026-01-17, WP06). The last runtime method calls outside worktree.py (`vcs.create_workspace`, `vcs.get_workspace_info` in `implement.py`) were removed in 87058c1d9 (#398, 2026-04-05).
- **What replaced it.** Raw git helpers in the allocator, `git/destructive_guard.guarded_worktree_remove` for removal (its docstring at :249 already calls `remove_workspace` "dead code, zero production callers"), and the module-level `git_*`/`capture_branch_tip`/`merge_base_changed_files`/`git_get_reflog` functions in the same git.py (:886-1284), which are live and stay.
- **Live residue.** `cli/commands/ops.py:94` calls `get_vcs(workspace_path)` purely as a "git present?" probe and discards the result. `init.py` uses `VCSBackend`, `is_git_available` and `VCSNotFoundError`. `implement.py:1279` uses `VCSBackend`. No `GitVCS` method is invoked from src.
- **Tests that keep it alive:**
  - `tests/git_ops/test_git.py` (568, 32): (b), except `test_git_get_reflog`, which is (a) and moves to a reflog test.
  - `tests/git_ops/test_vcs_integration.py` (386, 13): (b), apart from the `is_git_available`/reflog assertions, which are (a).
  - `tests/git_ops/test_detection.py` (189, 15): (c). The `is_git_available`/`get_git_version` parts stay.
  - `tests/agent/cli/commands/test_ops.py` (377, 10): (c). It patches `get_vcs`; retarget to `is_git_available`.
  - `tests/specify_cli/lanes/test_lane_naming_gate_sites.py`: uses `get_vcs`/`_get_locked_vcs_from_feature`, (c).
  - Architectural pins: `test_destructive_op_routing.py:243` (census entry for `GitVCS.remove_workspace`, explicitly labelled "dead adapter") and :461-463 (`_KNOWN_DIRTY_PREDICATES` entries). Drop these entries with the class.
  - `TestNoSparseCheckoutInVCS` (slice 1 file).
- **Open intent.** None. Only the jj retirement ADR and #314 mention it, and no open issue plans a second backend.
- **Risk if deleted.** The public import path `specify_cli.core.vcs` (`__init__` exports `VCSProtocol`, `get_vcs`, and others). No hits in the offline spec-kitty-planning checkout; spec-kitty-saas and spec-kitty-events are not available offline, so that remains unconfirmed. Keep `VCSBackend`, `is_git_available`, `VCSNotFoundError`, `OperationInfo`, `ConflictType` and the module-level functions.
- **Verdict.** DELETE after slice 1. The class is dead (High confidence); whether to keep a `VCSBackend`-only façade is a Medium-confidence scope question for the owner. Removable: git.py:40-885 (about 846), protocol.py (267), and the unused types.py dataclasses and exceptions.py classes (about 250). Replace the ops.py:94 probe with `is_git_available()`. Tests: about 1,100 LOC.
- **Behaviour gap.** Only the preflight item in slice 1, point 3.

## Slice 3: subtask checkbox writers (core/subtask_rows.py)

- **What.** The dashboard progress counters (`count_*`) and the rollback unchecker for tasks.md checkboxes.
- **History.** Introduced 30496532d/b9667d6aa (#2504, 2026-07-09) and c9fe21e8b (#2513, 2026-07-09). The uncheck caller was removed in 04953ea44 (#2684, 2026-07-19); the count callers were removed in dfe6b2ead (#2816, 2026-07-21, runtime-state event-sourcing).
- **Replaced by.** The snapshot `subtasks` slot: `unchecked_subtask_ids_from_snapshot` (:337), and the rollback delta in `tasks_move_task.py:2978` ("#2513, via the log — not the checkbox"). The dashboard reads the snapshot.
- **Tests:**
  - `tests/specify_cli/core/test_uncheck_wp_section_subtask_rows.py` (157, 12): (b).
  - `tests/specify_cli/core/test_subtask_rows.py`: `count_subtask_rows` cases are (b). The `count_wp_section_subtask_rows` cases (:72-162) are **(a)**: they pin the shared `_walk_wp_section` heading rules (#2346 first-WP-token, NFR-005 no-reopen) that the live `iter_wp_section_subtask_rows` (migration backfill, backfill_runtime_state.py:551) and the guard rely on. Retarget them to `iter_wp_section_subtask_rows`. Direct live coverage exists but is thin (test_subtask_rows.py has 6 iter refs).
  - `test_find_unchecked_tasks_canon.py:123`: docstring mention only.
- **Intent.** The module docstring (:12, :31) still claims the "move-task --to planned rollback writer" and "dashboard progress" use it. That is stale and should be fixed.
- **Risk.** None.
- **Verdict.** MOVE-TESTS-THEN-DELETE. High confidence. src 67 LOC; tests about 260.
- **Gap.** No. (The acceptance gate still reads checkboxes via `iter_unchecked_subtask_rows`, which is by design.)

## Slice 4: context_validation leftovers

- **What.** The `@require_worktree` decorator and the `SPEC_KITTY_CONTEXT`/`SPEC_KITTY_*` env-var exporter and reader. `require_either` is DEAD.
- **History.** Introduced f672f4aed (2026-01-23, ADR 1.x `2026-01-23-5-decorator-based-context-validation`). **No src caller has ever existed** (`git log -S'require_worktree(' -- src` outside the file finds nothing).
- **Replaced by.** Nothing needed. Only `require_main_repo` is used (consolidate, implement, next_cmd), and `SPEC_KITTY_CONTEXT` is never read in src. Worktree-only commands resolve the workspace through `resolve_workspace_for_wp`.
- **Tests.** In `tests/agent/test_context_validation_unit.py` (659 LOC, 35 tests), `TestRequireWorktree` (:343-375) and `TestEnvironmentVariables` (:434-565) are (b), about 160 LOC. `TestEnvVarBypass` (:402) is (a): it asserts the filesystem beats the env var, on the live `detect_execution_context`. Keep it.
- **Intent/risk.** ADR 1.x lists the decorators; add a superseded note. They are in `__all__` and `_CATEGORY_B_GRANDFATHERED_LEGACY`; drop those allowlist rows.
- **Verdict.** DELETE (with `require_either`). High confidence. src 116 LOC.
- **Gap.** No.

## Slice 5: core path/topology/git_ops helpers

- **`has_tracking_branch`** (git_ops.py:258, 24 LOC). Introduced fd371dc48 (2026-01-26). The last callers (the merge upstream check) were removed in 87058c1d9 (#398). Push safety is now `consolidation/push_preflight` (`TargetBranchSyncStatus.is_safe_to_push`). Tests: `tests/git_ops/test_git_ops.py` (9 refs), (b). DELETE.
- **`resolve_with_context`, `check_broken_symlink`** (paths.py:366/:393; 43 LOC). WP01 foundation (baba1e674, 2025-12-17), **never called**. Tests: `tests/runtime/test_paths_unit.py`, (b). DELETE.
- **`assert_worktree_supported` + `StatusReadUnsupported`** (paths.py:689/:543; 30 LOC). Introduced c12cc95cb (#1034, mission 116). The docstring says it is "NOT called by any active command… available for future commands". Tests: `tests/core/test_paths_coverage_supplements.py`, `tests/status/test_status_read_worktree_resolution.py`, (b). DELETE. The speculative API has had no consumer in 4.5 months.
- **`render_topology_text`** (worktree_topology.py:323, 25 LOC). Introduced e1fc828fc (2026-02-07), **never called outside the module**. Production uses `render_topology_json` (workflow_executor.py:1361). Tests: `tests/init/test_worktree_topology.py` (2 refs), (b).
- **Verdict.** DELETE all. High confidence. src about 122; tests about 200.
- **Gap.** No.

## Slice 6: status write-door residue

- **`append_event_jsonl`** (status/emit.py:235, 18 LOC). Introduced 6e1e6f178 (2026-05-28, WP06 BookkeepingTransaction). It has **never had an outside caller**; production writes go through `coordination.status_transition` → `append_event_stream_log`. Tests: `tests/specify_cli/status/test_emit.py` (7 refs), (b). DELETE.
- **`filter_dossier_snapshots`** (status/preflight.py:63, 8 LOC). Introduced 409f74e6b (#867). It is a list wrapper that was **never called**. The live predicate `is_dossier_snapshot` is used at coordination/coherence.py:119/154. Tests: `tests/status/test_preflight.py` and `tests/integration/test_dossier_snapshot_no_self_block.py` should switch their assertions to `is_dossier_snapshot`, so (c). DELETE.
- **`append_event_log`** (coordination/status_service.py:305, 17 LOC).
  - History: introduced 9ea764050 (#1614, 2026-06-02); the last src caller was removed in dfe6b2ead (#2816).
  - Replaced by `append_event_stream_log` (:323), imported by transaction.py:34. The single-event case is `append_event_stream_log(contract, [event])`.
  - Tests: 16 test files (about 40 call sites) use it as the **event-seeding fixture door**, so (a)-style infrastructure. Pinned by `test_status_unsafe_allowlist.py:93` `COORD_WRAPPER_DOORS`; `test_1622_dead_symbol_retirement.py` references it.
  - Verdict: MOVE-TESTS-THEN-DELETE. Add a `tests/_support` seeding helper that calls `append_event_stream_log`, retarget the sites, delete the door and shrink `COORD_WRAPPER_DOORS`. Medium confidence, because of the mechanical churn.
- **Gap.** No.

## Slice 7: status FSM and helper leftovers

- **`_run_guard`** (transitions.py:103, 30 LOC). Its last caller was removed in ea12637d7 (#529, 065 typed WPState). The docstring says "retained for guard-equivalence tests". `TestGuardEquivalence` (test_wp_state.py:323+, 11 refs) compares `can_transition_to` against `_run_guard`; **both call `guard_for`, so the comparison is tautological**, (b). Real guard coverage exists elsewhere in test_wp_state.py. DELETE `_run_guard` and `TestGuardEquivalence`. High confidence.
- **`WPState.can_transition_to`** (wp_state.py:151, 12 LOC). Introduced ea12637d7. ADR 3.x `2026-04-06-1` names it part of the state-pattern contract. Tests: 5 files, 53 refs. **KEEP-with-note** ("documented boolean API of ADR 2026-04-06-1; gate uses `check_transition`"), or OWNER-DECISION to drop it and amend the ADR. Medium confidence.
- **`StatusDoctorReport.findings_by_category`** (doctor.py:82, 2 LOC). Introduced 05b21afd7 (WP12, 2026-02-08). Used by 2 test files as a query helper. KEEP-with-note, as a report API. Low value either way.
- **`_Builder.append_to_history` / `append_dependency`** (wp_metadata.py:593/598, 8 LOC). Introduced ea12637d7. Tests: `test_wp_metadata.py` only. `history[]` is a retired frontmatter field. DELETE `append_to_history` with its tests. `append_dependency` can stay as builder symmetry (Low) or go.
- **`ArtifactVerdict`/`EmissionArtifactVerdict`** (verdict_vocab.py:57/64). Only `test_verdict_vocab_single_source.py` and two comment mentions (review/cycle.py:1319, verdict_provenance_backfill.py:95) refer to them. **Better: WIRE as annotations** on the verdict writers (the aliases exist to type exactly those values). Otherwise KEEP-with-note. Low confidence.
- **`assert_birth_invariant_holds`** (cutover_eligibility.py:310, 38 LOC). Introduced 71a1bba98 (#2917). The docstring names it a "shared assertion body" for the corpus lock test. **MOVE into tests/** (`tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` is its only user). Medium confidence.
- **Gap.** No.

## Slice 8: consolidation leftovers

The consolidation directory was renamed from `merge/` in f5c15f9f8 (#3080), so `git log -S` output in that commit is move noise.

- **`TargetBranchSyncStatus.is_safe`** (push_preflight.py:82, 12 LOC). An always-`True` deprecated alias (ADR 3.x `2026-06-05-1`, #1706; deprecated in c4191bd30); its last caller was removed in 25e1a6715 (#2057). Test: `tests/consolidation/test_target_branch_preflight.py` (2), (b). DELETE, and amend ADR §5 ("removed"). High confidence.
- **`_print_remediation_lines`** (preflight.py:315, 10 LOC). Extracted in 25e1a6715 (#2057) but never called. Its job is done inline by `_enforce_git_preflight` (:247). Test: `test_preflight_seam.py`, (b). DELETE. High confidence.
- **`display_merge_order`** (ordering.py:211, 17 LOC). Introduced ac4c2a811 (2026-01-18); last caller removed in 5d2386574 (#347). Consolidate no longer prints an order. Test: `test_ordering_bake_seam.py`, (b). DELETE. High confidence.
- **`_durable_done_wps_on_coordination_ref`** (done_bookkeeping.py:645, 21 LOC).
  - History: introduced 333d0559c (#2709/#2711). The last caller `_reconcile_completed_wps_for_resume` was switched to `_durable_coordination_lanes` in **5ae9a4188 (#5046, 2026-09-29)**, which is why the wrapper went dead only yesterday.
  - Replaced by `_durable_coordination_lanes` (same file) through `_reconcile_completed_wps_for_resume`.
  - Tests: `test_done_bookkeeping_seam.py`, `test_done_bookkeeping_rollback_coherence.py`, `test_issue_2367_bake_strand.py` and `tests/architectural/test_resume_non_reemission_guard.py:297` are **(a)**: they pin FR-007 "durable coord ref, not worktree bytes", which the live path still needs. Retarget them to `_durable_coordination_lanes(...) == Lane.DONE`, or better to `_reconcile_completed_wps_for_resume`. `test_done_bookkeeping_seam.py` and `test_merge_recovery.py` already exercise the live pair partially.
  - Verdict: MOVE-TESTS-THEN-DELETE. High confidence.
- **`_final_authored_blobs` / `_final_authored_deletions`** (reconciliation.py:1674/1685, 25 LOC). Introduced 366bb2d5d (#5013) and 8636447c0 (#5022). The docstrings call them "thin wrapper[s] over `_final_authored_walk`". Tests in `test_reconciliation.py` are (a) through the wrapper: retarget to `_final_authored_walk` (:1618). MOVE-TESTS-THEN-DELETE. High confidence.
- **`lane_integrated_by_tree_or_ancestry`** (git_probes.py:698, 21 LOC). Introduced 6545dc532 (Epic #5001) and **never called**. The only reference is the executor.py:2580 docstring. Test: 1 in `test_reconciliation.py`, (b). DELETE, and fix the docstring and the `_CATEGORY_C_TERMINUS_RECONCILIATION_5001` allowlist row. Medium confidence.
- **`ConsolidationState.progress_percent`** (state.py:248) is documented in CLAUDE.md:438. Its last CLI use was removed in the `agent tasks status` rework. KEEP-with-note (a documented property), or delete it and update CLAUDE.md; this is an OWNER question. **`set_pending_conflicts`** (state.py:268): its last callers were removed in 5d2386574/87058c1d9. Nothing sets `has_pending_conflicts` to `True` any more, although docs/guides/how-to/recovery/* document it. DELETE the setter and its test (test_merge_state_unit.py). Mark the field vestigial.
- **`RollbackReport.advanced_branches`** (rollback.py:134, 4 LOC). Introduced 6070520f6 (2026-09-29, slice 10 rollback authority): brand new, test-only (`test_rollback_authority.py`). **OWNER-DECISION.** Recommendation: use it in `render()` or in the operator error, or delete it. Low confidence.
- **Totals.** src about 130; tests about 350 (much of it retargeted, not deleted).
- **Gap.** No.

## Slice 9: coordination/surface_authority forward API (#2160)

- **What.** `_classify_noncommit_outcome` maps router status labels (`no_op_wrong_surface` → Refuse, not NoOp) to verdicts. `_exit_code_for` is the canonical verdict→exit-code mapping.
- **History.** Introduced 735c67fab (2026-09-05, convergence regressions); never called.
- **Replaced by.** Nothing live. The CLI keeps its own status→exit mapping, which the docstring says this "mirrors" (a duplicated rule).
- **Tests.** `tests/coordination/test_surface_authority.py` (7/11 refs) and `tests/specify_cli/cli/commands/agent/test_tasks_surface_authority.py` (4/8), about 250 LOC. They are (b) today, but they would become (a) if wired.
- **Intent.** The module comment (:37-44) says these symbols "rejoin `__all__` as the remaining commit-surface loci are wired… (epic #2160)". implement_cores.py:540-549 still defers work to #2160. Status unknown offline.
- **Verdict.** OWNER-DECISION: is #2160 still going to route CLI exit codes through `_exit_code_for`? Recommendation: WIRE into the one CLI status→exit site so the "no_op_wrong_surface is a failure" rule has a single owner; otherwise delete them and their tests. Medium confidence.
- **Gap.** No.

## Slice 10: git/gitignore/lanes helpers

- **`GitignoreManager.protect_selected_agents` / `get_agent_directories`** (gitignore_manager.py:615/517, 49 LOC). WP01/WP02 of the original GitignoreManager (15c4ff9ad/6dbfa41b2, 2025-11-10); **never called in src**. `init.py` uses `protect_all_agents`. Tests: 4 cross_cutting files (`test_performance.py` 6, `test_gitignore_management.py` 5, `test_gitignore_manager_simple.py` 3, `test_gitignore_manager_unit.py` 8), mostly (b). Check whether any assertion checks shared logic (`_ensure_entries`) before deleting. DELETE. Medium-High confidence.
- **`protected_branches`** (git/commit_helpers.py:530). The live resolver is `protection_policy._resolve_protected_branches` (:347). This function is the test oracle used by `tests/git/protected_target_fixtures.py` and about 45 test files, and is referenced by pack tactics (`packs/built-in/tactics/architectural-gate-non-vacuity.tactic.yaml:84`, `packs/internal/tactics/spec-kitty-gate-non-vacuity-exemplar.tactic.yaml`). **KEEP-with-note**, or MOVE into tests/_support if the tactic prose is updated. Low priority.
- **`SparseCheckoutReport.any_active`** (sparse_checkout.py:106, 4 LOC). Introduced 976d7169d (#625). Used by 5 test files as a report query. KEEP-with-note (report API).
- **`is_mission_branch` / `is_legacy_branch`** (branch_naming.py:794/864, 25 LOC). Introduced 7d7496cae (#377) and c16291214 (#601); never called. Live parsing uses `is_lane_branch`, `parse_lane_worktree_dir` and `lane_id_for_worktree_dir`. Tests: `tests/lanes/test_branch_naming.py`, `tests/specify_cli/lanes/test_lane_naming_parsers.py`, `tests/core/test_branch_naming_human_slug.py` (11 refs), (b). DELETE. High confidence.
- **Gap.** No.

## Slice 11: runtime-state backfill utilities (migration/backfill_runtime_state.py)

- **`backfill_runtime_state_repo`** (:1562, 54 LOC). Introduced 04953ea44 (#2684). The CLI moved to `runtime_state_cutover.cutover_repo` (migrate_cmd.py:1354) in dfe6b2ead (#2816), and three src docstrings "mirror" it. Tests: `tests/unit/migration/test_backfill_runtime_state.py`, `tests/integration/test_migration_backfill.py`; `tests/architectural/untrusted_path_audit/inventory.md` lists it. The glob-selection semantics tests are (a): check `cutover_repo` has them before deleting.
- **`run_backfill_and_verify`** (:2262, 23 LOC). No src caller, **but `docs/operations/cutover-flip-linked-worktree.md:53-54` tells operators to `import` and call it**. Retarget the runbook to `runtime_state_cutover.cutover_mission`, then delete.
- **`assert_zero_readers` + `find_field_readers`** (:2367/:2307, 80 LOC). A one-time proof utility for WP07 history deletion (strip_frontmatter.py:72 cites it). MOVE into tests/ (unit tests only).
- **Verdict.** MOVE-TESTS-THEN-DELETE (runbook first). Medium confidence. src about 157.
- **Gap.** No, though the runbook would break if the function were deleted blind.

## Slice 12: mission / metadata / missions surface

- **`get_active_mission`** (mission.py:455, 58 LOC). Project-level mission selection. Its last callers were removed in 15b49c790, 2bb543ac9 and c6d2c6897 (#319, 2026-03-20). ADR 1.x `2026-01-27-10:412` scheduled "v1.0.0: Remove `get_active_mission()`". It is kept alive by `tests/architectural/test_loop_aware_resolution.py:146` (an AST target) and `test_org_mission_type_resolution.py`. DELETE, retargeting the AST test to `get_mission_for_feature`. High confidence.
- **`discover_missions`** (mission.py:988, 37 LOC). The live one is `runtime.next._internal_runtime.discovery.discover_missions`, a *different* function. Last caller in src removed around b6a721b29 (#3397, layered roster seam). Tests: `tests/missions/test_mission_schema_unit.py` (8), (b). DELETE. Medium confidence.
- **`validate_deliverables_path`** (mission.py:825, 105 LOC). Introduced e74320cc8 (2026-01-25); **never wired**. The live `get_deliverables_path` output is consumed unvalidated at workflow_executor.py:727/:1424 and acceptance/summary_core.py:178. Tests: `tests/adversarial/test_path_validation.py` (20 refs, xfail escape hatches per `docs/plans/testing/test-suite-friction-audit.md:80-92` "CT2… a live security gap") and `tests/research/test_research_deliverables_unit.py` (14). **OWNER-DECISION:** should research deliverable paths be containment-validated? Recommendation: WIRE at the point where `deliverables_path` is accepted (mission create / setup-plan meta write), make the adversarial tests strict, and drop the xfails. Medium confidence. **Possible behaviour gap (security).**
- **`get_template`, `get_workflow_phases`, `get_path_conventions`** (mission.py:321/397/413, 28 LOC). The last src callers died with the mission-DSL v1 runtime retirement (2f4659c2b, 2026-09-07). Tests: `tests/missions/test_documentation_templates.py`, `test_documentation_mission.py`, (b). DELETE. Medium confidence.
- **`clear_coordination_metadata`** (mission_metadata.py:914, 27 LOC). Introduced 2d23e32b1 (2026-06-24); replaced by `flatten_coordination_metadata` in 5696ed649 (#3086), with the last call removed in a5ae131e4 (mission 191). mission_type.py:942 documents that the old function had a *bug* (it never popped `topology`). Tests: `test_feature_metadata.py`, `test_flatten_primitive_single_source.py`, `test_mission_close_discard_pops_topology.py`, (b). DELETE. High confidence.
- **`get_change_mode`, `set_purpose_summary`** (:1004/:813). Introduced dc1be07f9 (#616) and 85cd80321; never called. `bulk_edit/gate.py:63` reads `change_mode` inline. Recommendation: **WIRE `get_change_mode` into bulk_edit/gate.py** (a canonical reader). DELETE `set_purpose_summary`. Medium confidence.
- **`resolve_feature_dir_for_slug`** (missions/_read_path_resolver.py:1592, 47 LOC). Its last src callers were removed in ecf45f52c, ca25dde23 and 27210e6ed (#2115/#2119/#1716). `docs/development/reference/read-side-seam-classification.md:684` warns that importing it "would silently re-open the exact gap". It is used by 19 test files, many as a *fixture* resolver (a). MOVE-TESTS-THEN-DELETE, retargeting to `placement_seam(...).read_dir(kind)`. Medium confidence; large mechanical churn.
- **`is_mission_archived`** (missions/_archive.py:279, 6 LOC). Introduced 8f82b037b; never called. Test: `tests/integration/test_mission_archiving.py` (5). DELETE, or wire into validation. Low confidence.
- **`missions/__init__` lazy shim** (`PrimitiveExecutionContext`, `execute_with_glossary`; C-006 back-compat). The only importers are `tests/agent/glossary/*`. Retarget them to `charter.primitives`, then drop the shim. Check `tests/architectural/test_charter_facades_reexport_doctrine.py` first. Medium confidence.
- **`clear_mission_brief`** (mission_brief.py:273, 5 LOC). Issue #728 ("should use unlink(missing_ok=True)") is marked OPEN/KEEP in docs/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md:28; status unknown offline. OWNER-DECISION: close #728 by deleting it. Low confidence.

## Slice 13: forward contracts that were never wired

- **`policy/audit.py`** (89 LOC module). Introduced 7d7496cae (#377); **never imported by src**. Nothing writes `kitty-specs/<slug>/policy-audit.jsonl`. Test: `tests/policy/test_audit.py` (62, 5), (b). The Cat-7 allowlist says "adopt-as-follow-up" with no issue number. **Recommendation: DELETE** (the target was "0 by 4.0"). Medium confidence.
- **`acceptance/post_consolidation.py`** (310 LOC) plus `scripts/ci/check_dangling_deferrals.py` (159). Introduced 8f82b037b (2026-07-24); never called. No workflow, Makefile or test runs the script, even though `docs/guides/how-to/missions/accept-and-merge.md` says it is wired in `ci-quality.yml`. Tests: `tests/acceptance/test_post_consolidation.py` (336, 11), plus mentions in test_acceptance_matrix_write_seam.py and test_no_dead_modules.py. **OWNER-DECISION:** add the CI job and document the dispatch, or retire the module, the script, the deferral state and the guide paragraph. Medium confidence.
- **`GateExecutionContext.not_applicable_below`** (execution_context.py:174, 21 LOC). Introduced 8f82b037b; the module docstring (:33) promises the PH-1 `NOT_APPLICABLE_IN_PHASE` rule. Tests: `tests/acceptance/test_gate_execution_context.py` (3 refs). **The contract is not enforced by any gate.** WIRE it into the gate runner, or drop PH-1 from the docstring and contract. Medium confidence.
- **Gap.** The documentation and contracts describe enforcement that does not exist. That is a correctness-of-docs issue, not a runtime regression.

## Slice 14: upgrade / task_utils residue

- **`skill_update.apply_text_replacements` / `exclude_paths`** (:130/:182, 72 LOC). Introduced 806d3e29b (#337) and b65a60dac. The module docstring presents them as a migration-authoring toolkit, but none of the 7 importing migrations uses them. Tests: `tests/specify_cli/upgrade/test_occurrence_classification.py` (16/10 refs). DELETE with tests, unless the owner wants them kept as an authoring API; in that case keep them with a note. Medium confidence.
- **`NEVER_SEED_VARS`** (m_3_2_8_provision_kitty_env.py:129). Introduced 9668bfb6f; the exclusion works by omission. **WIRE** as an assertion in the seeding loop (cheap and self-documenting). Low confidence.
- **`WorkPackage.authored_role/_agent_profile/_model`** (task_utils/support.py:537-553, 15 LOC). Introduced dfe6b2ead (#2816). The dashboard uses `view.authored.*` (scanner.py:1036). Test: `test_reconstruct_wp_view.py:555-579`. DELETE, or point the dashboard at them. Low confidence.

## Corrections to the first pass

1. **FR-016 is more than "not wired".** The helper targets `.git/worktrees/<name>/info/exclude`, which git never reads (verified on git 2.43). Wiring `_ensure_spec_kitty_exclude` as the first pass suggested would be a no-op. Use `core.git_ops.exclude_from_git_index` (common dir) instead, and amend spec FR-016's wording. `_exclude_from_git` (#79) is inert in the same way.
2. **FR-016 never shipped live.** It was written on 2026-04-14 into functions that were already dead: `create_feature_worktree` had lost its caller on 2026-01-11 (fd82f6cb0), and `create_wp_workspace` never had one. The live allocator predates it (#377, 2026-04-04). The first pass implied a later regression.
3. **Collateral TEST-ONLY the first pass missed:** `core/git_preflight.py` `GitPreflightError`, `.is_deterministic` and `_DETERMINISTIC_PREFLIGHT_CODES`. Their only src user is dead worktree.py:28/:288-296. `run_git_preflight` and `build_git_preflight_failure_payload` stay live.
4. **core/vcs:** `get_vcs` is not strictly TEST-ONLY. `ops.py:94` calls it, but only as a discarded probe. `get_git_version`, `detect_available_backends`, `VCSError`, `VCSCapabilityError`, `VCSBackendMismatchError`, `VCSLockError`, `VCSConflictError`, `ProjectVCSConfig`, `FeatureVCSConfig`, `WorkspaceCreateResult`, `WorkspaceInfo`, `ChangeInfo`, `ConflictInfo` and `VCSCapabilities` have 0 src users outside core/vcs. They are package exports reached only by tests or by `GitVCS`, and they go with slice 2.
5. **`_durable_done_wps_on_coordination_ref` went dead on 2026-09-29** (5ae9a4188, #5046). The resume path did not "move": it now calls the sibling `_durable_coordination_lanes` directly, so the FR-007 tests are category (a) and should be retargeted, not deleted. The first pass leaned "re-wire or delete"; retargeting is correct.
6. **`count_wp_section_subtask_rows` tests are partly (a):** they pin the shared `_walk_wp_section` heading semantics that the live `iter_wp_section_subtask_rows` also uses. Retarget them; do not delete them.
7. **Stale ownership pointer:** `state/contract.py:435` gives `owner_module="core/worktree"` for `.worktrees/`. The owner is now `lanes/worktree_allocator`.
8. **Stale test and docs claims found while verifying:**
   - tests/integration/core/test_worktree_exclude_spec_kitty.py:9 says "the live worktree-creation path"; it is not live.
   - `review/lock.py:14` calls the lock "git-ignored"; it is not ignored in consumer projects (`get_runtime_gitignore_entries()` has no `.spec-kitty/`). The spec-kitty repo's own `.gitignore:203` hides this.
   - core/subtask_rows.py docstring :12/:31 claims live rollback and dashboard callers that no longer exist.
9. **No change for the other rows.** Every other TEST-ONLY row was re-verified as having 0 src callers. `protected_branches`, `any_active`, `findings_by_category` and `can_transition_to` are better classed API/KEEP-with-note than delete candidates.
