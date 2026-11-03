---
work_package_id: WP01
title: The recipe's single home
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- NFR-002
- C-002
- C-003
planning_base_branch: issue-7108-subtask-recipe-wp-scoping
merge_target_branch: issue-7108-subtask-recipe-wp-scoping
branch_strategy: Planning artifacts for this mission were generated on issue-7108-subtask-recipe-wp-scoping. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7108-subtask-recipe-wp-scoping unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - The recipe's single home
history:
- at: '2026-10-30T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- src/specify_cli/core/subtask_recipe.py
- tests/specify_cli/core/test_subtask_recipe.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/core/subtask_recipe.py
- tests/specify_cli/core/test_subtask_recipe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The recipe's single home

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

Ship one pure function that renders the subtask-completion command, and prove every
option arm against an exact expected line. Success is: WP02 can replace four
hand-formatted f-strings with one call each, and the `--wp` scoping can no longer
be forgotten at a new emitter.

## Context

`mark-status` records subtask completion in the mission event log. Subtask ids are
**mission-scoped**, so several WPs may author `T001`. `mark-status` resolves that
with `--wp`, and refuses an unscoped id that several WPs own. The CLI's own
`--help` already documents this ("Use --wp when the same ID appears in more than
one WP.").

What is missing is that the *printed recipes* do not pass `--wp`. This WP builds
the single renderer. WP02 wires it into the four emitters.

Read first:

- `src/specify_cli/cli/commands/agent/tasks_mark_status.py` — `_resolve_task_owners`
  (the owner authority; do not change it) and `_ms_validate_inputs` (the `--wp`
  shape check: uppercased, `WP\d+`).
- `src/specify_cli/cli/commands/agent/tasks.py` around the `mark_status` Typer
  wrapper — the exact option names and types (`--status`, `--mission`, `--wp`,
  `--owned-checkout`).
- `src/specify_cli/cli/commands/_commit_recipes.py` — the established precedent
  for "one reviewed home for a printed copy/paste recipe" (`safe_commit_recipe`),
  whose docstring style and `_`-prefixed module name you should mirror in spirit.
- `tests/architectural/test_layer_rules.py` (`_RUNTIME_ALLOWED_SPECIFY_CLI`) —
  why the module lands under `specify_cli.core` and not `specify_cli.cli`.

## Subtasks

### T001 — Red-first shape test

Write `tests/specify_cli/core/test_subtask_recipe.py` before the module exists.
It must import `mark_status_recipe` from `specify_cli.core.subtask_recipe` and
assert these exact renderings (use a `mission_slug` such as
`port-completion-01M6FZ0K`):

1. `mark_status_recipe(["T001"], wp_id="WP02")` →
   `spec-kitty agent tasks mark-status T001 --wp WP02 --status done`
2. `mark_status_recipe(["T001"], wp_id="WP02", mission_slug="m-01X")` →
   `... T001 --wp WP02 --status done --mission m-01X`
3. `mark_status_recipe(["T001"], wp_id="WP02", mission_slug="m-01X", owned_root=Path("/tmp/own"))` →
   `... T001 --wp WP02 --status done --mission m-01X --owned-checkout /tmp/own`
4. `mark_status_recipe(["T001", "T002", "T003"], wp_id="WP02", mission_slug="m-01X")` →
   `... mark-status T001 T002 T003 --wp WP02 --status done --mission m-01X`
5. `mark_status_recipe(["T001"], wp_id="WP02", mission_slug=None)` renders **no**
   `--mission` token and the string `None` never appears.

Also assert the marker on the collection for the fast lane
(`pytest.mark.fast`) and that no `import` of `kernel`, `specify_cli.status` or
`pathlib` happens at the module's top level (an `inspect.getsource` /
`ast` check is acceptable, mirroring how the repo pins purity elsewhere).

Run it; it must fail with `ModuleNotFoundError`.

### T002 — The renderer

Create `src/specify_cli/core/subtask_recipe.py`. Shape:

- Module docstring explaining *why it exists* (one reviewed home for printed
  advice, following the `_commit_recipes.py` precedent) and *why it lives in
  `core`* (the `runtime` layer may not import `specify_cli.cli`).
- `from __future__ import annotations`; imports limited to `collections.abc`
  (`Sequence`) and `os.PathLike` if needed for the type only (`TYPE_CHECKING`).
- `def mark_status_recipe(task_ids: Sequence[str], *, wp_id: str, mission_slug: str | None = None, owned_root: str | os.PathLike[str] | None = None) -> str:` with a full Google-style docstring (Args/Returns) in the style of
  `_commit_recipes.safe_commit_recipe`.
- The WP id is keyword-only and required: a caller cannot forget it.

### T003 — Pin the option order

The rendered order is fixed and load-bearing:

```
mark-status <ids...> --wp <WP> --status done [--mission <slug>] [--owned-checkout <root>]
```

`--wp` sits before `--status`; `--mission` then `--owned-checkout` keep their
current relative order so the existing owned-arm assertion in
`tests/integration/test_prompt_builder_owned_arms.py` remains a suffix match.
Add a short comment saying the order is asserted by tests, so a future edit does
not reorder silently.

## Definition of Done

- [ ] `uv run pytest tests/specify_cli/core/test_subtask_recipe.py -q` — all arms green.
- [ ] `uv run pytest tests/architectural -q -k "dead_symbol or layer_rules"` — green.
- [ ] `uv run ruff check src/specify_cli/core/subtask_recipe.py tests/specify_cli/core/test_subtask_recipe.py` — clean.
- [ ] No change to any existing refusal, guard or CLI option.

## Risks & Mitigations

- **New-module census gates.** The module is imported by three emitters in WP02;
  if you land WP01 alone before WP02 is wired, a dead-symbol gate may flag it.
  Keep WP01 and WP02 in the same mission and run the architecture gate after
  WP02 if it reds.
- **Purity drift.** Anything beyond `collections.abc` in the module's import block
  is a review finding: `tasks_transition_core` calls this on the refusal path and
  must stay I/O-free.
