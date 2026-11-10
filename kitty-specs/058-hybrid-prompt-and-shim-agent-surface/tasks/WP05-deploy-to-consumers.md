---
work_package_id: WP05
title: Deploy to Consumer Projects
dependencies:
- WP04
requirement_refs:
- FR-008
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this feature were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: 058-hybrid-prompt-and-shim-agent-surface-WP04
base_commit: 173650c3cd93aad43bbe352d6ae806cdff500746
created_at: '2026-03-30T15:24:44.591926+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: 1
history:
- at: '2026-03-30T13:59:29Z'
  event: created
  actor: spec-kitty
  note: WP05 generated from tasks.md for feature 058-hybrid-prompt-and-shim-agent-surface
authoritative_surface: kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP05-deploy-to-consumers.md
execution_mode: planning_artifact
mission_id: 01KN2371WVZGV7TH7WMR2CN9Q4
owned_files:
- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP05-deploy-to-consumers.md
wp_code: WP05
---

# WP05 — Deploy to Consumer Projects

## Branch Strategy

- **No feature branch required** — this is an operational deployment WP, not a code change.
- Work is done directly in each consumer project's repository.
- This is Wave 4 — starts only after WP04 is merged to `main` in the spec-kitty source repo.
- The implementing agent must have filesystem access to the consumer project repositories (spec-kitty-tracker, spec-kitty-saas, spec-kitty-planning).

## Objectives & Success Criteria

**Goal**: Run `spec-kitty upgrade` in the three known broken consumer projects to restore working slash commands. Prompt-driven command files should be replaced with full prompts. CLI-driven command files should remain as thin shims.

**Success criteria**:
- In each of spec-kitty-tracker, spec-kitty-saas, spec-kitty-planning:
  - `.claude/commands/spec-kitty.specify.md` contains 100+ lines of workflow instructions (full prompt).
  - `.claude/commands/spec-kitty.plan.md` contains 100+ lines.
  - `.claude/commands/spec-kitty.tasks.md` contains 100+ lines with ownership metadata guidance.
  - `.claude/commands/spec-kitty.implement.md` contains fewer than 5 lines (thin shim, unchanged).
  - `.claude/commands/spec-kitty.review.md` contains fewer than 5 lines (thin shim, unchanged).
- `spec-kitty upgrade` exits with code 0 in all three projects.
- All other agent directories configured in each project are also upgraded (not just `.claude/commands/`).

## Context & Constraints

**Why this WP exists**: Feature 057 deployed thin shims for all 16 commands to these three consumer projects. They are currently broken — agents cannot run planning workflows because the command files contain 3-line shims instead of full prompts. The WP04 migration, once released, will fix this via `spec-kitty upgrade`.

**Prerequisite**: The spec-kitty package with WP01–WP04 changes must be installed in the environment where `spec-kitty upgrade` runs. If running from local dev, `pip install -e .` from the spec-kitty source repo. If running from PyPI, the new version must be released first.

**Version lock note**: Delete `~/.kittify/cache/version.lock` before running upgrades. This file caches the last-seen version and prevents `ensure_runtime()` from re-copying templates when the version string hasn't changed. Deleting it forces a full runtime refresh to deploy the new command-templates.

**Existing migration conflict**: There may already be a `m_2_1_3_fix_planning_repository_terminology` migration that ran in these projects. The new `m_2_1_3_restore_prompt_commands` migration must either:
- Have a higher effective sort key than the terminology migration so it runs after, OR
- Be idempotent enough that re-running it on already-terminology-fixed files still works correctly.
  Check the migration registry sort order. If the terminology migration already replaced prompts, the restore migration may detect them as "already full prompts" (≥10 lines) and skip them — which is fine IF the terminology was already fixed. Verify by checking the actual file content after upgrade.

**Operational note**: This WP involves running shell commands in separate repositories. It does not produce Python code changes. The implementing agent must have `spec-kitty` CLI available and filesystem access to all three consumer project paths.

**Requirement ref**: FR-008

## Subtasks & Detailed Guidance

### T019 — Delete ~/.kittify/cache/version.lock to force runtime refresh

**Purpose**: Force `ensure_runtime()` to re-copy the mission templates from the installed package to `~/.kittify/missions/` so the new command-templates are available for the migration to source from.

**Steps**:
1. Check if `~/.kittify/cache/version.lock` exists:
   ```bash
   ls -la ~/.kittify/cache/version.lock
   ```
2. If it exists, delete it:
   ```bash
   rm ~/.kittify/cache/version.lock
   ```
3. Run `spec-kitty --version` (or any spec-kitty command) to trigger `ensure_runtime()` and populate `~/.kittify/missions/software-dev/command-templates/`.
4. Verify the templates are deployed:
   ```bash
   ls ~/.kittify/missions/software-dev/command-templates/
   # Should show: analyze.md checklist.md constitution.md plan.md research.md specify.md tasks-outline.md tasks-packages.md tasks.md
   ```
5. Verify one template is a full prompt (not a shim):
   ```bash
   wc -l ~/.kittify/missions/software-dev/command-templates/specify.md
   # Should be 100+ lines
   ```

**Files**: None (shell operations on `~/.kittify/`)

---

### T020 — Run spec-kitty upgrade in spec-kitty-tracker

