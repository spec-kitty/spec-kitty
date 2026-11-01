---
title: Use the wps.yaml Manifest
description: How to use the wps.yaml manifest with Spec Kitty 3.2, including work-package dependencies and plan-concern traceability.
doc_status: active
updated: '2026-06-06T00:00:00Z'
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/missions/create-plan.md
- docs/guides/how-to/missions/generate-tasks.md
kind: How-To
---
# Use the `wps.yaml` Manifest

Learn about the structured work-package manifest format introduced in 3.1.0 and how it fits into the `finalize-tasks` workflow.

## What is `wps.yaml`?

`wps.yaml` is a machine-readable manifest at `kitty-specs/<mission>/wps.yaml`. It is the authoritative structured source of work-package definitions, replacing the previous approach of extracting dependency graphs by parsing prose in `tasks.md`.

For modern software-development missions, `wps.yaml` also records which plan-level implementation concern each WP addresses. Implementation concerns are the `IC-##` entries in `plan.md`; they are not executable units. Work packages are the executable units.

## Why It Exists

Before `wps.yaml`, `finalize-tasks` had to parse natural-language task descriptions to extract dependency graphs and file ownership. This was fragile: ambiguous phrasing, markdown formatting changes, or prose rewrites would silently alter the computed lane graph.

`wps.yaml` replaces that unbounded prose-parser with a structured contract: the LLM writes the manifest directly during `/spec-kitty.tasks-outline`, and `finalize-tasks` reads it deterministically.

## Fields

```yaml
# kitty-specs/042-auth-system/wps.yaml
work_packages:
  - id: WP01
    title: "Set up database schema"
    dependencies: []          # present and empty = no deps; never overwritten
    owned_files:
      - src/models/user.py
      - migrations/0001_initial.py
    requirement_refs:
      - FR-001
    plan_concern_refs:
      - IC-01
    subtasks:
      - "Create User model"
      - "Write migration"
    prompt_file: tasks/WP01.md

  - id: WP02
    title: "Implement login endpoint"
    dependencies: [WP01]
    owned_files:
      - src/views/auth.py
    requirement_refs:
      - FR-002
    plan_concern_refs:
      - IC-02
    subtasks:
      - "POST /api/login handler"
      - "JWT token generation"
    prompt_file: tasks/WP02.md

  - id: WP03
    title: "Shared test harness"
    dependencies: []
    owned_files:
      - tests/auth/**
    requirement_refs:
      - NFR-001
    plan_concern_refs: []
    cross_cutting: true
    subtasks:
      - "Create reusable auth fixtures"
    prompt_file: tasks/WP03.md
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Work-package identifier (e.g., `WP01`) |
| `title` | Yes | Short human-readable name |
| `dependencies` | No | List of WP IDs this WP depends on. **Key invariant**: once present (even as `[]`), this field is never overwritten by the pipeline. |
| `owned_files` | No | Files this WP exclusively writes. Used for parallelism assignment (see [Parallelism Preservation](../../../architecture/execution-lanes.md#parallelism-preservation)). |
| `requirement_refs` | No | Requirement IDs from `spec.md` this WP implements |
| `plan_concern_refs` | No | `IC-##` implementation concern IDs from `plan.md` this WP addresses |
| `cross_cutting` | No | Set to `true` when a WP is shared infrastructure with no specific IC-## concern |
| `subtasks` | No | Fine-grained checklist items inside the WP |
| `prompt_file` | No | Path to the WP prompt (defaults to `tasks/<id>.md`) |

## Plan-Concern Traceability

`/spec-kitty.plan` creates an **implementation concern map** in `plan.md` for non-trivial missions. Those `IC-##` entries describe architectural intent, sequencing, affected surfaces, and risks.

`/spec-kitty.tasks` translates those concerns into executable `WP##` units. The mapping is many-to-many:

- One concern may split into several WPs.
- One small WP may cover multiple concerns.
- A shared infrastructure WP may use `cross_cutting: true` instead of `plan_concern_refs`.

`plan_concern_refs` belongs only in `wps.yaml`. Do not copy it into WP prompt frontmatter; WP prompt frontmatter rejects unknown fields.

## How `/spec-kitty.tasks-outline` Produces `wps.yaml`

During the `tasks-outline` workflow step, the agent writes `wps.yaml` directly (not `tasks.md`). The LLM receives the spec and plan and emits a structured manifest. This is the canonical source of WP definitions.

## How `finalize-tasks` Uses It

`finalize-tasks` reads `wps.yaml` and:

1. Validates each entry as a structured work-package manifest
2. Computes the lane graph from `dependencies` and `owned_files`
3. Writes `lanes.json` with the computed assignment and a `collapse_report`
4. Regenerates `tasks.md` as a human-readable derived artifact, including `Plan Concerns` lines when `plan_concern_refs` is present

`tasks.md` is now a **derived view** of `wps.yaml`. Do not hand-edit it; edit `wps.yaml` instead, then re-run `finalize-tasks`.

## Key Invariant: `dependencies` Is Never Overwritten

If a WP's `dependencies` field is present in `wps.yaml` (even as an empty list `[]`), the pipeline treats it as authoritative and never overwrites it. This lets you explicitly declare that a WP has no dependencies even if the file-overlap analysis would suggest otherwise.

## JSON Schema

The schema is at `src/specify_cli/schemas/wps.schema.json`. Validate manually with:

```bash
python -m jsonschema --instance kitty-specs/042-auth-system/wps.yaml \
  src/specify_cli/schemas/wps.schema.json
```

## Backward Compatibility

Missions without a `wps.yaml` continue to work. `finalize-tasks` falls back to the prose parser for those missions. New missions created with spec-kitty 3.1.0+ will always produce a `wps.yaml`.

Existing `wps.yaml` files without `plan_concern_refs` continue to parse and finalize without concern-traceability warnings when their `plan.md` has no `IC-##` concern headings. Once a manifest opts in by adding `plan_concern_refs` or `cross_cutting`, or the mission plan contains an implementation concern map with `IC-##` headings, `finalize-tasks` warns for any WP missing both.

## See Also

- [Parallelism Preservation](../../../architecture/execution-lanes.md#parallelism-preservation) — how `owned_files` drives lane assignment
- [Create a Plan](create-plan.md) — how implementation concerns are created
- [Generate Tasks](generate-tasks.md) — the full task generation workflow
- [CLI Reference: spec-kitty tasks](../../../api/cli-commands.md#spec-kitty-tasks)
