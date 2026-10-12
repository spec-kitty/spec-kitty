---
work_package_id: WP01
title: Derive the audit trigger list and remove the hand copy
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
planning_base_branch: issue-6090-audit-trigger-derivation
merge_target_branch: issue-6090-audit-trigger-derivation
branch_strategy: Planning artifacts for this mission were generated on issue-6090-audit-trigger-derivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6090-audit-trigger-derivation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-audit-trigger-derivation-01M4RKRD
base_commit: 47f900745172142448cfdca76a1cdda703892a39
created_at: '2026-10-12T18:02:10.445238+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Derived trigger check
history:
- at: '2026-10-12T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/ci/test_mission_state_audit_routing.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/ci/test_mission_state_audit_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Derive the audit trigger list and remove the hand copy

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (role: implementer). Follow its guidance before implementing.

## Objectives & Success Criteria

- The audit's executed-module set is **derived** at test time from an in-process
  `run_audit` on a small git fixture — not hand-listed.
- The test is **non-vacuous** and **self-mutation-proven**: RED when the audit
  executes a `src/` module no `mission_state` glob matches (planted module or
  dropped glob), GREEN on the real current code; carries a same-fixture positive
  control (derived set asserted non-empty and containing known audit anchors).
- `AUDIT_INPUT_PATHS` is removed; its two consumers read the derived set plus a
  small explicit non-executed-input list (manifests, workflow, renderer).
- No `ci-router.yml` edit (all executed modules already covered); no runtime
  behaviour change; no suppressions; mypy-clean; complexity ≤ 15.

## Context & Constraints

- Spec: `kitty-specs/audit-trigger-derivation-01M4RKRD/spec.md`
- Plan: `kitty-specs/audit-trigger-derivation-01M4RKRD/plan.md`
- Grounding: `kitty-specs/audit-trigger-derivation-01M4RKRD/research/code-grounding.md`
- Charter SO#5 (non-vacuous gate), SO#6 (canonical-source unification), C-011 (ATDD).
- Reuse `scripts/ci/gate_selection.load_router`/`select_gates` for coverage — never restate globs.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-6090-audit-trigger-derivation`; completed changes must merge back into `issue-6090-audit-trigger-derivation`.
- **Planning base branch**: `issue-6090-audit-trigger-derivation`
- **Merge target branch**: `issue-6090-audit-trigger-derivation`

## Subtasks & Detailed Guidance

### Subtask T001 – Derived non-vacuity test + fixture (failing-first)

- **Purpose**: Derive the executed-module set and assert glob coverage (the acceptance test).
- **Steps**:
  1. Build a `tmp_path` git fixture: one modern mission under `kitty-specs/<slug>/`
     with `meta.json` (`mission_id`, no legacy `feature_slug`), a valid
     `status.events.jsonl` (events keyed on `mission_id`), a reducer-generated
     `status.json`, `spec.md`, and `tasks/WP01.md`; `git init` + commit.
  2. Warm up with one `run_audit(AuditOptions(repo_root, scan_root=<kitty-specs>, …))`,
     then profile a second `run_audit` under `sys.setprofile`, recording only
     function-call frames (`co_name != '<module>'`).
  3. Map executed filenames under `src/` to repo-relative module paths.
  4. Assert the derived set is non-empty and includes anchors
     (`src/specify_cli/audit/engine.py`, `src/specify_cli/status/reducer.py`) —
     positive control — then assert each executed module ∈ `mission_state` group
     via `select_gates([m], router=load_router()).matched_groups`.
- **Files**: `tests/ci/test_mission_state_audit_routing.py`.
- **Notes**: Witness RED by (a) planting an out-of-glob executed module and (b)
  dropping a covering glob; record the commands/outputs; **do not commit the break**.

### Subtask T002 – Remove the hand copy; re-point consumers

- **Purpose**: Canonical-source unification (SO#6).
- **Steps**: Delete `AUDIT_INPUT_PATHS`; re-point `test_audit_inputs_match_the_group_directly`
  (executed-src-module rows → derived set; manifests/workflow/renderer → a small
  explicit `NON_EXECUTED_TRIGGER_INPUTS` list that keeps the manifest/alignment
  assertions) and `test_the_reducer_bump_commit_selects_the_audit_job` (keep the
  `MANIFESTS` alignment).
- **Files**: `tests/ci/test_mission_state_audit_routing.py`.

### Subtask T003 – Validate

- **Steps**: Run by name `tests/ci/test_mission_state_audit_routing.py` + sibling
  guards (`tests/architectural/test_ci_router_transcription_guards.py`,
  `tests/ci/test_contracts_workflows.py`) + `make test-fast`. `ruff check`,
  `ruff format --check --force-exclude` (via `make format-check-files`), mypy on
  the changed file; complexity ≤ 15.

## Test Strategy

- The WP's deliverable is the test itself. Red-first proof = the witnessed
  self-mutation (both directions). Typecheck: `.venv/bin/python -m mypy` on the
  changed file (matching CI).

## Risks & Mitigations

- Capture order-sensitivity → warm-up + function-call frames only.
- Fixture artifact modules → modern `mission_id` events + reducer-generated `status.json`.

## Review Guidance

- Verify RED→GREEN: the derived test catches a planted out-of-glob module and is
  green on the real set. Confirm `AUDIT_INPUT_PATHS` is gone and coverage still holds.
- Confirm no `ci-router.yml` change and no suppressions.

## Progress & Status

Progress/status live in `status.events.jsonl`. Record with
`spec-kitty agent tasks add-history WP01 --note "…"` and `move-task`.
