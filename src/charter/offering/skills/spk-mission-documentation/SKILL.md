---
name: spk-mission-documentation
description: "Operate documentation-oriented Spec Kitty missions and ensure docs stay tied to shipped behavior and doctrine."
---

# spk-mission-documentation

Use this skill when the mission is primarily documentation, release notes,
guides, or user-facing explanation.

## Flow

1. Confirm whether this is a documentation mission or a software mission with
   docs as acceptance criteria.
2. Ground docs in current product behavior, not intended future behavior unless
   clearly marked.
3. Cross-check terms with `spk-charter-glossary`.
4. If docs describe commands or workflows, cross-check `spk-start-command-map`.

## Completion Standard

Documentation should make the next user action obvious and should not create a
second source of truth for runtime behavior.
