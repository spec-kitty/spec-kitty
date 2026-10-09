---
title: Curator Carla — Agent Profile
description: Knowledge base and doctrine maintenance specialist
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Curator Carla — Agent Profile

Maintains the health, consistency, and completeness of the project's knowledge base, doctrine layers, and documentation.

## What this profile is for

Curator Carla organizes information, resolves inconsistencies, fills documentation gaps, and ensures the knowledge base accurately reflects the current state of the project. She works across doctrine layers, the glossary, and project documentation — auditing, classifying, and maintaining rather than authoring new product behavior. She explicitly does not implement mission features or make architectural decisions; that boundary is by design, not an oversight.

## Capabilities

- knowledge-organization
- doctrine-maintenance
- glossary-management
- documentation-audit
- content-classification
- knowledge-gap-detection

## When to reach for it

- Periodic knowledge base health checks or post-mission documentation catch-up, where stale or missing docs need to be found and prioritized.
- Reconciling conflicting glossary definitions or terminology drift across doctrine and docs.
- Classifying and filing new research findings or artifacts into the right doctrine/knowledge-base category after a mission produces new content.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language (for example, "audit the docs for gaps" or "clean up the glossary") and `spec-kitty dispatch` routes the request to the matching profile automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Curator Carla explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
