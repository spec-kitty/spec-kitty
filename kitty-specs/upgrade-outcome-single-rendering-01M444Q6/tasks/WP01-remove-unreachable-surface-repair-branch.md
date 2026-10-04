---
work_package_id: WP01
title: Remove the unreachable legacy surface-repair branch
dependencies: []
requirement_refs:
- FR-016
planning_base_branch: issue-4925-upgrade-outcome-single-rendering
merge_target_branch: issue-4925-upgrade-outcome-single-rendering
branch_strategy: Planning artifacts for this mission were generated on issue-4925-upgrade-outcome-single-rendering. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4925-upgrade-outcome-single-rendering unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-outcome-single-rendering-01M444Q6
base_commit: f0d8a453add1b1771e8838aa52e01afc8e4850b5
created_at: '2026-10-04T19:15:54.087404+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Tidy first
history:
- at: '2026-10-04T19:11:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent:
- tests/upgrade/test_legacy_surface_repair_unreachable.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/compat/test_dry_run_parity.py
- tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py
- tests/upgrade/test_legacy_surface_repair_unreachable.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Remove the unreachable legacy surface-repair branch

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Tidy-first, behaviour-preserving (spec FR-016). `spec-kitty upgrade` has two code paths for tool-surface repair in `src/specify_cli/cli/commands/upgrade.py`. The older one cannot be reached on any real run, yet six tests still patch it. Remove it so the next work package has exactly one path to make outcome-driven.

Done when:

- `_run_upgrade_surface_repair` and `_surface_drift_exit_required` no longer exist, and `_finalizer_step_surface_repair` has no fallback to them.
- No test patches a symbol that no longer exists; the tests that patched it still pass and still test what their names say.
- No user-visible behaviour of `spec-kitty upgrade` changes (same output, same exit codes).

## Context & Constraints

- Read first: `.kittify/charter/charter.md` (Standing Orders 2, 4, 5), then this mission's `spec.md`, `plan.md`, `data-model.md` and `contracts/upgrade-outcome-contract.md` under `kitty-specs/upgrade-outcome-single-rendering-01M444Q6/`.
- Load doctrine with `spec-kitty charter context --action implement`.
- **Read-only**: `src/specify_cli/upgrade/runner.py` and `src/specify_cli/upgrade/assessment.py` (a sibling mission and an open pull request own them). `worktree_failures` stays `list[str]`.
- Do not change the planner / compatibility exit paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, agent-check flags).
- Do not edit the mission's tracer files under `traces/`; report friction and decisions in your hand-back and the orchestrator records them.
- Use CodeGraph first: `codegraph explore "<symbols>"`.
- In a lane worktree there is no `.venv`: run `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest ...`, and drive the CLI in-process (`CliRunner`), never the global `spec-kitty` binary. Never a bare `uv run`.
- Tests: run only the files named in this prompt. No whole directories, no `make test-fast`, no full `tests/architectural/`.
- New code passes `ruff check`, `ruff format --check --force-exclude <files>` and `mypy --strict` with no new suppressions. Complexity ≤ 15 per function. Repeated literals (3+) become constants.
- No machine-local paths or personal data in code, tests or commit messages.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path that `spec-kitty implement` returns.

- **Ownership note**: this WP's `owned_files` lists the tests it repoints. The deletion in `src/specify_cli/cli/commands/upgrade.py` is an out-of-map edit, allowed under ownership-map leeway: WP02 owns that file and depends on this WP, so there is no parallel writer. Say so in your hand-back.

## Subtasks & Detailed Guidance

### Subtask T001 – Pin unreachability with a test (first commit)

- **Purpose**: prove the branch is dead before deleting it, so the deletion is a tidy and not a behaviour change.
- **Steps**:
  1. Read `_finalizer_step_surface_repair`, `_prepare_finalizer_repairs`, `_finalizer_repair_preflight` in `src/specify_cli/cli/commands/upgrade.py` and `finalize_upgrade` in `src/specify_cli/upgrade/finalize.py`.
  2. The claim to prove: the fallback call to `_run_upgrade_surface_repair` needs `not dry_run`, `outcome.result.success` and `ctx.prepared_repairs is None`. Under those conditions `_prepare_finalizer_repairs` either sets `prepared_repairs` or returns errors; returned errors become `activation_errors` in `finalize_upgrade`, which then skips the surface-repair step.
  3. Write `tests/upgrade/test_legacy_surface_repair_unreachable.py`: patch `_run_upgrade_surface_repair` with a spy that fails the test if called, then drive `finalize_upgrade` wired exactly as `upgrade()` wires it for (a) preparation succeeds, (b) preparation raises `OSError`, (c) preparation raises `ValueError`, (d) dry run, (e) failed migration result. Assert the spy is never called in any case.
  4. Commit this test alone: `test(upgrade): pin that the legacy surface-repair branch is unreachable`.
- **If the claim is false** (the spy is called on some reachable path): stop, do not delete anything, and report the path in your hand-back. The plan then keeps the branch and routes it through the new report type in WP02.
- **Files**: `tests/upgrade/test_legacy_surface_repair_unreachable.py` (new).

### Subtask T002 – Delete the branch

