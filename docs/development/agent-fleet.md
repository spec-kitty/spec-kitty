---
title: The SkyKitty Agent Fleet
description: 'SkyKitty is the company agent fleet that executes Spec Kitty missions under an operator who stays human-in-command: who is in the fleet, the roles they play, and the ready-for-squad label handshake that hands work from an implementer to the review squad and CI.'
doc_status: active
updated: '2026-09-11'
audience: docs/context/audience/internal/maintainer.md
type: explanation
related:
- docs/architecture/governed-profile-invocation.md
- docs/architecture/multi-agent-orchestration.md
- docs/development/how-to/manage-issue-tracker.md
- docs/development/how-to/pr-landing.md
- docs/context/charter-overview.md
---

# The SkyKitty Agent Fleet

**SkyKitty** is the proper name of the Spec Kitty **company agent fleet** — the set of
governed AI agents that execute missions on this repository under an **operator** who
stays human-in-command. The charter's Collaboration Strategy already governs how the
operator and the fleet divide the work (see the [charter overview](../context/charter-overview.md));
this page names the fleet, enumerates the roles inside it, and documents the tracker
signals — chiefly the `ready-for-squad` label — through which those roles hand work to one
another.

## SkyKitty is the fleet; Spec Kitty is the toolkit

Keep the two terms distinct:

- **Spec Kitty** is the toolkit — the CLI, the templates, the doctrine, the runtime that
  drives the specify → plan → tasks → implement → review → merge loop.
- **SkyKitty** is the **fleet of agents that operate *with* Spec Kitty** — the crew the
  operator dispatches to run those missions. The charter's shorthand for the same thing is
  "the fleet" / "fleet agents"; **SkyKitty** is that fleet's proper name.
- **Team Kitty** is a third, unrelated Kitty-branded noun: the **hosted SaaS product**
  (CLI → Zeitgeist relay → Team Kitty Pulse projection). It is neither the toolkit nor the
  fleet — see [Team Kitty and Zeitgeist](../context/team-kitty.md). The tool-vs-agent split
  behind these names is the [tool-vs-agent naming decision](../context/naming-decision-tool-vs-agent.md).

The operator is not part of the fleet. SkyKitty executes; the operator commands, sets
scope, and performs the mainline merge (see [Roles](#roles-in-the-fleet)).

## Roles in the fleet

A mission is run by several governed profiles, each **profile-LOADED** (its doctrine
context resolved and injected), never merely a persona name. One agent may wear more than
one role across a mission, but the roles stay distinct and, where independence is required,
are held by different agents.

| Role | Who | What they own | What they must not do |
|------|-----|---------------|-----------------------|
| **Operator** | Human-in-command | Delegates the mission, sets and approves scope, performs the **mainline merge** | — |
| **Orchestrator** | Governed profile (e.g. `planner-priti` for planning/tracker work) | Claims the mission's tickets, plans (spec → plan → tasks with an adversarial squad at each planning point-cut), runs the implement → review loop | Merge to mainline |
| **Implementer** | Governed profile, in an isolated worktree | Builds the work package, runs the required tests + self-review, labels the PR `ready-for-squad` | Merge; review its own work |
| **Review / adversarial squad** | Independent profile-loaded lenses (reviewer ≠ implementer) | Squad review of the aggregate diff | Implement the change it reviews |
| **CI / fleet agents** | Fleet | Continuous integration; CI is the authoritative release gate | — |
| **Merge agent** | Fleet profile | Local lane consolidation and the fleet-side integration mechanics | Publish to origin/`main` without the operator |

Two invariants bind every role:

- **Implementers never merge — agent consolidates, operator publishes.** The overloaded
  term `merge` has three senses (see the
  [orchestration glossary](../context/orchestration.md#lane-consolidation)); keep them
  apart here. The fleet owns CI, squad review, and the merge *mechanics* — the merge agent
  runs **lane consolidation** (`spec-kitty merge` → **local** `main` only, never origin).
  The **operator, not an agent, performs the mainline merge** — in the glossary's terms the
  **publish to origin/`main`** (directive `045-prs-only-and-read-intent`).
- **Reviewer ≠ implementer.** Squad review is independent of the agent that wrote the code.

For the mechanics of how a governed profile is dispatched, its doctrine context injected,
and its work tracked as an Op, see
[Understanding Governed Profile Invocation](../architecture/governed-profile-invocation.md)
and [Multi-Agent Orchestration](../architecture/multi-agent-orchestration.md).

## The `ready-for-squad` handshake

The fleet coordinates through the tracker, not through side channels. The load-bearing
signal is the **`ready-for-squad`** label, which hands a pull request from the implementer
to the review squad and CI:

1. **Issue branch first.** Completed mission work is opened from an `issue-<n>-<slug>`
   branch as a pull request targeting `main`, with compact, logically-sliced history.
2. **Ready only when complete.** The implementer runs the required tests and a self-review,
   then labels the PR **`ready-for-squad`**. The label means *this PR is finished and
   independently testable* — not *please start looking*.
3. **The fleet takes over.** Once the PR carries `ready-for-squad`, **fleet agents own CI
   and squad review**. The adversarial review squad is the recommended mechanism for the
   independent review the charter requires (recommended, never a mandated gate).
4. **The operator merges.** Implementers never merge; after CI and squad review are
   satisfied, the operator performs the mainline merge.

Do not apply `ready-for-squad` to a PR that is still a draft of its intended scope, that
has not had its tests run, or that has not been self-reviewed — the label is the fleet's
contract that the work is ready to be owned downstream.

### Related PR-workflow labels

`ready-for-squad` is one of the fleet-coordination labels on pull requests. It travels with
the `pr:*` family (`pr:needs-refresh`, `pr:needs-revision`, `pr:kept-for-reference`,
`pr:deferred`, `pr:skip-ci`) and the CI control `ci:full`. All of them, together with the
issue-side taxonomy, are documented in
[Managing the Issue Tracker → Label taxonomy](how-to/manage-issue-tracker.md#label-taxonomy).

## See also

- [Managing the Issue Tracker](how-to/manage-issue-tracker.md) — the full label taxonomy,
  including the fleet-coordination labels.
- [Landing contributor PRs](how-to/pr-landing.md) — the maintainer runbook the fleet and
  operator follow to bring a PR onto `main`.
- [Understanding Governed Profile Invocation](../architecture/governed-profile-invocation.md)
  — how a fleet agent is dispatched under governance.
- [Multi-Agent Orchestration](../architecture/multi-agent-orchestration.md) — the
  host/provider coordination model beneath the fleet.
- [Charter overview](../context/charter-overview.md) — where the Collaboration Strategy and
  Agent Operating Discipline that bind the fleet live.
