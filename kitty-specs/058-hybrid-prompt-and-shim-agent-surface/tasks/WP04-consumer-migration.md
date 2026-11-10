---
work_package_id: WP04
title: Migration for Consumer Projects
dependencies:
- WP03
requirement_refs:
- FR-008
- FR-009
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this feature were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: 058-hybrid-prompt-and-shim-agent-surface-WP03
base_commit: 0ddd9c53d82b584ffc6d0659059776a9547680f2
created_at: '2026-03-30T14:47:36.901925+00:00'
subtasks:
- T016
- T017
- T018
phase: 1
history:
- at: '2026-03-30T13:59:29Z'
  event: created
  actor: spec-kitty
  note: WP04 generated from tasks.md for feature 058-hybrid-prompt-and-shim-agent-surface
authoritative_surface: src/specify_cli/upgrade/migrations/
execution_mode: code_change
mission_id: 01KN2371WVZGV7TH7WMR2CN9Q4
owned_files:
- src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py
wp_code: WP04
---

# WP04 — Migration for Consumer Projects

## Branch Strategy

- **Base branch**: `main`
- **Feature branch**: `058-hybrid-prompt-and-shim-agent-surface-WP04`
- **Merge target**: `main`
- Branch from `main` and merge in (or rebase on) the WP03 branch, since WP04 depends on init being functional.
- This is Wave 3 — starts only after WP03 is merged.

## Objectives & Success Criteria

**Goal**: Write a spec-kitty upgrade migration (`m_2_1_3_restore_prompt_commands.py`) that detects thin shims for prompt-driven commands in existing consumer projects and replaces them with full prompts sourced from the global runtime. CLI-driven shims are left untouched. The migration must be idempotent.

**Success criteria**:
- `m_2_1_3_restore_prompt_commands.py` exists in `src/specify_cli/upgrade/migrations/`.
- Migration has `target_version = "2.1.3"` and is registered in the migration registry.
- Detection logic: a file is a thin shim if it is fewer than 10 lines AND contains the string `"spec-kitty agent shim"`.
- After running migration on a project with 16 thin shims, exactly 9 prompt-driven command files are replaced with full prompts (100+ lines) and exactly 7 CLI-driven command files remain as thin shims.
- Running the migration a second time (idempotency check) produces zero changes.
- Migration uses `get_agent_dirs_for_project()` to respect agent configuration (only processes configured agents, does not recreate deleted agent directories).
- mypy --strict passes on the new migration file.

## Context & Constraints

**Why this WP exists**: Existing consumer projects (spec-kitty-saas, spec-kitty-tracker, spec-kitty-planning) all have thin shims for all 16 commands from the feature 057 deployment. Running `spec-kitty upgrade` must replace the prompt-driven thin shims with full prompts from the global runtime, restoring working slash commands without requiring a fresh `spec-kitty init`.

**Detection heuristic**:
- File line count < 10 AND file contains `"spec-kitty agent shim"` → it is a thin shim to replace.
- Any file that doesn't match this heuristic is left untouched (it may be a project override or already a full prompt).

**Prompt source**: Read full prompts from `~/.kittify/missions/software-dev/command-templates/` (the global runtime, deployed by `ensure_runtime()`). Render through `generate_agent_assets()` for proper agent-specific formatting (adds agent-specific frontmatter, adjusts command invocation syntax, etc.).

**Migration registration**: Locate the migration registry (likely in `src/specify_cli/upgrade/registry.py` or `src/specify_cli/upgrade/__init__.py`) and register the new migration there. The `target_version` must be `"2.1.3"`.

**Agent-awareness**: Use `get_agent_dirs_for_project()` from `m_0_9_1_complete_lane_migration.py`. This returns only the agent directories that are configured in `.kittify/config.yaml`. Do not recreate agent directories that have been deleted. Skip non-existent agent directories with `continue`.

**Potential conflict with m_2_1_3_fix_planning_repository_terminology**: There may already be a migration at the 2.1.3 version slot. Read the existing migrations directory first. If a conflict exists, name the new migration `m_2_1_3_restore_prompt_commands.py` and ensure the version bump logic handles running multiple migrations at the same target version, OR use a minor subversion suffix if the registry requires unique versions.