- **Purpose**: one surface-repair path.
- **Steps**:
  1. In `_finalizer_step_surface_repair`, remove the trailing fallback (the `ctx.surface_repair_summary = _run_upgrade_surface_repair(...)` assignment and the `return _surface_drift_exit_required(...)`). After the prepared block the function must still return on every path; when `ctx.prepared_repairs is None` on a real run, return `False` (nothing was attempted). Keep the `confirm` parameter only if something else still uses it; if it becomes unused, remove it here and at the `functools.partial` call site.
  2. Delete `_run_upgrade_surface_repair` and `_surface_drift_exit_required`.
  3. `_repair_stale_command_manifest` was called only from the deleted helper. Check with CodeGraph whether the prepared path (`prepare_upgrade_repairs` / `apply_upgrade_repairs` in `src/specify_cli/upgrade/assessment.py`, read-only) already covers command-skill manifest repair. If it does, delete `_repair_stale_command_manifest` too. If it does not, keep the function, do not call it from anywhere new, and report it in your hand-back as a finding; do not change behaviour in this WP.
  4. Keep `render_surface_summary_lines` in `src/specify_cli/tool_surface/repair.py`: `init` uses it. Keep `_surface_drift_error` and `_surface_repair_payload`.
  5. Update the docstrings that still describe the removed helper (`upgrade/finalize.py` module docstring names `_run_upgrade_surface_repair`; that one-line docstring fix in `finalize.py` is in scope).
  6. Replace the T001 spy test with a simpler structural assertion that the two names are gone from the module (`not hasattr`), and keep the five finalizer cases as behaviour tests asserting what does happen (surface repair skipped / applied). Commit: `refactor(upgrade): remove the unreachable legacy surface-repair branch`.
- **Files**: `src/specify_cli/cli/commands/upgrade.py`, `src/specify_cli/upgrade/finalize.py` (docstring only), `tests/upgrade/test_legacy_surface_repair_unreachable.py`.

### Subtask T003 – Repoint the tests that patched the dead helper

- **Purpose**: the six patches were inert; a test that stubs a symbol nothing calls documents a false setup.
- **Steps**:
  1. `tests/compat/test_dry_run_parity.py` (around line 99) and `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` (around lines 240, 269, 298, 330, 373) patch `_run_upgrade_surface_repair`. Remove each patch. If the test's intent was "surface repair is stubbed / scoped out", stub the live seam instead (`prepare_upgrade_repairs` / `apply_upgrade_repairs` as imported in `cli/commands/upgrade.py`) only where the test needs it to stay isolated; otherwise just delete the patch and fix the comment that claims a stub.
  2. Search for any other reference: `grep -rn "_run_upgrade_surface_repair\|_surface_drift_exit_required" src tests`. `tests/specify_cli/skills/test_crlf_skill_render_4998.py`, `tests/upgrade/test_upgrade_char_net.py`, `tests/upgrade/test_worktree_stamp_guard.py` and `tests/upgrade/test_upgrade_integration.py` reference related symbols; fix only references to the two deleted names.
  3. Do not weaken any assertion. Commit: `test(upgrade): stop patching the removed surface-repair helper`.
- **Files**: the two owned test files, plus any other file that references a deleted name (one-line rationale in the commit body).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/upgrade/test_legacy_surface_repair_unreachable.py tests/compat/test_dry_run_parity.py \
  tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py \
  tests/upgrade/test_finalizer.py tests/upgrade/test_upgrade_integration.py \
  tests/specify_cli/tool_surface/test_drift_policy.py tests/specify_cli/tool_surface/test_surface_repair_wiring.py
ruff check src/specify_cli/cli/commands/upgrade.py tests/upgrade/test_legacy_surface_repair_unreachable.py
ruff format --check --force-exclude <changed files>
mypy --strict src/specify_cli/cli/commands/upgrade.py src/specify_cli/upgrade/finalize.py
```

## Risks & Mitigations

- A test elsewhere may depend on the legacy path through `monkeypatch.setattr(..., raising=True)`; the grep in T003 catches these.
- Dead-symbol gates: if deleting leaves an import unused, remove it.

## Review Guidance

- T001's commit must exist and precede the deletion; the spy test must have been able to fail (check it patches the real name).
- No output or exit-code change: `tests/upgrade/test_upgrade_integration.py` and `test_drift_policy.py` pass unmodified.
- No assertion was weakened in the repointed tests.

## Amendments from the post-tasks review (binding; these override the text above where they differ)

1. **T001 must drive the real command.** The finalizer wiring is inline in `upgrade()` and cannot be imported, so a hand-copied wiring proves nothing. Drive `upgrade` through `CliRunner` with the spy on `_run_upgrade_surface_repair`. Cases: preparation succeeds; preparation raises `OSError`; raises `ValueError`; raises `AgentConfigError` (`specify_cli.core.agent_config`); dry run; failed migration result.
2. **Patch targets.** `prepare_upgrade_repairs` and `apply_upgrade_repairs` are function-local imports inside `cli/commands/upgrade.py`; patching them on that module raises `AttributeError`. Patch `specify_cli.upgrade.assessment.prepare_upgrade_repairs` / `apply_upgrade_repairs`, or `specify_cli.cli.commands.upgrade._prepare_finalizer_repairs`.
3. **`_repair_stale_command_manifest`.** Delete the call with the dead helper. Do not rewire it anywhere. Deleting it leaves `repair_stale_manifest` and `remove_unsafe_symlinks` with no production caller; unsafe-symlink removal under `.agents/skills/` then has no live caller in upgrade (it already had none in practice). Do not fix that here. Report it in your hand-back as a tracker finding with the file and line of both functions, and leave the two functions and their tests in place.
4. **Ownership note extends to `src/specify_cli/upgrade/finalize.py`** (docstring-only edit); WP02 owns that file and depends on this WP.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:11:03Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
