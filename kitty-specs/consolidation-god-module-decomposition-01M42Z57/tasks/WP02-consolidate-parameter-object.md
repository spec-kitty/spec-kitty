---
work_package_id: WP02
title: ConsolidateOptions parameter object
dependencies: []
requirement_refs:
- FR-004
- FR-005
- C-001
- C-006
- NFR-003
- SC-005
planning_base_branch: issue-2026-consolidation-decomposition
merge_target_branch: issue-2026-consolidation-decomposition
branch_strategy: Planning artifacts for this mission were generated on issue-2026-consolidation-decomposition. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2026-consolidation-decomposition unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 1 - Slices
history:
- at: '2026-10-04T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: src/specify_cli/cli/commands/consolidate.py
create_intent:
- tests/consolidation/test_consolidate_options.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/consolidate.py
- tests/consolidation/test_merge_preflight_mission_branch.py
- tests/consolidation/test_consolidate_options.py
role: reviewer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – ConsolidateOptions parameter object

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Close #3457 (Introduce Parameter Object, tactic `change-function-declaration` / introduce parameter object):

- A frozen dataclass `ConsolidateOptions` in `src/specify_cli/cli/commands/consolidate.py` with one field per `consolidate` option and the CLI's real default (data-model.md table). No field defaults to a `typer.OptionInfo`.
- `run_consolidate(options: ConsolidateOptions) -> None` holds the current `consolidate()` body. To keep the body text identical, it starts by binding `strategy = options.strategy`, ... for each field (the rest of the body is unchanged).
- The Typer `consolidate(...)` keeps its 19 `typer.Option` parameters byte-for-byte (C-006; `test_wrapper_delegation.py:202` and `test_merge_cli_golden.py` read that signature) and its `@require_main_repo` decorator; its body becomes `run_consolidate(ConsolidateOptions(strategy=strategy, ...))`.
- The 8 direct-call sites build `ConsolidateOptions(...)` with only the fields they care about and call `run_consolidate(...)` (the old `__wrapped__` call bypassed `require_main_repo`; `run_consolidate` is likewise undecorated, so semantics match).

Out of scope (follow-ups named in #3457): a new doctrine refactoring tactic, a `**kwargs` lint rule.

## Context & Constraints

- Spec FR-004/FR-005, data-model.md, research.md R-4. C-001: no refusal text/exit code changes; `_validated_attestation_flags` keeps its sentinel defence (the Typer path still passes real values; direct `consolidate()` callers may still exist outside tests).

## Branch Strategy

- **Strategy**: single_branch — repository root checkout.
- **Planning base branch**: issue-2026-consolidation-decomposition
- **Merge target branch**: issue-2026-consolidation-decomposition

## Subtasks & Detailed Guidance

### T008 – Failing-first test (`tests/consolidation/test_consolidate_options.py`, `fast`)

1. `ConsolidateOptions()` constructs with no arguments and no field value is an instance of `typer.models.OptionInfo`.
2. The dataclass field names equal the Typer command's parameter names (`inspect.signature(consolidate.__wrapped__).parameters`) — so adding a CLI option without a field fails here, loudly, in one place.
3. Each field default equals the Typer option's `.default`.
4. `ConsolidateOptions` is frozen.

Commit red (fails: no `ConsolidateOptions`).

### T009 – Introduce the parameter object

Add the dataclass and `run_consolidate` next to `consolidate`; export both in `__all__`. Do not move or reorder anything else. Rename nothing.

### T010 – Re-point direct-call sites

`tests/consolidation/test_merge_preflight_mission_branch.py` lines ~97-543 (7 sites, `command = merge_mod.consolidate.__wrapped__` + 16 kwargs) and `tests/consolidation/test_executor_coverage.py:1274` (out-of-map; WP03 owns that file — one call site). Pass only non-default values; keep each test's meaning.

### T011 – Validation

```bash
.venv/bin/python -m pytest tests/consolidation/test_consolidate_options.py tests/consolidation/test_merge_preflight_mission_branch.py tests/consolidation/test_executor_coverage.py tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py tests/specify_cli/cli/commands/test_merge_cli_golden.py tests/specify_cli/cli/commands/test_merge.py -q
.venv/bin/python -m pytest tests/consolidation -n 4 --dist loadfile -q
ruff check / ruff format --check --force-exclude / mypy on changed files
```

## Risks & Mitigations

- Typer reads parameter defaults from the function signature: never change `consolidate`'s parameters.

## Review Guidance

- `run_consolidate`'s body after the binding prologue must match the old `consolidate` body exactly.

## Activity Log

- 2026-10-04T09:00:00Z – system – Prompt created.
