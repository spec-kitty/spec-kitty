---
doc_status: active
updated: '2026-09-30'
---

# Test-only deep dive — Domain B: CLI surface

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

Checkout: `bd1577a3` (history unshallowed to 13,975 commits mid-run; every `git log -S` below was re-run after that). I ran the 14 test files that keep these slices alive: **337 passed, 1 skipped** (`pytest -q` on the individual files, 89 s). LOC figures are AST spans of the symbol (src) and of the test functions/classes that would be deleted or moved (test).

| # | slice | symbols | src LOC | test LOC | verdict | confidence | behaviour gap? |
|---|---|---|---|---|---|---|---|
| 1 | workflow.py shim re-exports (WP02 trio degod) | `_has_prior_rejection`, `_latest_review_feedback_reference`, `_render_isolation_banner`, `_render_resolved_agent_identity`, `_render_wp_prompt_wrapper`, `_resolve_review_feedback_context`, `_resolve_review_feedback_pointer`, `_write_prompt_to_file` | 8 (+6 comment) | 0 deleted; about 35 import/attr edits in 12 files | MOVE-TESTS-THEN-DELETE | High | No |
| 2 | workflow.py `_render_charter_context` dead twin | `_render_charter_context` | 16 | 16 deleted, 44 moved | MOVE-TESTS-THEN-DELETE | High | No |
| 3 | implement.py base-ref twin | `_validate_base_ref` | 12 | 31+50 moved (about 30 deleted) | MOVE-TESTS-THEN-DELETE | High | No (a coverage gap: #4969 origin preference is untested) |
| 4 | implement.py porcelain-path twin | `_feature_dir_status_paths` | 3 | 32 | DELETE | High | No |
| 5 | implement_cores claim-commit fail-close | `_resolve_claim_commit_target` | 39 (+1 import, 3 stale comments) | 36 deleted, plus 2 oracle tests to repoint | MOVE-TESTS-THEN-DELETE (extract the message) | High | No, but 5 comments and docstrings claim a fail-close that no longer exists |
| 6 | accept.py dirty-scan twin | `_spec_artifact_dirty_paths` | 21 | 37 moved | MOVE-TESTS-THEN-DELETE | High | No (the twin *lacks* the live `effective_root`) |
| 7 | orchestrator append-history placement | `_resolve_history_commit_args` | 45 (+`CommitTarget` import) | 40 | DELETE | High | No |
| 8 | tasks seam residue (#2058/#2056 degod) | `_persist_inline_subtask_status`, `_materialize_inline_subtask_status` (cascade), `_wp_id_exists`, `_parse_dependencies_from_tasks_md` | 95 | about 120 | DELETE | High | No |
| 9 | mission-create `pr_bound` write-back | `_persist_pr_bound_phase` (DEAD, kept alive by tests), `_read_meta_for_pr_bound` (cascade) | 22 (+1 shim line) | 42 (+1 vacuous patch, +1 shim-list entry) | DELETE | High | No |
| 10 | mission shim constant | `INVALID_WP_OWNED_FILES_KITTY_SPECS` (mission.py:346) | 1 changed | 0 | KEEP as a re-export (replace the redefinition) | High | No |
| 11 | invocations index/tail helpers | `append_to_index`, `_read_last_line` | 48 | 25 deleted, 4 fixture calls repointed | MOVE-TESTS-THEN-DELETE | High | No (the dead copy is *less* safe) |
| 12 | intake size-cap constant | `MAX_BRIEF_FILE_SIZE_BYTES` | 5 | 4 deleted, 1 test repointed | MOVE-TESTS-THEN-DELETE | High | No |
| 13 | init 4-tier command-template resolver | `_resolve_mission_command_templates_dir` | 58 | 203 (+9 census) | DELETE | High | No |
| 14 | dashboard mission-context injection | `get_dashboard_html` (+`_MISSION_PLACEHOLDER`, the `json` import, the index.html:17 island) | about 35 | 16 deleted, 6 call sites repointed | MOVE-TESTS-THEN-DELETE | High | No |
| 15 | shims.registry accessors | `is_consumer_skill`, `get_consumer_skills`, `get_all_skills` | 16 | 38 | DELETE | High | No |

**Headline.** All 15 slices are the leftovers of decompositions or features that were superseded: the #2056/#2058/#2464 god-module splits, #610, #2684, #413, v3.1.1a3 and #1496. Each one has an identified live replacement, and **none of them does something the live path fails to do**. I found no FR-016-style behaviour gap. The real risk goes the other way: in slices 3, 5 and 6 the regression tests for #1917, SC-002/#5113 and M2/T008 guard the *dead twin*, not production. `test_coordination_remedy_5113.py` has a parametrized case, `implement_claim_commit_target`, whose docstring claims to exercise "the real `implement()` production resolver", but `implement()` never calls that helper. Those tests have to be repointed before anything is deleted, or the protection they give disappears silently. About 480 src LOC and about 560 test LOC can go. Two first-pass classifications change: `get_dashboard_html` should be DELETE, not owner-decision, and `_resolve_claim_commit_target` has 2 more test dependants than the first pass recorded (see Corrections).

---

## Slice 1: workflow.py shim re-exports (8 names)

- **What.** `workflow.py:137-161` holds aliased re-exports of `workflow_cores.*` and `workflow_executor.write_prompt_to_file`. The comment at :131-136 says "existing ``from …workflow import <name>`` imports and ``monkeypatch.setattr(workflow, "<name>")`` call sites resolve identically".
- **History.** Added in `ed336e034` (2026-07-11, "refactor(#2464,#2465,#2508): decompose coord-authority trio", WP02 coord-authority-trio-degod-01KX7094). Since then production has had no caller of these names via `workflow`. `workflow_executor.py:48-58` imports the cores names *frozen*, and its `_wf()`/`w.` late-binding set (27 names) contains none of these 8.
- **Replaced by.** The same functions under their public names: `workflow_cores.has_prior_rejection`, `latest_review_feedback_reference`, `render_isolation_banner`, `render_resolved_agent_identity`, `render_wp_prompt_wrapper`, `resolve_review_feedback_context`, `resolve_review_feedback_pointer`, and `workflow_executor.write_prompt_to_file` (executor:499).
- **Tests.** All are class (a): they pin live behaviour through an alias, so the fix is to repoint them. None of them patches around the calls, so the repoint is mechanical.
  - `tests/integration/test_rejection_cycle.py`: 10 local imports of `_has_prior_rejection` (:145-395)
  - `tests/characterization/test_trio_pure_cores.py:41-44`
  - `tests/agent/test_workflow_review_cycle_pointer.py`: 8 `workflow._…` calls (:88-497)
  - `tests/agent/test_workflow_feedback_pointer_2x_unit.py:182-192`
  - `tests/agent/test_review_feedback_pointer_2x_unit.py:21`
  - `tests/review/test_artifacts.py:217,242,273`
  - `tests/specify_cli/cli/commands/agent/test_workflow_render_helpers.py:13`
  - `tests/integration/test_agent_identity_prompt.py:17`
  - `tests/integration/test_implement_review_retrospect_smoke.py:109`
  - `tests/runtime/test_tmp_prompt_namespace.py:31,219` (`inspect.getsource`, which works the same on the executor function)

  Direct coverage of the cores already exists in `tests/specify_cli/cli/commands/agent/test_workflow_cores.py:218-230` and `tests/unit/runtime/test_prompt_tmp_namespace.py:187`.
- **Open intent.** None. The only mention is the WP02 comment.
- **Risk.** None outside the repo, because the names are private and nothing in packs/, docs/ or the planning repo references them. The trap stays open while they exist: a future `monkeypatch.setattr(workflow, "_has_prior_rejection", …)` would be vacuous.
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Also rewrite the :131-136 comment so it names only the 5 late-bound names, and replace the per-file `F401` in `ruff.toml:31` with a narrow `# noqa: F401` on the live late-bound imports. That must include **`build_charter_context`** (read via `_wf()` at executor:485), which will look unused once slice 2 is gone.
- **Gap.** None.

## Slice 2: `_render_charter_context` (workflow.py:896)

- **What.** This renders charter governance text for prompts and falls back to "Governance: unavailable (…)". It is byte-for-byte the same logic as `workflow_executor.render_charter_context_text` (executor:474-491), except that the live copy reads `build_charter_context` through `_wf()`.
- **History.** Introduced in `e4a1c75ba` (2026-04-05, constitution→charter rename #390). It lost its last caller in `ed336e034` (2026-07-11, trio degod), which added `render_charter_context_text` (called at executor:1352, :2045).
- **Tests.**
  - `tests/agent/test_workflow_charter_context.py:116-159`, `TestWorkflowRenderCharterContext` (5 tests: charter present, missing, exception fallback, no library/ dir, partial bundle). These are class (a) → **MOVE**: swap the import to `workflow_executor.render_charter_context_text`. The exception test patches `…agent.workflow.build_charter_context`, and that still intercepts because the live function reads through `_wf()`. The fallback, missing and partial-bundle behaviours are **uncovered** on the live function today.
  - `tests/charter/test_every_load_delivery.py:323-338`, `test_workflow_render_forwards_mission_type`. This is class (b) → DELETE. The live twin is already pinned at :303-321 (`test_executor_render_forwards_mission_type`).
- **Open intent.** FR-012/B-8 (WP11 T062) is satisfied by the live function. There is a historical mention in `docs/plans/initiatives/2026-03-doctrine-execution-integration/README.md:231`.
- **Risk.** Low. Keep the `build_charter_context` import in workflow.py, because it is live via `_wf()`.
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes 16 src LOC and 16 test LOC; 44 test LOC move.
- **Gap.** None.

## Slice 3: `_validate_base_ref` (implement.py:346)

- **What.** It validates `--base` and returns the origin-preferred SHA, or prints the canonical error and raises `typer.Exit(1)`.
- **History.** Introduced in `26c17d9a3` (2026-04-07, v3.1.0a8 / mission 068 #528). The #1917 `--end-of-options` fix was later closed by #2001 (docs/plans/…/planner-priti-tracker-landscape.md:44). Its only caller was removed in `6545dc532` (2026-09-24, "terminus/merge-coord integrity spine (Epic #5001)", #4969). That commit made `implement()` inline `_resolve_base_ref` + `_raise_base_ref_unresolved` (implement.py:1621-1623) so it can also use the effective *ref name*. The wrapper was kept in the same commit.
- **Replaced by.** `_resolve_base_ref` (implement.py:323) + `_raise_base_ref_unresolved` (:292), called at :1621.
- **Tests.**
  - `tests/specify_cli/cli/commands/test_implement_base_ref.py:68-102` (3 tests: #1917 normal ref, leading-dash ref, and exit on unresolved). Class (a) → MOVE to `_resolve_base_ref`, asserting the `(ref, sha)` result and `None`. The leading-dash #1917 guarantee is **uncovered** on the live path otherwise.
  - `tests/cli/commands/test_implement_base_flag.py:149-198`, `TestValidateBaseRef` (3 tests). This is mixed → SPLIT:
    - valid/invalid move to `_resolve_base_ref`;
    - the error-message test is (b) → delete, because `test_implement_base_flag_invalid_ref_fails_clearly` (:273) already drives the live CLI path.
    - The class docstring "called by implement --base" is false.
- **Open intent.** #1917 is closed per the in-repo tracker notes; status of #4969 is unknown offline. Stale docstring references: `workspace/context.py:1100` and `lanes/worktree_allocator.py:870`.
- **Risk.** Low. It is private and not referenced from packs.
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes 12 src LOC; about 50 test LOC move and about 30 are deleted.
- **Gap.** None in behaviour. There is a **coverage gap**: the #4969 origin-preference branch of `_resolve_base_ref` has no unit test. The file that shows up in a grep (`tests/architectural/test_out_of_matrix_evidence.py:105`) defines its own, unrelated `_resolve_base_ref`. Add one origin-preference test while moving.

## Slice 4: `_feature_dir_status_paths` (implement.py:375)

- **What.** It returns the repo-relative non-structural porcelain paths under the feature dir.
- **History.** Introduced in `f89df153d` (2026-06-01, #1560). It was orphaned the next day by `2a7257b92` (2026-06-02, "fix(#1598 review): fail closed on structural planning-artifact changes"). That commit switched the caller to `_feature_dir_status_entries` and rewrote this helper as a filter in the same commit.
- **Replaced by.** `implement_cores._feature_dir_status_entries` (implement_cores.py:171) plus the structural gate at :619-622.
- **Tests.** `tests/specify_cli/cli/commands/test_implement.py:62-94` (1 test plus a 20-line fixture) pins "the ` M path` porcelain entry is not truncated". That behaviour is already covered on the live parser at `test_implement_cores.py:108-112` (`test_modified_unstaged_tracked_file_not_truncated`) and :141-145 (via the port). So this is class (b) → DELETE.
- **Open intent.** None.
- **Risk.** None.
- **Verdict.** DELETE, High. Removes 3 src LOC and 32 test LOC.
- **Gap.** None.

## Slice 5: `_resolve_claim_commit_target` (implement_cores.py:716, re-imported at implement.py:85)

- **What.** A pure D11 fail-close: `None` placement leads to `PlacementResolutionRequired` with the `doctor coordination --mission <slug> --fix` remedy.
- **History.** Introduced in `5c9424fc8` (2026-07-08, "route every write site through the seam, fail-closed") and moved into cores by `ed336e034` (2026-07-11). Its last caller was removed in `0d0b739ab` (2026-08-27, "wip: salvaged at implementer exit (sk-impl-spec-kitty-610)"). That commit found that targeting `placement_ref` (the coord ref) made the claim commit hit `SafeCommitHeadMismatch` on the primary checkout, and switched to the primary write home. The message was still edited afterwards by `af8759bf5` (2026-09-27, #5108) while the helper was already dead.
- **Replaced by.** `placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK)` (implement.py:1718). The only surviving D11 raise is the inline narrow-triple raise at implement.py:1222-1235 in `_commit_planning_artifacts_transaction`.
- **Tests.** There are more than the first pass found.
  - `test_implement_placement_routing.py:57-81` (2 tests) and `test_implement_cores.py:708-719` (`TestResolveClaimCommitTarget`, 2 tests) are class (b) → DELETE.
  - `test_implement_writeside.py:330-368` uses the dead helper as the **oracle** for the byte-identical SC-002 message of the live inline raise. That is class (a) → MOVE: extract the message into one builder, e.g. `placement_resolution_required_message(mission_slug)` in implement_cores. Have implement.py:1222 use it, then assert against the builder. This also settles the "follow-up: dedupe" note at implement.py:1216-1220.
  - `test_coordination_remedy_5113.py:207-222` (`_run_implement_claim_commit_target`, plus `"implement_claim_commit_target"` in `_CASE_NAMES`) says it runs "the real `implement()` production resolver + fail-closed helper". It does not: `implement()` never calls the helper. This is class (c) → SPLIT. Keep the `_resolve_placement_ref`→`None` half, and point the text half at the extracted builder or the live narrow-triple raise.
- **Open intent.** Two sets of comments and docstrings describe a status-commit fail-close that is gone:
  - implement.py:1106-1108 and :1207-1209 ("the status-commit half (`_resolve_claim_commit_target`) already raises") and :1218;
  - `tests/architectural/test_no_write_side_rederivation.py:477,485` (`_SEAM_FOLD_CALLEES` exempts a callee that is never called).

  #2648, #5113 and #610: status unknown offline.
- **Risk.** Wiring it back would reintroduce the #610 head-mismatch bug, so WIRE is rejected. The deletion needs the message extraction first, otherwise the SC-002 "both halves identical" guarantee loses its oracle.
- **Verdict.** MOVE-TESTS-THEN-DELETE (extract the message builder first), High. Removes 39 src LOC + the import + the `_SEAM_FOLD_CALLEES` entry; deletes 36 test LOC; 2 tests are repointed.
- **Gap.** No behaviour gap. This is a documentation/test-truth defect: five places claim a guarantee on the claim status commit that production no longer has by design.

## Slice 6: `_spec_artifact_dirty_paths` (accept.py:243)

- **What.** The union of primary and coord dirty paths under `kitty-specs/<slug>/`, used for the post-accept residual commit.
- **History.** Introduced in `26ad9b3a3` (2026-05-30, #1353/#1396). It was orphaned by `27210e6ed` (2026-07-08, "3.2.x/G2: read-surface SSOT completion & #1716 closeout"). That commit rewrote `_commit_residual_acceptance_artifacts` to scan each surface separately (accept.py:498-503) and re-added the helper with the M2 union as a standalone function.
- **Replaced by.** `_commit_residual_acceptance_artifacts` (accept.py:483), which calls `_coord_dirty_paths(..., effective_root=…)` and `_primary_dirty_paths` directly. **The twin omits `effective_root`**, so it would give a different answer for owned-checkout missions. The live path is the correct one.
- **Tests.** `tests/specify_cli/cli/commands/test_accept_residual_partition.py:163-199` (`test_dirty_scan_detects_coord_worktree_residue`, the M2/T008 RED-proof). Class (a) → MOVE: call `_coord_dirty_paths(repo_root, _HANDLE)`, a one-line change. The end-to-end live path is also covered by `test_residual_commit_routes_matrix_to_coord_branch` (:202).
- **Open intent.** None (#1716 is closed per the commit subject).
- **Risk.** None.
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes 21 src LOC; 37 test LOC are repointed.
- **Gap.** None.

## Slice 7: `_resolve_history_commit_args` (orchestrator_api/commands.py:2065)

- **What.** It resolved `(worktree_root, CommitTarget)` for committing a WP prompt-file history edit, and failed closed on `ActionContextError`.
- **History.** Introduced in `9590b0467` (2026-06-20, "append-history commits the WP prompt file via the coordination worktree"). Orphaned in `04953ea44` (2026-07-19, "feat(#2684): evict WP runtime state into the event log via InnerStateChanged"), where append-history became a `note` InnerStateChanged emit.
- **Replaced by.** Nothing does the same job, because the capability was dropped: no WP-file commit happens any more. The `append-history` command emits via `specify_cli.status.emit_inner_state_changed`.
- **Tests.** `tests/specify_cli/orchestrator_api/test_commands_fail_closed.py:74-115` (2 tests). Class (b) → DELETE. The module docstring (:15-22) keeps them "as a standalone unit guarantee for any future WP-prompt-file commit caller", which is speculative. Keep the third test (:118, the live `HISTORY_COMMIT_FAILED` envelope). Also update the comment at `test_no_write_side_rederivation.py:735`.
- **Open intent.** Only the "future caller" note. Its remedy text also names the **retired** `doctor workspaces --fix` (#5113 replaced it elsewhere), so it has already rotted.
- **Risk.** None. After deletion the module-level `CommitTarget` import (commands.py:151) becomes unused.
- **Verdict.** DELETE, High. Removes 45 src LOC and 40 test LOC.
- **Gap.** None.

## Slice 8: tasks seam residue (tasks_materialization / tasks_outline / mission_parsing)

- **What.** Four helpers:
  - `_persist_inline_subtask_status` / `_materialize_inline_subtask_status`: write a `- [x] T001` checkbox row into tasks.md for inline "Subtasks: T001" references.
  - `_wp_id_exists`: WP-id existence probe for bare-WP mark-status.
  - `_parse_dependencies_from_tasks_md`: a tasks.md dependency parser.
- **History.**
  - persist/materialize: introduced in `e8eecc79a` (2026-05-05, "stabilize 3.2.0 release blockers") and moved by `aaa4670e3` (#2058/#2114). The last caller was removed in `04953ea44` (2026-07-19, #2684). Completion now goes to the `InnerStateChanged` subtasks delta, and `_resolve_inline_subtasks` does `del feature_dir`.
  - `_wp_id_exists`: introduced in `e8eecc79a`. Orphaned in `046219ca3` (2026-05-31, "Reject WP lane changes in mark-status (#1414)"), because bare WP ids are now refused.
  - `_parse_dependencies_from_tasks_md`: orphaned in `2c1e8ee5d` (2026-04-06, mission 065, #449). That mission's own reviewer event says "old `_parse_dependencies_from_tasks_md` in mission.py is dead code but non-blocking". It was moved into mission_parsing by `e36547461` (#2056/#2134).
- **Replaced by.**
  - persist/materialize: `tasks_mark_status._ms_emit_subtask_state` (InnerStateChanged).
  - `_wp_id_exists`: nothing; the capability was deliberately removed (#1414).
  - the parser: `core.dependency_parser.parse_dependencies_from_tasks_md` (mission_finalize.py:1073, tasks_finalize.py:219).
- **Tests.** All class (b) → DELETE:
  - `test_tasks_materialization.py:171-248` (10 tests)
  - `test_tasks_outline.py:264-286` (4 tests)
  - `test_mission_parsing.py:65-83` (3 tests)

  The live parser has its own suite (`core.dependency_parser`).
- **Open intent.** The comments at tasks.py:161 and tasks_mark_status.py:648-649 only describe the move.
- **Risk.** Cascades to handle:
  - `tasks.py:160` re-exports `_materialize_inline_subtask_status` (no test uses `tasks._materialize…`);
  - the `_INLINE_SUBTASKS_RE` import in tasks_materialization.py:40 becomes unused;
  - two first-pass ERA001 false positives (mission_parsing.py:74,83) disappear with the function.
- **Verdict.** DELETE, High. Removes about 95 src LOC and about 120 test LOC.
- **Gap.** None.

## Slice 9: `_persist_pr_bound_phase` + `_read_meta_for_pr_bound`

- **What.** A post-create write-back of `pr_bound: true` into meta.json, plus its silent-empty meta reader.
- **History.** `_read_meta_for_pr_bound` was introduced in `661d4c328` (2026-06-24, #2090) and `_persist_pr_bound_phase` was extracted in `e36547461` (2026-06-25, #2056/#2134). The caller was removed in `ccb8ea82a` (2026-08-22, "fix(specify): create mission before discovery (#3660)"), which threads `pr_bound` into core.
- **Replaced by.** `core/mission_creation.py:1282-1283` (`if pr_bound: meta["pr_bound"] = True`), covered by `test_mission_create.py:626,668,695`.
- **Tests.**
  - `test_mission_create_phases.py:289-303` (2 tests) → (b) DELETE.
  - `:152` `monkeypatch.setattr(seam, "_persist_pr_bound_phase", …)` is **vacuous** → drop the line.
  - `test_wp06_meta_reader_sweep.py:126-150` (3) and `test_mission_check_prerequisites.py:447-456` (2) → (b) DELETE. They pin the reader's silent-empty contract, which the live path doesn't use; `load_meta_or_empty` has its own tests in `tests/specify_cli/test_mission_metadata.py`.
  - Drop `"_read_meta_for_pr_bound"` from `test_mission_shim_reexports.py:68` and from the shim `mission.py:231`.
- **Open intent.** FR-033 is met by core.
- **Risk.** None. The meta-read census (`_load_meta_census.py:150`) lists only `_read_meta_for_emission`.
- **Verdict.** DELETE, High. Removes 22 src LOC and 42 test LOC.
- **Gap.** None.

## Slice 10: `INVALID_WP_OWNED_FILES_KITTY_SPECS` (agent/mission.py:346)

- **What.** A local *redefinition* of the error-code string. The authoritative copy is at `mission_finalize.py:122` and is emitted at :1815.
- **History.** First introduced in `c8c5a34ee` (2026-05-21, #1269); duplicated into the shim during the `e36547461` split (#2056).
- **Tests.** It is imported via the shim by `tests/agent/test_finalize_tasks_owned_files_validation.py:9`, `tests/tasks/test_finalize_tasks_owned_files_validation.py:13` and `tests/tasks/test_finalize_planning_artifact_kitty_specs.py:28`, and pinned in `test_mission_shim_reexports.py:53`. The code is also named in packs (`task-prompt-template.md:9`, `mission-steps/software-dev/tasks/prompt.md:223`) as a string, not an import.
- **Verdict.** KEEP as shim surface, but replace the literal with `from …mission_finalize import INVALID_WP_OWNED_FILES_KITTY_SPECS` so it cannot drift. Allowlist note: "shim re-export of the mission_finalize error code (pinned by test_mission_shim_reexports)". High.
- **Gap.** None.

## Slice 11: invocations_cmd `append_to_index` + `_read_last_line`

- **What.**
  - `append_to_index` appends `{invocation_id, profile_id, started_at}` to `kitty-ops/ops-index.jsonl`. Its docstring claims it is "Called by `InvocationWriter.write_started()`", which is false.
  - `_read_last_line` is an O(1) tail read.
- **History.** Both came in `177cb91ab` (2026-04-21, mission profile-invocation-runtime-audit-trail-01KPQRX2). `append_to_index` was **never wired**: that same squash gave the writer its own `_append_to_index` (writer.py:207, called at :257). `_read_last_line` was replaced by `_read_completed_record` in `d3e94b44b` (2026-05-31, #1496, duplicate completion after correlation links).
- **Replaced by.** `InvocationWriter._append_to_index` (writer.py:207-231) and `_read_completed_record` (invocations_cmd.py:97).
- **Tests.** In `tests/specify_cli/invocation/cli/test_invocations.py`:
  - `TestReadLastLine` (:169-193, 3 tests) → (b) DELETE.
  - `append_to_index` is used as a **fixture** to seed the index for the live indexed reader (:138, :325, :342, :346) → (a) MOVE: seed through `InvocationWriter.write_started`, or a 6-line local helper.
- **Open intent.** It is on the #470 widened-scope grandfather list (`test_no_dead_symbols.py:3769`); drop that entry.
- **Risk.** Wiring it would be a regression. The dead copy opens with a plain `open("a")`, while the live writer uses `_append_line_no_follow` (a symlink-safe append).
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes 48 src LOC; 25 test LOC are deleted and 4 call sites repointed.
- **Gap.** None (the live path is stricter).

## Slice 12: `MAX_BRIEF_FILE_SIZE_BYTES` (intake.py:43)

- **What.** A 5 MB constant documented as "must match `intake.scanner.DEFAULT_MAX_BRIEF_BYTES`".
- **History.** Introduced in `3aa9a0ff0` (2026-04-21, mission-stabilization-release-core-bug-fixes-01KPQJAN). Its enforcement was removed by `2beaf0612` (2026-04-26, "wire size cap into CLI"), which moved the enforcement to `load_max_brief_bytes()` + `read_brief(cap=…)` (intake.py:163-165, :303).
- **Tests.** `tests/specify_cli/cli/commands/test_intake_size_cap.py`:
  - `test_max_brief_file_size_bytes_is_importable` → (b) DELETE.
  - `test_size_cap_rejects_oversized_file` drives the live `_write_brief_from_candidate` → (a) MOVE to `DEFAULT_MAX_BRIEF_BYTES`.

  Integration coverage is in `tests/integration/test_intake_size_cap.py`.
- **Open intent.** It is on the #470 list (`test_no_dead_symbols.py:3768`).
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes 5 src LOC.
- **Gap.** None.

## Slice 13: `_resolve_mission_command_templates_dir` (init.py:630)

- **What.** It materialized a scratch `.kittify/.resolved-command-templates-<mission>` dir by resolving each legacy `command-templates/*.md` through the tiered resolver.
- **History.** Introduced in `d751aee0f`/`7830cfc1e` (2026-02-09, "wire init template discovery through 4-tier resolver"). The caller was removed in `54269f7c1` (2026-04-07, "global slash command installation for all 13 agents (v3.1.1a3)"). Mission 076 deleted the function (`937a1477d`), then the mission-077 squash `c0ef5d284` (#553, 2026-04-08) **resurrected it** without a caller.
- **Replaced by.** Global command installation (`specify_cli/skills/command_installer.py`). The tier resolution itself lives on in `specify_cli.runtime.resolver.resolve_command` (called from runtime/next/prompt_builder.py:144 and decision.py:458), which is tested directly in the same test file.
- **Tests.** `tests/runtime/test_resolver_unit.py:944-1146`, `TestInitResolverIntegration` (4 tests, 203 LOC). Class (b) → DELETE.
- **Other gates to update.** Remove the mutation-routing census entry at `tests/architectural/test_mutation_ownership_routing.py:367-376` (qualname `_resolve_mission_command_templates_dir`, `shutil.rmtree(resolved_dir)`). Consider whether init's `.resolved-*` scratch sweep is still needed.
- **Open intent.** None.
- **Risk.** None.
- **Verdict.** DELETE, High (upgraded from the first pass's Medium). Removes 58 src LOC and 212 test LOC.
- **Gap.** None.

## Slice 14: `get_dashboard_html(mission_context=…)` (dashboard/templates/__init__.py:30)

- **What.** It returns the shell HTML and can inject a JSON mission context into the inert `initial-mission` data island.
- **History.**
  - Introduced in `56ca326c3`/`07ff184af` (2025-10-08).
  - The mission-context injection and its JS consumer (`window.__INITIAL_MISSION__`) came in `7bfaaee1c` (2025-11-16).
  - **Both the server-side injection and the JS consumer were removed on purpose** in `bcd938265` (2026-04-05, "validate bootstrap before reuse (#413)").
  - The last no-arg caller went in `155516ac1` (2026-04-09, "harden sonar security hotspots"), which switched the handler to `get_dashboard_html_bytes()`.
  - `ffcae0be6` (2026-08-25, #66, CSP) later converted the dead placeholder to a JSON island without re-wiring it.
- **Replaced by.** `get_dashboard_html_bytes()` (handlers/api.py:30). Mission selection is done client-side, and no JS reads `initial-mission`.
- **Tests.**
  - `tests/test_dashboard/test_templates.py:22-37` (2 tests on injection and the null island) → (b) DELETE.
  - `test_static.py:18,25` and `test_csp_conformance.py:50-80` (4 calls, no args) → (a) MOVE to `get_dashboard_html_bytes().decode()`. This is actually better, because those tests then check the bytes that are really served.
- **Open intent.** None. The first pass's "unwired feature" framing is wrong: #413 withdrew it deliberately.
- **Risk.** Low. It is exported in `__all__`, but no importer exists in src, packs, or the saas/planning checkouts. Also drop the `_CATEGORY_B` entry at `test_no_dead_symbols.py:580`, the `json` import, `_MISSION_PLACEHOLDER` and the index.html:17 island.
- **Verdict.** MOVE-TESTS-THEN-DELETE, High. Removes about 35 src LOC; 16 test LOC are deleted and 6 call sites repointed.
- **Gap.** None.

## Slice 15: shims.registry accessors

- **What.** `is_consumer_skill`, `get_consumer_skills` and `get_all_skills` are thin wrappers over the `CONSUMER_SKILLS`/`INTERNAL_SKILLS` frozensets.
- **History.** All three came in `5d2386574` (2026-03-30, "Canonical Context Architecture Cleanup + Hybrid Agent Surface (#347)"). `git log -S'is_consumer_skill('` shows only that commit, so they were **never wired**. Callers use the frozensets directly (command_installer.py:62,106; m_2_1_4 migration :273). The sibling predicates `is_cli_driven`/`is_prompt_driven` *are* live (runtime/next/decision.py:483-485) and stay.
- **Tests.** `tests/specify_cli/shims/test_registry.py:74-115` (`TestIsConsumerSkill`, `TestGetConsumerSkills`, `TestGetAllSkills`) → (b) DELETE. The consumer/internal disjointness they touch is already pinned by `test_internal_skills_not_in_consumer` (:60).
- **Open intent.** They are on the #470 list (`test_no_dead_symbols.py:3836-3838`); drop those entries.
- **Verdict.** DELETE, High. Removes 16 src LOC and 38 test LOC.
- **Gap.** None.

---

## Corrections to the first pass

1. **`get_dashboard_html`: change owner-decision to DELETE.** The mission-context feature and its JS reader were removed on purpose in `bcd938265` (#413), and the last caller went in `155516ac1`. It is withdrawn, not unwired.
2. **`_resolve_claim_commit_target`: more test dependants than recorded.** Besides `test_implement_placement_routing.py`, it is imported by `test_implement_cores.py:32,708-719`, `test_implement_writeside.py:337-364` and `test_coordination_remedy_5113.py:210-221`. The last two use it as the **oracle for the live narrow-triple message**, so plain "remove with its tests" would silently drop SC-002/#5113 coverage. The remedy_5113 docstring (:207-212) falsely says the case exercises `implement()` production code. The "needs-owner-decision / wire" option should be struck: wiring it would reintroduce the #610 `SafeCommitHeadMismatch` bug that `0d0b739ab` fixed.
3. **`INVALID_WP_OWNED_FILES_KITTY_SPECS`: more importers than recorded.** It is imported via the shim by 3 test files (`tests/agent/…`, `tests/tasks/test_finalize_tasks_owned_files_validation.py:13` and `tests/tasks/test_finalize_planning_artifact_kitty_specs.py:28`), not 1. It is effectively shim API, so the verdict is KEEP as a re-export.
4. **`_resolve_mission_command_templates_dir`: raise confidence from Medium to High.** It was resurrected dead by a squash (`c0ef5d284`). It also has a mutation-routing census entry (`test_mutation_ownership_routing.py:369`) that must go with it.
5. **`append_to_index` is also a test fixture.** It seeds the index for the live indexed-reader tests (test_invocations.py:138,325,342,346), so it needs MOVE-TESTS-THEN-DELETE, not a plain delete.
6. **`_persist_pr_bound_phase` (DEAD) cascade.** It cascades to `_read_meta_for_pr_bound` and to 5 extra reader tests plus the shim re-export and shim-list entry. `mission.py:231` must be edited in the same change.
7. **`_render_charter_context` removal side effect.** Deleting it makes workflow.py's `build_charter_context` import look unused to ruff, but it is live via `workflow_executor._wf().build_charter_context` (executor:485). Give it an explicit `# noqa: F401` rationale when the per-file F401 ignore is dropped.
8. **`_spec_artifact_dirty_paths` is not an exact twin.** It lacks the `effective_root` argument the live path passes, so the M2 test was checking a variant production never runs.
9. **Missing test on the live `_resolve_base_ref`.** Its #4969 origin-preference branch has no unit test. The `_resolve_base_ref` in `tests/architectural/test_out_of_matrix_evidence.py:105` is an unrelated local function.
