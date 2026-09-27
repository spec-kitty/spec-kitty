---
work_package_id: WP04
title: Docs prose + CLAUDE.md campsite
dependencies:
- WP01
requirement_refs:
- C-003
- C-006
- C-008
- FR-008
- NFR-004
planning_base_branch: feat/consolidate-canonical-terminology
merge_target_branch: feat/consolidate-canonical-terminology
branch_strategy: Planning artifacts for this mission were generated on feat/consolidate-canonical-terminology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidate-canonical-terminology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-canonical-terminology-01M3GSSV
base_commit: 3539a24878d4d391919dcb7b45605ca6ad8e1bda
created_at: '2026-09-27T11:36:21.015337+00:00'
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 2 - High-value docs prose
history:
- at: '2026-09-27T07:39:01Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- docs/context/orchestration.md
- docs/context/ops-vs-missions.md
- docs/architecture/git-workflow.md
- docs/architecture/spec-kitty-mission-workflow.md
- docs/architecture/mission-system.md
- docs/development/how-to/review-gates.md
- docs/guides/how-to/missions/accept-and-merge.md
- docs/guides/how-to/recovery/recover-from-interrupted-merge.md
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Docs prose + CLAUDE.md campsite

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!** Check the `review_ref` field (`spec-kitty agent tasks status`) and address all feedback before completion.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Convert the high-value **active** doc files to `consolidate` for the lane-consolidation sense,
and fix the stale `CLAUDE.md:396` `merge-state.json` reference (the modern file is `state.json`).
Defer the long-tail/archival prose (C-008) and never touch immutable history or generated docs.

Complete when:

- The owned doc files read `consolidate` for the lane-consolidation sense; git-merge/publish prose is intact (C-003). *(FR-008)*
- `CLAUDE.md:396` reads `state.json` (campsite fix, DIRECTIVE_025). *(FR-008)*
- Deferred/immutable trees untouched; the WP01 drift-guard is green over `docs/`. *(NFR-004, C-006, C-008)*

## Context & Constraints

- **Authoritative reads**: `.kittify/charter/charter.md`, [`plan.md`](../plan.md) (IC-06), [`spec.md`](../spec.md) FR-008, [`occurrence_map.yaml`](../occurrence_map.yaml).
- **`occurrence_map.yaml` is the classification authority (C-001).** `docs/**` is `manual_review`; v1 converts the ~5–8 high-value files below only. Classify each site: convert only the **lane-consolidation sense**; keep `git merge`/publish verbatim (C-003).
- **C-008 — long-tail deferred.** Do NOT convert `docs/plans/**`, engineering-notes, investigations, retros, or user-journey archives — the WP01 shrink-only ratchet grandfathers them; they are boyscouted over time.
- **C-006 — immutable history untouched.** Do NOT touch `docs/adr/**` or `docs/changelog/**`.
- **Boundary**: `docs/api/**` is **generated** and owned by **WP01** (regenerated via `build_cli_reference.py`). **WP04 must not write `docs/api/**`.** `src/`, `tests/`, `packs/`, generated agent dirs belong to other WPs.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: `feat/consolidate-canonical-terminology`
- **Merge target branch**: `feat/consolidate-canonical-terminology`

## Subtasks & Detailed Guidance

### T024 – `docs/context/` canon
- **Purpose**: The orchestration glossary/routing canon is the highest-value reader surface (named in plan IC-06 + the terminology footguns).
- **Steps**: Convert lane-consolidation-sense `spec-kitty merge`/prose in `docs/context/orchestration.md` and `docs/context/ops-vs-missions.md`. Preserve the `#lane-consolidation` / `#branch-integration--git-merge` / `#publish-to-originmain` glossary distinctions — the whole point is that git-merge and publish keep their words.

### T025 – [P] `docs/architecture/`
- **Purpose**: The workflow/architecture docs describe the settled command.
- **Steps**: Convert lane-consolidation-sense sites in `docs/architecture/git-workflow.md`, `spec-kitty-mission-workflow.md`, `mission-system.md`. Keep git-integration mechanics ("merge commit", `git merge --no-ff`, merge drivers) verbatim.

### T026 – [P] `docs/development/` + `docs/guides/how-to/`
- **Purpose**: Active how-to guidance.
- **Steps**: Convert `docs/development/how-to/review-gates.md`, `docs/guides/how-to/missions/accept-and-merge.md`, `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`. Where a heading/filename references "merge" as the lane-consolidation step, convert the prose (leave filenames as-is unless trivially safe — file renames are out of v1 scope).

### T027 – CLAUDE.md campsite
- **Purpose**: Correct the stale `merge-state.json` claim.
- **Steps**: (a) `CLAUDE.md:396` "Merge progress saved in `.kittify/merge-state.json`…" → the modern file is `state.json` under `.kittify/runtime/merge/<id>/`. Fix the filename reference; keep the frozen `state.json` name (DIRECTIVE_025 campsite fix). (b) **MAJOR-2 self-drift (post-tasks squad):** the `## Merge & Preflight Patterns` block in `CLAUDE.md` documents `MergeState`, `Import from specify_cli.merge: …`, `merge/state.py`, `_run_lane_based_merge` — ALL renamed by WP01 (dep). Convert these code-identifier references to `ConsolidationState` / `specify_cli.consolidation` / `consolidation/state.py` / `_run_lane_based_consolidation` so the always-loaded dev guide does not describe non-existent symbols. Keep the FROZEN keeps verbatim where CLAUDE.md names them (`baseline_merge_commit`, `MergeStrategy` values, `state.json`). This block is repo-root `CLAUDE.md`, NOT covered by the occurrence-map `docs/**` deferral — it must be converted here, not deferred.

## Test Strategy

- `pytest tests/architectural/test_no_legacy_terminology.py -q` — the WP01 ratchet scans `docs`; expect green over the converted files (≈0.1 s).
- Grep each owned file for residual lane-consolidation-sense `spec-kitty merge` (expect none) and for surviving `git merge`/publish lines (expect intact).
- Confirm `docs/api/**`, `docs/adr/**`, `docs/changelog/**`, `docs/plans/**` untouched (`git status`).
- Record commands + counts in the PR *Tests run* section.

## Risks & Mitigations

- **Over-reaching into archival/immutable artifacts** → obey occurrence_map exceptions; defer `docs/plans/**`, `docs/adr/**`, `docs/changelog/**`.
- **Touching generated `docs/api/**`** → owned by WP01; WP04 must not write there.
- **Sweeping a git-merge/publish sense** → per-site classification (C-003).

## Review Guidance

- Confirm only the listed `docs/**` files + `CLAUDE.md` changed; no `docs/api/**` or immutable trees.
- Confirm each converted site is Sense 1; git-merge/publish prose intact.
- Confirm `CLAUDE.md:396` now names `state.json`.

## Activity Log

> **CRITICAL**: chronological order, APPEND at the END.

- 2026-09-27T07:39:01Z – system – Prompt created.
