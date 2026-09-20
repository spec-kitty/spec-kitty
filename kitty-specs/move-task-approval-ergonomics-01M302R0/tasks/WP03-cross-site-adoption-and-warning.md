---
work_package_id: WP03
title: Cross-site adoption + early-warning surfacing
dependencies:
- WP01
- WP02
requirement_refs:
- FR-007
- FR-012
- NFR-005
- NFR-006
planning_base_branch: fix/move-task-approval-ergonomics
merge_target_branch: fix/move-task-approval-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/move-task-approval-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/move-task-approval-ergonomics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-approval-ergonomics-01M302R0
base_commit: e4c5b224c7d6ea1205bfd2b3314d512532e0cef0
created_at: '2026-09-20T20:51:32.104517+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 1 - Implementation
history:
- at: '2026-09-20T19:15:00Z'
  actor: system
  action: Prompt generated for move-task-approval-ergonomics mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/policy/test_issue_matrix_cross_site_consistency.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/policy/merge_gates.py
- src/specify_cli/status/doctor.py
- packs/built-in/missions/mission-steps/software-dev/specify/prompt.md
- packs/built-in/missions/mission-steps/software-dev/plan/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md
- packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md
- tests/policy/test_issue_matrix_cross_site_consistency.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3469'
---

# Work Package Prompt: WP03 – Cross-site adoption + early-warning

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill first. Then read
`spec.md`, `plan.md`, `contracts/classification-and-verdict-contract.md`, and the landed WP01
classifier + WP02 approval-blocker.

## Objective

Eliminate the parallel-authority defect: make `merge_gates` and `status/doctor` derive
"referenced-but-missing" from the SAME WP01 classifier the approval blocker uses, so a reference
non-gating at `approved` is non-gating at merge and clean in doctor (NFR-006 / FR-012). Add a
non-gating early approval-gating warning to the specify/plan/tasks/analyze mission-step prompts
(FR-007).

## Context (grounding — verify anchors; they may have drifted)

- `src/specify_cli/policy/merge_gates.py` (anchors VERIFIED) — `_evaluate_issue_matrix_completeness_gate`
  L360–419; referenced set L393, subtract at **L395**. Its matrix rows come from `load_issue_matrix`
  (L394) **without** the diagnostic-regex recovery that the approval blocker and doctor use — a subtle
  pre-existing matrix-set divergence (see T011). The never-implemented WP09 `not_applicable` Gate-4
  docstring is real at **L375–378** — align its comment to WP02's ADR; do NOT add a second
  `not_applicable` authority.
- `src/specify_cli/status/doctor.py` (anchors VERIFIED) — referenced set L433, subtract at **L439**
  (diagnostic-regex inline L433–438). Route it through the shared helper.
- `packs/built-in/missions/mission-steps/software-dev/{specify,plan,tasks,analyze}/prompt.md` — 0 hits
  today for issue-matrix/approval-gating. Add a short, non-gating heads-up.
- **Consume WP01's exported shared helper by import** (`gating_issue_numbers` / `is_gating` from
  `tasks/`). Do NOT re-encode the gating predicate here, and do NOT touch `tasks_parsing_validation.py`
  (WP02 owns it — it imports the same helper). If the helper is missing, STOP and coordinate with
  WP01; do not fork.

## Subtasks

### T011 — Red-first END-STATE test (RED on main) + fail-open guard
`tests/policy/test_issue_matrix_cross_site_consistency.py`, `@pytest.mark.regression`, pinned `#3469`.
Anti-laziness caught that "the three gating sets are IDENTICAL" is **vacuously green on main** (all
three gate every ref identically today). Anchor the RED on the **end-state per-site OUTCOME** instead:
- a context-only citation and a `PR #N` ref are **NON-gating at `merge_gates` AND report clean in
  `doctor`** (RED on main — both demand a matrix row today).
- **Fail-open guard:** a bare unmarked `#N` **STILL gates** at the approval blocker, `merge_gates`, AND
  `doctor` post-fix (guards against a filter that drops everything = fully fail-open).
- **Matrix-set parity:** because `merge_gates` reads `load_issue_matrix` while blocker/doctor add
  diagnostic-regex rows, assert parity on BOTH the referenced set and the matrix set, not just refs.
Keep an "all three agree" assertion as a secondary check, not the red-first anchor.

### T012 — merge_gates consumes the shared helper [P]
Refactor `_evaluate_issue_matrix_completeness_gate` (L393/L395) to derive the gated reference set from
WP01's imported shared helper — do NOT re-encode the predicate. Preserve every other merge-gate
behavior. Align the stale WP09 `not_applicable` comment (L375–378) to WP02's ADR.

### T013 — doctor consumes the shared helper [P]
Refactor the `status/doctor.py` issue-matrix completeness check (L433/L439) to use the same imported
helper. A `not-applicable`/non-gating reference must not report dirty.

### T014 — Early approval-gating warning [P]
Add a concise, non-gating note to each of the four mission-step prompts (specify, plan, tasks,
analyze) stating that approvals will require an issue-matrix verdict for referenced implementation
issues, and that context-only/PR references classify non-gating (or can be marked `not-applicable`).
Keep it short; do not turn it into a gate.

## Branch Strategy

Planning base `fix/move-task-approval-ergonomics`; branches from WP02's result; merges back to the
same branch (then upstream `main` via PR). Worktree per computed lane from `lanes.json`.

## Test Strategy (ATDD / red-first — required)

T011 RED first, exercising all three consumers against one classifier, pinned `#3469`. Targeted:
`PWHEADLESS=1 .venv/bin/python -m pytest tests/policy/ tests/status/ -q -k "issue_matrix or consistency"`.

## Definition of Done

- `merge_gates` and `doctor` derive gating from the WP01 classifier; NFR-006 consistency test GREEN.
- Early-warning note present in all four mission-step prompts.
- Stale WP09 `not_applicable` comment in merge_gates aligned to the ADR.
- T011 RED→GREEN; ruff + mypy --strict clean; complexity ≤15.

## Reviewer Guidance

Confirm all three sites share ONE decision (no residual independent `referenced - matrix`
computation). Confirm the early-warning note is non-gating prose. Confirm no second `not_applicable`
authority was introduced.
