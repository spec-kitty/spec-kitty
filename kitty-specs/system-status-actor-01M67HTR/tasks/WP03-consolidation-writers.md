---
work_package_id: WP03
title: Consolidation bookkeeping, the override and both attestations
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- C-005
- SC-001
planning_base_branch: issue-6722-system-status-actor
merge_target_branch: issue-6722-system-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6722-system-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6722-system-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-system-status-actor-01M67HTR
base_commit: 2b85289cdd6472c1e91c3f5d21e4ebdaa6561ffa
created_at: '2026-10-31T00:44:01.803952+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 2 - Writers
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_system_actor_6722.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/done_bookkeeping.py
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/approved_attestation.py
- src/specify_cli/consolidation/canceled_attestation.py
- tests/consolidation/test_system_actor_6722.py
- tests/consolidation/test_merge_done_recording.py
- tests/specify_cli/consolidation/test_done_evidence_snapshot.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Consolidation bookkeeping, the override and both attestations

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- The merge-time approval replay and the done mark store `{"tool": "merge", "role": "system", "profile": None, "model": None}`.
- The done-write refusal probe in `preflight.py` builds the **same** shape as the real write.
- The review-artifact override annotation's *event* actor is the system actor built from the
  resolved operator identity, while `ReviewOverride.actor` stays the plain string.
- Both attestations store the system actor with the resolved operator identity in `tool`, keep
  their `policy_metadata.attestation`, and stay out of the reviewer read.
- FR-004, FR-005, FR-006, C-005.

## Context & Constraints

- Read: `contracts/system-actor.md` §2, §3; `data-model.md` §SystemWriter rows 3–8.
- `ReviewOverride` (`status/models.py:633`) has four `str` fields and is a **pinned** shape ("do
  NOT reuse … do NOT invent …"). Only the event's `actor` changes at that site.
- The approved-reviewed attestation is recognised by `policy_metadata[ATTESTATION_KEY]`
  (`_is_operator_attestation`, `preflight.py:575`), **not** by its actor; a test must hold that line.
- `_resolve_merge_actor` (`done_bookkeeping.py:88`) returns the operator identity string; keep using
  it for the identity and for `evidence={"review": {...}}`.
- Do not change merge behaviour, ordering, `policy_metadata`, `force`, or `reason`.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6722-system-status-actor`; completed
  changes merge back into it. Execution worktrees are allocated per computed lane from `lanes.json`.
- **Planning base branch**: `issue-6722-system-status-actor`
- **Merge target branch**: `issue-6722-system-status-actor`

## Subtasks & Detailed Guidance

### T001 – Red-first: the approval replay and the done mark

- **Purpose**: the two bookkeeping emits.
- **Steps**: drive the done bookkeeping through its seam (`_mark_wp_merged_done` /
  `_replay_approval_for_preapproved_lane`) on an approved WP and assert both emitted events' actors.
  Observe the failure on the base (strings).
- **Files**: `tests/consolidation/test_system_actor_6722.py`.

### T002 – Red-first: the refusal probe matches the write

- **Purpose**: the probe is a dry `TransitionRequest` used to compute `status_write_refusal`; a
  guard that reads `request.actor` must see the same value the real write will carry.
- **Steps**: assert the probe's request actor equals the shaped merge actor, and that
  `status_write_refusal` still returns what it does on the base for the same fixture.
- **Files**: `tests/consolidation/test_system_actor_6722.py`.

### T003 – Red-first: the override annotation

- **Purpose**: the one site where one variable feeds two different types.
- **Steps**: run `_persist_review_artifact_override` (or the `--skip-review-artifact-check` path
  through the preflight) and assert (a) the persisted `InnerStateChanged.actor` is
  `{"tool": <resolved identity>, "role": "system", "profile": None, "model": None}` and (b) the
  delta's `review.actor` is still the plain identity string, with all four `ReviewOverride` fields
  intact. Assert the same on the reduced snapshot's review slot.
- **Files**: `tests/consolidation/test_system_actor_6722.py`.

### T004 – Red-first: both attestations

- **Steps**: record `--attest-approved-reviewed` and `--attest-canceled-superseded` on fixtures and
  assert the event actor, that `policy_metadata[ATTESTATION_KEY]` is unchanged, and that
  `_latest_actor_for_transition` still skips the approved attestation (no review verdict is
  inferred from `role`). A positive control on the same fixture proves the skip is the attestation
  rule and not an empty read.
- **Files**: `tests/consolidation/test_system_actor_6722.py`.

### T005 – Move the four modules onto the builder

- **Steps**: add one `MERGE_ACTOR = "merge"` identity constant in `done_bookkeeping.py` beside
  `_resolve_merge_actor`, use `build_system_actor(MERGE_ACTOR)` at both emits and at the
  `preflight.py:1240` probe; wrap `_resolve_merge_actor(...)` with `build_system_actor(...)` for
  the override event actor and for the two attestation `TransitionRequest`s.
- **Files**: `src/specify_cli/consolidation/{done_bookkeeping,preflight,approved_attestation,canceled_attestation}.py`.
- **Notes**: update the existing assertions that read the writer's request:
  `tests/consolidation/test_merge_done_recording.py` (`assert request.actor == "merge"`),
  `tests/specify_cli/consolidation/test_done_evidence_snapshot.py` (same),
  `tests/specify_cli/cli/commands/test_merge.py:355` (`emit_calls[0].actor == "merge"`). Fixtures
  that *construct* `TransitionRequest(actor="merge")` as input are unaffected — do not edit those.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_system_actor_6722.py -q
uv run --frozen pytest tests/consolidation tests/specify_cli/consolidation tests/specify_cli/cli/commands -k "merge or attest or preflight or done" -q
uv run --frozen ruff check src/specify_cli/consolidation tests/consolidation/test_system_actor_6722.py
uv run --frozen mypy src/specify_cli/consolidation/done_bookkeeping.py src/specify_cli/consolidation/preflight.py src/specify_cli/consolidation/approved_attestation.py src/specify_cli/consolidation/canceled_attestation.py
```

## Risks & Mitigations

- **Casting the operator identity into the delta slot** would break the pinned `ReviewOverride`
  shape. Split the variable; do not cast.
- **The probe drifting from the write.** Both must use the same constant; assert it in T002.
- **The attestation losing its kind.** If a reviewer read starts trusting `role`, an attestation
  could be mistaken for a review. T004's positive control guards it.

## Review Guidance

- Is `policy_metadata`, `reason`, `force` or ordering touched? It must not be.
- Does the attestation still carry the operator identity in `tool` (not `spec-kitty`)?
- Is `ReviewOverride.actor` still a `str` at both the construction and the persisted delta?

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP03 --to <status>`
