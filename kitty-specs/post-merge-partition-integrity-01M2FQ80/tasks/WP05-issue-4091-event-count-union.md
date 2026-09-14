---
work_package_id: WP05
title: '#4091 contingent: event_count union consistency (coord fixture)'
dependencies:
- WP04
requirement_refs:
- FR-007
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T11:45:30.716207+00:00'
subtasks:
- T012
- T013
history:
- created by /spec-kitty.tasks
agent_profile: debugger-debbie
authoritative_surface: src/specify_cli/merge/bookkeeping_projection.py
create_intent:
- tests/merge/test_event_count_union_4091.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/merge/bookkeeping_projection.py
- tests/merge/test_event_count_union_4091.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – #4091 contingent: event_count union consistency

## ⚡ Do This First: Load Agent Profile

- **Profile**: `debugger-debbie` (falsifier / live-evidence)
- **Role**: `implementer`

---

## Objectives & Success Criteria

**CONTINGENT WP.** First prove whether #4091 is LIVE on HEAD with a coord-fixture repro; then either fix (if RED) or verify-and-close (if GREEN). Do NOT build a fix-test that is already green on HEAD (green-regression trap).

- SC (repro): a coord-fixture test drives `_project_status_bookkeeping_to_target` (`merge/bookkeeping_projection.py:282`) on a two-stream fixture and checks `status.json.event_count` against the unioned `status.events.jsonl`.
- SC (branch): if RED → reconcile the measure and turn it green; if GREEN → record #4091 as **verify-and-close** with the mechanism citation (no code change) and close #4091 in the issue-matrix accordingly.

## Context & Constraints (brownfield finding)

The brownfield squad found `_project_status_bookkeeping_to_target` **already** unions the two logs (`_union_event_logs`, `:243`) and re-reduces `status.json` (`_rematerialize_status_snapshot`, `:264` → `reduce(union)`), so the target-projected `event_count` should already be consistent. Moreover `event_count = len(unique transition events)` **by definition** (`spec_kitty_events/status.py:799`) — annotations (`InnerStateChanged`), lifecycle (`MissionReopened`/`FollowUpRecorded`) and decision events are NOT transitions, so `event_count < raw jsonl line count` is expected, not a bug. The union branch runs only under a coord husk (`bookkeeping_projection.py:315` `is_under_worktrees_segment`) — this `single_branch` mission never hits it, so the repro MUST use a coord fixture. Likely outcome: verify-and-close (or a documentation/measure clarification), not a code fix.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T012 – Coord-fixture repro
- **Steps**: Build a coord-husk fixture with two divergent `status.events.jsonl` streams; drive `_project_status_bookkeeping_to_target`; assert `status.json.event_count == number of unique transition events in the unioned log` (NOT raw line count — distinguish the two measures explicitly). Record RED or GREEN on HEAD.

### Subtask T013 – Fix-or-verify-close
- **If RED**: reconcile in `bookkeeping_projection.py` (or the reducer) so the projected snapshot's count matches the intended measure; keep the test green.
- **If GREEN**: do NOT change product code. Write the verify-and-close note (cite the union+re-reduce mechanism + the transition-count definition) and set #4091's issue-matrix verdict to `verified-already-fixed`. The delivered test becomes a regression guard (assert current-correct behavior — clearly labelled characterization, not a phantom fix).

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest tests/merge/test_event_count_union_4091.py -q -p no:cacheprovider
```

## Risks & Mitigations
- **Green-regression trap**: if T012 is GREEN on HEAD, do not author a "fix" — this is the documented landing defect. Verify-and-close instead.
- **Wrong measure**: assert against unique-transition count, not raw jsonl lines, or the test asserts a false expectation.

## Review Guidance
- Confirm the repro uses a coord fixture (single_branch never unions).
- Confirm the disposition (fix vs verify-close) matches the actual HEAD result and the issue-matrix verdict is set accordingly.

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
