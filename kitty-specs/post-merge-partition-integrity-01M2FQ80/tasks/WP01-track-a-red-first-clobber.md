---
work_package_id: WP01
title: 'Track A red-first: squash clobbers target-newer planning file (#3942)'
dependencies: []
requirement_refs:
- FR-001
- FR-008
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T10:55:39.422772+00:00'
subtasks:
- T001
- T002
history:
- created by /spec-kitty.tasks
agent_profile: debugger-debbie
authoritative_surface: tests/merge/
create_intent:
- tests/merge/test_squash_target_newer_planning_3942.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/merge/test_squash_target_newer_planning_3942.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Track A red-first: squash clobbers target-newer planning file (#3942)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the profile in the frontmatter before anything else.

- **Profile**: `debugger-debbie` (falsifier / live-evidence)
- **Role**: `implementer`

---

## Objectives & Success Criteria

Deliver a **red-first** pytest that proves #3942 is LIVE on HEAD by driving the **real** squash-merge path and asserting the correct (not-yet-implemented) behavior, so it is **RED on HEAD** and turns GREEN only after WP02.

- SC: the test drives `specify_cli.lanes.merge.integrate_mission_into_target(..., strategy=SQUASH)` (or the `spec-kitty merge` executor entry that reaches it) on a throwaway git repo — **no mocks**.
- SC: it asserts a **target-newer primary-artifact-kind** file (e.g. `kitty-specs/<m>/spec.md` and `kitty-specs/<m>/tasks/WP01.md`) **survives** the squash; on HEAD this FAILS (the older lane copy currently wins).
- SC: committed with `@pytest.mark.xfail(strict=True, reason="#3942 target-newer clobber; fixed in WP02")` so the suite stays green until WP02 removes the marker. Document the confirmed raw RED (assertion diff) in the Activity Log before applying the xfail.

## Context & Constraints

Verified by the pre-spec squad (repro at `scratchpad/repro_3942.py`): the real squash path is `merge/executor._phase_mission_to_target` → `lanes/merge.py::integrate_mission_into_target(SQUASH)` → `_merge_branch_into` → `git merge --squash -X theirs` (`lanes/merge.py:635`). `_MERGE_DRIVERS` (`lanes/merge.py:59-121`) reconciles only 6 allowlisted classes; every other `kitty-specs/` file falls to blanket `-X theirs` = lane wins, clobbering target-newer content. There is **no** recency guard.

- The classifier `mission_runtime.is_primary_artifact_kind(kind_for_mission_file(path))` returns True for spec.md/plan.md/tasks/WP*.md/research.md/data-model.md — use it to pick the specimen file(s) so the test documents the exact protected class.
- The bug requires a **both-sides-modified** conflict: target (main) edits the file AFTER the mission branch forked, and the lane carries a stale copy. A one-sided target edit is kept correctly by git — do NOT assert on that case.
- Charter: ATDD red-first (C-004). The tracker is systematically stale — this WP is the gate that proves liveness in-repo before WP02 builds anything.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T001 – Real-path red-first repro
- **Purpose**: Reproduce the clobber through the real consolidation code.
- **Steps**: Start from `scratchpad/repro_3942.py`. Build a throwaway git repo with a `kitty-specs/<slug>/` containing `spec.md` and `tasks/WP01.md`; commit a base; on the target branch make a NEWER edit to those files; on a mission/lane branch make an OLDER conflicting edit; invoke the real `integrate_mission_into_target(strategy=SQUASH)`; assert the target-newer content survives.
- **Files**: `tests/merge/test_squash_target_newer_planning_3942.py` (new).
- **Notes**: Env `SPEC_KITTY_SYNC_DISABLE=1`. Keep it hermetic (temp dir, `.venv/bin/python`). Reference the seam `lanes/merge.py:635`.

### Subtask T002 – Confirm RED, apply xfail-strict
- **Purpose**: Keep the suite green while the fix is pending, without hiding the defect.
- **Steps**: Run the test, capture the failing assertion (paste into Activity Log), then add `@pytest.mark.xfail(strict=True, reason=...)`. Re-run — it must report XFAIL (not XPASS).

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest tests/merge/test_squash_target_newer_planning_3942.py -q -p no:cacheprovider
```

## Risks & Mitigations
- **Green-regression trap**: an assertion that already passes on HEAD proves nothing. Confirm the raw (pre-xfail) run is RED and paste the diff.
- **Over-broad specimen**: pick a genuinely driver-uncovered file; do NOT use meta.json/gate matrices (they are reconciled).

## Review Guidance
- Confirm the test drives the REAL merge path (grep the import of `integrate_mission_into_target`).
- Confirm xfail-strict is present and the documented raw RED is a real clobber, not a setup error.

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
