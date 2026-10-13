---
title: 'Context: Spec Kitty Inc. Product Lines'
description: 'Glossary context for the Spec Kitty Inc. product lines (Build Kitty, Brain Kitty, Team Kitty) and how they differ from the Spec Kitty toolkit and CLI.'
doc_status: active
updated: '2026-10-13'
audience: docs/context/audience/internal/system-architect.md
type: reference
related:
- docs/context/team-kitty.md
- docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md
- docs/adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md
- docs/adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md
---
## Context: Spec Kitty Inc. Product Lines

Terms naming the product lines of Spec Kitty Inc. They are distinct from
**Spec Kitty**, the toolkit and CLI this repository ships. The October
2026 direction frames the open-core line as a **producer** side (Build Kitty and
Brain Kitty) and Team Kitty as the **consumer** side.

### Build Kitty

| | |
|---|---|
| **Definition** | The open-core producer line for governed mission delivery: the free CLI and its Mission Status Read API, the stable entry point to ledger and event data that consumers read across a public contract boundary. |
| **Context** | Product lines |
| **Status** | canonical |
| **Applicable to** | `4.x` |
| **Do NOT use when** | Naming the CLI package, an executable or a command (those are `spec-kitty` and its subcommands), or using it as a code identifier; it is a product-line name, not a runtime surface. For the hosted consumer side use [Team Kitty](#team-kitty). |
| **Related terms** | [Brain Kitty](#brain-kitty), [Team Kitty](#team-kitty), [ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) |

---

### Brain Kitty

| | |
|---|---|
| **Definition** | The open-core governance and doctrine line: the charter, a producer-side open-core unit that is being extracted into its own repository so open-core consumers can depend on it without the whole CLI. |
| **Context** | Product lines |
| **Status** | canonical |
| **Applicable to** | `4.x` |
| **Do NOT use when** | Naming the charter files, the `charter` command group or a Python package; use the charter terms in [Governance](./governance.md). Do not use it as a code identifier. |
| **Related terms** | [Build Kitty](#build-kitty), [Team Kitty](#team-kitty), [ADR 2026-10-12-2](../adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md) |

---

### Team Kitty

| | |
|---|---|
| **Definition** | The consumer line, framed as "Multiplayer Mode": the UI and multiplayer surfaces (mission-ui, the pack composer) that consume the open-core Mission Status Read API across its public contract, never reaching into CLI internals. The hosted collaboration product behind it is no longer actively supported; its model is in [Team Kitty and Zeitgeist](team-kitty.md). |
| **Context** | Product lines |
| **Status** | canonical |
| **Applicable to** | `4.x` |
| **Do NOT use when** | Describing the open-core producer surfaces ([Build Kitty](#build-kitty), [Brain Kitty](#brain-kitty)), or the old "sync" transport; do not use it as a code identifier. |
| **Related terms** | [Build Kitty](#build-kitty), [Brain Kitty](#brain-kitty), [Team Kitty and Zeitgeist](team-kitty.md), [ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md) |
