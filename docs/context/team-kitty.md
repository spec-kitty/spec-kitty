---
title: 'Context: Team Kitty and Zeitgeist'
description: "Glossary context for Team Kitty and Zeitgeist: the hosted surfaces were removed from open-core in #6164, what that leaves, and why 'sync' is a dead word."
doc_status: active
updated: '2026-10-14'
audience: docs/context/audience/internal/ai-collaboration-agent.md
type: explanation
related:
- docs/context/system-events.md
- docs/context/orchestration.md
- docs/api/environment-variables.md
- docs/api/configuration.md
- docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md
- docs/adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md
- docs/adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md
---
# Context: Team Kitty and Zeitgeist

> **Status (2026-10-14):** the hosted, sync and drain surfaces and their clients
> were **removed from open-core in #6164**. The removed code is preserved in
> `spec-kitty/event-router` (PR #45). This page is now a glossary and a map of what
> is gone, so a reader who meets the old vocabulary can translate it. Do not build
> toward hosted surfaces unless the operator asks.

## What was removed

**Team Kitty** is the hosted product. **Zeitgeist** is the per-team presence-and-moments
relay it runs. Until #6164 the CLI shipped the client side of that: it authenticated,
minted a capability, and published each status **moment** to the team's relay when an
opt-in called **drain** was on. All of that client code left this repository:

- the `auth`, `issue-search`, `live-work`, `moments`, `routes` and `zeitgeist` CLI entries;
- the `zeitgeist_client/` and `saas_client/` packages and the auth package;
- the drain posture (`core/hosted_posture.py`) and `status/zeitgeist_bridge.py`.

Nothing hosted ships configured or gates a release. The SaaS and relay repositories are
separate and are not covered here.

## What stays

- **The produce seam.** `src/specify_cli/status/adapters.py` is the publish/subscribe
  surface for status events. Open-core ships no default handler, so every `fire_*` call
  is a no-op until a transport owner registers one. Producing an event never depends on a
  drain. `status/emit.py` still writes the canonical event log first.
- **The Mission Status Read API** (producer) and the consumer side built on it
  ("Multiplayer Mode": mission-ui, the pack composer). See
  [ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md)
  and the Amendment in
  [ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)
  (its drain and hiding mechanics are now historical).
- **One-way cleanup migrations.** For example `m_4_0_0_retired_hosted_target` deletes a
  stale `config.toml [sync].server_url` that names the retired `app.spec-kitty.ai`. It is
  self-contained and touches nothing else.

## "Sync" is dead

The transport called "sync" (a local daemon, an offline queue, a per-project consent
store, `spec-kitty sync opt-in`, `api/v1/sync/*`) was deleted in August 2026, and the
`specify_cli.sync` package with it. `tests/architectural/test_no_retired_subsystems.py`
refuses its return. The word survives only as residue in identifiers, stale docs and
comments. When you read "sync" here, translate it: it is leftover naming, never design
against or "re-enable" it. `spec-kitty charter sync` is unrelated: it syncs charter
artifacts.

## Canonical vocabulary

For where Team Kitty sits among the Spec Kitty Inc. product lines (Build Kitty, Brain Kitty), see [Product Lines](product-lines.md).

| Term | Meaning | Do not say |
|---|---|---|
| **Team Kitty** | The hosted product (separate SaaS repository). Not part of open-core. | "the SaaS sync", "Spec Kitty Cloud" |
| **Zeitgeist** | The presence-and-gossip relay Team Kitty runs, one container per team. | "the event server", "sync server" |
| **Moment** | One content-agnostic, bounded status event published to a relay. | "sync event" |
| **Drain** | The former client-side opt-in for automatic outbound hosted interaction. Removed with the hosted surfaces. | "sync", "fan-out enabled" |

## Stale surfaces you will meet

Marked deprecated and kept for history: `docs/architecture/team-kitty-saas.md`,
`docs/operations/sync-drain.md`, `docs/guides/project-sync-consent.md`, and the 2.x/3.x
sync ADRs. ADR [hosted interaction is opt-in](../adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md)
and [convergence retirement and client-repo inversion](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md)
describe the earlier design. See also [system events](system-events.md) for the canonical
event envelope.