**Purpose**: Apply the migration to spec-kitty-tracker, restoring full prompts for prompt-driven commands.

**Steps**:
1. Navigate to the spec-kitty-tracker repository.
2. Verify the current broken state (thin shims):
   ```bash
   wc -l .claude/commands/spec-kitty.specify.md
   # Should be ~3 lines (broken thin shim)
   ```
3. Run dry-run first to preview changes:
   ```bash
   spec-kitty upgrade --dry-run
   ```
   Confirm the migration lists 9 prompt-driven files as targets for replacement.
4. Run the actual upgrade:
   ```bash
   spec-kitty upgrade
   ```
5. Verify the output shows the migration was applied and changes were made.
6. Commit the changes in spec-kitty-tracker:
   ```bash
   git add .claude/ .codex/ .opencode/  # (and any other configured agent dirs)
   git commit -m "chore: upgrade spec-kitty — restore full prompts for planning commands"
   ```

**Files**: `.claude/commands/spec-kitty.*.md` and equivalent in other configured agent dirs within the spec-kitty-tracker repo.

---

### T021 — Run spec-kitty upgrade in spec-kitty-saas

**Purpose**: Apply the migration to spec-kitty-saas.

**Steps**:
1. Navigate to the spec-kitty-saas repository.
2. Check current state: `wc -l .claude/commands/spec-kitty.specify.md` — expect ~3 lines.
3. Run dry-run: `spec-kitty upgrade --dry-run`.
4. Run upgrade: `spec-kitty upgrade`.
5. Commit the changes:
   ```bash
   git add .claude/ .codex/ .opencode/  # (all configured agent dirs)
   git commit -m "chore: upgrade spec-kitty — restore full prompts for planning commands"
   ```

**Files**: Agent command directories within the spec-kitty-saas repo.

---

### T022 — Run spec-kitty upgrade in spec-kitty-planning

**Purpose**: Apply the migration to spec-kitty-planning.

**Steps**:
1. Navigate to the spec-kitty-planning repository.
2. Check current state: `wc -l .claude/commands/spec-kitty.specify.md` — expect ~3 lines.
3. Run dry-run: `spec-kitty upgrade --dry-run`.
4. Note: spec-kitty-planning may have the `m_2_1_3_fix_planning_repository_terminology` migration already applied. If the files are already full prompts from that migration, the new migration will skip them. Verify after upgrade.
5. Run upgrade: `spec-kitty upgrade`.
6. Commit the changes:
   ```bash
   git add .claude/ .codex/ .opencode/  # (all configured agent dirs)
   git commit -m "chore: upgrade spec-kitty — restore full prompts for planning commands"
   ```

**Files**: Agent command directories within the spec-kitty-planning repo.

---

### T023 — Verify hybrid output in all 3 consumer projects

**Purpose**: Confirm the post-upgrade state is correct in all three projects.

**Steps**:
For each project (spec-kitty-tracker, spec-kitty-saas, spec-kitty-planning):

1. **Check prompt-driven commands** — each should be a full prompt:
   ```bash
   for cmd in specify plan tasks tasks-outline tasks-packages checklist analyze research constitution; do
     lines=$(wc -l < .claude/commands/spec-kitty.${cmd}.md 2>/dev/null || echo "MISSING")
     echo "${cmd}: ${lines} lines"
   done
   # Each should be 100+ lines
   ```

2. **Check CLI-driven commands** — each should remain a thin shim:
   ```bash
   for cmd in implement review accept merge status dashboard tasks-finalize; do
     lines=$(wc -l < .claude/commands/spec-kitty.${cmd}.md 2>/dev/null || echo "MISSING")
     echo "${cmd}: ${lines} lines"
   done
   # Each should be < 5 lines
   ```

3. **Spot-check content**: open `spec-kitty.specify.md` and confirm it contains discovery gate language (not "spec-kitty agent shim").

4. **Content cleanliness check**:
   ```bash
   grep -r "057-" .claude/commands/  # Should return nothing
   grep -r "planning repository" .claude/commands/  # Should return nothing
   ```

5. Document results in this WP's activity log.

**Files**: Read-only verification across all three consumer project repos.

---

## Integration Verification

This WP is operational rather than code-driven. Verification is the outputs from T023.

Expected final state across all 3 consumer projects:
- 9 prompt-driven command files: 100+ lines each, no shim marker, no 057 slugs, no "planning repository" occurrences.
- 7 CLI-driven command files: < 5 lines each, contain "spec-kitty agent shim".
- All changes committed to each consumer project's default branch.

## Review Guidance

Reviewer should check:
- T019 was completed before T020–T022 (version.lock deleted, runtime templates confirmed present).
- All 3 projects had the upgrade applied and changes committed.
- Verification output from T023 is documented showing actual line counts.
- No CLI-driven shim files were accidentally replaced.
- If spec-kitty-planning already had full prompts from a prior migration, that is noted and acceptable.

## Activity Log

- 2026-03-30T13:59:29Z — WP created (planned)
- 2026-03-30T15:24:44Z – coordinator – shell_pid=20345 – lane=doing – Started implementation via workflow command
- 2026-03-30T15:25:50Z – coordinator – shell_pid=20345 – lane=approved – Approved: deployment happens post-merge when templates are on main
