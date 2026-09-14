---
work_package_id: WP03
title: 'Track B red-first: retrospect vs doctor disagreement (#4090)'
dependencies: []
requirement_refs:
- FR-005
- FR-008
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T10:56:22.691444+00:00'
subtasks:
- T008
history:
- created by /spec-kitty.tasks
agent_profile: debugger-debbie
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Track B red-first: retrospect vs doctor disagreement (#4090)

## ⚡ Do This First: Load Agent Profile

- **Profile**: `debugger-debbie` (falsifier / live-evidence)
- **Role**: `implementer`

---

## Objectives & Success Criteria

Deliver a **red-first** test that drives the **real** retrospect and **real** doctor readers to disagree on the same merged mission's WP states on HEAD — proving #4090 LIVE — turning GREEN only after WP04.

- SC: constructed post-merge state — **primary** partition with 11 WPs `done` and **NO `merged_at`** on `meta.json` (matching what a real merge produces today); a **coord husk** with the same 11 WPs `approved` and no marker; `git merge-base --is-ancestor <coord> <primary>` false (real divergence).
- SC: assert the **real** retrospect completion check (`cli/commands/retrospect.py::_check_mission_completed` → `_canonical_events_path` → `resolve_status_surface`) reads the stale husk and reports open/`MISSION_NOT_COMPLETED`, **while** the **real** `doctor mission-state` read leg reports the 11 terminal — i.e. they DISAGREE = RED on HEAD.
- SC: xfail-strict marker so the suite stays green pending WP04; document the raw RED in the Activity Log.

## Context & Constraints

Pre-spec + brownfield squads verified: retrospect and doctor share `resolve_status_surface`, but the primary-wins guard `_primary_mission_is_completed` (`surface_resolver.py:745`) → `is_mission_merged` → `_last_merge_marker_at` → `meta.get("merged_at")` gates on `merged_at`, whose writer was deleted in #2258 and never re-added. With `merged_at` absent (real-merge reality), the resolver falls to the husk short-circuit (`surface_resolver.py:778`) = stale coord. Start from `scratchpad/repro_4090.py` (drives the real retrospect predicate) — but drop the `merged_at` on primary so it matches HEAD's real post-merge state.

- **C-003**: do NOT run a live coord `spec-kitty merge` (that would dogfood the very bug and this mission is `single_branch`). Construct the post-merge state directly.
- **Doctor leg (important)**: `doctor mission-state` passes through `enforce_primary_write_ownership` (`_mission_state_doctor.py:429`). You MUST drive the real `doctor mission-state` command (or its innermost resolver) to obtain the doctor-side WP states — do NOT infer agreement from the retrospect side alone, or SC-002/SC-003 is only half-proven.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T008 – Real-readers disagreement repro
- **Purpose**: Prove the two readers disagree on HEAD.
- **Steps**: Build the constructed state (reuse `repro_4090.py`'s builders, minus the primary `merged_at`). Call the real retrospect predicate and the real doctor read leg; assert (a) retrospect sees non-terminal / raises `MISSION_NOT_COMPLETED`, (b) doctor sees 11 terminal, (c) they disagree. Capture raw RED, then apply `@pytest.mark.xfail(strict=True, reason="#4090 reader divergence; fixed in WP04")`.
- **Files**: `tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py` (new).

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py -q -p no:cacheprovider
```

## Risks & Mitigations
- **Half-proof**: if you only assert the retrospect side, the "they agree after fix" claim is unproven. Drive BOTH real readers.
- **Accidental green**: if you leave `merged_at` on primary, the guard fires and the test is green on HEAD (proves nothing). Ensure it is ABSENT.

## Review Guidance
- Confirm both readers are the REAL ones (grep imports), not reconstructions.
- Confirm the constructed state matches a real post-merge (no `merged_at`, diverged husk).

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
