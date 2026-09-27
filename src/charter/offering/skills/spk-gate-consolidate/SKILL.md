---
name: spk-gate-consolidate
description: "Consolidate an accepted Spec Kitty mission safely, preserving git invariants, mission state, and post-merge follow-through."
---

# spk-gate-consolidate

Use this skill after `spk-gate-accept` passes or when a user asks to
consolidate a mission (merge its lanes into the target branch).

## Flow

1. Confirm the mission passed accept.
2. Run `/spec-kitty.consolidate` or the equivalent CLI command.
3. Resolve git/worktree blockers with `spk-admin-git-workflow`.
4. After consolidation, route to `spk-gate-mission-review`.
5. Then route to `spk-gate-retrospective`.

## Rule

Do not consolidate rejected, blocked, or partially reviewed work.
