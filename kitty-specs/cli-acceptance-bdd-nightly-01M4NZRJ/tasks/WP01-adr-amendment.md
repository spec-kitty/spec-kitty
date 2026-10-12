---
work_package_id: WP01
title: ADR amendment — record the owner ruling
dependencies: []
requirement_refs:
- FR-001
- FR-014
- C-003
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Governance
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/adr/4.x/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-11-3-acceptance-testing-and-bdd-support.md
role: curator
tags: []
task_type: specify
tracker_refs: []
---

# Work Package Prompt: WP01 – ADR amendment — record the owner ruling

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

This is the mission's **first deliverable**. Amend ADR
`docs/adr/4.x/2026-10-11-3-acceptance-testing-and-bdd-support.md` (Status: Accepted) to record
the **owner ruling of 2026-10-11** that narrows promise machinery out of core, WITHOUT rewriting
the original decision.

Done when:
- An **Amendment** section records the four items moved out of core scope (below).
- The consequences (the `scenarios`-group gating flip; inert tags) are stated.
- The original "Decision" text is preserved verbatim; the ADR reads coherently with the amendment.

## Context & Constraints

- Read the ADR in full first, and `kitty-specs/cli-acceptance-bdd-nightly-01M4NZRJ/research.md` §0 and §7 — the grounding already reconciled the contradiction.
- **Grounded fact**: `tests/scenarios/promise-index.json`, `tests/architectural/test_scenario_promise_tags.py`, and `PROMISE_INDEX_SYNC_TOKEN` **do not exist in the tree**. The accepted ADR specified them; they were never built. So the amendment records a *narrowing of a never-built plan*, not the deletion of code.
- This is a `planning_artifact` WP: it touches **only** the ADR under `docs/`. Do not edit code, CI, or `src/`.
- Spec refs: FR-001, FR-014, C-003.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

> Populated by `spec-kitty agent mission finalize-tasks`; do not change manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Amendment section: the four narrowed items

- **Purpose**: Record what leaves core scope.
- **Steps**: Add a new section, e.g. `## Amendment (2026-10-11 owner ruling)`, stating that the following belong to **spec-kitty-qa**, not core, and were never built here:
  1. `tests/scenarios/promise-index.json` (the public promise-index slice + its `schema_version`),
  2. the per-PR check `tests/architectural/test_scenario_promise_tags.py`,
  3. the `PROMISE_INDEX_SYNC_TOKEN` org sync (the ADR's Open Question 1),
  4. the act of turning a promise into a scenario (promise→scenario mapping).
- **Notes**: Name the owner (Stijn Dejongh) and the date; cross-reference spec-kitty-qa ADR-0001/0002 as the owning home.

### Subtask T002 – Amendment section: consequences and tag semantics

- **Purpose**: State what the narrowing changes for the parts core keeps.
- **Steps**: In the same amendment, record:
  - The `scenarios` ci-router group now gates **no** per-PR job (the accepted ADR had it "gate the architectural job"; that job was the dropped promise-tag check). `acceptance_jvm` still gates no job.
  - Core keeps scenarios, the runner and the nightly.
  - Tags `@promise:<id>`, `@defect:<issue>`, `@qa:SC-A-NNN` are **inert in core**; only `@wip` and `@manual` have meaning — each excludes a scenario from the gating nightly run. `@manual` is an allowed tag (reserved for heavy/on-demand scenarios).
- **Notes**: Keep it crisp; this is the authoritative record the implementation points back to.

### Subtask T003 – Preserve the original decision; keep coherence

- **Purpose**: Amend, don't rewrite.
- **Steps**: Leave the original "Decision", "Context", "Considered Options" and "Consequences" intact. Update only the front-matter/Status area with a one-line pointer like `Amended 2026-10-11 — see Amendment section` so a reader is not misled by the now-superseded promise-machinery paragraphs. Optionally annotate the superseded paragraphs with a parenthetical pointer to the amendment, but do not delete them.
- **Notes**: The ADR must read coherently end to end after the edit.

## Risks & Mitigations

- **Rewriting history**: never delete the original Decision; add an Amendment section and a Status pointer only.

## Review Guidance

- Confirm all four narrowed items and the `scenarios`-gates-no-job flip are recorded, the original Decision is intact, and the ADR is internally consistent.

## Progress & Status

Progress/history/status live in the status event log — never in this file.
- Record a note: `spec-kitty agent tasks add-history WP01 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP01 --to <status>`

## Activity Log

- 2026-10-11T18:41:49Z – claude – shell_pid=3076381 – Amended ADR 2026-10-11-3: added '## Amendment (2026-10-11 owner ruling)' recording the four promise-machinery items (promise-index.json, test_scenario_promise_tags.py, PROMISE_INDEX_SYNC_TOKEN, promise->scenario mapping) as owned by spec-kitty-qa and never built in core; recorded the scenarios-group gates-no-job flip and inert @promise/@defect/@qa tags (@wip/@manual meaningful); added Status pointer and annotated Open Question 1. Original Decision/Context/Options/Consequences preserved verbatim.
