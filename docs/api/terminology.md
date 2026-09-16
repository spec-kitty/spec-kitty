---
title: Terminology Reference
description: Terminology reference for Spec Kitty. Clear vocabulary definitions for missions, work packages, lanes, charters, and status event logs.
doc_status: active
updated: '2026-06-13'
related:
- docs/migrations/mission-id-canonical-identity.md
---
# Terminology Reference

This document defines the **target-state** canonical terminology for Spec Kitty's three-tier domain model and identity layer. All new code, CLI surfaces, documentation, and API contracts should converge on these terms.

> **Not yet implemented.** This reference describes the canonical model defined by mission 081. The current codebase still uses the pre-081 names (`project_uuid` for the locally minted identity, `project_slug` for the display label, `ProjectIdentity` for the identity class, etc.). Follow-up implementation missions will rename code, config keys, and wire protocol fields to match these definitions. Until then, treat this document as the authoritative *target* — not a description of current behavior.

**Canonical source**: Mission 081 -- Canonical Baseline and Repository Boundary

---

## The Three Domain Terms

| Term | Definition | Identity Field | Example Usage |
|------|-----------|----------------|---------------|
| **Project** | SaaS collaboration surface that groups one or more repositories under a shared identity for collaboration, visibility, and governance. A project may span multiple repositories and exists independent of any single Git checkout. | `project_uuid` (optional, SaaS-assigned) | "Bind this repository to a project" |
| **Repository** | Local Git resource (one `.git` directory) that holds mission artifacts, source code, and `.kittify/` configuration. Multiple checkouts (worktrees) of the same repository share one repository identity. | `repository_uuid` (stable, locally minted) | "Initialize a new repository" |
| **Build** | One checkout or worktree of one repository. Each build has its own working tree, `.kittify/` state snapshot, and execution context. Builds are ephemeral relative to the repository they belong to. | `build_id` (per worktree) | "This build is running lane-a" |

---

## Identity Fields

| Field | Scope | Description | Stability | Migration Note |
|-------|-------|-------------|-----------|----------------|
| `repository_uuid` | Repository | Stable local repository identity, minted once per repository. Required namespace key for body sync and deduplication. | Immutable once minted | Was mislabeled as `project_uuid` before mission 081 |
| `repository_label` | Repository | Human-readable display name derived from git remote or directory name. | Mutable; display only | Was called `project_slug` before mission 081 |
| `repo_slug` | Repository | Optional `owner/repo` Git provider reference (e.g. `spec-kitty/spec-kitty`). | Unchanged from current; optional | No change -- retains pre-081 meaning |
| `project_uuid` | Collaboration | SaaS-assigned project binding. Absent until a repository is bound to a SaaS project. Never locally minted. | Absent until binding | Was incorrectly used for locally minted repository identity |
| `mission_id` | Mission | **Canonical mission machine identity.** ULID (26 chars), minted at `agent mission create`. Aggregate key for events, selectors, and dashboard scanner. | Immutable once minted | Replaces `mission_number` as canonical identity as of mission 083 |
| `mid8` | Mission | First 8 characters of `mission_id`. Short disambiguator used in branch and worktree names. | Derived from `mission_id` | New in mission 083 |
| `mission_slug` | Mission | Human-readable kebab slug (e.g. `auth-system`). Used in directory names and as a convenience selector. | Mutable in principle; stable in practice | Pre-083 slugs embedded a `NNN-` numeric prefix; that prefix is display-only as of mission 083 |
| `mission_number` | Mission | **Display-only** numeric prefix (`int \| None`). `null` pre-merge, assigned at merge time via `max(existing)+1` inside the merge-state lock. Never used for identity, routing, or locking. | Assigned once at merge time | Was canonical identity pre-mission-083 |
| `build_id` | Build | Per-checkout/worktree identity, unique per working tree. | Stable per worktree | No change -- already correctly scoped |
| `node_id` | Machine | Stable machine fingerprint (12-char hex). | Stable per host | No change -- already correctly scoped |

See the [mission identity migration runbook](../migrations/mission-id-canonical-identity.md) for the operator upgrade path and ADR 2026-04-09-1 for the design rationale.

---

## Quick Rules

1. If you mean the local Git directory, say **repository**.
2. If you mean the SaaS collaboration group, say **project**.
3. If you mean one specific checkout or worktree, say **build**.
4. If you mean the Jira/Linear/GitHub workspace, say **tracker project** (qualified).
5. `repository_label` is a mutable display name -- never use it as a primary key.
6. `repo_slug` means `owner/repo` from the Git provider -- do not repurpose it for display names.
7. `repository_uuid` is the required namespace key for local operations -- not `project_uuid`.
8. `repository root checkout` is a location, not a branch name.
9. Use `current branch`, `primary branch`, `feature branch`, `start branch`, `target branch`, `base_branch`, `planning_base_branch`, and `merge_target_branch` when you mean branch intent.
10. Do not use `main repository`, `main repo`, or `main repository root` in new docs or prompts.

