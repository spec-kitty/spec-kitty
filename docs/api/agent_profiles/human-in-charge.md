---
title: Human in Charge — Agent Profile
description: Workflow sentinel indicating this work package requires direct human execution
doc_status: active
updated: '2026-10-08'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Human in Charge — Agent Profile

This is not an AI persona. It is a routing sentinel marking a work package for direct human execution; no agent context is injected. Nothing in the codebase blocks resolving or loading this profile-id the way it would any other, but doing so is a no-op: doctrine-layers, directives, and the initialization-declaration are all empty, so there is no persona voice or context for `spk-charter-profile-load` to apply.

## What it signals

When a work package carries the `human-in-charge` profile-id, that WP requires direct human action rather than agent execution. The Human in Charge remains accountable for the deliverable and its quality — an agent should not silently claim or implement it on the human's behalf.

## Why routing-priority is 100

`routing-priority: 100` is the highest of any built-in profile, but it is a tie-break precedence, not a workload or complexity signal: it exists so that a WP assigned to a human is never silently auto-claimed by an agent when routing logic considers multiple candidate profiles.

## What it does NOT do

- No directives or tactics are loaded (the profile declares no `directive-references` / `tactic-references`).
- No directives are applied (`directive-references` is empty).
- No persona voice or initialization declaration is used — the field is a literal empty string.

## See also

- [Agent Profiles index](index.md)
- [spk-charter-profile-load](../skills/spk-charter-profile-load.md) — how profile loading works for the 16 real personas this sentinel is excluded from
