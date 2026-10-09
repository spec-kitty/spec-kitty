---
title: Doctrine Daphne — Agent Profile
description: External-agent onboarding and doctrine artifact curation specialist
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Doctrine Daphne — Agent Profile

Onboards agents built outside the framework — Cursor rules, system prompts, no-code bots,
LangChain/CrewAI/AutoGen scripts, custom GPTs — into well-formed, validated doctrine pack
content.

## What this profile is for

Doctrine Daphne is the entry point for governing an agent that already works outside Spec
Kitty. She interviews the owner in plain, non-technical language, gathers whatever
documentation exists (Markdown, wiki pages, system prompts, configuration, sample
input/output), and only then decomposes the agent's embedded knowledge into the correct
doctrine artifact kinds. She checks the existing pack for overlap before authoring anything,
wires new artifacts into the DRG, and runs validation until it reports zero errors. She does
not perform the onboarded agent's domain work, and does not promote artifacts into shared
doctrine without explicit human approval.

## Capabilities

- Agent knowledge audit
- Source documentation gathering
- Platform-agnostic agent onboarding
- Artifact-kind classification
- Pack artifact authoring
- DRG registration
- Pack validation
- Existing-artifact overlap detection
- Cross-pack connection suggestion
- Template authoring
- DRG content-consistency audit
- External-reference flagging

## When to reach for it

- You have a Cursor rules file, a bare system prompt, or a no-code bot and want it turned into
  reusable Spec Kitty doctrine (directives, tactics, procedures, styleguides).
- You're deciding whether a team's ad-hoc assistant deserves a dedicated agent profile, or
  whether its behavior already exists in the built-in catalog.
- You need doctrine artifacts registered in the DRG with correct edges, and cross-artifact
  references audited so nothing points at an undocumented external tool or URL.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness you don't run a CLI command to load
a profile directly. Instead:

- **Let routing pick it**: describe what you need in chat (for example, "onboard my Cursor
  rules into doctrine") and `spec-kitty dispatch` routes the request to this profile
  automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Doctrine
  Daphne explicitly by id (`doctrine-daphne`) — see the `spk-charter-profile-load` skill for the
  mechanic.

## See also

- [Agent Profiles index](index.md)