**Constraint**: Do not modify any other migration files. Do not change behavior for CLI-driven commands.

**Requirement refs**: FR-008, FR-009

## Subtasks & Detailed Guidance

### T016 — Write m_2_1_3_restore_prompt_commands.py

**Purpose**: The core migration logic that replaces thin prompt-driven shims with full prompts.

**Steps**:
1. Read existing migration files in `src/specify_cli/upgrade/migrations/` to understand the migration class structure (look at 2-3 recent migrations for the pattern).
2. Create `src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py` with this structure:

   ```python
   """Migration 2.1.3: Replace thin shims for prompt-driven commands with full prompts."""
   from pathlib import Path
   from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project
   from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
   from specify_cli.template.asset_generator import generate_agent_assets
   from specify_cli.runtime.bootstrap import get_runtime_command_templates_dir

   TARGET_VERSION = "2.1.3"
   SHIM_MARKER = "spec-kitty agent shim"
   SHIM_LINE_THRESHOLD = 10


   def _is_thin_shim(file_path: Path) -> bool:
       """Return True if file looks like a thin shim generated by WP057."""
       try:
           content = file_path.read_text(encoding="utf-8")
           lines = [l for l in content.splitlines() if l.strip()]
           return len(lines) < SHIM_LINE_THRESHOLD and SHIM_MARKER in content
       except OSError:
           return False


   class Migration:
       target_version = TARGET_VERSION
       description = "Replace thin shims for prompt-driven commands with full prompts"

       def apply(self, project_path: Path, dry_run: bool = False) -> list[str]:
           changes: list[str] = []
           command_templates_dir = get_runtime_command_templates_dir()
           agent_dirs = get_agent_dirs_for_project(project_path)

           for agent_root, subdir in agent_dirs:
               agent_dir = project_path / agent_root / subdir
               if not agent_dir.exists():
                   continue

               for command in PROMPT_DRIVEN_COMMANDS:
                   # Conventional filename: spec-kitty.<command>.md
                   shim_file = agent_dir / f"spec-kitty.{command}.md"
                   if not shim_file.exists():
                       continue
                   if not _is_thin_shim(shim_file):
                       continue  # Already a full prompt or custom override — leave it

                   if not dry_run:
                       generate_agent_assets(
                           command_templates_dir=command_templates_dir,
                           commands={command},
                           project_path=project_path,
                           agent_dirs=[(agent_root, subdir)],
                       )
                   changes.append(str(shim_file.relative_to(project_path)))

           return changes
   ```

3. Adjust the import paths and function signatures to match the actual codebase (read the files before writing).
4. Register the migration in the migration registry.

**Files**:
- `src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py` (create)
- Migration registry file (update to include new migration)

---

### T017 — Ensure migration is idempotent

**Purpose**: Verify that running the migration twice produces the same result as running it once (no double-replacement, no errors on already-full prompts).

**Steps**:
1. The idempotency is built into the `_is_thin_shim()` check: after the first run, the file is a full prompt (100+ lines), so `_is_thin_shim()` returns `False` on the second run and the file is skipped.
2. Add a docstring comment to `apply()` stating: "Idempotent: files that are already full prompts (≥10 lines or lacking shim marker) are skipped."
3. In the test (T018), run `apply()` twice and assert the second invocation returns an empty `changes` list.

**Files**:
- `src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py` (docstring update only)

---

### T018 — Test migration with mock consumer project

**Purpose**: Validate the migration against a realistic scenario: a project with 16 thin shims gets upgraded to hybrid output.

