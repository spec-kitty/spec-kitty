---
work_package_id: WP01
title: Command-registry censuses follow the registry
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: kitty/nightly-reds-2026-10-03
merge_target_branch: kitty/nightly-reds-2026-10-03
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-2026-10-03. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-2026-10-03 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-2026-10-03-01M42RR1
base_commit: a7d8407fbe1ebdb66f010b83b298f2362b652e68
created_at: '2026-10-04T06:19:56.122768+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Test repairs
history:
- at: '2026-10-04T06:16:20Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/specify_cli/cli/commands/test_doctor_skills.py
- tests/specify_cli/cli/commands/test_init_hybrid.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Command-registry censuses follow the registry

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this work package was returned from review, the feedback reference is in the status event log (`spec-kitty agent tasks status --mission nightly-reds-2026-10-03-01M42RR1`). Address every item before handing back.

---

## Objectives & Success Criteria

- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py`, `test_doctor_skills.py::test_doctor_skills_json_error_schema_stable` and `test_init_hybrid.py::TestHybridInstallOutputShape` pass (FR-001, FR-002, FR-003).
- The four node ids that are red on base `b2c466d7d1` are green, and no other test in those three files changes outcome.
- Red on base (record this yourself before editing):
  - `test_doctor_cli_surface_golden.py::test_registered_command_names_match_frozen_subcommands` — registered set has extra `run-index`
  - `test_doctor_skills.py::test_doctor_skills_json_error_schema_stable` — `canonical_commands` 14 != 15
  - `test_init_hybrid.py::TestHybridInstallOutputShape::test_generate_all_shims_produces_thin_cli_shims` — 6 != 7
  - `test_init_hybrid.py::TestHybridInstallOutputShape::test_hybrid_layout_full_prompts_plus_cli_shims` — 15 != 16

## Context & Constraints

- Evidence and classification: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/research/nightly-red-memo.md`.
- Spec and plan: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/spec.md`, `plan.md`.
- **Hard rules (NFR-001, C-001)**: change only the files listed under `owned_files`. Do not edit anything under `src/`. Do not raise a budget or timeout, add a retry, or skip, xfail, deselect or delete a test. Keep every existing assertion except the stale literal you are replacing (NFR-002).
- **Test runs (C-003)**: run only the named node ids or the named file, in the foreground, serially:
  `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 <ids>` where `<repo>` is `/home/stijn/Documents/_code/SDD/fork/sk-nightly-reds-2026-10-03` and the command is run **from your lane worktree** with `PYTHONPATH=$PWD/src`. Never run a whole directory, `make test-fast` or `make test-full`; the orchestrator runs the breadth.
- **Red-first evidence (NFR-003)**: before editing, run the named tests and record the failing summary line. After the fix, record the passing summary line. Put both in the commit message body.
- Lint: `<repo>/.venv/bin/ruff check <files>` and `<repo>/.venv/bin/ruff format --check --force-exclude <files>` must be clean. No new `# noqa` or `# type: ignore`.
- Commit on the lane branch with a conventional message `test(<area>): ...`. Do not push. Do not touch `uv.lock`.
- Terminology: write Mission, never Feature, in new prose.

## Branch Strategy

- **Strategy**: lane worktree allocated by `spec-kitty agent action implement WP01 --agent claude`
- **Planning base branch**: kitty/nightly-reds-2026-10-03
- **Merge target branch**: kitty/nightly-reds-2026-10-03

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission nightly-reds-2026-10-03-01M42RR1`

## Subtasks & Detailed Guidance

### Subtask T001 – Record the red baseline

- **Purpose**: red-first evidence.
- **Steps**: run the four node ids above with `-n0`; keep the `4 failed` summary line and each assertion message.

### Subtask T002 – Add `run-index` to the frozen doctor surface (FR-001)

- **Purpose**: `ac4e8b84a8` (PR #5487) added the self-registering `doctor run-index` subcommand (`src/specify_cli/cli/commands/_run_index_doctor.py`). The golden file is a deliberate frozen snapshot, so it is updated by hand; do **not** derive it from the Typer app.
- **Steps**:
  1. In `test_doctor_cli_surface_golden.py` add `"run-index"` to `FROZEN_SUBCOMMANDS` (near line 70), keeping the existing ordering convention of the set.
  2. The option and help tests are parametrised on that set. Add `EXPECTED_OPTIONS["run-index"]` and `EXPECTED_HELP["run-index"]` entries that match the shipped command exactly. Read the real surface with `spec-kitty doctor run-index --help` (or by importing the command) and copy what the other entries' format requires; do not invent option names.
  3. Update any docstring or comment in the file that states the subcommand count.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py`
- **Validation**: run the whole file; every test passes, including the parametrised `run-index` cases.

### Subtask T003 – Take the `doctor skills` command count from the canonical set (FR-002)

- **Purpose**: `3d5c85d09c` (PR #5545) removed the dashboard command, so the canonical command set has 14 entries. The literal `15` in the frozen envelope (near line 290) is a duplicate census; the single literal census the suite keeps is `tests/specify_cli/skills/test_command_installer.py` (`== 14`), which you must not edit.
- **Steps**:
  1. Replace only the `canonical_commands` literal with `len(command_installer.CANONICAL_COMMANDS)` (import from `specify_cli.skills.command_installer`; the production value comes from the same constant in `_command_surface_doctor.py`).
  2. The surrounding block is marked as a frozen envelope: keep the exact-equality comparison of the whole dict and every other key and value byte-for-byte.
  3. Fix any comment that states 15.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_skills.py`
- **Validation**: run the whole file.

### Subtask T004 – Derive the hybrid-install counts from the registry (FR-003)

- **Purpose**: `CLI_DRIVEN_COMMANDS` in `src/specify_cli/shims/registry.py` now has 6 entries and `PROMPT_DRIVEN_COMMANDS` 9, so 7 and 16 are stale.
- **Steps**:
  1. In `TestHybridInstallOutputShape::test_generate_all_shims_produces_thin_cli_shims` (near line 143) expect `len(CLI_DRIVEN_COMMANDS)` shim files.
  2. In `test_hybrid_layout_full_prompts_plus_cli_shims` (near line 189) expect `len(PROMPT_DRIVEN_COMMANDS) + len(CLI_DRIVEN_COMMANDS)` files. The test already imports both sets around line 167; move or reuse that import rather than adding a second one.
  3. The left-hand side of each assertion must stay the count of files actually written to disk by the code under test; never compare a registry length with itself.
  4. Where the test already checks names, keep it. If neither test checks that the produced command names equal the registry sets, add that name-set equality assertion: it is stronger than a count and keeps the test meaningful after the literal goes.
  5. Fix the docstrings that say 7 and 16 (near lines 128 and 150-155) so they describe the registry-derived expectation.
- **Files**: `tests/specify_cli/cli/commands/test_init_hybrid.py`
- **Validation**: run the whole file.

## Risks & Mitigations

- A derived count can hide a real regression if the produced files are not also checked by name; T004 step 4 covers that.
- The help snapshot is whitespace-sensitive; follow the normalisation the file already uses.

## Review Guidance

- Confirm `EXPECTED_OPTIONS["run-index"]` and `EXPECTED_HELP["run-index"]` match the real command, not a guess.
- Confirm the `doctor skills` envelope is still one exact dict comparison with only the count derived.
- Confirm no assertion in `test_init_hybrid.py` became tautological (registry compared with registry).
- Confirm `tests/specify_cli/skills/test_command_installer.py` and everything under `src/` are untouched.

## Activity Log

- 2026-10-04T06:16:20Z – system – Prompt created.
