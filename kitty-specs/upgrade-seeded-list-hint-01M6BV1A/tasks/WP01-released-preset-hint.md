---
work_package_id: WP01
title: The released-preset provenance in the seeded-list hint
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
planning_base_branch: issue-6684-upgrade-seeded-list-hint
merge_target_branch: issue-6684-upgrade-seeded-list-hint
branch_strategy: Planning artifacts for this mission were generated on issue-6684-upgrade-seeded-list-hint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6684-upgrade-seeded-list-hint unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T008
phase: Phase 1 - Red first, then the hint
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
execution_mode: code_change
owned_files:
- tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# WP01 — The released-preset provenance in the seeded-list hint

## Objective

Teach the seeded-list hint of `4.0.0rc8_promote_interview_selections` to recognise a present
activation list that a **released** `default` activation preset wrote, in addition to the list that
equals today's full in-force set. Warn; write nothing.

## Subtasks

- **T001** Red-first case: a project whose `activated_directives` is set-equal to a released `default`
  preset list (e.g. the 19-id 3.2.6rc1 list in `DEFAULT_SNAPSHOTS["activated_directives"][0]`), with an
  interview that selected some of those ids, must produce one seeded-list warning. On `main` it produces
  none (today's in-force set has 38 directives).
- **T002** Red-first case: the released preset list **plus** one interview id the preset lacks (the shape
  the superseded seeding wrote) must produce the same warning.
- **T003** Guards: a hand-picked two-id list produces no hint; a list equal to today's in-force set keeps
  the existing warning; the activation surface bytes are unchanged in every case (the migration already
  has `_bytes` for this).
- **T004** `_seeded_list_hints` gains the second provenance: for each candidate kind, if a released preset
  set `D` for that key satisfies `D ⊆ listed ⊆ in_force(kind)` and `listed ⊆ (D ∪ selected)`, emit the
  hint. One warning per kind, today's-in-force taking precedence. Read `D` from
  `_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS`; do not copy the data.
- **T005** The new message says which provenance it reports (a released `default` activation preset), the
  listed and selected counts, and names both `charter interview --narrow-activation` and
  `charter activate <kind> <id> --only`.
- **T008** The module docstring's "A list an earlier build seeded is reported, never narrowed" rule states
  both provenances and the residual (a whole-catalogue seed from a release whose catalogue later grows).

## Definition of done

- `uv run pytest tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py -q` is green,
  and T001/T002 fail if the new provenance is reverted.
- `uv run pytest tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py -q` stays green
  (the frozen data now has a second reader).
- `uv run pytest tests/upgrade/test_upgrade_keeps_absent_activation_6629.py -q` stays green.
- No write path is added; `git diff` touches only the two owned files.
- `uv run ruff check` and `uv run ruff format --check` clean on both files; `uv run mypy` clean for the
  module (project settings).

## Notes

- The resolved in-force set stays lazily built and only for candidate kinds, exactly as now.
- Stems on both sides (`resolver.stems`), so a list spelled by declared id (`DIRECTIVE_003`) is not a miss.
- The hint only reports. `charter interview --narrow-activation`, `charter activate --only` and a hand
  edit are the only ways a list narrows (#6499, #6684 ruling).
