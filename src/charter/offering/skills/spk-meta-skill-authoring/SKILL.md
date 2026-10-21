---
name: spk-meta-skill-authoring
description: "Author future Spec Kitty spk skills using the 3.2.0 naming convention, lifecycle families, and doctrine/command boundaries."
---

# spk-meta-skill-authoring

Use this skill when creating or revising a Spec Kitty skill.

## Rules

1. Name public operating skills `spk-<family>-<action-or-topic>`.
2. Keep generated `spec-kitty.<command>` slash-command files separate from
   generated `spec-kitty-<command>` command skills.
3. Preserve the older `spec-kitty-<topic>` guide skills (for example
   `spec-kitty-runtime-next`) when they remain useful aliases or detailed
   workflows. Never give a new skill a `spec-kitty-<command>` name: those
   names belong to the generated command skills.
4. Keep mission behavior in doctrine mission composition, not in skill prose.
5. Add tests when changing the public skill inventory.

## Families

Use only established families unless a new family improves discovery:
`start`, `mission`, `run`, `gate`, `admin`, `team`, `charter`, `practice`,
`integrate`, or `meta`.
