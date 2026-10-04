---
work_package_id: WP01
title: mission_number bake cluster leaves ordering.py
dependencies: []
requirement_refs:
- FR-003
- FR-006
- FR-007
- NFR-001
- NFR-003
- C-001
- C-005
- SC-004
planning_base_branch: issue-2026-consolidation-decomposition
merge_target_branch: issue-2026-consolidation-decomposition
branch_strategy: Planning artifacts for this mission were generated on issue-2026-consolidation-decomposition. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2026-consolidation-decomposition unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Slices
history:
- at: '2026-10-04T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: src/specify_cli/consolidation/mission_number/
create_intent:
- src/specify_cli/consolidation/mission_number/__init__.py
- src/specify_cli/consolidation/mission_number/bake.py
- tests/consolidation/test_mission_number_package.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/ordering.py
- src/specify_cli/consolidation/mission_number.py
- src/specify_cli/consolidation/mission_number/**
- src/specify_cli/consolidation/__init__.py
- src/specify_cli/consolidation/forecast.py
- tests/consolidation/test_ordering_bake_seam.py
- tests/consolidation/test_merge_compat_surface.py
- tests/consolidation/test_mission_number_package.py
- tests/architectural/_load_meta_census.py
- tests/architectural/untrusted_path_audit/inventory.md
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/test_mission_resolver_walker_gate.py
- tests/specify_cli/cli/commands/test_commit_recipes.py
- pyproject.toml
role: reviewer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – mission_number bake cluster leaves ordering.py

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Close #2600 with a pure relocation:

- `src/specify_cli/consolidation/ordering.py` keeps only `MergeOrderError`, `has_dependency_info`, `get_merge_order` (+ its own imports/logger).
- `src/specify_cli/consolidation/mission_number.py` becomes `src/specify_cli/consolidation/mission_number/__init__.py`, **content unchanged** (stdlib-only leaf, imported by `drivers.py` inside git's merge-driver subprocess).
- Every function of the bake cluster (`assign_next_mission_number` through `_read_target_tree_mission_number`, `ordering.py:138-911`) moves **verbatim** to `src/specify_cli/consolidation/mission_number/bake.py`, including the #2037 `assert_safe_path_segment` guards inside `_compute_next_mission_number_or_none`.
- All callers, tests and gates point at the new module; no gate loses an entry or a floor.

## Context & Constraints

- Spec FR-003; research.md R-1 (why a package, not the leaf file).
- C-001 no behaviour change; C-005 move first, then callers; no logic edit while moving.
- Code-grounding §1.3 and §3 list every gate keyed on `ordering.py`.

## Branch Strategy

- **Strategy**: single_branch — work directly in the repository root checkout.
- **Planning base branch**: issue-2026-consolidation-decomposition
- **Merge target branch**: issue-2026-consolidation-decomposition

## Subtasks & Detailed Guidance

### T001 – Failing-first structural test

New file `tests/consolidation/test_mission_number_package.py` (`pytestmark = pytest.mark.fast`):

1. `ordering`'s top-level definitions are exactly `{MergeOrderError, has_dependency_info, get_merge_order}` (AST over `inspect.getsource`).
2. The source of `specify_cli/consolidation/mission_number/__init__.py` imports only stdlib modules (AST: every `Import`/`ImportFrom` module root is in `sys.stdlib_module_names` or `__future__`).
3. `specify_cli.consolidation.mission_number.bake` defines the cluster names (`assign_next_mission_number`, `_bake_mission_number_into_mission_branch`, `_write_mission_number_to_branch`, `_read_target_tree_mission_number`, ...).

Commit it red first (it fails on main: ordering defines the cluster, `mission_number.bake` does not exist).

### T002 – Package conversion

`git mv src/specify_cli/consolidation/mission_number.py src/specify_cli/consolidation/mission_number/__init__.py`. No content change (the docstring's mention of `ordering.py` stays true: `ordering` still must not be imported by `drivers.py`; update only if a sentence becomes false).

### T003 – Verbatim move

Slice `ordering.py` lines 138-911 (from `def assign_next_mission_number` to EOF) into `mission_number/bake.py` with a module docstring ("mission_number assignment/bake/verify cluster, relocated verbatim from ordering.py by #2600") and `ordering.py`'s import header; prune unused imports with `ruff check --select F401 --fix` on both files. Keep lazy in-function imports lazy (C-007). Keep `__all__` split accordingly. Check byte-identity of each moved function with an AST/source comparison against `git show HEAD:src/specify_cli/consolidation/ordering.py`.

### T004 – Callers

`consolidation/__init__.py:22`, `forecast.py:43`, `executor.py:144` (out-of-map, one import line — rationale: executor's own import of the moved names), `cli/commands/consolidate.py:200` and its module-map comment line naming `ordering.py` (out-of-map; WP02 owns the file — one import/comment line).

### T005 – Tests

- `tests/consolidation/test_ordering_bake_seam.py`: retarget the module object and the lazy-import AST guard to `mission_number.bake` (the guard must still parse the module that now holds the lazy imports — never left parsing `ordering`, which would make it vacuous).
- `tests/consolidation/test_merge_compat_surface.py`: `_ORDERING_SYMBOLS` → the bake module; add `specify_cli.consolidation.mission_number.bake` to `_SEAM_IMPORT_TARGETS`.
- Grep `tests/` for `consolidation.ordering` / `from specify_cli.consolidation.ordering import` / `ordering\.` attribute use of moved names and re-point each.

### T006 – Gates and ledgers (re-point, never loosen)

- `tests/architectural/_load_meta_census.py:208-210` → `.../mission_number/bake.py`.
- `tests/architectural/test_destructive_op_routing.py:258-270` (two `worktree_remove_force` keys + prose) → bake module (out-of-map: WP03 also edits this file).
- `tests/architectural/untrusted_path_audit/inventory.md:65-66, :103, :170` → `consolidation/mission_number/bake.py:<line>`, append the relocation to the rationale history.
- `tests/architectural/dead_symbol_allowlist.yaml:1099-1104` → `module: specify_cli.consolidation.mission_number.bake`.
- `tests/architectural/test_mission_resolver_walker_gate.py:26` → the bake module (replace, do not add).
- `tests/specify_cli/cli/commands/test_commit_recipes.py:74-77` → bake module.
- `tests/specify_cli/test_meta_fail_closed_full_census_contract.py` `_WP09_OWNED_FILES`: add the bake module (keep ordering.py only if it still has a site; the stale guard decides).
- `tests/architectural/test_exemption_registry_ratchet.py` `CHURN_SURFACE_MODULES`: add the bake module if it holds filename collections.
- `tests/architectural/test_layer_rules.py` `_MERGE_CLI_CONSOLE_IMPORTERS`: add the bake module; drop `ordering.py` if it no longer imports `console` (stale-entry guard).
- `tests/architectural/test_no_dead_symbols.py` / allowlist: run and re-point anything keyed on `specify_cli.consolidation.ordering`.
- `pyproject.toml` mypy quarantine: run `mypy` on the bake module first; if the moved code is not strict-clean, move the `specify_cli.consolidation.ordering` quarantine entry to `specify_cli.consolidation.mission_number.bake` (the debt follows the code; ordering leaves the quarantine only if clean) and record it in traces/design-decisions.md.

### T007 – Validation

```bash
.venv/bin/python -m pytest tests/consolidation -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/architectural/_load_meta_census.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/untrusted_path_audit tests/specify_cli/cli/commands/test_commit_recipes.py tests/specify_cli/test_meta_fail_closed_full_census_contract.py -q
ruff check <changed> && ruff format --check --force-exclude <changed> && mypy <changed src>
```

## Risks & Mitigations

- A gate that greps the old path keeps passing vacuously → for each re-pointed entry, confirm the new file contains the pinned code.

## Review Guidance

- Diff of moved functions must be pure deletion in `ordering.py` + identical addition in `bake.py` (`git diff --color-moved=dimmed-zebra`).
- `mission_number/__init__.py` is a pure rename (100% similarity).

## Activity Log

- 2026-10-04T09:00:00Z – system – Prompt created.
