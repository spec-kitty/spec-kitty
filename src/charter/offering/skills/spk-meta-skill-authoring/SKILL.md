---
name: spk-meta-skill-authoring
description: "Author future Spec Kitty spk skills using the 3.2.0 naming convention, lifecycle families, and doctrine/command boundaries."
---

# spk-meta-skill-authoring

Use this skill when creating or revising a Spec Kitty skill.

## Rules

1. Name public operating skills `spk-<family>-<action-or-topic>`.
2. Keep generated slash-command files separate from generated
   `spec-kitty.<command>` Agent Skills.
3. Preserve legacy `spec-kitty-*` skills when they remain useful aliases or
   detailed workflows.
4. Keep mission behavior in doctrine mission composition, not in skill prose.
5. Add tests when changing the public skill inventory.

## Families

Use only established families unless a new family improves discovery:
`start`, `mission`, `run`, `gate`, `admin`, `team`, `charter`, `practice`,
`integrate`, or `meta`.
