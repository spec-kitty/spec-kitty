---
work_package_id: WP03
title: Upgrade migration — backfill pack.yaml (pack_level project) for existing project packs
dependencies:
- WP01
requirement_refs:
- FR-010
- C-003
- NFR-006
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: 3878054587955ce00bba793f37fe677c018ff6fb
created_at: '2026-10-11T17:21:12.325747+00:00'
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 2 - Migration
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_pack_level_backfill.py
- tests/upgrade/test_pack_level_backfill.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_pack_level_backfill.py
- tests/upgrade/test_pack_level_backfill.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/spk-charter-profile-load`. Read `plan.md` (IC-04), `contracts/pack-descriptor.contract.md` (Migration contract), and CLAUDE.md's "Writing Migrations" guidance (config-aware `get_agent_dirs`-style patterns; never mkdir). Depends on WP01 (the schema must accept `pack_level: project`).

## Objective

Add an upgrade migration that writes `pack.yaml` (`pack_level: project` + a minted `pack_id`) for each existing consumer PROJECT pack that lacks one, bringing installs into compliance.

## Context
Project packs live under `.kittify/charter-packs/`. The migration must be config-aware, idempotent, and surgical. Confirm the exact migration module naming/registration against a recent sibling migration before coding (canonical source — do not improvise). Pick the version-prefixed module name to match the current release train (adjust the `m_4_0_0rc8_` prefix if the repo's convention differs).

## Subtasks

### T013 — ATDD anchor (RED first)
`tests/upgrade/test_pack_level_backfill.py`: a fixture project pack lacking `pack.yaml` gains `pack.yaml` with `pack_level: project` + a valid minted `pack_id`; `packs/built-in` and `packs/internal` are untouched; zero `mkdir`; an existing authored `pack.yaml` is NOT clobbered (a differing `pack_id` is preserved; `pack_level` added only if absent). Commit RED first.

### T014 — Implement the migration
Follow the config-aware discovery pattern (never create a missing dir; only process packs that already exist). Write `pack.yaml` with `pack_level: project` and a minted ULID `pack_id`. Skip `packs/built-in` and `packs/internal` explicitly.

### T015 — Idempotency + non-clobber
Re-running the migration is a no-op on a pack that already has `pack.yaml`. Never overwrite a differing `pack_id`; only add `pack_level` when absent.

### T016 — Register + wire
Register the migration in the migration chain per the canonical mechanism (match a recent sibling). Ensure it is discoverable by the upgrade runner.

## Definition of Done
- ATDD test GREEN (RED on base); `tests/upgrade/` passes.
- No `mkdir`; built-in/internal untouched; non-clobber proven.
- ruff/format/mypy clean (NFR-006, C-003).

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/upgrade/test_pack_level_backfill.py tests/upgrade/ -q`

## Reviewer guidance
Verify config-aware discovery (no mkdir, no assumption all packs present); verify skip of built-in/internal; verify non-clobber + idempotency; confirm registration matches the canonical pattern.

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP03 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
