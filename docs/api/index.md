---
title: Reference
description: 'Authoritative Spec Kitty specifications: CLI and agent subcommands, slash commands, charter commands, configuration, environment variables, schemas, skills, and agent profiles.'
doc_status: active
updated: '2026-08-10T00:00:00Z'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/api/agent-subcommands.md
- docs/api/agent_profiles/index.md
- docs/api/batch-api-contract.md
- docs/api/charter-commands.md
- docs/api/cli-commands.md
- docs/api/configuration.md
- docs/api/environment-variables.md
- docs/api/event-envelope.md
- docs/api/file-structure.md
- docs/api/missions.md
- docs/api/orchestrator-api.md
- docs/api/retrospective-schema.md
- docs/api/skills/index.md
- docs/api/slash-commands.md
- docs/api/supported-agents.md
- docs/api/supported-harnesses.md
- docs/api/terminology.md
kind: Hub
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
