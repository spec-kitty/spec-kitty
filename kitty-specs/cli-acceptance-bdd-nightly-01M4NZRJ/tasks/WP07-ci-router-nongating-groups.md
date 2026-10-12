---
work_package_id: WP07
title: Non-gating ci-router groups
dependencies:
- WP02
- WP03
requirement_refs:
- FR-012
- C-005
- NFR-004
- SC-003
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: d91d8dce5cfe8fc4a38ccec366dc8a33a73b38b0
created_at: '2026-10-11T18:59:38.599282+00:00'
subtasks:
- T022
- T023
phase: Phase 5 - CI
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- tests/architectural/test_workflow_coherence.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Non-gating ci-router groups

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Add two routing groups to `.github/workflows/ci-router.yml` — `scenarios` (`tests/scenarios/**`)
and `acceptance_jvm` (`acceptance-jvm/**`) — that gate **no** per-PR job, and register them in the
coherence gate's deliberately-ungated set.

Done when:
- Both groups appear in the dorny filter block and the `changes.outputs` block.
- No job `if:` references either group (they gate nothing — contributors need no JDK).
- `tests/architectural/test_workflow_coherence.py` and the ci-router transcription guards stay green.

## Context & Constraints

- **Depends on WP02 + WP03**: `test_every_restored_filter_glob_is_live` requires each glob to match ≥1 **git-tracked** path. `tests/scenarios/**` (WP02) and `acceptance-jvm/**` (WP03) must already be tracked — this WP's dependencies enforce that ordering.
- **Two authorities** (research.md §3): the dorny `changes` filter block (group→globs) and the per-job `if: needs.changes.outputs.<group>` (group→job). A group referenced by no job `if:` gates nothing — exactly how the `ci` group works today ("No job gates on this group BY DESIGN").
- **Gates to satisfy** (research.md §4):
  - `test_workflow_coherence.py::_DELIBERATELY_UNGATED_FILTER_GROUPS` — add `"scenarios"` and `"acceptance_jvm"` (honest: they truly gate no job).
  - `test_changes_outputs_cover_every_routing_group` — the `changes.outputs` block (minus `unmatched`) must equal the filter routing groups, so add both there too.
  - `test_unmatched_union_covers_every_src_backed_group` — both are **non-src**, so do NOT add them to the `unmatched` union.
  - No `ci_retirement_scrub.json` edit (non-src groups are outside scrub).
- **Hot file** (54 commits/90d) — keep the diff minimal and additive; mirror how a recent group (e.g. `mission_state`) was added.
- Spec refs: FR-012, C-005, NFR-004, SC-003.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T022 – Add the two groups to ci-router.yml

- **Purpose**: Route the two new trees without gating any per-PR job (FR-012, C-005).
- **Steps**:
  1. In the dorny `changes` filter block, add `scenarios: ['tests/scenarios/**']` and `acceptance_jvm: ['acceptance-jvm/**']` (match the block's existing style).
  2. In the `changes.outputs` block, add `scenarios` and `acceptance_jvm` entries mirroring an existing non-src group's `${{ … unmatched … || steps.filter.outputs.<grp> }}` line shape.
  3. Do NOT reference either group in any job `if:` (they gate nothing). Do NOT add them to the `unmatched` union (non-src).
  4. Optionally add a short comment like the `ci` group's "No job gates on this group BY DESIGN" for reviewer clarity.
- **Files**: `.github/workflows/ci-router.yml`.

### Subtask T023 – Register the deliberately-ungated groups + confirm guards

- **Purpose**: Keep the coherence gate green honestly (FR-003b).
- **Steps**:
  1. In `tests/architectural/test_workflow_coherence.py`, add `"scenarios"` and `"acceptance_jvm"` to `_DELIBERATELY_UNGATED_FILTER_GROUPS`.
  2. Run the coherence + transcription guards and confirm green: `test_every_restored_filter_group_is_consumed_live`, `test_every_restored_filter_glob_is_live`, `test_changes_outputs_cover_every_routing_group`, `test_unmatched_union_covers_every_src_backed_group`.
- **Files**: `tests/architectural/test_workflow_coherence.py`.
- **Notes**: the frozenset exemption is a real-code gate edit — justify it in the PR (both groups genuinely gate no job; the gate's fault-injection twin still catches real orphans).

## Test Strategy

- Targeted gate files only (per NO_FULL_HEAVY_SUITES_IN_MISSION — never the bare `tests/architectural/`):
  `uv run --frozen pytest tests/architectural/test_workflow_coherence.py tests/architectural/test_ci_router_transcription_guards.py -q`.

## Risks & Mitigations

- **glob-is-live red** → ensure WP02 + WP03 files are tracked first (enforced by deps).
- **Accidentally gating a job** → do not add either group to any job `if:`.
- **Hot-file conflict** → keep additive; rebase if CI/operator signals staleness.

## Review Guidance

- Confirm both groups route but gate no job, the frozenset addition is honest, the `unmatched` union is untouched, and all four named guards pass.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP07 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP07 --to <status>`

## Activity Log

- 2026-10-11T19:07:05Z – claude – shell_pid=3145802 – Added non-gating scenarios+acceptance_jvm router groups to ci-router.yml (filter + changes.outputs); registered both in _DELIBERATELY_UNGATED_FILTER_GROUPS. Both gate no job by design; non-src, excluded from unmatched union; no scrub edit.
