---
work_package_id: WP02
title: Descriptive mission.yaml + doc reconcile
dependencies: []
requirement_refs:
- FR-006
planning_base_branch: fix/plan-guard-artifact-vocabulary
merge_target_branch: fix/plan-guard-artifact-vocabulary
branch_strategy: Planning artifacts for this mission were generated on fix/plan-guard-artifact-vocabulary. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/plan-guard-artifact-vocabulary unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-plan-guard-artifact-vocabulary-01M57FKP
base_commit: d571aa34fe06ceff2605b90e1eb0e682f69c3a7c
created_at: '2026-10-18T12:36:35.370532+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Descriptive coherence
history:
- timestamp: '2026-10-18T09:20:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/plan/
create_intent: []
execution_mode: code_change
mission_id: 01M57FKP4Z0HV4E5AQVPQEKX31
model: sonnet
owned_files:
- packs/built-in/missions/plan/mission.yaml
- src/specify_cli/missions/plan/mission.yaml
- src/charter/offering/skills/spec-kitty-mission-system/references/mission-comparison-matrix.md
role: implementer
tags: []
tracker_refs: []
wp_code: WP02
---

# Work Package Prompt: WP02 — Descriptive mission.yaml + doc reconcile

## ⚡ Do This First: Load Agent Profile

Load your agent profile via `/spk-charter-profile-load` with profile id **`python-pedro`**, adopt its
scope/boundaries, then read `kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/{spec.md,plan.md,research.md}`.

## Objective

Reconcile the two descriptive `plan` `mission.yaml` copies and the reference doc to the canonical runtime
action vocabulary (`specify/research/plan/review`; artifacts `spec.md`/`plan.md`), removing the stale
`goals.md` phantom and the `goals/structure/draft` phase vocabulary where it misrepresents the shipped
mission. These surfaces are **descriptive-only** — no runtime consumer reads them on the gather/guard
path (confirmed: only `expected-artifacts.yaml` feeds `_presence_filenames_for`/`required_artifacts_for`).
This WP must not change runtime behavior.

## Context & Constraints

- **Descriptive-only** (confirmed this session by grep): nothing reads `mission.yaml`'s
  `artifacts.required` / `workflow.phases` on the gather/guard path. Keep this WP coherence-only — do not
  turn these fields into a second authority.
- **Independent of WP01** (disjoint write scope): WP01 owns `expected-artifacts.yaml` + tests; this WP
  owns the two `mission.yaml` copies + the doc. No dependency.
- Do NOT touch `expected-artifacts.yaml`, the guard, or any test owned by WP01.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`.

## Subtasks & Detailed Guidance

### T007 — Reconcile `packs/built-in/missions/plan/mission.yaml`

- Update `artifacts.required` from `[goals.md, plan.md]` to the action vocabulary (`[spec.md, plan.md]`)
  and align/annotate `workflow.phases` so the file no longer presents the stale `goals.md`/`goals` phase
  as the plan specify output. Keep it internally consistent with the `commands:` block (specify/plan/review).
- Preserve YAML validity and any fields other consumers DO read (e.g. `name`, `description`, `commands`,
  checks) — only the descriptive artifact/phase naming changes.

### T008 — Reconcile duplicate `src/specify_cli/missions/plan/mission.yaml`

- Apply the same reconciliation to the duplicate copy in the second package tree so the two do not drift.

### T009 — Update the doc matrix

- `src/charter/offering/skills/spec-kitty-mission-system/references/mission-comparison-matrix.md`: update
  the plan row that references `goals.md` to the action vocabulary (`spec.md`).

### T010 — Verify

- `mark-status` T007–T009 done.
- Confirm no runtime behavior change: run the charter/mission suites that load mission.yaml
  (`tests/charter/`, `tests/mission_runtime/`, `tests/specify_cli/` mission-template tests) narrowly and
  confirm green; confirm no test asserted the old `goals.md` phase for plan in a way this WP breaks
  (if one does and it is WP01-owned, coordinate — it belongs to WP01's mirror updates, not here).

## Branch Strategy

Planning/base = final merge target = `fix/plan-guard-artifact-vocabulary` (PR to `main`, operator
merges). Execution worktrees are allocated per computed lane from `lanes.json`.

## Test Strategy

```bash
PYTHONPATH="$PWD/src:$PWD" /home/stijn/Documents/_code/SDD/fork/spec-kitty/.venv/bin/python -m pytest \
  tests/charter/ tests/mission_runtime/ -q -k "mission_yaml or plan or template" 2>&1 | tail -20
```
Record commands + counts. Do NOT run `make test-full`.

## Definition of Done

- Both `mission.yaml` copies and the doc reference the action vocabulary (no `goals.md` phantom), stay
  YAML-valid, and change no runtime behavior.
- No overlap with WP01's owned files; no edit to `expected-artifacts.yaml` or the guard.

## Risks & Reviewer Guidance

- **Reviewer**: confirm this is purely descriptive — no runtime consumer of the changed fields; the
  charter/mission suites stay green.
- Confirm the two `mission.yaml` copies are reconciled identically (no new drift between them).
