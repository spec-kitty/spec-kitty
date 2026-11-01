---
title: Private Teamspace and Repository Sharing Boundary
description: 'New checkouts belong to a Private Teamspace by default, and a repository is the unit a user explicitly and non-destructively shares into a team.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-21'
---

## Context and Problem Statement

Spec Kitty's collaboration model needs a stronger trust boundary than the current "team sees whatever has synced" behavior.

The product requirement is not merely better filtering. The system must answer two different questions with two different surfaces:

1. what repository/build activity belongs to a user privately?
2. what repository activity has been intentionally shared into a team?

The existing product direction around Teamspace and the observed dashboard behavior show a domain mismatch:

1. teams can see too many historical projects/builds by default
2. users who belong to multiple teams do not have a strong enough routing boundary
3. the product vocabulary needs a stable distinction between a shareable repository, a team-facing project, and a build

## Decision Drivers

* **Trust boundary first** — no repository/build data may appear in a team without explicit share and team approval, unless the team explicitly enables auto-approval.
* **User-owned first** — data should belong to a user before it becomes team-visible.
* **Local-first execution** — build execution and mission progress remain local-first and repository-native.
* **Clear vocabulary** — `repository`, `project`, and `build` must describe distinct domain objects.
* **Active-work emphasis** — default Teamspace must answer "what is happening now?" rather than act as a historical registry.

## Considered Options

* **Option 1:** Keep team-owned ingress and improve Teamspace filtering only.
* **Option 2:** Make repositories opt-in to SaaS globally from the CLI with no user-owned private surface.
* **Option 3 (chosen):** User-owned first, `Private Teamspace` by default, explicit repository sharing into teams, and activity-ranked Teamspace surfaces.

## Decision Outcome

**Chosen option: Option 3**, because it establishes the missing trust boundary while preserving local-first behavior and giving Teamspace a product shape that matches how teams actually work.

### Core Decisions

**Decision 1 — New checkouts/builds default to `Private Teamspace`.**

Every newly observed repository/build belongs to its owning user first. No team sees it until the user explicitly shares the repository into that team.

**Decision 2 — `Repository` is the share/admission unit.**

The first team admission decision is made for `repository + destination team`. Sharing is explicit and non-destructive: the repository remains visible in `Private Teamspace` after sharing.

**Decision 3 — `Project` is the team-facing collaboration surface.**

A `Project` is created or reused when a repository is shared to a team. It is not the same thing as a local repository or a specific build.

**Decision 4 — `Build` remains the checkout/worktree identity.**

A `Build` is one checkout/worktree on one machine at one local path. `build_id` remains the canonical build key. Machine and absolute local path are required provenance for Teamspace presentation.

**Decision 5 — Team approval is one-time per `repository + team`.**

The first share to a team requires approval unless that team has an explicit auto-approve policy. Once approved, later teammates sharing the same repository into that team join automatically.

**Decision 6 — Team disconnect is team-local.**

Admin disconnect removes the repository/project from one team's visibility, search, and discoverable history within that team. It does not delete user-owned data and does not affect other teams.

**Decision 7 — Default Teamspace is activity-ranked, not history-ranked.**

The default Teamspace project card shows only the 1-3 most relevant `active now` or `recently completed` mission/build items. Historical missions/builds remain discoverable via drilldown/history rather than the landing page.

**Decision 8 — GitHub canonicalization ages work off the default surface.**

`merged_local_only` may remain discoverable briefly, but once the work is canonicalized on GitHub it leaves the default Teamspace surface and GitHub becomes the canonical inspection point.

**Decision 9 — Forks are separate repositories by default.**

Forks may expose a visible relationship to upstream, but they do not collapse automatically into the upstream project.

## Consequences

### Positive

* Users get a clear safety boundary between private work and team-visible work.
* Teamspace can become a live operational board rather than a project graveyard.
* Vocabulary aligns cleanly: repository for sharing, project for team collaboration, build for checkout.
* The same repository can appear in multiple teams without blurring ownership or disconnect semantics.

### Negative

* The SaaS data model will need migration away from direct team-owned sync materialization assumptions.
* CLI routing UX must become more explicit because the system can no longer assume "sync means team-visible."
* Approval/disconnect state introduces new operational and testing complexity.

### Neutral

