---
title: 'Context: Identity Fields'
description: 'Glossary context for the 3-tier identity model from mission 081: the repository, collaboration, and build/machine identity fields and their boundaries.'
doc_status: active
updated: '2026-04-10'
related:
- docs/context/orchestration.md
---
## Context: Identity Fields

Terms describing the 3-tier identity model introduced in mission 081. The identity layer separates three boundary levels:

- **Repository** (`repository_uuid`, `repository_label`, `repo_slug`): The local Git resource. `repository_uuid` is the primary stable identity, minted once per repository and used as the namespace key for body sync and deduplication. `repo_slug` is the optional `owner/repo` Git provider reference.
- **Collaboration** (`project_uuid`): Optional external binding. `project_uuid` is a SaaS-assigned identity that is absent until a repository is explicitly bound to a project.
- **Build / Machine** (`build_id`, `node_id`): Per-checkout and per-machine fingerprints for execution context isolation.

See `kitty-specs/081-canonical-baseline-and-repository-boundary/spec.md` for the full contract.

### repository_uuid

| | |
|---|---|
| **Definition** | Stable local repository identity, minted once per repository. Required namespace key for body sync and deduplication. Was mislabeled as `project_uuid` before mission 081. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Repository |
| **Note** | This is the primary local identity. It must never be reassigned or reused across different repositories. Prior to mission 081, this value was stored under the key `project_uuid` in config.yaml. |
| **Related terms** | [repository_label](#repository_label), [project_uuid](#project_uuid), [Repository](./orchestration.md#repository) |

---

### repository_label

| | |
|---|---|
| **Definition** | Human-readable repository display name derived from git remote or directory name. Mutable, not a stable identity. Was called `project_slug` before mission 081. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Repository |
| **Note** | Display-only value used in CLI output and SaaS dashboards. Must not be used as a namespace key or deduplication anchor because it can change. |
| **Related terms** | [repository_uuid](#repository_uuid), [repo_slug](#repo_slug), [Repository](./orchestration.md#repository) |

---

### project_uuid

| | |
|---|---|
| **Definition** | Optional SaaS-assigned collaboration identity. Absent until a repository is bound to a SaaS project. Never locally minted. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Collaboration |
| **Note** | A repository operates fully offline without a `project_uuid`. This field is populated only when the user binds the repository to a SaaS project via explicit action. Before mission 081, this key name was incorrectly used for what is now `repository_uuid`. |
| **Related terms** | [repository_uuid](#repository_uuid), [repo_slug](#repo_slug), [Project](./orchestration.md#project) |

---

### repo_slug

| | |
|---|---|
| **Definition** | Optional `owner/repo` Git provider reference (e.g. `spec-kitty/spec-kitty`). Unchanged from pre-081 meaning. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Repository |
| **Note** | Derived from the git remote URL. Used for GitHub/GitLab integration features. Absent when no remote is configured. This is a repository-scoped field — it identifies the repository on the Git provider, not a SaaS collaboration binding. |
| **Related terms** | [repository_label](#repository_label), [repository_uuid](#repository_uuid), [Repository](./orchestration.md#repository) |

---

### build_id

| | |
|---|---|
| **Definition** | Per-checkout/worktree identity, unique per working tree. Unchanged from pre-081. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Build |
| **Note** | Each worktree or checkout of the same repository gets its own `build_id`. Used to isolate execution context and prevent cross-worktree state collisions. |
| **Related terms** | [node_id](#node_id), [repository_uuid](#repository_uuid), [Build](./orchestration.md#build) |

---

### node_id

| | |
|---|---|
| **Definition** | Stable machine fingerprint (12-char hex). Unchanged from pre-081. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Machine |
| **Note** | Identifies the physical or virtual machine running the build. Stable across reboots. Used alongside `build_id` to fully qualify an execution context. |
| **Related terms** | [build_id](#build_id), [repository_uuid](#repository_uuid) |
