# Brownfield scout: WP12–WP22 (coord-artifact-single-home-01M3V4BE)

**Loaded**: `spec-kitty agent profile show debugger-debbie` (investigator; squad-delegate mode, no swarm dispatched); `spec-kitty charter context --action implement --json` (compact; DIRECTIVE_001..053, DIR-001..013, brownfield-onboarding paradigm, the gate-discipline/campsite standing orders). Read-only scout at HEAD `79c453e286` (product code == `bc826fcbcb`; only 2 src commits since `ecb5dd914a`, so the prompts' line numbers mostly hold). Timebox ~35 min.

**Lane bases** (lanes.json): j(WP12)=a+i · k(WP13)=a · l(WP14)=a · m(WP15)=a · n(WP16)=a+j · o(WP17→WP18)=g+j · f(WP19→WP08)=b+e (so it includes WP01–05 and WP07) · p(WP20)=d,e,f,g,h,k,l,m,n,o · q(WP21)=d,f,n,o,p · planning(WP22)=q. lane-a contains lane-c→lane-b, so WP02's factory and WP03's seed are present in every lane at or after a.

---

## WP12 — Decision ledger moves to the PRIMARY partition

**Seam map**
- `src/mission_runtime/artifacts.py`:
  - enum docstring L108-118;
  - `_PRIMARY_ARTIFACT_KINDS` L158-186;
  - `_PLACEMENT_ARTIFACT_KINDS` L194-213 (ledger at L209-211);
  - `_COORD_RESIDUE_DIRS["decisions"]` L280-287;
  - `artifact_home_for` L302;
  - `assert_partition_invariant` L337 (checks disjoint and total; the move keeps both true).
- `kind_is_coordination_residue` (L131-149) returns `kind in _PLACEMENT_ARTIFACT_KINDS`. It is already partition-derived, so T065 step 2 needs **no code change**. Say so in the activity log and do not add a branch.
- `resolution.py` imports `_PRIMARY_ARTIFACT_KINDS` by reference. The guard's `_patch_partition` already patches both bindings, so this is not an issue for a static move.
- **Readers missing from the D12 table** (git grep `is_primary_artifact_kind|is_toolchain_generated_churn|is_coord_residue_churn` at HEAD):
  - `commit_router.py`: L697-698 `_representative_kind_for_bucket`, L839-841 `_merge_group_results`, L915, L1193, L1337 (destructive-guard residue predicate);
  - `coordination/surface_authority.py:232` (`use_coord`);
  - `missions/_read_path_resolver.py:1446`;
  - `resolution.py` L1289/1316/1419/2487/2704;
  - `git/ref_advance.py` (injected `is_toolchain_generated_churn`);
  - `cli/commands/agent/workflow.py:393` (`_partition_paths_by_primary_kind`);
  - `acceptance/__init__.py:1219/1269` (non-primary checks);
  - **`consolidation/planning_recency.py:47` `_is_primary_planning_path`** (see Hazards; this one is load-bearing).
- `executor.py:2036` calls `is_toolchain_generated_churn(path_part, mission_slug=...)` with **no topology**. That is the COORD default, so after the flip ledger dirt blocks the porcelain invariant on every topology, not only coordination ones. This is WP17's message site; the predicate itself is unchanged.

**Pinning tests**
- Deliberate re-pins (declared):
  - `tests/mission_runtime/test_artifact_partition_mapping.py::test_decisions_ledger_classifies_to_coord` (L149) and `::test_decisions_ledger_is_coord_residue_churn` (L173);
  - `tests/coordination/test_coherence_integrity.py` (the `decisions/DM-…` row at L268).
- Also check `::test_decisions_ledger_kind_is_distinct_from_neighbor_kinds` (L197). It should stay green; verify.
- `tests/architectural/test_write_surface_placement_guard.py:356-359`: `coord_kinds` includes `DECISION_LEDGER`. The guard drives the real `resolve_placement_only` and asserts `primary_kinds | coord_kinds == set(MissionArtifactKind)`, so the move must be applied to both sets.
- `tests/architectural/test_merge_reconciliation_class_guard.py`, `_NON_DIVERGENT_COORD_RESIDUE_DIRS` L316-334, and `test_both_sides_divergent_canonical_artifacts_carry_merge_driver` L337:
  - **CORRECTION (T068 step 2):** the guard does NOT resolve drivers through `_MERGE_DRIVERS`. It reads root `.gitattributes` (`_gitattributes_merge_drivers()`, L161).
  - It hard-asserts `divergent_dirs == {"traces"}` and, per divergent dir, requires the glob `kitty-specs/**/<dir>/*.md`.
  - If `decisions` leaves the frozenset, the guard goes red twice: the set becomes `{"traces","decisions"}`, and there is no `decisions/*.md` driver, because WP11's driver targets `index.json` and `DM-*.md` files are ULID-unique.
  - Cheapest truthful option: keep `"decisions"` in the non-divergent set (`tasks`/`checklists` are PRIMARY kinds there too, so the dict name is already a misnomer). Amend the comment: the dir is PRIMARY, `DM-*.md` are ULID-unique one-shot writes, and `index.json` is covered by the `spec-kitty-decision-index` driver. Add an assertion that the `.gitattributes` pattern for `decisions/index.json` is registered, discovered via `_MERGE_DRIVERS` config_key, not a literal.
  - `test_init_seed_is_superset_of_registry_merge_drivers` (L579) and `test_migration_seed_is_superset…` (L592) must stay green with WP11's row.
- `tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py::test_b11` uses a `decisions/` dir, but only as a directory-argument case. It is not a ledger pin.

**Hazards**
- **TOP RISK: `planning_recency` undermines WP11's driver.**
  - `target_newer_primary_artifacts` (planning_recency.py:84) classifies any PRIMARY kind as a "planning path".
  - It is called by `lanes/consolidation.py:748-750` (`_restore_target_newer_planning`, which runs over ALL target-changed paths, `changed_paths=None`) and by `:892-901` (`_resolve_planning_conflicts`).
  - After the flip, `decisions/index.json` (and `DM-*.md`) become "target-newer planning" candidates. When both sides advanced the index, the committer-date tiebreak gives the target the win. The squash result produced by the `spec-kitty-decision-index` driver is then **overwritten** by `git merge-file --ours` (a text 3-way merge favouring the target) and the squash commit is amended. That can drop lane-added entries or emit invalid JSON, which is an FR-009b violation.
  - `meta.json` escapes this only because `kind_for_mission_file("meta.json")` returns `None`.
  - No WP owns `planning_recency.py`, and `lanes/consolidation.py` is WP11's.
  - Recommendation: `_is_primary_planning_path` excludes paths that match a `_MERGE_DRIVERS` pattern (driver-covered wins). Add a D12-style row and test in WP12: `target_newer_primary_artifacts` must not return `decisions/index.json`. Escalate the ownership question to the operator before implement.
- Behaviour flip not stated in the prompt: on **lanes/single_branch** Missions, `kind_is_coordination_residue` is already False (coord-less topology), so the flip only changes COORD/LANES_WITH_COORD Missions. The exception is the `topology=None` callers (executor L2036, `tasks_move_task:824`, `tasks_shared:750`, `implement.py:905/947`, `auto_rebase:225`, `commit_router:768`), which project COORD and therefore flip for every topology.
- Layer rules: no new imports, so this is a no-op. Dead-symbol gate: no new public symbols.

**Repro feasibility**
- R13 (`artifact_home_for(DECISION_LEDGER, CommitTarget(ref=...)).read_surface is PRIMARY`): red at the lane-j base. Note that it needs a `placement_ref`.
- Router reader test: at the base, kind=SPEC with a dirty root `decisions/index.json` sends the file to the coord bucket (`_group_files_by_partition` L764-769). It is then staged or translated by WP05 on the coordination branch, or refused. Red holds either way. Assert on `git log` per branch, not only on `surfaces`.
- `owned=` bypasses grouping entirely (`commit_for_mission` L281: `groups=[(kind, files)] if owned`), so do not use an owned fixture.
- Spec-commit leg: `decisions/service.open_decision` writes the ledger to `_ledger_dir` (PRIMARY_METADATA) and **does not commit**, so the ledger is dirty after open. Red at the base: it is re-routed to coordination.

**Quick-run**
```
uv run --frozen pytest tests/mission_runtime/test_artifact_partition.py tests/mission_runtime/test_artifact_partition_mapping.py tests/mission_runtime/test_decision_ledger_reader_flips.py tests/specify_cli/decisions/test_ledger_primary_ratchet.py tests/coordination/test_coherence_integrity.py -q
uv run --frozen pytest tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_layer_rules.py -q
uv run --frozen pytest tests/consolidation/test_planning_recency_helper.py tests/lanes/test_squash_seam_reconciliation.py -q   # recency hazard
```

## WP13 — spec-commit names every argument's fate

**Seam map**
- `spec_commit_cmd.py` (309 lines):
  - `_payload` L70;
  - `_resolve_commit_inputs` L103 (already exists; T002's proposed `_resolve_spec_commit_inputs` would be a near-duplicate name, so extend or rename consistently);
  - `spec_commit_command` L155, **C901 = 15 (zero headroom)**;
  - the `commit_for_mission` call is at L214, the status arms at L228-286, and the `--target-branch` help at L166-170.
- The only caller is the typer registration. `_payload` and `_err` are used internally.
- `--target-branch` is ALSO passed to `resolve_owned_or_refuse(target_override=target_branch)` (L200), not only to the router. The help rewrite must mention the owned-checkout target override.

**CORRECTIONs (internal contradictions)**
- L98 says "WP01 (same lane) extracted the render branch into a helper. Work inside that helper."
- T071 step 1 says "the render helper that WP01 extracted", and step 4 says "WP01 brought it to about 10".
- Per P-m7 / T002, that extraction is now **this WP's own first commit**, so WP01 did nothing here and `spec_commit_command` is still at 15 on the base.

**Pinning tests**
- `test_spec_commit_cmd.py` (existing JSON keys).
- `test_issue_2739_spec_commit_protected_primary_guard.py`: B03 `committed:false` plus `reason`; B11 directory argument; B16 coordination-kind file false success.
- `tests/coordination/test_commit_router_fail_loud.py`.
- Integration tests (CI-owned): `test_owned_lifecycle_acceptance_e2e.py`, `test_explicit_checkout_commands.py`.

**Hazards**
- An owned checkout gets no partition grouping (router L281), so `surfaces` has one entry. Mirror this in the `_argument_fates` owned test.
- Keep stdout clean in `--json` mode; the existing `console.print` arms are text-only.

**Repro**
- At the lane-k base (lane-a, without WP12) the ledger is COORD. The taxonomy-derived assertion makes R5 order-independent.
- The status-lock refusal (`STATUS_LOCK_HELD`) depends on WP05's named refusals, which are present.

**Quick-run**
```
uv run --frozen pytest tests/specify_cli/cli/commands/test_spec_commit_cmd.py tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py tests/coordination/test_commit_router_fail_loud.py tests/coordination/test_commit_outcome.py -q
```

## WP14 — Planning-command consumers render the commit outcome

**Seam map (HEAD)**
- setup-plan:
  - `mission_setup_plan.py::_commit_to_branch` L181 (C901 8), call at L237;
  - discarded results at L892 and L951;
  - `setup_plan` L1225 (C901 11).
- record-analysis: `mission_record_analysis.py::record_analysis` L225 (C901 13). **The commit at L374 is INSIDE `record_analysis`**, within a `contextlib.suppress(...)`.
- orchestrator: `orchestrator_api/commands.py::_do_record_analysis_write` L2979. Its commit (L3018) is under `contextlib.suppress`, and the function returns the `write_analysis_report` result. To surface `commit_surfaces`, change its return to carry the router result. Its caller is `record_analysis` (C901 12) at L3031, which runs it under `_run_write_with_timeout` (`transition` is at 14).
- report transaction: `git/report_transaction.py::record_report_transaction` L130, C901 **15** (the T003 extraction is mandatory before adding anything).
- retrospect:
  - `retrospect.py::_canonical_events_path` L109;
  - **`_maybe_auto_commit` L294** (commit at L315);
  - the residue reader at L281.
- agent-retrospect: `agent_retrospect.py::_canonical_events_dir` L198.

**CORRECTIONs**
- (1) "`_maybe_auto_commit` (mission_record_analysis.py ≈L294 onward)" is wrong. `_maybe_auto_commit` is in **retrospect.py:294**. The record-analysis commit is in `record_analysis` itself (mission_record_analysis.py L355-391). "Leave `record_analysis` alone, change only `_maybe_auto_commit`" is therefore unsatisfiable. Extract the suppress-and-commit block into a private helper first (C901 13, headroom 2).
- (2) T074 step 1 says "`_auto_commit` helper around L305-330". The helper is `_maybe_auto_commit` at L294-344.
- (3) The "WP01 extracted `record_report_transaction`" wording at L106 and in T076 step 3 is stale; per T003 it is this WP's own first commit.
- WP20's consumer list repeats error (1).

**Pinning tests**
- `tests/git/test_report_transaction.py`, `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`;
- `tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py`, `tests/retrospective/`;
- `tests/orchestrator_api/` (4 files; envelope pins).
- Most orchestrator contract tests live elsewhere: `grep -rl orchestrator_api tests --include=test_*.py`.

**Hazards**
- Existing protected-target warnings (`_refused_on_protected_target`, `_warn_protected_target_refused`) must keep firing. Do not double-print the surface line plus the warning.
- `_canonical_events_path` has a read fallback to `candidate_feature_dir_for_mission`, so keep the read variant byte-identical.
- If WP20's census still names `_canonical_events_path` while the write moved into `_canonical_events_write_path`, re-point the census.

**Repro**
- Retrospect auto-commit is gated by `get_auto_commit_default(repo_root)`, so set it in the fixture.
- The retrospect create command needs a "completed" Mission (`_check_mission_completed` L170). The masked-surface fixture must therefore be a completed coordination Mission, which costs more than the prompt suggests. Consider driving `_maybe_auto_commit` through the `backfill`/`create` CLI with a minimal completed Mission (look at `test_retrospect_doctor_surface_4090.py` for its builder).

**Quick-run**
```
uv run --frozen pytest tests/git/test_report_transaction.py tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py tests/orchestrator_api/ -q
```

## WP15 — finalize-tasks: single home, honest output, default planning-pin refresh

**Seam map (lines match HEAD)**
- `mission_finalize.py` (5118 lines):
  - `_emit_local_canonical_events` L2266;
  - `_execution_has_begun` L2325;
  - `_resolve_refresh_planning_commit_decision` L2521;
  - `_refuse_planning_pin_refresh` L2576;
  - `_refresh_worktree_status_findings` L2586;
  - `_preflight_refresh_planning_commit` L2682;
  - `_commit_planning_pin_refresh` L2768;
  - `_commit_planning_pin_refresh_locked` L2807 (C901 **15**);
  - `_preserve_or_capture_planning_commit_sha` L3017;
  - `_CommitOutcome` L3513;
  - `_resolve_finalize_commit_candidates` L3542;
  - `_apply_finalize_commit_router_result` L3585;
  - `finalize_tasks` L4758 (C901 14).
- `tasks_finalize.py::_ft_apply_writes` L250 (C901 14), with `read_dir(STATUS_STATE)` at L444.

**HIDDEN GATE (not mentioned in the prompt): `tests/architectural/test_finalize_refresh_pin_authority.py` AST-pins**
- `_preserve_or_capture_planning_commit_sha` is called **exactly once, directly in `finalize_tasks`**.
- `_emit_validate_only_report(... planning_sha=)` and `_run_commit_pipeline(... planning_sha=)` keywords stay present.
- `_preflight_refresh_planning_commit` is called once in `finalize_tasks`, inside an `if not validate_only:` block, and lexically before every writer (`_persist_branch_contract_for_finalize`, `_scaffold_issue_matrix_if_present`, `_flush_frontmatter_writes`, `_emit_tasks_started`, `_run_commit_pipeline`).
- `_commit_planning_pin_refresh` holds `lanes_json_lock` and calls `_commit_planning_pin_refresh_locked`.
- **`_commit_planning_pin_refresh_locked` contains exactly one `commit_for_mission(...)` call** with `files=plan.files`, `kind=…LANE_STATE` and `expected_parent_sha=<x>.expected_parent_sha`, and `_prepare_primary_pin_refresh_commit` assigns `files = (lanes_path,)` or `owned.files([lanes_path])`.
- No `_emit_local_canonical_events` / `_emit_tasks_started` / scaffold calls in the refresh path.

**CORRECTION (T004 step 2):** extracting `_commit_pin_refresh_files(...)`, which moves the `commit_for_mission` call out of `_commit_planning_pin_refresh_locked`, **reds this gate**. Extract the result interpretation only, or edit the gate as part of the WP. The same applies to T004 step 1 / T083: an "options" helper must not absorb the pin-authority or preflight calls.

**CORRECTION (T083 design): `refresh_planning_commit=True` is a refresh-ONLY mode, not "also refresh"**
- `finalize_tasks` L4939-5026:
  - `_run_finalize_ownership_gates(validate_only=validate_only or refresh_planning_commit)` puts every writer in zero-mutation mode;
  - `_emit_tasks_started` is skipped;
  - the run returns right after `_commit_planning_pin_refresh`, and `_run_commit_pipeline` never runs.
- So `refresh = flag or planning_changed` would silently turn a normal re-finalize (tasks.md, frontmatter, lanes rewrite) into a pin-only run.
- The automatic refresh must happen **inside** the normal pipeline. Thread a resolved `planning_sha` through `_preserve_or_capture_planning_commit_sha`'s no-flag branch, i.e. `_resolve_preserve_planning_commit_decision`, and do not flip the mode flag.

**CORRECTION (US5.3 vs #4827)**
- At HEAD a plain finalize on an orphaned pin **already fails closed before any write** (`_resolve_preserve_planning_commit_decision`), pinned by `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py::test_plain_finalize_fails_closed_on_orphaned_pin` (L206). That test asserts an `error` is emitted that names `--refresh-planning-commit` and `--allow-orphaned`.
- The prompt's US5.3 fixture (amend plus force the target ref) IS that orphan case. Ruling Q6 ("warn, keep the old pin, exit 0") directly re-pins this #4827 test, which is outside owned_files.
- Get explicit operator sign-off that Q6 overrides #4827's fail-closed rule. Otherwise use a non-orphan refusal (for example a dirty-checkout preflight finding) for US5.3.
- Other #4827/#4141 pins to run: `tests/lanes/test_issue_4827_allocator_orphan_pin.py`, `tests/lanes/test_planning_commit_classify.py`, `tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py`.

**Other notes**
- `_collect_finalize_artifacts` (≈L312) lists `feature_dir/status.events.jsonl` and `status.json` as root-checkout candidates. After T080/T081 the COORD candidates come from `write_dir`, so make sure the root copies are not also staged (that would be R7-style leakage).
- Before execution begins, a no-flag re-finalize already re-captures the tip (action "captured"). R17 needs execution begun, as the prompt says.

**Quick-run**
```
uv run --frozen pytest tests/architectural/test_finalize_refresh_pin_authority.py tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py -q
```

## WP16 — accept residual legs through the router

**Seam map**
- `accept.py`:
  - `_primary_dirty_paths` L111;
  - `_coord_worktree_root` L117 (uses `resolve_artifact_surface(ACCEPTANCE_MATRIX)`);
  - `_coord_status_feature_dir` L154 (C901 2);
  - `_coord_dirty_paths` L196;
  - `_stamp_birth_cutover_for_accept` L238 (call at L308);
  - `_commit_primary_residuals` L370 (raw `run_git add/commit`);
  - `_commit_coord_residuals` L405 (root-join bug at **L427** `files = tuple(repo_root / path for path in dirty)`, then `write_artifact`);
  - `_commit_residual_acceptance_artifacts` L445, called at **L1079**.
- `acceptance/__init__.py::_filter_coordination_residue` (≈L411-440).

**CORRECTION:** T088 step 1 (add `_is_coordination_owned`) contradicts the P-M5 note at the end of T088 ("do not add"). P-M5 wins: use WP05's public per-path predicate.

**Pinning tests and callers the prompt does not mention**
- `tests/specify_cli/cli/commands/test_accept_clean_tree.py::test_residual_acceptance_commit_is_scoped_to_mission_paths` (L325):
  - the Mission has **no meta.json**, the dirty file is `acceptance-matrix.json` at the repository root, and an unrelated file is **pre-staged**;
  - it asserts `created is True`, the matrix committed at HEAD, and the unrelated file still staged.
  - Through the router this may (a) fail topology resolution without meta.json, or (b) hit `SafeCommitBackstopError` ("staging area contains unexpected paths", `git/commit_helpers.py:393-419`).
  - Run it first. It is either a deliberate re-pin (say so) or needs the router path to tolerate pre-staged foreign paths.
- `tests/specify_cli/cli/commands/test_accept_decomposition.py:202` monkeypatches `_commit_residual_acceptance_artifacts` with `h.residual`, and L687 asserts `... is False`. Keep the bool return, or update both.
- `tests/integration/test_accept_matrix_coord_partition.py:361` (CI-owned) asserts `created is True` plus a mixed batch. Do not break the bool contract. Recommendation: keep `_commit_residual_acceptance_artifacts -> bool`, and have it call a new private helper that returns `CommitRouterResult | None` for the JSON/text rendering.
- `src/specify_cli/coordination/write_seam.py:55` names `_commit_coord_residuals` as "the canonical" write-seam consumer, so update that docstring and the WP20 consumer list.

**Hazards**
- Protected target: raw commit → router `PROTECTED_BRANCH_REFUSED` is a behaviour change. Run the `#2739` tests and `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py`.
- `_coord_status_feature_dir` is in WP20's census, so keep the qualname. The C901 headroom is fine.
- R9 (per the prompt's R-M6): after WP12, `decisions/*` already agree. Use `traces/*.md` as the disagreeing path.

**Quick-run**
```
uv run --frozen pytest tests/specify_cli/cli/commands/test_accept_residual_partition.py tests/specify_cli/cli/commands/test_accept_clean_tree.py tests/specify_cli/cli/commands/test_accept_decomposition.py tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py -q
uv run --frozen pytest tests/acceptance/ -q
```

## WP17 — decisions doctor and fork detection

**Seam map**
- `_decisions_doctor.py`:
  - `_LOCK_FILENAME` L86;
  - `DecisionsReconciliationReport` L94 (`clean` L127);
  - `_ledger_dir` L146;
  - `_diagnose(events_dir, ledger_dir, mission_slug)` L372 (the orphan rule at L397; **no repo_root parameter**, so it has to be threaded from `run_decisions_reconciliation` L529);
  - `_repair(events_dir, ledger_dir)` L404;
  - `_emit_human` L492, `_emit_json` L507.
- `decisions/verify.py::verify(mission_dir, mission_slug)` L104 (C901 10) is re-exported by `specify_cli/decisions/__init__.py:32`, so it is **public API**.
  - Either add a kw-only `repo_root: Path | None = None`, or do the fork check in `cli/commands/decision.py::cmd_verify` (L568, which already has `repo_root`).
  - Note `--no-fail-on-stale`: decide whether a fork still exits 1. The contract says 1, so document the precedence.
- `coordination/teardown.py`:
  - `ProjectionTeardownAbort` L90: `error_code` is a class attribute, and `__init__(*, reason, coord_ref, expected_sha, actual_sha=None)` has **required** `expected_sha`;
  - the message template hard-codes "re-run the merge (`spec-kitty consolidate --resume`)", which is the wrong remedy for a ledger refusal. Add kw-only `error_code` and a remedy override, and make `expected_sha` optional.
  - `teardown_coordination_topology` L222 is C901 4.
- Teardown callers:
  - `consolidate.py:408` (`--abort`, `persist=False`, after the rollback restore);
  - `mission_type.py:1144`, the discard/close leg, whose comment says "this never raises". A new raise changes discard semantics, so verify the CLI renders it.
  - `executor.py:3126`.
- `executor.py`:
  - `_phase_porcelain_invariant` L2013 (C901 10), predicate at L2033-2041;
  - `_pre_mutation_safety_preflight` L3450 (C901 6).

**Pinning tests**
- `tests/decisions/test_decisions_reconciler.py` (#4919 malformed, `status_mismatch`), `tests/decisions/test_defer_resolve_repair_4919.py`;
- `tests/specify_cli/decisions/test_verify_integration.py`;
- `tests/status/test_authoritative_non_lane_registry_4897.py`, which drives `_decisions_doctor._diagnose` directly, so a signature change breaks it;
- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` (a doctor output golden; additive JSON may need a refresh);
- `tests/coordination/test_projection_teardown.py`, `tests/consolidation/test_coord_teardown_order_3926.py`, `tests/consolidation/test_single_rollback_authority.py` (AST-pinned rollback caller set; adding no rollback call keeps it green).

**Hazards**
- `tests/architectural/test_status_unsafe_allowlist.py` is a shrink-only door gate. `fork.py` must **not** `import specify_cli.status.store`, nor `from specify_cli.status import store`, nor import any `append_*`. Reading via `from specify_cli.status.store import read_events` is fine; for ref reads, parse the bytes with an existing non-door parser.
- `coordination/teardown.py` keeps only stdlib imports at the top (all imports are late), so late-import `decisions.fork`.
- Dead-symbol gate (`tests/architectural/test_no_dead_symbols.py`): every public name in `fork.py` that is not used inside its module needs a src importer. Keep the value-object dataclasses out of `__all__` unless doctor or verify imports them.

**Repro**
- The lane-o base has WP02's fixtures, WP09 (lane-g) and WP12. R3/R14/R15/R16 are red at the base because `_diagnose` is single-surface and no fork field exists. Plausible.
- R16 teardown: fixture (d) needs a ledger committed only on the coordination branch. Build it with git plumbing in the WP02 factory.

**Quick-run**
```
uv run --frozen pytest tests/decisions/ tests/specify_cli/decisions/test_verify_integration.py tests/coordination/test_projection_teardown.py tests/consolidation/test_executor_ledger_preflight.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_coord_teardown_order_3926.py tests/status/test_authoritative_non_lane_registry_4897.py -q
uv run --frozen pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_worktree_name_guess.py -q
```

## WP18 — consolidation and materialize writers

**Seam map**
- `executor.py`:
  - `_phase_baseline_and_surface` is at **L799** (the prompt says 799 in one place and 825 in another; the `resolve_status_surface` call is at L825);
  - `_run_lane_based_consolidation` L4114, **C901 14**. Its `seam.read_dir(STATUS_STATE)` is at L4181 with the `except` arms at L4182-4194.
  - Adding `CoordSeedForkRefused` plus `FeatureStatusLockTimeoutError` arms brings it to **16**. Extract `_resolve_run_status_dir(seam, …) -> Path` (raising `typer.Exit`) with focused tests.
- `materialize.py`:
  - `_resolve_selected_dir` L26 (`read_dir` at L31);
  - `materialize` L40, **C901 15 (zero headroom)**, with the loop at L103-127 and the per-Mission `except` at L126.
  - In the loop the slug is `feature_dir.name`. After swapping in the coordination path, keep the **root dir name** as the slug for `.kittify/derived/<slug>`; do not take the name of the coordination path.

**Pinning tests**
- `tests/cli/commands/test_merge_status_commit.py::TestUnmaterializedCoordWorktreeMerge::test_lane_based_merge_exits_cleanly_on_unmaterialized_coord_worktree` (L271): its fixture is a **local** `git branch <coord>` with no worktree (L320).
  - After the change that case materializes (the deliberate re-pin).
  - The remote-only control needs a **new fixture**: a `file://` bare remote, the branch pushed, and the local head deleted. Only the assertions can be kept byte-for-byte.
- `tests/consolidation/test_coord_deleted_degrade_paths.py` (L170-202 asserts "Merge aborted before any state change" for DELETED).
- `tests/consolidation/test_dry_run_fails_closed_on_unmaterialized_coord.py`: dry-run stays fail-closed on UNMATERIALIZED, while the real run now materializes. That **UX asymmetry** (the forecast says abort, the run proceeds) is worth a note in the PR or a follow-up.
- The full T102 guard list is accurate. `tests/consolidation/test_canceled_content_residuals.py` uses strict xfail, so an XPASS is red.

**Hazards**
- The seed commit lands before `_capture_pre_mutation_coord_checkpoint` (call at L3748) and before `rollback.capture_pre_mutation_snapshot`, so it is part of the pre-mutation state. Check that `_run_lane_based_consolidation` really runs outside the global merge lock: the locked driver is `_run_lane_based_consolidation_locked` (L3587), and the preflight-with-recovery is at L4029.
- R22's seed-commit message (`chore(<mission>): seed coordination surface`) must match WP03's actual constant; import it, do not use a literal.
- `--resume`: the persisted `pre_mutation_*` fields are never recaptured, and `write_dir` on MATERIALIZED is a no-op, as the prompt says.

**Quick-run**
```
uv run --frozen pytest tests/consolidation/test_executor_coord_reconcile.py tests/consolidation/test_done_bookkeeping_seam.py tests/cli/commands/test_merge_status_commit.py tests/specify_cli/cli/commands/test_materialize.py tests/consolidation/test_coord_deleted_degrade_paths.py tests/consolidation/test_dry_run_fails_closed_on_unmaterialized_coord.py -q
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_content_residuals.py tests/consolidation/test_done_bookkeeping_rollback_coherence.py tests/consolidation/test_issue_4764_terminus_safety.py -q
```

## WP19 — implement receipts name the real branch

**CORRECTION (red premise):** on a coordination-routed Mission with a complete identity triple, `workflow_executor.commit_workflow_change` (L292) **never reaches** `_commit_via_legacy_safe_commit`.
- It uses `_commit_via_coordination_transaction`. That path records `coord_branch` with `receipt.commit_sha` from `txn.commit_idempotent` (`transaction.py:781`), which is a no-op receipt "pinned at the current HEAD", so the sha is non-null and contained in the branch. The PRIMARY group (L487) records `primary_ref` plus the sha.
- With an incomplete triple plus a `coord_branch`, it refuses (`workflow_executor.py` ≈L351-365).
- The legacy fallback is reached only for **coord-less** Missions (`lanes`/`single_branch`, "genuinely coord-less", `workflow_executor.py` ≈L366-372). The `sha=None` receipt at L806-813 therefore surfaces on **lanes/single_branch** Missions.
- R18 as written (coordination Mission) is likely **GREEN at the base**, and the "C-008 lanes control: every entry has a sha" is the actual red.
- Re-derive by running R18 on the lane-f base before committing it as red-first. Consider re-targeting R18 at the lanes/single_branch receipt, and keep the coordination run as the control.

**CORRECTION (dependencies):** "no dependencies… can run in parallel from the start" contradicts the frontmatter (WP02) and lanes.json. lane-f's base = lane-b + lane-e, so WP01–05 and WP07 are present.

**Seam map**
- `workflow.py`:
  - `_record_receipt` L235;
  - PRIMARY receipt L487 / refused L480;
  - coordination receipts L556/L568;
  - `_workflow_placement_seam` L661;
  - **`_resolve_workflow_placement(...)` L680, the documented single choke point for `write_target`. Use it** (`.ref`), and do not add a raw `placement_seam(...)`;
  - `_resolve_legacy_porcelain_root` L716;
  - `_commit_via_legacy_safe_commit` L768;
  - `_print_commit_summary` L837.
- The only caller is `workflow_executor.py:372`.

**Hazards**
- `tests/architectural/test_no_write_side_rederivation.py:780-790` allowlists the token `CommitTarget ( ref = target_branch )` inside `_commit_via_legacy_safe_commit`, and the liveness twin `test_checkout_grammar_allow_list_entries_are_still_live` (L973) requires it to stay.
  - Keep that `safe_commit(target=CommitTarget(ref=target_branch))` line verbatim in that function, not moved into a helper.
  - Do not add a new non-seam `CommitTarget(ref=…)` either, because the checkout grammar would flag it.
- `tests/git/test_guard_capability_regression.py:252-261` calls `_commit_via_legacy_safe_commit` directly (protected-target refusal), so keep the kw signature.
- `tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py` references it too.

**Quick-run**
```
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_workflow.py tests/git/test_guard_capability_regression.py -q
uv run --frozen pytest tests/architectural/test_no_write_side_rederivation.py -k "checkout_grammar_allow_list or adopted" -q
```

## WP20 — write-side gate extension and consumer pin

**Gate anatomy**: verified at HEAD (`_REPO_ROOT` L76, `_SRC` L77, `_ALLOW_LIST_SEED` L175, bite L318, twins L428/L973). There is no `test_no_write_side_rederivation` section in `_baselines.yaml` yet. `BaselinesFile` is `extra="allow"`, and `_REQUIRED_TOP_LEVEL_KEYS` is derived from `_SIZE_RATCHETS`, so one row plus one yaml leaf is enough.

**Census**: all 22 qualnames resolve at HEAD (spot-checked, including `RealCoordCommitRouter.feature_write_dir`, `_emit_create_events`, `reconcile_status`, `BookkeepingTransaction._acquire_locked`). Re-point after the WP08/WP14/WP15 splits.

**CORRECTIONs (consumer list, T110)**
- `mission_record_analysis.py::_maybe_auto_commit` does not exist; the consumer is `record_analysis`, or the helper WP14 extracts.
- `retrospect.py::_maybe_auto_commit` (L294) is the retrospect consumer.
- `acceptance/matrix.py` ≈L524 is a `write_seam.write_artifact` consumer, not `commit_for_mission`. Pin its caller, per the prompt's wrapper edge case.
- `report_transaction` and the `spec_commit` helpers are extracted by WP14/WP13 themselves, not by WP01.

**Hazards**
- `test_ratchet_baselines.py::test_lowering_an_enforced_leaf_below_live_fails` and `test_growth_fails_shrinkage_warns` are parametrized over every row, so a cap-0 leaf with an empty live list is an edge case. Run the whole file.
- `test_fast_collection_does_not_import_round_trip_corpus` (L780) requires lazy module resolution, so do not import the gate module at the top level.
- Red-at-base proof: base `ecb5dd914a` is an ancestor of HEAD. `decisions/emit.py::_mission_dir` and `decisions/service.py::_mission_dir` both still hold `read_dir(STATUS_STATE)` at HEAD, so the proof is feasible now.

**Quick-run**
```
uv run --frozen pytest tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_ratchet_baselines.py tests/coordination/test_commit_outcome_consumer_pin.py -q
```

## WP21 — end-to-end single-home workflow

**CORRECTION (T119 step 2):** neither `setup-plan` nor `finalize-tasks` commits `decisions/`.
- `setup-plan` passes `files=(file_path,)` (`mission_setup_plan.py` ≈L240).
- `_collect_finalize_artifacts` (`mission_finalize.py` ≈L312) lists status, tasks.md, wps.yaml, meta.json, the acceptance matrix and the issue matrix, and no `decisions/`.
- So the "auto-commit point" assertion is red on the final tree by construction, which conflicts with "green on the final tree".
- Use `accept` (WP16 commits the ledger) or `spec-commit` as the ledger commit point, or make the defect a filed follow-up rather than an e2e assertion.

**Other notes**
- `_collect_finalize_artifacts` also lists the **root-checkout** `status.events.jsonl` / `status.json`. If WP15 does not drop or translate those, SC-001 (0 COORD commits on the target) will catch it, which is a good cross-check.
- Moved-merge-base variant: once the WP12 planning-recency hazard is unresolved, an index.json changed on both sides would be clobbered. The variant only touches `docs/unrelated.md`, so it will not catch it. Consider a third hook that opens a decision on the target branch mid-flight to exercise WP11's driver and recency together. That is optional and new scope, so flag it to the operator.
- `--pr-bound` defaults to lanes on an unprotected primary; the prompt covers this.
- The test shells out to `spec-kitty` (merge drivers), so use `uv run --frozen spec-kitty` from the lane worktree (stale-install gotcha).

**Quick-run**
```
uv run --frozen pytest tests/integration/test_coord_single_home_workflow.py -q -p no:randomly --durations=10
```

## WP22 — ADR and seam documentation

**Verified at HEAD**
- `PlacementSeam` L2261, `resolve_placement_only` L1827, `write_target` L2304, `read_dir` L2318, `placement_seam` L2835, `resolve_artifact_surface` L2647, `coord_read_dir_for` L2765. These match the prompt's table; they shift again after WP04.
- `grep -rn 3928 docs/adr` is empty (confirmed).
- All five docs test files exist.
- ADR 2026-06-19-1's frontmatter is `status: Superseded`. Adding a binding amendment to a Superseded ADR may confuse readers. Consider stating in the amendment that it binds despite the status, or point to the superseding record (keep the status MADR-valid, as the prompt says).
- `docs/architecture/artifact-placement-seam.md` has `updated: '2026-09-30'` at L5.

**Quick-run**: as in the prompt (5 docs files plus `tests/architectural/test_no_legacy_terminology.py`).