---

## Checkout and Branch Terms

| Term | Meaning | Do Not Use It To Mean |
|------|---------|------------------------|
| **repository root checkout** | The non-worktree checkout where planning commands run | The branch name |
| **current branch** | The branch checked out when planning starts | The mission's intended landing branch if it was explicitly overridden |
| **primary branch** | The repository's default integration branch, usually resolved from `origin/HEAD` | The mission's intended landing branch after `target_branch` is persisted |
| **feature branch** | A dedicated branch for pr-bound mission planning and implementation work | The protected/default branch or every lane worktree branch |
| **start branch** | The branch `agent mission create <mission_slug> --start-branch <feature-branch>` creates or switches to before writing mission scaffolding | A later merge override or a separate branch from `--target-branch` |
| **target branch** | The branch the mission records planning and merge intent against | "Whatever branch happens to be checked out later" |
| **base_branch** | At mission level, alias for `target_branch`; at WP level, the immediate parent branch for a lane worktree | A universal synonym for `main` |
| **planning_base_branch** | Canonical helper alias for the intended planning branch | A second repository or a worktree |
| **merge_target_branch** | Canonical helper alias for the intended final merge branch | Proof that the branch must be `main` |

When location and branch both matter, name both explicitly. Example: "Run `/spec-kitty.plan` from the repository root checkout on `develop`."

---

## Naming Conventions

### Variables and parameters

| Correct | Incorrect | Why |
|---------|-----------|-----|
| `repo_root` | `project_root` | It is a repository root, not a project root |
| `repository_uuid` | `project_uuid` (for local identity) | The locally minted UUID is repository-scoped |
| `repository_label` | `project_slug` (for the display name) | It is a repository label, not a project slug |
| `repo_slug` | (no change needed) | Already correct for `owner/repo` Git provider reference |

### Functions

| Correct | Incorrect |
|---------|-----------|
| `locate_repository_root()` | `locate_project_root()` |
| `get_repository_root_or_exit()` | `get_project_root_or_exit()` |
| `generate_repository_uuid()` | `generate_project_uuid()` |
| `derive_repository_label()` | `derive_project_slug()` |

### Config keys

| Correct | Incorrect |
|---------|-----------|
| `repository.repository_uuid` | `project.uuid` |
| `repository.repository_label` | `project.slug` |
| `repository.repo_slug` | `project.repo_slug` |
| `project.project_uuid` (SaaS binding only) | `project.uuid` (for local identity) |

### Wire protocol fields

| Correct | Incorrect |
|---------|-----------|
| `repository_uuid` | `project_uuid` (for locally minted identity) |
| `repository_label` | `project_slug` (for display name) |
| `repo_slug` (unchanged) | Repurposing `repo_slug` for display names |
| `project_uuid` (only when SaaS binding exists) | `project_uuid` (for local identity) |

### CLI help text

| Correct | Incorrect |
|---------|-----------|
| "Path to repository to repair" | "Path to project to repair" |
| "Name for your new repository directory" | "Name for your new project directory" |
| "Initialize a new spec-kitty repository" | "Setup tool for spec-driven development projects" |

---

## Decision Tree

Use this tree to resolve ambiguous naming cases:

```
Is the thing you're naming...
+-- The local .git directory?
|   +-- Use "repository" / repo_root / repository_uuid
+-- A specific checkout or worktree?
|   +-- Use "build" / build_id
+-- The SaaS collaboration group?
|   +-- Use "project" / project_uuid
+-- A Jira/Linear/GitHub workspace?
|   +-- Use "tracker project" / tracker_project_slug
+-- A human-readable label for the repo?
|   +-- Use repository_label (and note it's display-only, not an identity)
+-- The owner/repo Git provider reference?
|   +-- Use repo_slug (and note it's optional, unchanged from current)
+-- A namespace key for body sync or dedup?
    +-- Use repository_uuid (never project_uuid, which is optional)
```

---

## What Changed (Migration Summary)

Mission 081 established canonical definitions and identified naming drift. The renames below are the target state for follow-up implementation missions. No existing identity values are lost — only names and labels change.

| Old Name | New Name | Reason |
|----------|----------|--------|
| `project_uuid` (locally minted) | `repository_uuid` | The locally minted UUID is repository-scoped, not project-scoped |
| `project_slug` | `repository_label` | It is a repository display name, not a project slug |
| `project_root` | `repo_root` | The path refers to the repository root directory |
| `locate_project_root()` | `locate_repository_root()` | Resolves the repository, not a project |
| `get_project_root_or_exit()` | `get_repository_root_or_exit()` | Resolves the repository, not a project |
| `ProjectIdentity` | `RepositoryIdentity` | The identity class represents a repository |
| "project" (meaning local Git resource) | "repository" | Reserved "project" for SaaS collaboration surface |

Fields that are **unchanged**: `repo_slug`, `build_id`, `node_id`, `project_uuid` (when used for actual SaaS binding).
