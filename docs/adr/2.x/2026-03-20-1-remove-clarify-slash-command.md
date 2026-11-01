---
title: Remove the Clarify Slash Command
description: Deletes the clarify slash command outright and ships a destructive upgrade migration, folding its value back into stronger specification work up front.
status: Accepted
date: '2026-03-20'
doc_status: active
kind: ADR
updated: '2026-03-20T00:00:00Z'
---

## Context and Problem Statement

`/spec-kitty.clarify` currently exists as a distinct public workflow step and as a
generated prompt file across every supported agent directory. That command adds
product surface area, docs, upgrade complexity, and dedicated maintenance code.
At the same time, its value is not meaningfully distinct from stronger
specification work inside `/spec-kitty.specify` and the direct transition into
`/spec-kitty.plan`.

We want the command gone completely. That means removing it from packaged
templates, generated agent prompts, project-local `.kittify` copies, and
current product documentation. Existing initialized projects also need an
upgrade path that deletes stale prompt files rather than leaving them behind.

## Decision Drivers

* Reduce the public slash-command surface area.
* Simplify the default workflow from `specify -> plan`.
* Eliminate clarify-specific maintenance code and migration repair logic.
* Prevent stale generated prompt files from surviving upgrades.
* Keep current product documentation aligned with the shipped command set.

## Considered Options

* Option 1: Keep `/spec-kitty.clarify` as-is
* Option 2: Deprecate `/spec-kitty.clarify` first, then remove it later
* Option 3: Remove `/spec-kitty.clarify` immediately with a destructive upgrade migration

## Decision Outcome

**Chosen option:** "Option 3: Remove `/spec-kitty.clarify` immediately with a destructive upgrade migration", because it satisfies the goal of making the command disappear completely while keeping existing projects clean after upgrade.

### Consequences

#### Positive

* The public workflow becomes simpler and easier to teach.
* Spec Kitty ships one fewer slash command across every supported agent.
* Upgrade logic stops repairing a command we no longer want.
* Current docs, examples, and init output become easier to keep consistent.

#### Negative

* Existing users lose a named clarification phase.
* Upgrade must delete already-generated prompt files and project-local templates.
* Users who relied on the old command must move that behavior into stronger spec review before planning.

#### Neutral

* Historical records such as changelog entries and archived `kitty-specs/` artifacts remain unchanged.
* Clarification still happens as part of specification quality work, but not as a dedicated slash command.

### Confirmation

We will validate this decision by:

* Ensuring fresh `spec-kitty init` output and generated agent prompts contain no `clarify` command.
* Ensuring `spec-kitty upgrade` deletes stale `spec-kitty.clarify.*` prompt files and `.kittify` template copies from existing projects.
* Ensuring current product docs and examples describe a 13-command surface and a direct `specify -> plan` flow.

## Pros and Cons of the Options

### Option 1: Keep `/spec-kitty.clarify` as-is

**Pros:**

* No migration work required
* Existing users keep the familiar named step

**Cons:**

* Preserves command-surface bloat
* Keeps docs, templates, and migrations more complex than necessary
* Conflicts with the explicit goal to remove the command completely

### Option 2: Deprecate first, remove later

**Pros:**

* Gives users a softer transition path
* Allows warning-based rollout

**Cons:**

* Requires compatibility shims we do not want
* Extends the lifetime of command-specific code and docs
* Leaves the repo in a half-removed state for at least one more release

### Option 3: Remove immediately with a destructive upgrade migration

**Pros:**

* Delivers the cleanest end state in one step
* Keeps upgrade behavior explicit and deterministic
* Removes stale artifacts instead of preserving them accidentally

**Cons:**

* More work in a single PR
* Requires coordinated updates across templates, migrations, tests, and docs

## More Information

* Upgrade cleanup implementation: `src/specify_cli/upgrade/migrations/m_2_0_11_remove_clarify_command.py`
* Current-source template removals: `src/specify_cli/templates/command-templates/` and `src/specify_cli/missions/software-dev/command-templates/`
* Current-product doc updates: `README.md`, `docs/reference/`, and `examples/`
