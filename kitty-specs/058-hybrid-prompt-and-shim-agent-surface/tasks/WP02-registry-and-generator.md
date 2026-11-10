---
work_package_id: WP02
title: Update Registry and Generator
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-006
- FR-007
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this feature were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: main
base_commit: 5f610cc2df502d13e40ea8c8f023dcbb79f9988a
created_at: '2026-03-30T14:23:01.960689+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: 1
history:
- at: '2026-03-30T13:59:29Z'
  event: created
  actor: spec-kitty
  note: WP02 generated from tasks.md for feature 058-hybrid-prompt-and-shim-agent-surface
authoritative_surface: src/specify_cli/shims/
execution_mode: code_change
mission_id: 01KN2371WVZGV7TH7WMR2CN9Q4
owned_files:
- src/specify_cli/shims/**
wp_code: WP02
---

# WP02 — Update Registry and Generator

## Branch Strategy

- **Base branch**: `main`
- **Feature branch**: `058-hybrid-prompt-and-shim-agent-surface-WP02`
- **Merge target**: `main`
- Branch from `main` before making any changes.
- This WP is independent of WP01 — it can run in parallel with WP01 (Wave 1).

## Objectives & Success Criteria

**Goal**: Add a formal PROMPT_DRIVEN / CLI_DRIVEN classification to the shim registry. Update the shim generator to only produce shims for CLI-driven commands (7 files, not 16). Update the shim entrypoint dispatcher to return `None` for prompt-driven commands (since their full prompt files handle the workflow) and delegate to existing handlers for CLI-driven commands.

**Success criteria**:
- `src/specify_cli/shims/registry.py` exports `PROMPT_DRIVEN_COMMANDS` (frozenset of 9 command names) and `CLI_DRIVEN_COMMANDS` (frozenset of 7 command names).
- `PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS` (the existing full set).
- `generate_all_shims()` produces exactly 7 shim files (implement, review, accept, merge, status, dashboard, tasks-finalize) — not 16.
- `shim_dispatch()` returns `None` immediately for any prompt-driven command without raising an error.
- `shim_dispatch()` delegates CLI-driven commands to their existing handlers.
- mypy --strict passes on all modified files.

## Context & Constraints

**Why this WP exists**: Feature 057 created thin shims for all 16 commands including the 9 prompt-driven planning commands. Prompt-driven commands (specify, plan, tasks, etc.) should never have thin shims — they need full prompt templates. This WP adds the classification that gates shim generation and dispatch behavior.

**PROMPT_DRIVEN_COMMANDS (9)**:
`specify`, `plan`, `tasks`, `tasks-outline`, `tasks-packages`, `checklist`, `analyze`, `research`, `constitution`

**CLI_DRIVEN_COMMANDS (7)**:
`implement`, `review`, `accept`, `merge`, `status`, `dashboard`, `tasks-finalize`

**Key invariant**: `PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS` must equal `CONSUMER_SKILLS` (the existing set of all consumer-facing command names). If `CONSUMER_SKILLS` doesn't exist yet, define it in `registry.py` and use it as the union.

**Constraint**: Do not change the behavior of existing CLI-driven shim handlers. This WP only changes which commands get shims generated and how `shim_dispatch()` routes prompt-driven commands.

**Constraint**: Do not modify files outside `src/specify_cli/shims/`. The init.py changes are WP03's responsibility.

**Requirement refs**: FR-001, FR-004, FR-006, FR-007

## Subtasks & Detailed Guidance

### T008 — Add PROMPT_DRIVEN_COMMANDS and CLI_DRIVEN_COMMANDS to registry.py

**Purpose**: Establish the authoritative classification of all consumer-facing commands as either prompt-driven or CLI-driven.

**Steps**:
1. Open `src/specify_cli/shims/registry.py`.
2. Define (near the top, after existing constants):
   ```python
   PROMPT_DRIVEN_COMMANDS: frozenset[str] = frozenset({
       "specify",
       "plan",
       "tasks",
       "tasks-outline",
       "tasks-packages",
       "checklist",
       "analyze",
       "research",
       "constitution",
   })

   CLI_DRIVEN_COMMANDS: frozenset[str] = frozenset({
       "implement",
       "review",
       "accept",
       "merge",
       "status",
       "dashboard",
       "tasks-finalize",
   })
   ```
3. If there is an existing `CONSUMER_SKILLS` (or equivalent) constant that lists all 16 commands, add an assertion:
   ```python
   assert PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS, \
       "Command classification sets must cover all consumer skills exactly"
   ```
   If no such constant exists, create it as the union of the two sets.
4. Export both frozensets in `__all__` if the module uses one.

**Files**:
- `src/specify_cli/shims/registry.py`

---

### T009 — Update generate_all_shims() to skip prompt-driven commands

**Purpose**: Make the shim generator only produce shim files for CLI-driven commands, resulting in 7 shim files instead of 16.

**Steps**:
1. Open `src/specify_cli/shims/generator.py`.
2. Import `CLI_DRIVEN_COMMANDS` from `registry.py`.
3. Locate the loop or list comprehension in `generate_all_shims()` that iterates over commands.
4. Add a filter so only `CLI_DRIVEN_COMMANDS` are processed:
   ```python
   from .registry import CLI_DRIVEN_COMMANDS

   def generate_all_shims(...):
       for command in CLI_DRIVEN_COMMANDS:  # was: all commands
           # existing shim generation logic
   ```
5. Do not change the shim template content — only which commands get shims generated.
6. Verify the function signature and return type remain compatible with callers (WP03's `init.py` will still call `generate_all_shims()`).

**Files**:
- `src/specify_cli/shims/generator.py`

---

### T010 — Update shim_dispatch() to return None for prompt-driven commands

**Purpose**: Prevent `shim_dispatch()` from failing when invoked for a prompt-driven command (e.g., when an agent happens to call `spec-kitty agent shim specify`). Prompt-driven commands are handled entirely by their full prompt files; the CLI shim pathway is a no-op for them.

**Steps**:
1. Open `src/specify_cli/shims/entrypoints.py`.
2. Import `PROMPT_DRIVEN_COMMANDS` from `registry.py`.
3. In `shim_dispatch()`, at the top of the function body (before any context resolution or handler lookup), add:
   ```python
   from .registry import PROMPT_DRIVEN_COMMANDS

   def shim_dispatch(command: str, ...) -> ...:
       if command in PROMPT_DRIVEN_COMMANDS:
           return None  # prompt-driven: full prompt file handles this, nothing to dispatch
       # existing CLI-driven dispatch logic follows
   ```
4. For CLI-driven commands, the existing dispatch logic (handler lookup, context resolution) continues unchanged.
5. Ensure the return type annotation accommodates `None` (add `| None` if needed).

**Files**:
- `src/specify_cli/shims/entrypoints.py`

---

### T011 — Tests for registry classification and generator output count

**Purpose**: Verify the classification invariants and the 7-shim output count.

**Steps**:
1. Create or update test file `tests/specify_cli/shims/test_registry.py` (if it doesn't exist, create it).
2. Write tests:

   **Test 1 — Classification coverage**:
   ```python
   def test_command_sets_cover_all_consumer_skills():
       from specify_cli.shims.registry import (
           PROMPT_DRIVEN_COMMANDS, CLI_DRIVEN_COMMANDS, CONSUMER_SKILLS
       )
       assert PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS
       assert PROMPT_DRIVEN_COMMANDS & CLI_DRIVEN_COMMANDS == frozenset()
   ```

   **Test 2 — Prompt-driven set contents**:
   ```python
   def test_prompt_driven_commands():
       from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
       for cmd in ["specify", "plan", "tasks", "checklist", "analyze", "research", "constitution"]:
           assert cmd in PROMPT_DRIVEN_COMMANDS
   ```

   **Test 3 — Generator output count**:
   ```python
   def test_generate_all_shims_produces_seven_files(tmp_path):
       from specify_cli.shims.generator import generate_all_shims
       generated = generate_all_shims(output_dir=tmp_path)  # adjust signature as needed
       assert len(list(tmp_path.glob("*.md"))) == 7
   ```

   **Test 4 — shim_dispatch returns None for prompt-driven**:
   ```python
   def test_shim_dispatch_returns_none_for_prompt_driven():
       from specify_cli.shims.entrypoints import shim_dispatch
       result = shim_dispatch("specify", ...)
       assert result is None
   ```

3. Run: `pytest tests/specify_cli/shims/ -v` and confirm all tests pass.

**Files**:
- `tests/specify_cli/shims/test_registry.py` (create or update)

---

## Integration Verification

After completing all subtasks:

1. Run `python -c "from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS, CLI_DRIVEN_COMMANDS; print(len(PROMPT_DRIVEN_COMMANDS), len(CLI_DRIVEN_COMMANDS))"` — should print `9 7`.
2. Run `pytest tests/specify_cli/shims/ -v` — all tests pass.
3. Run `mypy --strict src/specify_cli/shims/` — no errors.
4. Confirm `generate_all_shims()` invoked in isolation (without WP03 changes) still produces 7 files.
5. This WP does not touch `init.py` — that is WP03. Confirm no imports from `init.py` were added.

## Review Guidance

Reviewer should check:
- `registry.py` has both frozensets with exactly the right commands (9 prompt-driven, 7 CLI-driven).
- The invariant assertion `PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS` is present and correct.
- `generator.py` iterates only over `CLI_DRIVEN_COMMANDS` — no prompt-driven command names appear in shim generation paths.
- `entrypoints.py` returns `None` for prompt-driven commands at the top of `shim_dispatch()`, before any context resolution.
- Tests cover classification invariants and the 7-file output count.
- mypy --strict passes.
- No changes outside `src/specify_cli/shims/` (except the test file).

## Activity Log

- 2026-03-30T13:59:29Z — WP created (planned)
- 2026-03-30T14:23:02Z – coordinator – shell_pid=73918 – lane=doing – Started implementation via workflow command
- 2026-03-30T14:29:30Z – coordinator – shell_pid=73918 – lane=for_review – Registry split: PROMPT_DRIVEN_COMMANDS (9) and CLI_DRIVEN_COMMANDS (7) added to registry.py with invariant assertion. Generator produces 7 shims only. shim_dispatch() returns None for all 9 prompt-driven commands. 176 tests pass, mypy clean on shims package.
- 2026-03-30T14:30:21Z – coordinator – shell_pid=73918 – lane=approved – Review passed: registry split, generator 7 shims, 176 tests