* Historical missions/builds still exist and remain discoverable; they simply lose default-surface priority.
* Exact stale-work cleanup policy is deferred; v1 only requires stale work to stay off the default surface.

## Confirmation

This decision is validated when all of the following are true:

1. a brand-new checkout/build appears only in the user's `Private Teamspace` until explicit share
2. no team sees repository/build data without explicit share plus approval, unless that team chose auto-approval
3. once a repository is approved for a team, later teammates sharing the same repository join automatically
4. default Teamspace project cards show only 1-3 relevant active/recent mission/build items
5. each surfaced card includes mission progress plus build provenance including machine and local path
6. admin disconnect removes visibility from one team only without deleting user-owned data
7. canonicalized GitHub work leaves the default Teamspace surface and remains discoverable through history/drilldown

## Pros and Cons of the Options

### Option 1: Keep team-owned ingress and filter harder

**Pros:**

* Lowest short-term migration cost.
* Minimal new domain concepts.

**Cons:**

* Does not create a real trust boundary.
* Keeps Teamspace conceptually backwards.
* Leaves multi-team routing safety weak.

### Option 2: Global CLI opt-in without a private surface

**Pros:**

* Simple mental model for "send or do not send."
* Lower SaaS modeling cost than a user-owned first system.

**Cons:**

* Does not give the product a first-class private collaboration surface.
* Fails the requirement that data should remain visible to the user privately even when not shared to a team.
* Makes governance and discoverability less expressive.

### Option 3: User-owned first with explicit sharing

**Pros:**

* Matches the trust and routing requirements.
* Gives Teamspace the right default behavior.
* Supports multi-team participation without collapsing boundaries.

**Cons:**

* Requires cross-repo implementation work.
* Introduces new approval/disconnect states and migration needs.

## More Information

**Related planning doc:**
* `spec-kitty-planning/product-ideas/prd-private-teamspace-repository-sharing-and-active-teamspace-v1-2026-04-21.md`

**Related issue:**
* `Priivacy-ai/spec-kitty-saas#99`

## Implementation Status (2026-04-21)

Status: shipped in `spec-kitty` commit `de8274f5` and verified against the
deployed `spec-kitty-dev` SaaS environment.

The current monorepo implementation now reflects this ADR in the CLI layer:

1. checkout routing resolves to `Private Teamspace` by default
2. repository sharing is explicit through CLI sync commands
3. per-checkout opt-in and opt-out persist locally without git-tracked side effects
4. future new checkouts can inherit a remembered repository-level sync preference
5. routing visibility exposes the owning user/build plus current shared-team state
6. opting out can stop ingress immediately and optionally delete already-synced
   private-only data after explicit confirmation

Validation completed for the shipped slice:

1. targeted CLI/auth/sync pytest coverage passed (`248 passed`)
2. targeted Ruff checks passed on the changed CLI/sync surface
3. the corresponding SaaS deployment and smoke checks passed on
   `https://spec-kitty-dev.fly.dev/`

## Current Progress (2026-04-22)

Status: validated on `main`; the CLI lifecycle/migration lane is no longer the
active blocker for the MVP critical path.

The current monorepo implementation now extends this ADR with the
stale/abandoned mission lane required for the MVP:

1. canonical mission lifecycle derivation exists in `specify_cli.status.lifecycle`
2. `lifecycle.json` is generated alongside other derived mission views
3. `spec-kitty migrate normalize-lifecycle` can repair historical
   `kitty-specs` missions into the current lifecycle-compatible shape
4. a versioned upgrade migration exists to roll that normalization forward
5. `spec-kitty agent status lifecycle` exposes the product-facing lifecycle
   state directly in the CLI
6. targeted CLI lifecycle and migration pytest slices passed on 2026-04-22
   (`16 passed`)
7. the CLI reference docs now include both `migrate normalize-lifecycle` and
   `agent status lifecycle`, so the upgrade/inspection path is discoverable to
   users
8. the sync hardening needed to trust this lifecycle lane in SaaS is already on
   `main`:
   zero-byte dossier placeholders are skipped, queue scoping follows the
   encrypted auth session, and permanent upload failures persist structured
   diagnostics instead of collapsing to `bad_request: unknown`

With this slice validated, the active MVP lane moves back to SaaS Teamspace
projection/backfill completion under `Priivacy-ai/spec-kitty-saas#101`.
