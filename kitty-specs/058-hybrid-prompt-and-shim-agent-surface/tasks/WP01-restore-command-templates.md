---
work_package_id: WP01
title: Restore Canonical Command Templates
dependencies: []
requirement_refs:
- C-004
- FR-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this feature were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: main
base_commit: 3e3c07c2d8f95539e1e5c2bbdb303ae2504e02bd
created_at: '2026-03-30T14:22:59.984598+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: 1
history:
- at: '2026-03-30T13:59:29Z'
  event: created
  actor: spec-kitty
  note: WP01 generated from tasks.md for feature 058-hybrid-prompt-and-shim-agent-surface
authoritative_surface: src/specify_cli/missions/software-dev/command-templates/
execution_mode: code_change
mission_id: 01KN2371WVZGV7TH7WMR2CN9Q4
owned_files:
- src/specify_cli/missions/software-dev/command-templates/**
wp_code: WP01
---

# WP01 — Restore Canonical Command Templates

## Branch Strategy

- **Base branch**: `main`
- **Feature branch**: `058-hybrid-prompt-and-shim-agent-surface-WP01`
- **Merge target**: `main`
- Branch from `main` before making any changes.
- This WP is independent — it can run in parallel with WP02.

## Objectives & Success Criteria

**Goal**: Create `src/specify_cli/missions/software-dev/command-templates/` with cleaned-up, generic prompt files for all 9 prompt-driven commands. Port today's applied fixes (project root checkout terminology, template path instructions, ownership metadata guidance, `--feature` requirement note) from `.claude/commands/` into canonical source files that will serve as the package-level source of truth.

**Success criteria**:
- All 9 files exist under `src/specify_cli/missions/software-dev/command-templates/`:
  `specify.md`, `plan.md`, `tasks.md`, `tasks-outline.md`, `tasks-packages.md`, `checklist.md`, `analyze.md`, `research.md`, `constitution.md`
- Every file is 50+ lines
- Zero references to `057-` feature slugs or any other specific feature slug
- Zero references to `/Users/robert/` or any absolute dev-repo path
- Zero instructions to read template files from `.kittify/missions/`
- All files use "project root checkout" not "planning repository"
- All files include a note: "In repos with multiple features, always pass `--feature <slug>` to every spec-kitty command"
- `tasks.md` includes ownership metadata guidance: `owned_files`, `authoritative_surface`, `execution_mode` requirements and validate-only hint
- No YAML frontmatter `---` blocks (the asset generator adds its own frontmatter during rendering)

## Context & Constraints

**Why this WP exists**: Feature 057 introduced thin shims for all commands, accidentally deleting the canonical prompt templates from the package source. The `.claude/commands/` files in this dev repo received several fixes (terminology corrections, template path removal, ownership guidance) and now need to be ported back into the canonical source location so the source → runtime → project chain is restored.

**Key rule — filename convention**: Files are named `specify.md` (not `spec-kitty.specify.md`). The `spec-kitty.` prefix is added by `generate_agent_assets()` during rendering.

**Key rule — no frontmatter**: Strip any `---` YAML frontmatter blocks from the source files. The asset generator writes its own frontmatter when deploying to agent directories.

**Key rule — generic content**: Every prompt must work in any consumer project. No feature slugs, no hardcoded paths, no dev-specific instructions.

**Source of truth for today's fixes**: The files in `.claude/commands/spec-kitty.*.md` in this dev repository (the spec-kitty source repo itself) have the latest applied fixes. Use them as the source to port from.

**Constraint**: Do not introduce any new Python dependencies. This WP is purely file creation/editing.

**Requirement refs**: FR-002, C-004

## Subtasks & Detailed Guidance

### T001 — Create command-templates directory

**Purpose**: Create the directory that will house all 9 canonical prompt templates.

**Steps**:
1. Create `src/specify_cli/missions/software-dev/command-templates/` if it does not exist.
2. Verify `src/specify_cli/missions/software-dev/` already exists (it should from prior mission work).
3. Add a `.gitkeep` only if the directory would otherwise be empty during initial creation; remove it once files are added.

**Files**:
- `src/specify_cli/missions/software-dev/command-templates/` (directory)

---

### T002 — Port and clean specify.md

**Purpose**: Create the canonical `specify.md` prompt from the current `.claude/commands/spec-kitty.specify.md`.

**Steps**:
1. Read `.claude/commands/spec-kitty.specify.md` from this dev repo.
2. Strip any YAML frontmatter (`---` block at the top).
3. Search for and remove all occurrences of `057-` or any specific feature slug used in examples.
4. Replace every occurrence of "planning repository" with "project root checkout".
5. Search for any instruction that tells the agent to read a template from `.kittify/missions/` — remove or replace with a note that the agent should NOT read template files from `.kittify/`, and should instead write content directly.
6. Ensure the file contains the `--feature` note.
7. Verify: no `/Users/robert/` paths, no hardcoded machine-specific paths.
8. Write to `src/specify_cli/missions/software-dev/command-templates/specify.md`.

**Files**:
- Source: `.claude/commands/spec-kitty.specify.md`
- Output: `src/specify_cli/missions/software-dev/command-templates/specify.md`

---

### T003 — Port and clean plan.md

**Purpose**: Create the canonical `plan.md` prompt.

**Steps**:
1. Read `.claude/commands/spec-kitty.plan.md`.
2. Apply the same cleaning steps as T002: strip frontmatter, remove 057 slugs, fix "planning repository" → "project root checkout", remove `.kittify/missions/` template read instructions, add `--feature` note.
3. Write to `src/specify_cli/missions/software-dev/command-templates/plan.md`.

**Files**:
- Source: `.claude/commands/spec-kitty.plan.md`
- Output: `src/specify_cli/missions/software-dev/command-templates/plan.md`

---

### T004 — Port and clean tasks.md (ownership metadata guidance required)

**Purpose**: Create the canonical `tasks.md` prompt, which must include WP ownership metadata guidance.

**Steps**:
1. Read `.claude/commands/spec-kitty.tasks.md`.
2. Apply standard cleaning: strip frontmatter, remove feature-specific slugs, fix terminology, remove `.kittify/missions/` template read instructions, add `--feature` note.
3. Verify the file contains (or add if missing) explicit guidance on WP ownership metadata:
   - The `owned_files` field must list specific files/globs owned by each WP (non-overlapping across WPs in the same feature).
   - The `authoritative_surface` field must identify the canonical output location.
   - The `execution_mode` field must be set correctly (`code_change`, `planning_artifact`, etc.).
   - Include a validate-only hint: agents working on a WP must not modify files outside their `owned_files` list.
4. Write to `src/specify_cli/missions/software-dev/command-templates/tasks.md`.

**Files**:
- Source: `.claude/commands/spec-kitty.tasks.md`
- Output: `src/specify_cli/missions/software-dev/command-templates/tasks.md`

---

### T005 — Port and clean tasks-outline.md and tasks-packages.md

**Purpose**: Create canonical prompts for the two tasks sub-workflow commands.

**Steps**:
1. Read `.claude/commands/spec-kitty.tasks-outline.md` and `.claude/commands/spec-kitty.tasks-packages.md`.
2. For each file: strip frontmatter, remove feature slugs, fix "planning repository" terminology, remove `.kittify/missions/` template read instructions, add `--feature` note.
3. Write to:
   - `src/specify_cli/missions/software-dev/command-templates/tasks-outline.md`
   - `src/specify_cli/missions/software-dev/command-templates/tasks-packages.md`

**Files**:
- Sources: `.claude/commands/spec-kitty.tasks-outline.md`, `.claude/commands/spec-kitty.tasks-packages.md`
- Outputs: `src/specify_cli/missions/software-dev/command-templates/tasks-outline.md`, `tasks-packages.md`

---

### T006 — Port and clean checklist.md, analyze.md, research.md, constitution.md

**Purpose**: Create the four remaining canonical prompt templates.

**Steps**:
1. Read each of:
   - `.claude/commands/spec-kitty.checklist.md`
   - `.claude/commands/spec-kitty.analyze.md`
   - `.claude/commands/spec-kitty.research.md`
   - `.claude/commands/spec-kitty.constitution.md`
2. For each file: strip frontmatter, remove feature slugs, fix "planning repository" terminology, remove `.kittify/missions/` template read instructions, add `--feature` note.
3. Write each to `src/specify_cli/missions/software-dev/command-templates/<name>.md`.

**Files**:
- Sources: `.claude/commands/spec-kitty.checklist.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`, `spec-kitty.constitution.md`
- Outputs: `src/specify_cli/missions/software-dev/command-templates/checklist.md`, `analyze.md`, `research.md`, `constitution.md`

---

### T007 — Verify all 9 prompts are clean

**Purpose**: Run a systematic verification pass across all 9 files to confirm they meet the quality bar.

**Steps**:
1. For each of the 9 files, verify:
   - File exists and is 50+ lines.
   - No `---` YAML frontmatter at the top.
   - Zero occurrences of `057-` or other specific feature slugs.
   - Zero occurrences of `/Users/robert/` or other machine-specific paths.
   - Zero occurrences of `.kittify/missions/` in "read from" instructions.
   - Zero occurrences of "planning repository".
   - At least one occurrence of "project root checkout".
   - Contains `--feature` guidance.
2. `tasks.md` additionally: contains `owned_files`, `authoritative_surface`, `execution_mode`.
3. Document the verification result as a comment in the commit message.

**Files**: All 9 files in `src/specify_cli/missions/software-dev/command-templates/`

---

## Integration Verification

After completing all subtasks:

1. Confirm the directory structure:
   ```
   src/specify_cli/missions/software-dev/command-templates/
   ├── analyze.md
   ├── checklist.md
   ├── constitution.md
   ├── plan.md
   ├── research.md
   ├── specify.md
   ├── tasks-outline.md
   ├── tasks-packages.md
   └── tasks.md
   ```
2. Run a grep to confirm zero `057-` occurrences across all 9 files.
3. Run a grep to confirm zero "planning repository" occurrences.
4. Verify the `generate_agent_assets()` function in `src/specify_cli/template/asset_generator.py` accepts a `command_templates_dir` and would find these files via the 4-tier resolution chain.
5. This WP does not run tests — WP06 handles testing. However, confirm Python can `import specify_cli` cleanly (no import errors from the file additions, since these are markdown not Python).

## Review Guidance

Reviewer should check:
- All 9 files exist and are non-trivially large (50+ lines each).
- Absence of feature-specific content: no `057-` slugs, no absolute paths, no dev-repo references.
- Presence of canonical fixes: "project root checkout", `--feature` guidance, no `.kittify/missions/` read instructions.
- `tasks.md` has ownership metadata guidance.
- No YAML frontmatter in any file.
- Files are in `src/` (canonical source), not in `.claude/commands/` or other agent directories.

## Activity Log

- 2026-03-30T13:59:29Z — WP created (planned)
- 2026-03-30T14:23:00Z – coordinator – shell_pid=73868 – lane=doing – Started implementation via workflow command
- 2026-03-30T14:36:02Z – coordinator – shell_pid=73868 – lane=for_review – 9 prompt-driven command templates restored and cleaned
- 2026-03-30T14:36:35Z – coordinator – shell_pid=73868 – lane=approved – Review passed: 9 command templates restored and cleaned
