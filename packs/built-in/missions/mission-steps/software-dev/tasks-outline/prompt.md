---
description: Create a work package manifest
---
# /spec-kitty.tasks-outline - Create Work Package Manifest

**Version**: 3.2.0

## Purpose

Create `wps.yaml` — the structured work package manifest that defines WP metadata,
dependencies, and file ownership. `tasks.md` is generated automatically from this
manifest by `finalize-tasks`.

> ⚠️ DO NOT write `tasks.md`. The system generates it from `wps.yaml`. Writing
> `tasks.md` manually will have it overwritten by `finalize-tasks`.

## ⚠️ CRITICAL: THIS IS THE MOST IMPORTANT PLANNING WORK

**You are creating the blueprint for implementation**. The quality of work packages determines:
- How easily agents can implement the feature
- How parallelizable the work is
- How reviewable the code will be
- Whether the feature succeeds or fails

**QUALITY OVER SPEED**: Take your time to understand the full scope deeply,
break work into clear pieces, and write detailed guidance.

---

## 📍 WORKING DIRECTORY: Stay in the repository root checkout

**IMPORTANT**: This step works in the repository root checkout. NO worktrees created.

**Do NOT cd anywhere**. Stay in the repository root checkout.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Context Resolution

Before proceeding, resolve canonical command context:

```bash
spec-kitty agent context resolve --action tasks_outline --mission <mission-slug> --json
```

Treat that JSON as canonical for feature slug, feature directory, and target branch.
Do not probe git branch state manually inside the prompt.

## Steps

### 1. Setup

Run the exact `check_prerequisites` command returned by the resolver. Capture
`feature_dir` plus `available_docs`. All paths must be absolute.

**CRITICAL**: The command returns JSON with `feature_dir` as an ABSOLUTE path. **YOU MUST USE THIS PATH** for ALL subsequent file operations.

### 2. Load Design Documents

Read from `feature_dir` (only those present):
- **Required**: plan.md (tech architecture, stack), spec.md (user stories & priorities)
- **Optional**: data-model.md (entities), contracts/ (API schemas), research.md (decisions), quickstart.md (validation scenarios)

Scale your effort to the feature: simple UI tweaks deserve lighter coverage, multi-system releases require deeper decomposition.

### 3. Derive Fine-Grained Subtasks

Create complete list of subtasks with IDs `T001`, `T002`, etc.:
- Parse plan/spec to enumerate concrete implementation steps, tests (only if explicitly requested), migrations, and operational work.
- Capture prerequisites, dependencies, and parallelizability markers (`[P]` means safe to parallelize per file/concern).
- Assign IDs sequentially in execution order.
- **Ideal granularity**: One clear action (e.g., "Create user model", "Add login endpoint")

### 4. Roll Subtasks into Work Packages

Group subtasks into work packages (IDs `WP01`, `WP02`, ...):

**TARGET SIZE**: 3-7 subtasks per WP (200-500 line prompts)
**MAXIMUM**: 10 subtasks per WP (700 line prompts)
**If more than 10 subtasks needed**: Create additional WPs, don't pack them in

**GROUPING PRINCIPLES**:
- Each WP should be independently implementable
- Root in a single user story or cohesive subsystem
- Ensure every subtask appears in exactly one work package
- Name with succinct goal (e.g., "User Story 1 – Real-time chat happy path")
- Record metadata: priority, success criteria, risks, dependencies, included subtasks, and requirement references
- Every WP must include a `requirement_refs` list referencing IDs from `spec.md` (FR/NFR/C)

### 4a. Cite plan concern refs for each WP

For each work package, record which implementation concern(s) from `plan.md` it
addresses by populating `plan_concern_refs` in `wps.yaml`.

- If the WP covers exactly one concern: `plan_concern_refs: [IC-01]`
- If the WP spans multiple concerns: `plan_concern_refs: [IC-01, IC-03]`
- If the WP is cross-cutting infrastructure with no specific concern (e.g. a test
  harness setup WP), set `cross_cutting: true` and leave `plan_concern_refs` empty.

A WP missing both `plan_concern_refs` and `cross_cutting: true` will trigger a
warning from `finalize-tasks`. Every WP should cite at least one IC-## ref or
declare itself cross-cutting.

### 5. Write `wps.yaml`

Write to `feature_dir/wps.yaml` following the schema below. This is the **single
authoritative source** for WP metadata in the planning pipeline.

**Do NOT write `tasks.md` — it is generated automatically by `finalize-tasks` from `wps.yaml`.**

**Schema**:

```yaml
work_packages:
  - id: WP01
    title: "Foundation Setup"
    dependencies: []          # [] = explicitly no deps (authoritative)
    owned_files:
      - "src/myapp/core/**"
    requirement_refs:
      - FR-001
      - FR-002
    plan_concern_refs:
      - IC-01
    subtasks:
      - T001
      - T002
      - T003
    prompt_file: "tasks/WP01-foundation-setup.md"

  - id: WP02
    title: "API Layer"
    dependencies:
      - WP01
    owned_files:
      - "src/myapp/api/**"
    requirement_refs:
      - FR-003
    plan_concern_refs:
      - IC-02
      - IC-03
    subtasks:
      - T004
      - T005
    prompt_file: "tasks/WP02-api-layer.md"

  - id: WP03
    title: "Frontend Integration"
    dependencies:
      - WP02
    owned_files:
      - "src/myapp/frontend/**"
    requirement_refs:
      - FR-004
      - NFR-001
    plan_concern_refs:
      - IC-04
    subtasks:
      - T006
      - T007
      - T008
    prompt_file: "tasks/WP03-frontend-integration.md"
```

**Field semantics**:
- `id`: Work package identifier (`WP01`, `WP02`, …)
- `title`: Short human-readable name
- `dependencies`: List of WP IDs this WP depends on. `[]` = explicitly no deps (authoritative); if the key is **absent**, `tasks-packages` may fill it based on analysis.
- `owned_files`: Glob patterns for files this WP touches — no two WPs may overlap. A `code_change` WP must NOT list any `kitty-specs/` path here (see the staged ownership rule below).
- `requirement_refs`: Requirement IDs from `spec.md` (FR/NFR/C) addressed by this WP.
- `plan_concern_refs`: Implementation concern IDs from `plan.md` (IC-##) addressed by this WP. Use `cross_cutting: true` instead if the WP is shared infrastructure with no specific concern.
- `cross_cutting`: Set to `true` for infrastructure WPs that span all concerns and have no specific IC-## ref.
- `subtasks`: Ordered list of subtask IDs included in this WP.
- `prompt_file`: Relative path (from `feature_dir`) to the WP prompt file — set by `tasks-packages` in the next step.

**IMPORTANT**: Leave `prompt_file` as `null` or omit it — `tasks-packages` fills this field.

**Staged ownership rule**:
- A `code_change` WP must NOT list any `kitty-specs/` path in `owned_files` — `finalize-tasks --validate-only` rejects it with `INVALID_WP_OWNED_FILES_KITTY_SPECS`.
- The only exemption is a `planning_artifact` WP whose **every** `owned_files` entry is confined to `kitty-specs/` or `docs/`. A planning WP that also owns a `src/`, `tests/`, or any other non-planning path is not exempt and is rejected the same way.
- Per-WP design notes, plan-marker edits, and other `kitty-specs/` deliverables belong in their own separate confined `planning_artifact` WP. Split a mixed WP into a planning WP plus a code WP rather than mixing the two ownership kinds.

### 6. Analyze Dependencies

Analyze the spec and plan for dependency relationships. Express them in `wps.yaml`
`dependencies` fields.

**Do NOT include a Dependency Graph section in prose — it is not needed and cannot
be parsed by `finalize-tasks`.**

Rules:
- A WP with no predecessors: `dependencies: []`
- A WP that depends on another: `dependencies: [WP01]`
- Phase grouping: Phase 2 WPs typically depend on Phase 1 WPs

**DO NOT generate WP prompt files in this step.** That happens in the next step.

## Output

After completing this step:
- `feature_dir/wps.yaml` exists with all work package definitions
- Each WP has `id`, `title`, `dependencies`, `owned_files`, `requirement_refs`, `subtasks`
- `prompt_file` fields are absent or `null` (filled by `tasks-packages`)
- No WP prompt files have been created yet

**Next step**: `spec-kitty next --agent <name>` will advance to work package generation.

## Work Package Sizing Guidelines

**Target: 3-7 subtasks per WP** → 200-500 line prompts
**Maximum: 10 subtasks** → ~700 line prompts
**No arbitrary limit on WP count** — let complexity dictate

**Split if ANY of these are true**:
- More than 10 subtasks
- Prompt would exceed 700 lines
- Multiple independent concerns mixed together
- Different phases or priorities mixed

**Merge if ALL of these are true**:
- Each WP has <3 subtasks
- Combined would be <7 subtasks
- Both address the same concern/component
- No natural parallelization opportunity

Context for work-package planning: (refer to the User Input section above)
