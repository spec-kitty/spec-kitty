---
title: Reference
description: 'Authoritative Spec Kitty specifications: CLI and agent subcommands, slash commands, charter commands, configuration, environment variables, schemas, skills, and agent profiles.'
doc_status: active
updated: '2026-08-10'
type: reference
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
related:
- api/agent-subcommands
- api/agent_profiles
- api/batch-api-contract
- api/charter-commands
- api/cli-commands
- api/configuration
- api/environment-variables
- api/event-envelope
- api/file-structure
- api/missions
- api/orchestrator-api
- api/retrospective-schema
- api/skills
- api/slash-commands
- api/supported-agents
- api/supported-harnesses
- api/terminology
---
# Reference

Precise, authoritative specifications for Spec Kitty's command surfaces, configuration, and
schemas. Use these pages to look up exact flags, fields, and values — "what it is, not what to
do with it." For task-oriented instructions see the [How-to guides](../guides/index.md); for
conceptual background see [Explanation](../architecture/index.md).

## Commands

- [CLI commands](cli-commands.md) — the full `spec-kitty` CLI surface.
- [Agent subcommands](agent-subcommands.md) — the `spec-kitty agent` group.
- [Slash commands](slash-commands.md) — agent-facing `/spec-kitty.*` commands.
- [Charter commands](charter-commands.md) — the `charter` subcommands.
- [Orchestrator API](orchestrator-api.md) — external orchestration contract.
- [Batch Event Ingest API](batch-api-contract.md) — the batch endpoint wire contract.

## Configuration and schemas

- [Configuration](configuration.md) and [environment variables](environment-variables.md).
- [File structure](file-structure.md) — layout of a Spec Kitty project.
- [Missions](missions.md) — mission types and configuration.
- [Event envelope](event-envelope.md) and [retrospective schema](retrospective-schema.md).
- [Terminology](terminology.md) — canonical glossary.
- [Supported agents](supported-agents.md) and [supported harnesses](supported-harnesses.md).

## Catalogs

- [Skills](skills/index.md) — the operator-facing skill catalog: what each skill does and when
  to invoke it.
- [Agent profiles](agent_profiles/index.md) — the built-in agent profile roster: identity,
  roles, and routing for each shipped profile.
