---
affected_files: []
cycle_number: 1
mission_slug: subtask-recipe-wp-scoping-01M6G9TW
reproduction_command: spec-kitty agent tasks move-task WP02 --to approved --mission subtask-recipe-wp-scoping-01M6G9TW --agent reviewer-renata
reviewed_at: '2026-11-03T11:45:49Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

Approved by reviewer-renata: approval:WP02

## Anti-pattern checklist

1. **Dead code** — PASS. `mark_status_recipe` has four live production callers
   (`tasks_transition_core._guard_subtasks`, `prompt_builder._completion_lines`,
   `workflow_executor._subtask_completion_recipe`, which itself serves the three
   runbook sites); `_subtask_completion_recipe` is called from all three.
2. **Synthetic fixture** — PASS. The behavioural test drives the real
   `agent tasks mark-status` Typer app over a two-WP shared-id mission and reads
   the emitted `status.events.jsonl`; deleting the fix reds it. Verified: with
   `prompt_builder.py` and `tasks_transition_core.py` reverted to `790bd82a89^`,
   5 of 13 tests fail (refusal recipe, no-mission recipe, end-to-end gate replay,
   prompt line, AST census) — no test passes on the pre-fix source.
3. **Silent empty return** — PASS. No new `return ""/None/[]/{}` and no bare
   `except: pass` in the diff.
4. **FR coverage** — PASS. FR-001 refusal line, FR-002 executed recipe, FR-003
   prompt line, FR-004 owned render (`--wp` + `--owned-checkout`), FR-005 all
   three runbook sites, FR-006 no-roster wording, NFR-001 purity test in
   `tests/specify_cli/core/test_subtask_recipe.py`, NFR-002 AST census.
5. **Frozen surface** — PASS. No commit touches `tasks.py`, `tasks_mark_status.py`
   or `fixtures/tasks_cli/help/*`; `test_tasks_cli_contract.py` green (52 tests).
6. **Locked decision** — PASS. C-001 (no subtask-id renaming): ids stay `T###`.
   C-002: `_resolve_task_owners` untouched — only the printed recipe gains `--wp`.
   C-003: refusal, `--force` hint and guard verdict unchanged and asserted.
7. **Shared-file ownership** — PASS. `lanes.json` puts all three WPs in
   `lane-planning`; the diff touches only WP02's `owned_files`. A stray
   `pyproject.toml` mypy-override entry left by the interrupted run was reverted
   (no gate reads it; `mypy --strict` on the new module is clean without it).
8. **Production fragility** — PASS. No new `raise`; the renderer is pure text.

## Tests run at head

- `pytest tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py
  tests/next/test_prompt_builder_review_base.py
  tests/integration/test_prompt_builder_owned_arms.py -q` → 29 passed
- `pytest tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py
  tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py
  tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py -q` → 52 passed
- `pytest tests/specify_cli/core/ -q` → 560 passed, 1 skipped
- `pytest tests/next -q` → 694 passed, 1 skipped
- `ruff check` / `ruff format --check --force-exclude` on the touched files → clean
