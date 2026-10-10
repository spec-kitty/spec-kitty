---
work_package_id: WP05
title: Delete dead standalone generated copies
dependencies: []
requirement_refs:
- FR-015
- C-002
- C-004
planning_base_branch: feat/charter-kind-tier-vocab-closeout
merge_target_branch: feat/charter-kind-tier-vocab-closeout
branch_strategy: Planning artifacts for this mission were generated on feat/charter-kind-tier-vocab-closeout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/charter-kind-tier-vocab-closeout unless the human explicitly redirects the landing branch.
subtasks:
- T070
- T071
phase: Phase 5 - Residue cleanup
history:
- at: '2026-10-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: .github/prompts/spec-kitty-standalone.md
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .agent/workflows/spec-kitty-standalone.md
- .amazonq/prompts/spec-kitty-standalone.md
- .augment/commands/spec-kitty-standalone.md
- .cursor/commands/spec-kitty-standalone.md
- .gemini/commands/spec-kitty-standalone.md
- .github/prompts/spec-kitty-standalone.md
- .kilocode/workflows/spec-kitty-standalone.md
- .kiro/prompts/spec-kitty-standalone.md
- .llxprt/commands/spec-kitty-standalone.md
- .opencode/command/spec-kitty-standalone.md
- .qwen/commands/spec-kitty-standalone.md
- .roo/commands/spec-kitty-standalone.md
- .windsurf/workflows/spec-kitty-standalone.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Delete dead standalone generated copies

Closes #5322 (the actionable remainder; most residue the issue described is already gone). Independent WP.

## Objectives & Success Criteria

- The 13 dead `spec-kitty-standalone.md` generated agent copies (all point at the removed `src/doctrine/skills/spec-kitty/SKILL.md`, line 5) are deleted.
- `.kittify/charter/graph.yml` is NOT touched (operator decision; honor the existing migration decision + its guard test `test_retired_activation.py`).
- No `src/` reader or manifest/ownership contract referenced the deleted copies.

## Context & Constraints

Grounded: these 13 files have NO regeneration path — their body text ("standalone-invocation skill pack") exists nowhere in `src/` or `packs/`, and `spec-kitty upgrade`/`regen`/`agent config sync` do not produce them. `command_installer.verify` treats them as unmanaged orphans (consent-gated, not auto-pruned). The mission's "regenerate via the proper path" premise is unachievable; deletion is the operator-approved remedy. Smallest viable diff + hard scope fence (C-002): do not touch anything else in those agent dirs. graph.yml stays (C-004).

## Subtasks & Detailed Guidance

### Subtask T070 – Orphan-safety proof

- Confirm no `src/` code reads these files and no manifest (`.kittify/skills-manifest.json`, `.kittify/command-skills-manifest.json`, command-installer `CANONICAL_COMMANDS`) owns the `spec-kitty-standalone` name. `git ls-files '*/spec-kitty-standalone.md'` lists exactly the 13.
- Record the proof in the Activity Log.

### Subtask T071 – Delete the 13 copies

- `git rm` the 13 `*/spec-kitty-standalone.md` files (use `git rm` so the deletions are staged for the mission commit). Leave `.kittify/charter/graph.yml` and everything else untouched.

## Test Strategy

- After deletion: `git ls-files '*/spec-kitty-standalone.md'` returns nothing; `grep -rl 'src/doctrine/skills/' .agent .amazonq .augment .cursor .gemini .github .kilocode .kiro .llxprt .opencode .qwen .roo .windsurf` returns nothing.
- `pytest tests/specify_cli/upgrade/migrations/test_retired_activation.py -q` still passes; `graph.yml` unchanged (`git diff -- .kittify/charter/graph.yml` empty).
- Run the command-installer / skills verify tests if they cover orphans (`grep -rl command_installer tests/`).

## Review Guidance

- Confirm exactly 13 deletions, graph.yml untouched, guard test green, and the orphan-safety proof is recorded.

## Activity Log

- 2026-10-09T20:40:00Z – system – Prompt created.
