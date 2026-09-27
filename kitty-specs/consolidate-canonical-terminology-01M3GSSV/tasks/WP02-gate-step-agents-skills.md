---
work_package_id: WP02
title: Gate-step command surface + agents/skills regeneration
dependencies:
- WP01
- WP03
requirement_refs:
- C-005
- FR-006
- NFR-003
- NFR-004
planning_base_branch: feat/consolidate-canonical-terminology
merge_target_branch: feat/consolidate-canonical-terminology
branch_strategy: Planning artifacts for this mission were generated on feat/consolidate-canonical-terminology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidate-canonical-terminology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-canonical-terminology-01M3GSSV
base_commit: 50c752b3afa5196b8a1855e3a630e446e86ccf3b
created_at: '2026-09-27T11:56:12.454900+00:00'
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 2 - Gate-step + generated surfaces
history:
- at: '2026-09-27T07:39:01Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- src/charter/offering/skills/spk-gate-consolidate/
- .claude/commands/spec-kitty.consolidate.md
- .claude/skills/spk-gate-consolidate/
- .codex/prompts/spec-kitty.consolidate.md
- .cursor/commands/spec-kitty.consolidate.md
- .agents/skills/spec-kitty.consolidate/
- .agents/skills/spk-gate-consolidate/
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/skills/command_installer.py
- src/charter/offering/skills/spk-gate-merge/
- src/charter/offering/skills/spk-gate-consolidate/
- .kittify/command-skills-manifest.json
- .claude/commands/spec-kitty.merge.md
- .claude/commands/spec-kitty.consolidate.md
- .claude/skills/spk-gate-merge/
- .claude/skills/spk-gate-consolidate/
- .codex/prompts/spec-kitty.merge.md
- .codex/prompts/spec-kitty.consolidate.md
- .cursor/commands/spec-kitty.merge.md
- .cursor/commands/spec-kitty.consolidate.md
- .agents/skills/spec-kitty.merge/
- .agents/skills/spec-kitty.consolidate/
- .agents/skills/spk-gate-merge/
- .agents/skills/spk-gate-consolidate/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Gate-step command surface + agents/skills regeneration

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) and address all feedback before completion.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Rename the mission gate-step/command surface and the gate skill from `merge` to `consolidate`
**at their canonical sources**, then regenerate the 13 agent command/skill copies via
`spec-kitty upgrade`.

Complete when:

- **SC-004**: All 13 agent surfaces + command-skills expose `consolidate` (not `merge`) and `spk-gate-consolidate` (not `spk-gate-merge`) after `spec-kitty upgrade`, **verified on at least `.claude`, `.codex`, `.opencode`**. *(FR-006)*
- No generated copy is hand-edited — sources only (C-005).
- Quality gates clean (`ruff`, `ruff format --check .`, `mypy`); touched functions ≤ complexity 15. *(NFR-003, NFR-004)*

## Context & Constraints

- **Authoritative reads**: `.kittify/charter/charter.md`, [`plan.md`](../plan.md) (IC-04), [`spec.md`](../spec.md) FR-006, [`occurrence_map.yaml`](../occurrence_map.yaml).
- **C-005 — edit source, not generated copies.** The primary sources are:
  - `src/specify_cli/skills/command_installer.py` (the command list/description/command-map).
  - `src/charter/offering/skills/spk-gate-merge/SKILL.md` (the **canonical skill source** — `.claude/skills/…`, `.agents/skills/…` are generated copies).
  - `.kittify/command-skills-manifest.json` (the command-skills manifest).
  Then regenerate the 13 agent copies via `spec-kitty upgrade`. **Never hand-edit** `.claude/**`, `.codex/**`, `.cursor/**`, `.agents/**` copies — they are the deterministic output of the source edit.
