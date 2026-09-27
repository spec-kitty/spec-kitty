---
work_package_id: WP05
title: Issue-matrix partition regression guard (IC-05) — FR-008
dependencies:
- WP03
- WP04
requirement_refs:
- FR-008
- NFR-001
planning_base_branch: claude/spec-kitty-ci-failures-r0xui3
merge_target_branch: claude/spec-kitty-ci-failures-r0xui3
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-ci-failures-r0xui3. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-ci-failures-r0xui3 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-matrix-partition-integrity-01M3H10A
base_commit: 991a46898e5b50c080ad2865490cadb284941e78
created_at: '2026-09-27T11:45:32.657349+00:00'
subtasks:
- T015
history:
- Created by /spec-kitty.tasks 2026-09-27
agent_profile: implementer-ivan
authoritative_surface: tests/architectural/test_issue_matrix_partition_guard.py
create_intent:
- tests/architectural/test_issue_matrix_partition_guard.py
execution_mode: code_change
owned_files:
- tests/architectural/test_issue_matrix_partition_guard.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Close the improvised-path / split-bypass defect class by construction (DIRECTIVE_043). A non-vacuous
architectural guard asserts that no mission-review or merge issue-matrix consumer reconstructs a
topology-dependent `issue-matrix` path by hand or bypasses the WP02 shared split helper.

Depends on WP03 + WP04 (guards their result). Read `../plan.md` (IC-05), `../spec.md` (FR-008, NFR-001, SC-005).

## Subtasks

### T015 — Non-vacuous partition guard (with self-mutation check)
Create `tests/architectural/test_issue_matrix_partition_guard.py`:
- Assert the review gate (`review/__init__.py`), the merge completeness/terminal-verdict gates
  (`policy/merge_gates.py`), and the Gate-4 doctrine (`src/charter/offering/skills/spec-kitty-mission-review/SKILL.md`)
  contain NO raw `issue-matrix.{json,md}` working-tree path read (e.g. `cat kitty-specs/.../issue-matrix`,
  `feature_dir / "issue-matrix..."` fed to discovery+matrix both) — they must go through the WP02 helper /
  seam. Count of direct working-tree issue-matrix reads in these consumers == 0 (NFR-001).
- **Self-mutation / non-vacuity**: the test must be constructed so that injecting a raw read into one of
  the guarded consumers trips it (prove it in the test via a controlled fixture or a documented mutation
  check), so the guard cannot pass vacuously.
- Keep it fail-closed: if a guarded file is missing/unreadable, FAIL (do not skip).

## Definition of Done
- The guard FAILs when a raw read is injected and PASSes on the fixed tree (self-mutation demonstrated).
- `ruff`/`ruff format`/mypy clean.
- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_issue_matrix_partition_guard.py -q`
  plus the layer + terminology guards.

## Reviewer guidance
Confirm the guard is non-vacuous (the self-mutation check is real, not asserted). Confirm it covers all
three consumers (review gate, merge gates, doctrine) and is fail-closed on a missing file.
