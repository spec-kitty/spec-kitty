---
work_package_id: WP04
title: Route inventory and changelog
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-010
- SC-001
planning_base_branch: issue-957-dashboard-read-rehome
merge_target_branch: issue-957-dashboard-read-rehome
branch_strategy: Planning artifacts for this mission were generated on issue-957-dashboard-read-rehome. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-dashboard-read-rehome unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
phase: Phase 4 - Docs
history: []
agent_profile: scribe-sally
authoritative_surface: kitty-specs/mission-status-artifact-reads-01M57KY3/route-inventory.md
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/mission-status-artifact-reads-01M57KY3/route-inventory.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Route inventory and changelog

## Do This First: Load Agent Profile

Load the profile `scribe-sally` (role implementer).

## Objectives & Success Criteria

- Every routing condition of `router.py` at `3d5c85d09^` (18 conditions) maps to inventory rows (28 rows), and each
  handler name is correct.
- The `[Unreleased]` section of `docs/changelog/CHANGELOG.md` has one entry with a bold, impact-first lead, `(#957, #5533)`,
  and the before and after.
- That entry lists the dropped dashboard routes (R19, R24, R26–R29) and points at the inventory.

## Review Guidance

- Re-derive the route list with `git show 3d5c85d09^:src/specify_cli/dashboard/handlers/router.py`.
- Run `pytest tests/architectural/test_no_legacy_terminology.py`.
