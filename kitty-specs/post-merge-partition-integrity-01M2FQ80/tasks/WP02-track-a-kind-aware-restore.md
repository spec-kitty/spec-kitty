---
work_package_id: WP02
title: 'Track A fix: kind-aware target-newer restore on squash (#3942)'
dependencies:
- WP01
requirement_refs:
- C-001
- C-002
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-003
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T11:19:06.214968+00:00'
subtasks:
- T003
- T004
- T005
- T006
- T007
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- src/specify_cli/merge/planning_recency.py
- tests/merge/test_planning_recency_helper.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/merge/planning_recency.py
- src/specify_cli/merge/executor.py
- src/specify_cli/lanes/merge.py
- tests/merge/test_planning_recency_helper.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Track A fix: kind-aware target-newer restore on squash (#3942)

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro` (implementer feasibility / TDD)
- **Role**: `implementer`

Load it via `/ad-hoc-profile-load` before anything else.

---

## Objectives & Success Criteria

Make squash consolidation preserve **target-newer primary-artifact-kind** `kitty-specs/` files (and report the divergence), without altering the common `-X theirs` case or any driver-covered reconciliation.

- SC: WP01's red-first test passes (remove its xfail-strict marker — a documented one-line out-of-map edit to WP01's file).
- SC: a new **pure** three-way recency helper is unit-tested standalone.
- SC: the #2709/#2804 suites stay green (FR-003). Touched functions stay complexity ≤15 (NFR-003).

## Context & Constraints (locked design — see plan.md "Locked design decisions")

- **D-A2 (a), (b) rejected**: extend the post-squash restore `_restore_regressed_gate_artifacts` (`merge/executor.py:206`, the #2804 pattern). A git merge driver cannot compute recency (it sees only three blobs, no history), so a `_MERGE_DRIVERS` entry is structurally impossible for target-newer-wins — do NOT go that route.
- **D-A3 three-way divergence**: "target is newer" ⇔ **target diverged from the merge-base while the lane copy is base-or-ancestor**. Reuse the merge-base + per-side diff shape at `lanes/stale_check.py:39-67`. Committer-date tiebreak only; **never mtime**. This is topology-safe: on single_branch/LANES (lane≠base, target=base) the lane correctly wins with no special-case.
- **D-A1 classifier**: gate the restore on `mission_runtime.is_primary_artifact_kind(kind_for_mission_file(path))` (`src/mission_runtime/artifacts.py:158/402/415`). This advances epic #2907.
- **Do NOT touch** `merge/conflict_resolver.py` (DEAD — only `merge/__init__.py` re-exports it; the live auto-rebase classifier is the different `merge/conflict_classifier.py`). Do NOT touch the SQUASH block in `_merge_branch_into` (`lanes/merge.py:629-682`) beyond the comment amendment — the restore-after-squash approach keeps `-X theirs` byte-identical.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T003 – Pure three-way recency helper
- **Purpose**: Isolate the recency decision (keeps executor complexity ≤15).
- **Steps**: New module `src/specify_cli/merge/planning_recency.py` with a pure function, e.g. `target_newer_primary_artifacts(repo, target_ref, source_ref, changed_paths) -> list[Path]`: for each changed primary-artifact-kind path, compute `merge-base(target,source)` then decide target-newer via the three-way rule. Unit-test it in `tests/merge/test_planning_recency_helper.py` with a temp 3-commit repo (target-advanced-after-base + lane-stale ⇒ returned; lane-advanced ⇒ not returned; both-advanced ⇒ documented tiebreak).
- **Files**: `src/specify_cli/merge/planning_recency.py`, `tests/merge/test_planning_recency_helper.py`.

### Subtask T004 – Capture pre-squash target bytes for planning kinds
- **Purpose**: Mirror `_capture_pre_target_gate_artifacts` (`executor.py:189`) for primary-artifact-kind files.
- **Steps**: Add `_capture_pre_target_planning_artifacts(run)`; invoke it alongside the gate capture at the executor's pre-squash point (`~executor.py:1771`).

### Subtask T005 – Restore target-newer planning files + report
- **Purpose**: Write the captured target bytes back post-squash when recency says target is newer.
- **Steps**: Extend `_restore_regressed_gate_artifacts` (or add a thin sibling `_restore_target_newer_planning_artifacts`) called at `~executor.py:998`; use the helper from T003 to decide; record restored paths on `run.gate_artifact_restored_paths` (or a parallel list) so they fold into the same bookkeeping commit and are surfaced to the operator (FR-002). Keep the restore loop thin — the decision lives in T003's helper.

### Subtask T006 – Comment amendment + green flip
- **Purpose**: Correct the stale design-intent comment and turn WP01 green.
- **Steps**: Amend `lanes/merge.py:631-633` (its "mission branch authoritative" premise is false for primary-partition planning kinds — note they are authored on primary). Remove WP01's xfail-strict marker (documented out-of-map one-liner) and confirm the test PASSES.

### Subtask T007 – Regression + complexity census
- **Steps**: Run the #2709/#2804 suites (must stay green). Run `ruff check` + `ruff format --check` on touched files. Confirm complexity ≤15 on every touched/new function (extract if needed).

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest \
  tests/merge/test_squash_target_newer_planning_3942.py \
  tests/merge/test_planning_recency_helper.py \
  tests/merge/test_squash_target_newer_provenance_regression_2709.py \
  tests/merge/test_squash_reconcilers_2709.py \
  tests/merge/test_gate_artifact_merge_drivers_2804.py \
  tests/merge/test_issue_2804_merge_resets_gate_artifacts.py \
  -q -p no:cacheprovider
.venv/bin/ruff check src/specify_cli/merge/planning_recency.py src/specify_cli/merge/executor.py src/specify_cli/lanes/merge.py
.venv/bin/ruff format --check src/specify_cli/merge/planning_recency.py src/specify_cli/merge/executor.py src/specify_cli/lanes/merge.py
```

## Risks & Mitigations
- **Complexity creep** in `_restore_regressed_gate_artifacts`: keep the recency decision in `planning_recency.py`; the restore loop stays a thin 2-tuple-style loop.
- **FR-003 regression**: driver-covered artifacts must be untouched — gate the new path strictly on `is_primary_artifact_kind` (driver-covered kinds return False).
- **both-sides-advanced tiebreak**: define it explicitly and unit-test it (prefer target-newer by committer-date; document).

## Review Guidance
- Verify `-X theirs` block is byte-unchanged; the fix is restore-after-squash only.
- Verify the recency helper is pure + independently tested; verify the classifier gate excludes driver-covered kinds.
- Verify FR-002 divergence reporting is surfaced (operator-visible), not silent.

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
