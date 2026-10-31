---
work_package_id: WP03
title: Changelog
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-006
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-repair-historical-sweep-mission-overrides-01M68ZHQ
base_commit: 7323374ac695d6db299f0af1416d106f45853621
created_at: '2026-10-31T12:50:00.000000+00:00'
subtasks:
- T009
- T010
phase: Phase 3 - Documentation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: docs
tracker_refs:
- '#6548'
- '#5280'
---

# Work Package Prompt: WP03 – Changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(`python-pedro`), and behave according to its guidance before parsing the rest of this prompt.

## Objective

Record the operator-facing change under `[Unreleased]` → **Upgrade Notes** in
`docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it — edit the file, never
replace the symlink).

## Subtasks

- **T009** — Add one entry, modelled on the existing `4.0.0rc8_retire_stale_mission_template_forks`
  (#5280) note directly below it. It must:
  - lead with a bold, impact-first sentence naming the new step
    (`4.0.0rc8_repair_historical_sweep_overrides`) and carry `(#6548)`;
  - state **before**: an override an older `2.0.6_consistency_sweep` moved out of
    `.kittify/missions/` kept shadowing the shipped file, and no shipped step repaired it
    (`2.0.7_fix_stale_overrides` could not find the counterpart; the #5280 step only knows the 15
    documentation/research fork names);
  - state **after**: an override byte-identical to the shipped mission file is removed, so the
    shipped file resolves again; an override that differs is kept untouched and named in a warning,
    with what to do about it;
  - stay under 1,200 characters;
  - not restate the new-sweep classification fix (that already shipped).
- **T010** — Verify docs freshness and terminology (see *Verification*).

## Files You Own

- `docs/changelog/CHANGELOG.md`

Do not add a `docs/migrations/` page: the sibling #5280 repair shipped a changelog note only, and
`docs/migrations/index.md` lists runbook-shaped migrations, not single upgrade steps.

## Verification

```bash
uv run --frozen python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
git diff --stat docs/changelog/CHANGELOG.md
```

Do **not** run a full CLI-reference regeneration: the installed CLI's global asset cache is shared
with other concurrent agents and a full rebuild is not deterministic here.

## Definition of Done

- [ ] One `[Unreleased]` Upgrade Notes entry with the bold impact-first lead and `(#6548)`
- [ ] Before/after stated, under 1,200 characters
- [ ] Docs freshness errors=0; terminology test green
