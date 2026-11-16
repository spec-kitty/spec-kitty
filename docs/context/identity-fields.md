---
title: 'Context: Identity Fields'
description: 'Glossary context for the 3-tier identity model from mission 081: the repository, collaboration, and build/machine identity fields and their boundaries.'
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to know which identity field the code stores, where it is written, and how it is derived.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before naming an identity field in output or code, so you use the code name and note the mission 081 name.
related:
- context/orchestration
---
## Context: Identity Fields

Terms describing the 3-tier identity model that mission 081 defined as a terminology contract. Mission 081 named the fields; it did not rename them in the code. The code still uses the earlier names (`ProjectIdentity` in `src/specify_cli/identity/project.py`, written by `spec-kitty init` to `.kittify/config.yaml` under `project:` as `uuid`, `slug`, `node_id`, `build_id` and an optional `repo_slug`). Each entry below says what the code holds today. The identity layer separates three boundary levels:

- **Repository** (`repository_uuid`, `repository_label`, `repo_slug`): The local Git resource. `repository_uuid` is the primary stable identity, minted once per repository. `repo_slug` is the optional `owner/repo` Git provider reference.
- **Collaboration** (`project_uuid`): In mission 081's contract, an optional external binding to a hosted project. Nothing in open-core assigns it (#6164); in the code, `project_uuid` is the locally minted repository identity.
- **Build / Machine** (`build_id`, `node_id`): Build and machine fingerprints for execution context isolation.

See `kitty-specs/081-canonical-baseline-and-repository-boundary/spec.md` for the full contract.

### repository_uuid

| | |
|---|---|
| **Definition** | Stable local repository identity, minted once per repository. Mission 081 gave this name to the value the code calls `project_uuid`. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Repository |
| **Note** | This is the primary local identity. It must never be reassigned or reused across different repositories. The code has not been renamed: the value is still stored as `project.uuid` in `.kittify/config.yaml`. |
| **Code today** | No `repository_uuid` field exists in `src/`. The value is still `ProjectIdentity.project_uuid`, a UUID4 that `spec-kitty init` mints locally and writes to `.kittify/config.yaml` as `project.uuid` (`generate_project_uuid`, `ensure_identity`). |
| **Related terms** | [repository_label](#repository_label), [project_uuid](#project_uuid), [Repository](./orchestration.md#repository) |

---

### repository_label

| | |
|---|---|
| **Definition** | Human-readable repository display name derived from git remote or directory name. Mutable, not a stable identity. Mission 081 gave this name to the value the code calls `project_slug`. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Repository |
| **Note** | Display-only value used in CLI output. Must not be used as a namespace key or deduplication anchor because it can change. |
| **Code today** | No `repository_label` field exists in `src/`. The value is still `ProjectIdentity.project_slug`, written as `project.slug` and derived from the git remote's repository name or, without a remote, the directory name (`derive_project_slug`). |
| **Related terms** | [repository_uuid](#repository_uuid), [repo_slug](#repo_slug), [Repository](./orchestration.md#repository) |

---

### project_uuid

| | |
|---|---|
| **Definition** | In mission 081's contract: an optional collaboration identity that a hosted service would assign when a repository is bound to a project. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Collaboration |
| **Note** | The hosted surfaces were removed from open-core (#6164), so nothing in this repository assigns such an identity. |
| **Code today** | The field named `project_uuid` in the code is the locally minted repository identity that 081 calls [repository_uuid](#repository_uuid): `spec-kitty init` generates it as a UUID4 and writes it to `.kittify/config.yaml` as `project.uuid`. It is locally minted, not assigned. |
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
| **Note** | In the code it is an optional operator override stored as `project.repo_slug`; it is not generated automatically (`ProjectIdentity.with_defaults`). This is a repository-scoped field: it names the repository on the Git provider, not a hosted collaboration binding. |
| **Related terms** | [repository_label](#repository_label), [repository_uuid](#repository_uuid), [Repository](./orchestration.md#repository) |

---

### build_id

| | |
|---|---|
| **Definition** | Build identity, written to `.kittify/config.yaml` as `project.build_id`. Unchanged from pre-081. |
| **Context** | Identity Fields |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Scope** | Build |
| **Note** | When it is missing, the code derives it deterministically as a UUID5 of `project_uuid` and `node_id` (`derive_build_id`), so one project on one machine gets the same value across calls. |
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
| **Note** | The first 12 hex characters of a SHA-256 of the hostname and user name (`generate_node_id`), so it is stable across CLI restarts and differs per user on a shared machine. Used alongside `build_id` to fully qualify an execution context. |
| **Related terms** | [build_id](#build_id), [repository_uuid](#repository_uuid) |
