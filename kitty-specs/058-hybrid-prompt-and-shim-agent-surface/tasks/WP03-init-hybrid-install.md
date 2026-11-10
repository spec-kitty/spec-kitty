---
work_package_id: WP03
title: Update Init for Hybrid Install
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-010
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this feature were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: 058-hybrid-prompt-and-shim-agent-surface-WP01
base_commit: 64746d186e96e89ee9b42eb927bab6f822375c4c
created_at: '2026-03-30T14:36:45.658790+00:00'
subtasks:
- T012
- T013
- T014
- T015
phase: 1
history:
- at: '2026-03-30T13:59:29Z'
  event: created
  actor: spec-kitty
  note: WP03 generated from tasks.md for feature 058-hybrid-prompt-and-shim-agent-surface
authoritative_surface: src/specify_cli/cli/commands/init.py
execution_mode: code_change
mission_id: 01KN2371WVZGV7TH7WMR2CN9Q4
owned_files:
- src/specify_cli/cli/commands/init.py
- src/specify_cli/runtime/**
wp_code: WP03
---

# WP03 — Update Init for Hybrid Install

## Branch Strategy

- **Base branch**: `main`
- **Feature branch**: `058-hybrid-prompt-and-shim-agent-surface-WP03`
- **Merge target**: `main`
- Branch from `main` before making changes. Then merge in WP01 and WP02 branches (or rebase on them once they complete), since both are required.
- This is Wave 2 — starts only after WP01 and WP02 are merged.

## Objectives & Success Criteria

**Goal**: Update `spec-kitty init` so that it installs the correct file type for each command: full prompts for prompt-driven commands (via `generate_agent_assets()` using the restored command-templates directory) and thin shims for CLI-driven commands only (via `generate_all_shims()`). Also verify the `ensure_runtime()` bootstrap correctly deploys the restored templates to `~/.kittify/missions/software-dev/command-templates/` so the 4-tier resolution chain can find them.

**Success criteria**:
- After `spec-kitty init` in a fresh temp directory, `.claude/commands/spec-kitty.specify.md` contains 100+ lines (full prompt, not a shim).
- After `spec-kitty init` in a fresh temp directory, `.claude/commands/spec-kitty.implement.md` contains fewer than 5 lines (thin shim).
- The 4-tier resolver `_resolve_mission_command_templates_dir()` finds the files from `src/specify_cli/missions/software-dev/command-templates/` (via the global runtime at `~/.kittify/missions/`).
- `ensure_runtime()` in `runtime/bootstrap.py` copies the restored templates to `~/.kittify/missions/software-dev/command-templates/` on first run or version change.
- mypy --strict passes on all modified files.

## Context & Constraints

**Why this WP exists**: Before WP01/WP02, `init.py` called only `generate_all_shims()` which produced thin shims for all 16 commands (the broken state). This WP changes `init.py` to call both:
1. `generate_agent_assets()` for the 9 prompt-driven commands — reads from the canonical source via the 4-tier resolution chain.
2. `generate_all_shims()` for the 7 CLI-driven commands — produces thin shims as before (but now only 7 files, after WP02).

**4-Tier resolution chain** (for `_resolve_mission_command_templates_dir()`):
1. `<project>/.kittify/overrides/missions/software-dev/command-templates/` — project-level overrides
2. `<project>/.kittify/legacy/missions/software-dev/command-templates/` — legacy fallback
3. `~/.kittify/missions/software-dev/command-templates/` — global runtime (deployed by `ensure_runtime()`)
4. Package source: `src/specify_cli/missions/software-dev/command-templates/` — lowest priority fallback

**`ensure_runtime()` contract**: This function already exists in `src/specify_cli/runtime/bootstrap.py` and copies the package's `missions/` tree to `~/.kittify/missions/` on every CLI startup when the version changes. Since `src/specify_cli/missions/software-dev/command-templates/` is being restored by WP01, `ensure_runtime()` should automatically deploy those files to `~/.kittify/missions/`. Verify this is the case — no code changes should be required in `bootstrap.py` unless the glob pattern excludes the new directory.

**`generate_agent_assets()` contract**: Located in `src/specify_cli/template/asset_generator.py`. Accepts a `command_templates_dir` parameter pointing to the directory with `.md` files. For each `.md` file, it renders an agent-specific version and writes it to the appropriate agent directory (e.g., `.claude/commands/spec-kitty.<name>.md`). WP03 must call this for prompt-driven commands only.

**Constraint**: Do not modify `src/specify_cli/runtime/bootstrap.py` unless `ensure_runtime()` has a bug that prevents it from copying `command-templates/`. Report any such bug but do not change behavior beyond what is needed for the templates to deploy.

**Constraint**: Do not modify `src/specify_cli/template/asset_generator.py` — it is already functional and not owned by this WP.

**Requirement refs**: FR-003, FR-004, FR-005

## Subtasks & Detailed Guidance

### T012 — Update init.py to call generate_agent_assets() for prompt-driven commands

**Purpose**: Wire the hybrid install logic into `spec-kitty init` so that each command gets the right file type installed.

**Steps**:
1. Open `src/specify_cli/cli/commands/init.py`.
2. Locate the section that calls `generate_all_shims()` (or equivalent).
3. Before or after that call, add a call to `generate_agent_assets()` for prompt-driven commands:
   ```python
   from specify_cli.template.asset_generator import generate_agent_assets
   from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

   # Install full prompts for prompt-driven commands
   command_templates_dir = _resolve_mission_command_templates_dir(project_path)
   generate_agent_assets(
       command_templates_dir=command_templates_dir,
       commands=PROMPT_DRIVEN_COMMANDS,  # only prompt-driven
       project_path=project_path,
       agent_dirs=agent_dirs,  # configured agents
   )

   # Install thin shims for CLI-driven commands (WP02 makes this produce 7 files)
   generate_all_shims(project_path=project_path, agent_dirs=agent_dirs)
   ```
4. Adjust the call signatures to match the actual function signatures in `asset_generator.py` and `generator.py` (read both files first).
5. Ensure error handling is consistent with existing init error handling (no silent failures, no fallbacks).

**Files**:
- `src/specify_cli/cli/commands/init.py`

---

### T013 — Verify 4-tier resolution chain resolves restored templates

**Purpose**: Confirm that `_resolve_mission_command_templates_dir()` (or equivalent resolver) correctly finds the restored templates via the 4-tier chain.

**Steps**:
1. Locate `_resolve_mission_command_templates_dir()` — it may be in `init.py`, `runtime/bootstrap.py`, or `template/asset_generator.py`.
2. Trace the resolution logic: does it check the global runtime (`~/.kittify/missions/software-dev/command-templates/`) as tier 3? Does it fall back to the package source as tier 4?
3. If the resolver only checks project-level paths and the global runtime but not the package source, add the package source as the final fallback:
   ```python
   from importlib.resources import files as pkg_files

   package_templates = pkg_files("specify_cli") / "missions" / "software-dev" / "command-templates"
   ```
4. Write a brief inline comment in the resolver documenting the 4-tier order.
5. Do NOT change the precedence order — overrides always win, package is always last.

**Files**:
- Whichever file contains `_resolve_mission_command_templates_dir()` (read to locate it first)

---

### T014 — Ensure ensure_runtime() deploys new command-templates to ~/.kittify/

**Purpose**: Verify (and fix if broken) that `ensure_runtime()` copies `src/specify_cli/missions/software-dev/command-templates/` to `~/.kittify/missions/software-dev/command-templates/`.

**Steps**:
1. Read `src/specify_cli/runtime/bootstrap.py`.
2. Find the section that copies `missions/` from the package to `~/.kittify/missions/`.
3. Confirm the copy uses a recursive glob or `shutil.copytree` that includes `command-templates/` subdirectories.
4. If the copy logic uses an explicit list of subdirectories that excludes `command-templates/`, add it.
5. If `command-templates/` is already included implicitly (recursive copy of `missions/`), document this finding as a comment in the commit message: "ensure_runtime() already handles command-templates/ via recursive copy — no change needed".
6. If a code fix is required, keep it minimal: only add `command-templates/` to the copy scope without refactoring other bootstrap logic.

**Files**:
- `src/specify_cli/runtime/bootstrap.py` (read-only verification; modify only if a bug is found)

---

### T015 — Integration test: spec-kitty init in temp dir produces hybrid output

**Purpose**: Verify end-to-end that `spec-kitty init` in an isolated temp directory installs full prompts for prompt-driven commands and thin shims for CLI-driven commands.

**Steps**:
1. Create `tests/specify_cli/cli/commands/test_init_hybrid.py` (this file is owned by WP06, but the integration test content is designed here — WP06 will finalize it).
2. Draft the test:
   ```python
   def test_init_installs_hybrid_commands(tmp_path):
       """After init, prompt-driven commands get full prompts, CLI-driven get thin shims."""
       from specify_cli.cli.commands.init import run_init  # adjust to actual entrypoint

       run_init(project_path=tmp_path, agents=["claude"])

       claude_dir = tmp_path / ".claude" / "commands"

       # Prompt-driven: must be full prompt (100+ lines)
       specify_file = claude_dir / "spec-kitty.specify.md"
       assert specify_file.exists()
       lines = specify_file.read_text().splitlines()
       assert len(lines) >= 100, f"specify.md too short: {len(lines)} lines"

       # CLI-driven: must be thin shim (<5 lines)
       implement_file = claude_dir / "spec-kitty.implement.md"
       assert implement_file.exists()
       lines = implement_file.read_text().splitlines()
       assert len(lines) < 5, f"implement.md too long: {len(lines)} lines"
   ```
3. Run the test locally: `pytest tests/specify_cli/cli/commands/test_init_hybrid.py -v`.
4. If the test needs mocking of `ensure_runtime()` (to avoid side effects on `~/.kittify/`), add appropriate fixtures.

**Files**:
- `tests/specify_cli/cli/commands/test_init_hybrid.py` (note: this file is listed in WP06's `owned_files` — coordinate with WP06 if both WPs are running; WP03 writes the initial draft, WP06 finalizes)

---

## Integration Verification

After completing all subtasks:

1. Run `spec-kitty init` in a temp directory (or invoke the init function in a test):
   - Check `.claude/commands/spec-kitty.specify.md` — must be 100+ lines.
   - Check `.claude/commands/spec-kitty.plan.md` — must be 100+ lines.
   - Check `.claude/commands/spec-kitty.implement.md` — must be fewer than 5 lines.
   - Check `.claude/commands/spec-kitty.review.md` — must be fewer than 5 lines.
2. Confirm no Python import errors: `python -c "from specify_cli.cli.commands.init import app"`.
3. Run `mypy --strict src/specify_cli/cli/commands/init.py src/specify_cli/runtime/bootstrap.py`.
4. Run `pytest tests/specify_cli/cli/commands/test_init_hybrid.py -v`.
5. Confirm the total number of files installed for a single-agent (claude) init:
   - 9 files from `generate_agent_assets()` (one per prompt-driven command)
   - 7 files from `generate_all_shims()` (one per CLI-driven command)
   - Total: 16 files in `.claude/commands/`

## Review Guidance

Reviewer should check:
- `init.py` calls both `generate_agent_assets()` (for 9 prompt-driven) and `generate_all_shims()` (for 7 CLI-driven) — no commands are skipped and no commands are doubled.
- The 4-tier resolution chain is correct and documented.
- `ensure_runtime()` is confirmed to deploy `command-templates/` (either via existing recursive copy or an explicit fix).
- Integration test passes in isolation (not dependent on dev-repo state).
- No hardcoded paths in `init.py`.
- mypy --strict passes.

## Activity Log

- 2026-03-30T13:59:29Z — WP created (planned)
- 2026-03-30T14:36:45Z – coordinator – shell_pid=77070 – lane=doing – Started implementation via workflow command
- 2026-03-30T14:46:45Z – coordinator – shell_pid=77070 – lane=for_review – Hybrid init complete — full prompts + thin shims. 9 integration tests pass. ensure_runtime() confirmed to deploy command-templates/ via recursive copy.
- 2026-03-30T14:47:25Z – coordinator – shell_pid=77070 – lane=approved – Review passed: hybrid init, 4-tier resolution, 198 tests
