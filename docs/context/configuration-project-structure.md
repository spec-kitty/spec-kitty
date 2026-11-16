---
title: 'Context: Configuration and Project Structure'
description: Glossary context defining where policy, runtime configuration, and mission artifacts live in a Spec Kitty project (.kittify/, kitty-specs/, and related terms).
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to know where configuration, charter files and Mission artifacts live in a project.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before writing a path under .kittify/, kitty-specs/ or .worktrees/, so the path matches the code.
related:
- context/charter
- context/execution
- context/governance
- context/identity
- context/orchestration
- context/system-events
---
## Context: Configuration and Project Structure

Terms describing where policy, runtime configuration, and mission artifacts live in a Spec Kitty project.

### `.kittify/`

| | |
|---|---|
| **Definition** | Project-local configuration and shared memory directory. |
| **Context** | Configuration & Project Structure |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Key contents** | `config.yaml` (agents, project identity, charter packs), `charter/` (`charter.md`, `charter.yaml`, `activation.yaml`, `interview/answers.yaml`), `glossaries/` (glossary seed files), `metadata.yaml` and `migration-ledger.jsonl` (migration metadata), `events/` and `runtime/` (local event logs and consolidation state) |
| **Related terms** | [Charter](./governance.md#charter), [Mission](./orchestration.md#mission) |

---

### `kitty-specs/`

| | |
|---|---|
| **Definition** | Holds one Mission directory per Mission (`kitty-specs/<mission_slug>/`), with its planning artifacts (`spec.md`, `plan.md`, `tasks.md`, `tasks/`, plus supporting files), `meta.json` and the status event log `status.events.jsonl`. |
| **Context** | Configuration & Project Structure |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Mission](./orchestration.md#mission), [work package](./orchestration.md#work-package) |

---

### `.worktrees/`

| | |
|---|---|
| **Definition** | Holds the Git worktrees a Mission's execution lanes use: one lane worktree per lane (`.worktrees/<slug>-lane-<id>`) and, for a coordination topology, the coordination worktree (`<Mission directory>-coord`). A `single_branch` Mission has no lane worktree: its work packages run in the write checkout. |
| **Context** | Configuration & Project Structure |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [work package](./orchestration.md#work-package), [Lane](./orchestration.md#lane) |

---

### `glossary/`

| | |
|---|---|
| **Definition** | Policy-level language authority for terminology and semantic contracts. A project has no top-level `glossary/` directory: the glossary seed files live in `.kittify/glossaries/<scope>.yaml`, and the glossary code lives in `src/glossary/`. |
| **Context** | Configuration & Project Structure |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Glossary Scope](./system-events.md#glossary-scope), [Semantic Check](./execution.md#semantic-check) |

---

### Bootstrap (Candidate)

| | |
|---|---|
| **Definition** | Proposed onboarding flow to collect project intent, constraints, and glossary context early. It is not a CLI command: today `spec-kitty charter interview` captures the charter answers. Not to be confused with the bootstrap mode of charter context loading ([Bootstrap vs Compact Context](./charter-overview.md#bootstrap-vs-compact-context)). |
| **Context** | Configuration & Project Structure |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Charter](./governance.md#charter), [Mission](./orchestration.md#mission) |

---

### Project Charter

| | |
|---|---|
| **Definition** | The compiled, project-specific charter containing the HiC's governance decisions, activation choices, interview answers, and reference manifest. Stored in `.kittify/charter/`: decisions in `charter.md` and `charter.yaml`, activation choices in `activation.yaml`, interview answers in `interview/answers.yaml`, and the reference manifest as the `catalog` section of `charter.yaml` (it replaced the retired `references.yaml`). Use "Project Charter" when distinguishing from the Charter Library. |
| **Context** | Configuration & Project Structure |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Charter](./governance.md#charter), [Charter Library](#charter-library), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### Charter Library

| | |
|---|---|
| **Definition** | The project-local collection of doctrine source documents that the HiC has selected, stored alongside the Project Charter and indexed by a reference manifest. The compiler writes no separate library directory today: the references are listed in the `catalog` section of `charter.yaml` (`_build_catalog_dict` in `src/charter/activation/compiler.py`). |
| **Context** | Configuration & Project Structure |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Project Charter](#project-charter), [Charter offering](./charter.md#charter-offering) |
