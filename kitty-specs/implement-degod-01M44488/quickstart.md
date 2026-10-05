# Quickstart: validating a work package of this mission

All commands run from the repository root checkout, or from the WP's lane worktree, with the synced
venv (`uv sync --frozen --all-extras`). Never run `make test-full` or a whole `tests/architectural/`
sweep (NO_FULL_HEAVY_SUITES_IN_MISSION).

## 1. Baseline

```bash
make test-fast
```

## 2. Implement-direct regression subset (NFR-003: ≤ 30 s)

```bash
uv run --frozen pytest -n auto --dist loadfile -p no:randomly \
  tests/agent/test_implement_command.py tests/agent/cli/commands/test_implement_preflight.py \
  tests/agent/test_implement_programmatic_call.py tests/agent/test_mission_handle_json_errors.py \
  tests/cli/commands/test_implement_base_flag.py tests/specify_cli/workspace/test_context_implement_reads.py \
  tests/cli/test_implement_bulk_edit_planning.py tests/integration/test_status_emit_on_alloc_failure.py \
  tests/specify_cli/cli/commands/test_implement*.py \
  tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py \
  tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py \
  tests/specify_cli/cli/commands/test_coordination_remedy_5113.py \
  tests/specify_cli/cli/commands/test_precondition_ref_unification.py \
  tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py \
  tests/specify_cli/lanes/test_lane_base_honoring.py tests/specify_cli/core/test_dependency_graph_canceled.py \
  tests/specify_cli/coordination/test_flat_legacy_none_seam_success_arms.py \
  tests/lanes/test_issue_2993_lane_planning_ancestry.py tests/integration/test_wp_integrity_*.py
```

Add each new seam test file as it lands. Also run every test file the WP's diff touches, and the
owning subsystem directory of each source module touched (CLAUDE.md blast-radius rule):
`tests/lanes/`, `tests/specify_cli/workspace/`, `tests/specify_cli/coordination/`, `tests/status/`,
`tests/specify_cli/core/`.

## 3. Gate files (run the ones the WP implicates)

```bash
uv run --frozen pytest -p no:randomly -n0 \
  tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py \
  tests/architectural/test_trio_seam_only.py tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_wp_integrity_partition_call_shape.py tests/architectural/test_exemption_registry_ratchet.py \
  tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_status_module_boundary.py \
  tests/architectural/test_safe_commit_import_boundary.py tests/architectural/test_cold_import_status_boundary.py \
  tests/architectural/test_planning_lane_branch_requires_target.py tests/architectural/test_git_matrix_paths_resolve.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_no_legacy_terminology.py \
  tests/specify_cli/test_mid8_contract_sensitive_routing.py tests/specify_cli/status/test_cutover_byte_stability.py \
  tests/specify_cli/test_meta_fail_closed_full_census_contract.py \
  tests/contract/test_terminology_guards.py tests/contract/test_feature_alias_scope.py
```

## 4. Lint, format, types, complexity

```bash
uv run --frozen ruff check <changed files>
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen ruff check --select C901 <changed src files>
uv run --frozen mypy --strict <new/receiving src modules>
```

## 5. Patch-site counter (SC-002)

```bash
uv run --frozen python kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py
```

Run it before and after each test-touching WP and record the numbers in the WP's review notes.

## 6. End-to-end lesson (#3371)

For any planning-commit or lanes-dir change:

```bash
uv run --frozen pytest -p no:randomly tests/e2e/test_cli_smoke.py::TestFullCLIWorkflow::test_full_workflow_sequence
```