- **Depends on WP01**: the `consolidate` CLI command must exist before the gate-step and skill can name it.
- **Boundary**: this WP does NOT edit `packs/**` prompt templates (WP03) or `docs/**` prose (WP04). It owns the **command/skill** surface only.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: `feat/consolidate-canonical-terminology`
- **Merge target branch**: `feat/consolidate-canonical-terminology`

## Subtasks & Detailed Guidance

### T016 – `command_installer.py` list / description / command-map
- **Purpose**: The command surface names the gate-step (FR-006).
- **Steps**: In `src/specify_cli/skills/command_installer.py` update the command **list** (:99), the **description** (:110), and the **command-map** entry (:116) `merge`→`consolidate`. Classify against occurrence_map `cli_commands: rename`.

### T017 – Rename the gate skill at source
- **Purpose**: `spk-gate-merge`→`spk-gate-consolidate` (FR-006).
- **Steps**: `git mv src/charter/offering/skills/spk-gate-merge src/charter/offering/skills/spk-gate-consolidate`; update its `SKILL.md` name/description/body (lane-consolidation sense only). Update `.kittify/command-skills-manifest.json` to reference the renamed skill and the `consolidate` command. Also rename the `spec-kitty.merge` command-skill directory (`.agents/skills/spec-kitty.merge`→`spec-kitty.consolidate`) via the source/manifest, not by hand.

### T018 – Regenerate the 13 agent copies via `spec-kitty upgrade`
- **Purpose**: Deploy the source edits to every agent dir + command-skills (C-005).
- **Steps**: Run `spec-kitty upgrade`. Confirm the generated `spec-kitty.merge.*` command files are replaced by `spec-kitty.consolidate.*` and `spk-gate-merge/` by `spk-gate-consolidate/` across the configured agents. Do not `mkdir` agent dirs manually — the migration respects `config.yaml`.

### T019 – Verify SC-004
- **Purpose**: Prove regeneration is complete.
- **Steps**: Confirm `consolidate` / `spk-gate-consolidate` present and `merge` / `spk-gate-merge` absent in at least `.claude`, `.codex`, `.opencode`. Grep each for the old names.

## Test Strategy

- After `spec-kitty upgrade`: grep `.claude`, `.codex`, `.opencode` for `spec-kitty.merge` and `spk-gate-merge` (expect none) and for `consolidate`/`spk-gate-consolidate` (expect present).
- **Blast radius**: run the skills tests and — because this edits `src/charter/offering/skills/` — both `tests/charter/` and `tests/doctrine/` (each owning subsystem, per CLAUDE.md test policy), plus any `tests/**` covering `command_installer.py` (`grep -rl command_installer tests/`). Use narrow foreground file-scoped runs. Record commands + counts in the PR.
- `ruff check .`, `ruff format --check .`, `mypy` — zero issues.

## Risks & Mitigations

- **Editing a generated copy instead of source (C-005)** → edit only `command_installer.py`, `src/charter/offering/skills/`, and the manifest; regenerate.
- **Incomplete regeneration across 13 agents** → run `spec-kitty upgrade`; verify the three named agents; do not assume all agents are configured (respect `config.yaml`).
- **Ordering vs WP03**: `spec-kitty upgrade` also regenerates `packs/**`-sourced prompt copies. WP03 edits packs sources in parallel; if you run `upgrade` before WP03 lands, a later regeneration at mission finalize reconciles. Note this in the PR; do not claim WP03's prompt copies as owned here.
- **Editing `src/charter/offering/skills/` can trip doctrine gates** → run `tests/doctrine/` before completion.

## Review Guidance

- Confirm only sources were edited; generated copies are the deterministic output of `spec-kitty upgrade`.
- Verify SC-004 on `.claude`, `.codex`, `.opencode`.
- Confirm no `packs/**` or `docs/**` file was touched (those belong to WP03/WP04).

## Activity Log

> **CRITICAL**: chronological order, APPEND at the END.

- 2026-09-27T07:39:01Z – system – Prompt created.