**Steps**:
1. Create `tests/specify_cli/upgrade/test_m_2_1_3_restore_prompt_commands.py`.
2. Write the following tests:

   **Test 1 — Replaces 9 prompt-driven shims, leaves 7 CLI-driven intact**:
   ```python
   def test_migration_replaces_prompt_driven_shims(tmp_path, monkeypatch):
       # Setup: create .claude/commands/ with 16 thin shims
       claude_dir = tmp_path / ".claude" / "commands"
       claude_dir.mkdir(parents=True)

       all_commands = [
           "specify", "plan", "tasks", "tasks-outline", "tasks-packages",
           "checklist", "analyze", "research", "constitution",
           "implement", "review", "accept", "merge", "status", "dashboard", "tasks-finalize"
       ]
       for cmd in all_commands:
           (claude_dir / f"spec-kitty.{cmd}.md").write_text(
               "Run: spec-kitty agent shim {cmd}\n"
           )

       # Monkeypatch generate_agent_assets to write a fake full prompt
       def fake_generate(command_templates_dir, commands, project_path, agent_dirs):
           for agent_root, subdir in agent_dirs:
               d = project_path / agent_root / subdir
               for cmd in commands:
                   (d / f"spec-kitty.{cmd}.md").write_text("# Full prompt\n" * 50)

       monkeypatch.setattr("specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands.generate_agent_assets", fake_generate)

       from specify_cli.upgrade.migrations.m_2_1_3_restore_prompt_commands import Migration
       migration = Migration()
       changes = migration.apply(tmp_path)

       assert len(changes) == 9  # 9 prompt-driven replaced
       for cmd in ["specify", "plan", "tasks", "checklist"]:
           f = claude_dir / f"spec-kitty.{cmd}.md"
           assert len(f.read_text().splitlines()) >= 50

       for cmd in ["implement", "review", "accept"]:
           f = claude_dir / f"spec-kitty.{cmd}.md"
           assert "spec-kitty agent shim" in f.read_text()  # unchanged
   ```

   **Test 2 — Idempotency**:
   ```python
   def test_migration_is_idempotent(tmp_path, monkeypatch):
       # ... (run apply() twice, assert second run returns empty changes list)
   ```

   **Test 3 — dry_run produces no file changes**:
   ```python
   def test_migration_dry_run_makes_no_changes(tmp_path, monkeypatch):
       # ... (run apply(dry_run=True), assert files unchanged but changes list populated)
   ```

3. Run: `pytest tests/specify_cli/upgrade/test_m_2_1_3_restore_prompt_commands.py -v`.

**Files**:
- `tests/specify_cli/upgrade/test_m_2_1_3_restore_prompt_commands.py` (create)

---

## Integration Verification

After completing all subtasks:

1. Run `pytest tests/specify_cli/upgrade/test_m_2_1_3_restore_prompt_commands.py -v` — all tests pass.
2. Run `mypy --strict src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py`.
3. Verify the migration is registered: `python -c "from specify_cli.upgrade.registry import get_migrations; print([m.target_version for m in get_migrations()])"` — should include `"2.1.3"`.
4. Confirm the migration class has `target_version = "2.1.3"` and `description` attributes.
5. Dry-run the migration against this dev repo: `spec-kitty upgrade --dry-run` — should report changes to restore prompt-driven commands (or report no changes if the dev repo already has full prompts after WP01).

## Review Guidance

Reviewer should check:
- Detection heuristic (`_is_thin_shim`) is tight: line count < 10 AND contains shim marker. Not just one condition.
- Migration only processes `PROMPT_DRIVEN_COMMANDS` — never touches CLI-driven shims.
- `get_agent_dirs_for_project()` is used (not a hardcoded `AGENT_DIRS` list).
- Non-existent agent directories are skipped with `continue` (not recreated).
- Migration is registered in the registry with the correct version.
- Tests cover: normal replacement, idempotency, dry-run, and already-full-prompt passthrough.
- mypy --strict passes.
- No changes outside `src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py` and the registry file.

## Activity Log

- 2026-03-30T13:59:29Z — WP created (planned)
- 2026-03-30T14:47:37Z – coordinator – shell_pid=80689 – lane=doing – Started implementation via workflow command
- 2026-03-30T14:56:58Z – coordinator – shell_pid=80689 – lane=for_review – Migration complete: m_2_1_3_restore_prompt_commands.py detects thin shims for prompt-driven commands and replaces with full prompts. Idempotent, config-aware, 19 tests all passing.
- 2026-03-30T14:57:45Z – coordinator – shell_pid=80689 – lane=approved – Review passed: migration with thin-shim detection, 19 tests, idempotent
