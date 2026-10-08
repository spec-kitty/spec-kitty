---
name: spk-meta-skill-map
description: "Discover the Spec Kitty 3.2.0 spk skill hierarchy, naming convention, legacy aliases, and the correct skill for a user intent."
---

# spk-meta-skill-map

Use this skill when the user asks what skills exist, how `spk-*` names are
organized, or which skill applies.

## Naming Convention

Use `spk-<family>-<action-or-topic>`.

Legacy family means the pre-3.2.0 `spec-kitty-*` compatibility skills that
remain alongside the newer `spk-*` hierarchy.

Families:

- `spk-start-*`: onboarding and orientation.
- `spk-mission-*`: authoring mission artifacts before runtime execution.
- `spk-run-*`: runtime advancement, program orchestration, implementation,
  review, and blockers.
- `spk-gate-*`: accept, merge, mission review, and retrospectives.
- `spk-admin-*`: setup, configuration, upgrades.
- `spk-team-*`: auth, sync, tracker, connectors.
- `spk-charter-*`: charter governance, glossary, SPDD, profiles.
- `spk-practice-*`: bulk-edit policy, visual communication, semantic
  compression.
- `spk-integrate-*`: APIs, CI, external automation.
- `spk-meta-*`: skill discovery and authoring.

## Full 3.2.0 Pack

Use the reference map for the complete inventory:
`references/spk-skill-map.md`.

## Rule

Choose the narrowest matching skill. If multiple skills match, start at the
earliest lifecycle family: start, mission, run, gate, admin/team, charter,
practice, integrate, meta.
