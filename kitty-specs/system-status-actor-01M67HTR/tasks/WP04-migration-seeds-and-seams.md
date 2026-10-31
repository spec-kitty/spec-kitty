---
work_package_id: WP04
title: Migration seed writers and the two compatibility seams
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-009
- FR-010
- FR-012
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6722-system-status-actor
merge_target_branch: issue-6722-system-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6722-system-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6722-system-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-system-status-actor-01M67HTR
base_commit: 2b85289cdd6472c1e91c3f5d21e4ebdaa6561ffa
created_at: '2026-10-31T01:08:06.861778+00:00'
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
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/unit/migration/test_system_actor_6722.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/migration/wp_status_backfill.py
- src/specify_cli/migration/backfill_runtime_state.py
- src/specify_cli/migration/verdict_provenance_backfill.py
- tests/unit/migration/test_system_actor_6722.py
- tests/unit/migration/test_wp_status_backfill.py
- tests/unit/migration/test_backfill_runtime_state.py
- tests/migration/test_birth_cutover.py
- tests/migration/test_verdict_provenance_backfill.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Migration seed writers and the two compatibility seams

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- All three in-process backfills store the system actor with `tool: "migration:<id>"` and
  `role: "system"`, `profile`/`model` `None`.
- `status.models.is_migration_actor` is true for a structured seed; the reducer's seed arm,
  `validate_timestamp_continuity`, the consolidation window rule and the implementer-of-record read
  answer exactly as they do for a string seed.
- Seam A: `backfill_runtime_state._is_migration_actor` recognises **this** backfill's seed in
  either shape (`True` for the string row the module wrote before the change).
- Seam B: a stored seed row whose only difference from the rebuilt expectation is the actor's
  *shape* verifies `ok`; a different identity still fails.
- FR-007, FR-009, FR-010, FR-012, C-003.

## Context & Constraints

- Read: `contracts/system-actor.md` §2 §4; `data-model.md` §SeedIdentity §SeedRow; `research.md` §4.
- The three identity constants stay **strings** (`WP_STATUS_BACKFILL_ACTOR`,
  `BACKFILL_ACTOR` ×2): existing tests and the seams compare identities, and `.startswith` /
  equality against a dict would break them for no gain. Wrap at the emit sites.
- Emission is unchanged: same `event_id` derivation (none of the deterministic-id inputs is the
  actor), same `at`, same `reason`, same ordering. Only the `actor` value changes.
- Seam A must **project**, not widen: it answers "this backfill's seed", not "any seed". The
  shared `status.models.is_migration_actor` stays the "any seed" authority.
- Seam B tolerates **shape only**: same projected identity, one side a `str`, the other a 4-key
  dict. Any other divergence stays a hard, fail-closed mismatch.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6722-system-status-actor`; completed
  changes merge back into it. Execution worktrees are allocated per computed lane from `lanes.json`.
- **Planning base branch**: `issue-6722-system-status-actor`
- **Merge target branch**: `issue-6722-system-status-actor`

## Subtasks & Detailed Guidance

### T001 – Red-first: the three writers store the system actor

- **Steps**: for each backfill, run it on its fixture and assert the exact 4-key dict with the right
  `migration:` tool, plus `is_migration_actor` true. Observe the failure on the base.
- **Files**: `tests/unit/migration/test_system_actor_6722.py`.

### T002 – Red-first: Seam A

- **Steps**: assert `backfill_runtime_state._is_migration_actor` is true for the string identity, true
  for the built actor, and **false** for a different migration's identity in either shape. On the
  base the structured case fails.
- **Files**: `tests/unit/migration/test_system_actor_6722.py`.

### T003 – Red-first: Seam B

- **Steps**: build a `verify_backfill` fixture whose log holds the *string*-actor seed rows the
  pre-change code wrote; assert `VerifyResult.ok` with no mismatches on the new code (fails on the
  base only after the writer changes, so stage it against T004). Then tamper one seed's identity to
  `migration:another_backfill` and assert it is reported as a mismatch. A third arm: a genuinely
  corrupted slot value is still a mismatch.
- **Files**: `tests/unit/migration/test_system_actor_6722.py`.
- **Notes**: the paired negative arms are the point — a tolerance that accepts everything is a
  weakened gate.

### T004 – Move the three writers onto the builder

- **Files**: `src/specify_cli/migration/wp_status_backfill.py:279,302`;
  `backfill_runtime_state.py:873,1022`; `verdict_provenance_backfill.py:394`.
- **Notes**: import `build_system_actor` explicitly (these modules are deliberately free of the
  status package's higher-level seams); keep every other field identical.

### T005 – Make the two seams shape-blind and update the existing tests

- **Files**: `src/specify_cli/migration/backfill_runtime_state.py` (`_is_migration_actor` at ~331,
  `_seed_row_mismatch` at ~1652); `tests/unit/migration/test_wp_status_backfill.py` (helper at ~110,
  and the two constant assertions at ~848), `tests/unit/migration/test_backfill_runtime_state.py`
  (~10 `event.actor == b.BACKFILL_ACTOR` sites), `tests/migration/test_birth_cutover.py` (~590 JSON
  fixture, ~673 comparison), `tests/migration/test_verdict_provenance_backfill.py` (~274).
- **Notes**: prefer comparing the identity (`actor_identity_str(event.actor) == BACKFILL_ACTOR`) in
  filters, and the dict where the test asserts the stored shape. Keep
  `tests/migration/test_seed_lane_authority_consumer.py` untouched: it feeds a **string** seed and is
  the "existing logs reduce unchanged" witness — it must pass without modification.

## Test Strategy

```bash
uv run --frozen pytest tests/unit/migration/test_system_actor_6722.py -q
uv run --frozen pytest tests/unit/migration tests/migration -q
uv run --frozen pytest tests/consolidation/test_wp_attribution.py tests/status/test_seed_lane_authority_consumer.py tests/status -q
uv run --frozen ruff check src/specify_cli/migration tests/unit/migration tests/migration
uv run --frozen mypy src/specify_cli/migration/backfill_runtime_state.py src/specify_cli/migration/wp_status_backfill.py src/specify_cli/migration/verdict_provenance_backfill.py
```

## Risks & Mitigations

- **Fail-closed verification rejecting a healthy corpus.** That is the one user-visible way this
  mission can hurt someone. T003's `ok` arm on a pre-change corpus is mandatory, and the negative
  arms keep it from becoming a blanket pass.
- **Seam A silently widening to the shared prefix predicate**, which would change which rows count as
  history for the ordering guards. Keep it an identity equality on the projected value and say so in
  the docstring.
- **The deterministic ids drifting.** They do not include the actor; assert an unchanged `event_id`
  for a seed in T001 as a cheap guard.

## Review Guidance

- Is the actor the *only* changed field on the seed payload? Compare `to_dict()` minus `actor`.
- Does Seam B accept exactly two shapes and require an equal identity?
- Do the three constants still read as identity strings?

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP04 --to <status>`
