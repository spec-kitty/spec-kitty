---
work_package_id: WP04
title: 'Merge issue-matrix gate partition split + terminal-verdict enforcement (IC-03 + IC-04) — #4943'
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-004
- FR-006
planning_base_branch: claude/spec-kitty-ci-failures-r0xui3
merge_target_branch: claude/spec-kitty-ci-failures-r0xui3
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-ci-failures-r0xui3. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-ci-failures-r0xui3 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-matrix-partition-integrity-01M3H10A
base_commit: 991a46898e5b50c080ad2865490cadb284941e78
created_at: '2026-09-27T10:42:45.234023+00:00'
subtasks:
- T012
- T013
- T014
history:
- Created by /spec-kitty.tasks 2026-09-27
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/policy/merge_gates.py
create_intent:
- tests/policy/test_merge_gates_issue_matrix.py
execution_mode: code_change
owned_files:
- src/specify_cli/policy/merge_gates.py
- src/specify_cli/merge/executor.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- tests/policy/test_merge_gates_issue_matrix.py
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

Close both #4943 legs. (IC-03) Make the merge issue-matrix completeness gate discover references from
PRIMARY (via the placement seam, as the risk/dependency gates already do per #3439) and read verdicts from
COORD/ref (via the WP02 helper). (IC-04) Add a sibling gate that enforces the terminal-verdict rule — block
refuses before the target advances (naming rows), warn prints the same list — by REUSING the existing rule,
not re-implementing it.

Depends on WP02. Read `../plan.md` (IC-03, IC-04), `../spec.md` (US2, US3, FR-003/004/006),
`../contracts/merge-verdict-terminality.md`.

## Context (confirmed live code)

- `_evaluate_issue_matrix_completeness_gate(feature_dir, is_blocking)` (`merge_gates.py:360`) reads BOTH
  `gating_issue_numbers(feature_dir)` (:395) and the matrix (:404) off ONE `feature_dir`. On coord the
  merge flow passes the coord husk → no spec there → "No gating issue references discovered — nothing to
  enforce" (:400) → false PASS.
- Precedent to mirror: `_evaluate_risk_gate` (:217) and `_evaluate_dependency_gate` (:279) take
  `repo_root, mission_slug` and route PRIMARY reads through `placement_seam(repo_root, mission_slug).read_dir(KIND)`
  (:237, :301) while keeping STATUS on the coord `feature_dir` (#3439/C-001/C-002). `evaluate_merge_gates`
  (:86) already threads `repo_root`/`mission_slug`; `executor.py:559` already passes both. The issue-matrix
  gate is the straggler called WITHOUT them (:140-142).
- Terminal-verdict rule to REUSE: `_issue_matrix_approval_blocker` DEFINED in
  `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py:206` (imported/called by
  `tasks_move_task.py:1109`), keyed on `IssueMatrixVerdict.IN_MISSION` with the `target_lane == Lane.DONE`
  lever. NOTE: `unknown` non-terminality is enforced by a DIFFERENT (schema-validity) gate — reuse both so
  `unknown` is not missed. A hand-rolled "reject in-mission set" would be a second authority AND miss `unknown`.
- Gate mechanism already delivers block/warn: `executor.py:559-571` — block aborts via `overall_pass`
  before `_phase_merge_lanes`; warn prints `gate.details`. So `done_bookkeeping.py` should need NO change.

## Subtasks

### T012 — Failing-first test (RED before T013/T014)
`tests/policy/test_merge_gates_issue_matrix.py`:
- **Discovery (FR-003)**: coord mission citing `#1234` with no row, `mode: block` → gate FAILs (not
  "nothing to enforce"); lanes arm of the same fixture FAILs identically (parity).
- **Verdict read (FR-004)**: divergent fixture (primary `in-mission`/absent, coord `fixed`) → PASSes;
  inverted (primary `fixed`, coord `in-mission`) → FAILs (half-by-half proof of discovery vs verdict).
- **Terminality (FR-006)**: gating row `in-mission`, `mode: block` → refuses before advance, names row;
  `mode: warn` → advances/records done but prints the list; terminal verdict → advances clean (control).
  Include a coord post-consolidation arm (verdict on coord branch ref) via WP01/WP02.
RED on base.

### T013 — Partition split on the completeness gate (IC-03)
Give `_evaluate_issue_matrix_completeness_gate` `repo_root, mission_slug`; discover references from PRIMARY
via the seam (mirror risk/dependency gates); read verdicts via the WP02 helper (coord/ref). Update the
caller wiring at `merge_gates.py:140-142`. Keep the function ≤ complexity 15 (extract a helper).

### T014 — Terminal-verdict sibling gate (IC-04) + make the reused rule content-aware (MAJOR-1)
Add a sibling gate in `merge_gates.py` that reuses `_issue_matrix_approval_blocker`
(`tasks_parsing_validation.py:206`) with `target_lane=Lane.DONE` AND the schema-validity/unknown check, so
a gating row at `in-mission`/`unknown` refuses in block mode and warns in warn mode. Do NOT re-implement
the rule; do NOT modify `done_bookkeeping.py` unless a test proves it necessary.

**Content-aware reuse (blocks US3.1 post-consolidation otherwise):** `_issue_matrix_approval_blocker` and
`_issue_matrix_evaluation` (`tasks_parsing_validation.py:120`) are DIR-based (`issue_matrix_artifact_present(feature_dir)`
`:283`, `load_issue_matrix` via `feature_dir`). Post-consolidation there is no dir. Thread an **optional**
coord matrix content-source parameter (from the WP02 helper) through both, defaulting to the current
dir-behavior so the existing `move-task` caller (`tasks_move_task.py:1109`) is unaffected (backward-compatible
— do NOT change `tasks_move_task.py`). Import `_issue_matrix_approval_blocker` into `merge_gates.py` with a
**function-local import** (as merge_gates already does for its seam calls, `:231/:295/:392`) to avoid any
import cycle (MINOR-3). Hoist the new gate's `gate_name` string to a module constant (S1192, MINOR-2).

## Definition of Done
- T012 RED on base, GREEN on final; discovery, verdict half-by-half, terminality block/warn, coord-vs-lanes
  parity, and post-consolidation arms all green.
- Terminal-verdict enforcement reuses the existing rule and covers `unknown` (verified by a test that a
  bare in-mission-only mirror would miss).
- Re-judge any existing merge-gate test pinning the husk read — correct it, don't green-wash.
- `ruff`/`ruff format`/mypy clean.
- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/policy -q`.

## Reviewer guidance
Confirm discovery routes through the seam (PRIMARY) and verdict through the WP02 helper (coord/ref) — a
single `feature_dir` fed to both is the bug. Confirm IC-04 REUSES `_issue_matrix_approval_blocker` and
covers `unknown`. Confirm block refuses BEFORE the target advances (not after). Confirm done_bookkeeping is
untouched (or a test justifies the change).
