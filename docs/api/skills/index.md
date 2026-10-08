---
title: Skills
description: Catalog of Spec Kitty's operator-facing skills — the spk-* public hierarchy, their legacy spec-kitty-* aliases, and which skills have a deep reference page.
doc_status: active
updated: '2026-08-10'
type: reference
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/api/skills/spk-start-here.md
- docs/api/skills/spk-run-implement-review.md
- docs/api/skills/spk-run-next.md
- docs/api/skills/spk-gate-mission-review.md
- docs/api/skills/spk-charter-profile-load.md
- docs/api/skills/spk-admin-setup-doctor.md
- docs/api/skills/spk-meta-skill-map.md
- docs/api/index.md
- docs/api/agent_profiles/index.md
---
# Skills

Spec Kitty ships two overlapping skill surfaces. The newer, short-named
`spk-*` hierarchy is the 3.2.0 forward-looking public naming convention —
one skill per family, each covering a bounded slice of "how do I operate
Spec Kitty?" A set of `spec-kitty-*` legacy/detailed-workflow skills still
ships alongside it; several `spk-*` skills alias to one of these for their
full mechanics rather than duplicating that depth inline. This catalog leads
with `spk-*` ids as canonical: where a legacy skill is the one carrying the
real depth, the **Legacy Alias** column names it, and the linked deep page
(where one exists) documents both under the `spk-*` heading. Skills with no
confirmed legacy alias are self-contained.

Generated slash-command skills (`spec-kitty.specify`, `spec-kitty.plan`, and
so on) are a separate, distinct surface tied to slash-command compatibility
rather than the `spk-*`/legacy split — see
[Slash Commands](../slash-commands.md) for that catalog instead of
re-listing it here.

## spk-start-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-start-here` | First route for users and agents | — | [spk-start-here](spk-start-here.md) |
| `spk-start-first-feature` | First mission walkthrough | — | — |
| `spk-start-command-map` | Command-to-skill map | — | — |
| `spk-start-agent-surface` | Agent host compatibility | — | — |

## spk-mission-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-mission-specify` | Specification phase | — | — |
| `spk-mission-plan` | Planning phase | — | — |
| `spk-mission-tasks` | Tasks and WP authoring | — | — |
| `spk-mission-types` | Mission type selection | — | — |
| `spk-mission-research` | Research workflows | — | — |
| `spk-mission-documentation` | Documentation missions | — | — |

## spk-run-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-run-next` | Runtime-next control loop | `spec-kitty-runtime-next` | [spk-run-next](spk-run-next.md) |
| `spk-run-program-orchestrate` | Multi-mission program orchestration | `spec-kitty-program-orchestrate` | — |
| `spk-run-implement-review` | WP implementation/review orchestration | `spec-kitty-implement-review` | [spk-run-implement-review](spk-run-implement-review.md) |
| `spk-run-review-wp` | Single-WP review | `spec-kitty-runtime-review` | — |
| `spk-run-blocked-recovery` | Blocked-state recovery | — | — |

## spk-gate-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-gate-accept` | Accept gate | — | — |
| `spk-gate-merge` | Merge gate | — | — |
| `spk-gate-mission-review` | Post-merge mission review | `spec-kitty-mission-review` | [spk-gate-mission-review](spk-gate-mission-review.md) |
| `spk-gate-retrospective` | Post-merge retrospective | — | — |

## spk-admin-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-admin-setup-doctor` | Install and repair | `spec-kitty-setup-doctor` | [spk-admin-setup-doctor](spk-admin-setup-doctor.md) |
| `spk-admin-agent-config` | Agent setup | — | — |
| `spk-admin-upgrade` | Upgrade and migrations | — | — |
| `spk-admin-git-workflow` | Git and worktree workflows | `spec-kitty-git-workflow` | — |

## spk-team-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-team-auth` | Auth and accounts | — | — |
| `spk-team-sync` | Hosted/team sync | — | — |
| `spk-team-tracker` | Tracker workflows | — | — |
| `spk-team-connectors` | Connector integrations | — | — |

## spk-charter-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-charter-governance` | Charter workflows | — | — |
| `spk-charter-glossary` | Terminology | — | — |
| `spk-charter-spdd-reasons` | REASONS Canvas | — | — |
| `spk-charter-profile-load` | Agent profiles | — | [spk-charter-profile-load](spk-charter-profile-load.md) |

## spk-practice-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-practice-bulk-edit` | Bulk-edit classification | — | — |
| `spk-practice-semantic-compression` | Semantic compression | — | — |
| `spk-practice-show-me` | Compact visuals, diagrams, and TUI status rendering | — | — |

## spk-integrate-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-integrate-orchestrator-api` | External orchestrator API | `spec-kitty-orchestrator-api-operator` | — |

## spk-meta-*

| Skill ID | Purpose | Legacy Alias | Deep Page |
|---|---|---|---|
| `spk-meta-skill-map` | Discovery and naming convention | — | [spk-meta-skill-map](spk-meta-skill-map.md) |
| `spk-meta-skill-authoring` | Future skill authoring | — | — |

## Legacy / Detailed Workflow Skills

`spec-kitty-*` legacy skills not already captured as a Legacy Alias target
above:

| Skill ID | Purpose | Deep Page |
|---|---|---|
| `spec-kitty-mission-system` | Mission types, step contracts, procedures, action indices, template resolution | — |

All other legacy `spec-kitty-*` skills are named in the **Legacy Alias**
column of the family tables above, next to the `spk-*` skill they support.
