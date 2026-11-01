---
work_package_id: WP01
title: Default diagnostic run for a bare `doctor`
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6969-bare-doctor-default-checks
merge_target_branch: issue-6969-bare-doctor-default-checks
branch_strategy: Planning artifacts for this mission were generated on issue-6969-bare-doctor-default-checks. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6969-bare-doctor-default-checks unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Implementation
agent: reviewer-renata
shell_pid: 3570116
shell_pid_created_at: '1793548974.5'
history:
- timestamp: '2026-11-01T15:18:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/_default_run_doctor.py
- tests/cli/test_doctor_default_run.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_default_run_doctor.py
- src/specify_cli/cli/commands/doctor.py
- tests/cli/test_doctor_default_run.py
- tests/cli/test_top_level_group_empty_invocation.py
- tests/architectural/test_cli_placeholder_output.py
- docs/api/cli-commands.md
- docs/changelog/CHANGELOG.md
- src/charter/offering/skills/spec-kitty-setup-doctor/SKILL.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6969'
---

# Work Package Prompt: WP01 – Default diagnostic run for a bare `doctor`

## Goal

Make `spec-kitty doctor` with no subcommand actually diagnose the project. It runs three
fast, read-only, project-level checks — `command-files`, `state-roots`, `ops` — prints a
one-line summary per check that names its subcommand, and exits 0 when every check is
healthy and 1 when any reports a finding (or raises). Issue #6969.

Today the group callback (`_doctor_group` in `src/specify_cli/cli/commands/doctor.py`)
prints the help and exits 2 (#4678). Replace the refusal, not the reason: a bare
invocation must never read as a passing check, so it runs real checks and reports a real
verdict.

## Context

- Read [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md) and
  [quickstart.md](../quickstart.md) before editing.
- The three data primitives already exist and are pure (research.md Evidence):
  - `specify_cli.runtime.doctor.check_command_file_health(project_path) -> list[dict]`
  - `specify_cli.state.doctor.check_state_roots(repo_root) -> StateRootsReport` (`.healthy`)
  - `specify_cli.doctor.ops.list_orphan_ops(repo_root) -> list[Path]`
- Load `spec-kitty charter context --action implement` and the `python-pedro` profile
  before starting.

## Subtasks

- **T001 (red first).** Create `tests/cli/test_doctor_default_run.py`. Build the
  registered root (`register_commands(typer.Typer())`) and invoke `["doctor"]` with
  `CliRunner` inside a fixture project (a tmp dir with `.kittify/` and a
  `kitty-specs/` folder). Assert: exit 0, one line per default check, and each line names
  its subcommand. On today's code this fails with exit 2 — record that red state in the
  WP history before the fix. Add cases: a planted finding → exit 1 and the owning
  subcommand named on the finding line; a check that raises → that check reported failed,
  the other checks still reported, exit 1; not in a project → exit 1 and the standard
  not-in-project message.
- **T002–T003.** New sibling `src/specify_cli/cli/commands/_default_run_doctor.py` (the
  #2059 shim rule forbids new logic in `doctor.py`):
  - `DefaultCheck` frozen dataclass: `command`, `description`, `collect(root) -> list[str]`.
  - `DEFAULT_CHECKS: tuple[DefaultCheck, ...]` — the three checks, each a thin adapter over
    the primitive above. Every finding string names the text a user can act on.
  - `CheckResult` frozen dataclass: `check`, `findings`, `error`; `healthy` property.
  - `run_default_checks(repo_root) -> list[CheckResult]` — each check runs inside
    `try/except Exception` (FR-005); a raise becomes `error=str(exc)`.
  - `render_default_run(results) -> int` — prints the summary through the shared
    `console` (`_doctor_shared.console`, C-002) and returns 0/1. Keep the output shape in
    quickstart.md: `ok`/`FAIL`, the subcommand, its one-line status, and for a finding
    `full report: spec-kitty doctor <subcommand>`.
- **T004.** In `doctor.py`, `_doctor_group` returns immediately when
  `ctx.invoked_subcommand is not None`; otherwise resolve the project root through
  `_doctor_shared.resolve_project_root_or_exit(locate_project_root, False, exit_code=1)`
  and `raise typer.Exit(code=render_default_run(run_default_checks(root)))`. No new group
  options (C-003). Keep the module a shim: no aggregation logic here.
- **T005.** Update `tests/cli/test_top_level_group_empty_invocation.py`: the
  `#4678` test asserted exit 2 and "no diagnostic ran". Rewrite it to the new contract
  (exit 0/1 from the checks, "no diagnostic ran" never printed) while keeping its intent
  that a bare `doctor` is not silently a usage error, and keep the subcommand-help test.
- **T006.** Read-only proof: snapshot the fixture project's files (name + bytes) before
  and after a bare run and assert equality (NFR-002).
- **T007.** Change the group help string so `spec-kitty doctor --help` states that a bare
  invocation runs the default check set, and refresh **only** the recorded
  `## spec-kitty doctor` block in `docs/api/cli-commands.md` (summary line plus the
  fenced help body). Verify with
  `uv run python -m scripts.docs.check_cli_reference_freshness --ci` (or its module CLI)
  rather than a full regeneration.
- **T008.** `docs/changelog/CHANGELOG.md` `[Unreleased]`: bold impact-first lead with
  `(#6969)`, before/after, under 1,200 characters; note that it supersedes #4678's exit-2
  remedy. Update the setup-doctor skill text
  (`src/charter/offering/skills/spec-kitty-setup-doctor/SKILL.md`) so bare `doctor` is
  documented as a real check; keep the `--json` subcommand guidance intact.
- **T009.** Run the targeted gates: the new test file, the updated
  `tests/cli/test_top_level_group_empty_invocation.py`,
  `tests/architectural/test_cli_placeholder_output.py`, `ruff` on the touched files,
  `mypy` on the new module, and the docs-freshness CLI-reference check.

## Definition of done

- Bare `spec-kitty doctor` in a project exits 0 and prints one line per default check.
- A planted finding flips the exit code to 1 and names the owning subcommand.
- A raising check does not abort the run.
- Not-in-project exits 1 with the standard message.
- Every existing `doctor <subcommand>` is byte-for-byte unchanged in behaviour.
- Help, changelog, `docs/api/cli-commands.md` and the setup-doctor skill describe the
  default run.
- No new mutating flag; no second `Console()`; no logic added to the `doctor.py` shim.
