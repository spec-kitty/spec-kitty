---
work_package_id: WP02
title: Align the single_branch move-side refusal wording (#6369 scenario 6)
dependencies: []
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: issue-6370-single-branch-gate-fallout
merge_target_branch: issue-6370-single-branch-gate-fallout
branch_strategy: Planning artifacts for this mission were generated on issue-6370-single-branch-gate-fallout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6370-single-branch-gate-fallout unless the human explicitly redirects the landing branch.
subtasks:
- T003
- T004
- T005
phase: Phase 1 - Fallout fixes
history:
- at: '2026-10-18T13:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Align the single_branch move-side refusal wording (#6369 scenario 6)

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (`packs/built-in/agent_profiles/implementer-ivan.agent.yaml`) and follow its guidance.

## Objectives & Success Criteria

The move-side `SINGLE_BRANCH_IMPLEMENTATION_MISSING` refusal says "no implementation commit" (FR-003, SC-002). The code, the decision logic and the JSON envelope are unchanged (C-001, C-002).

## Context & Constraints

- `tests/scenarios/mission/single-branch.feature` scenario "A work package with no committed work cannot go to review" asserts "no implementation commit". `_mt_require_single_branch_implementation` (`src/specify_cli/cli/commands/agent/tasks_move_task.py`) now refuses before `lanes/for_review_gate.py`, with different words.
- The plan's decision record explains why the wording is aligned and the code is not asserted.

## Subtasks & Detailed Guidance

### Subtask T003 – Red-first unit test

- New `tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py`. Drive `_mt_require_single_branch_implementation` with a minimal state: a single_branch manifest, a computable window, and a diff that touches no owned file. Assert `ActionContextError.code == "SINGLE_BRANCH_IMPLEMENTATION_MISSING"` and that `"no implementation commit"` is in the message. It must fail on the old wording.
- Add a positive control on the same fixture: a diff that touches an owned file → no refusal.

### Subtask T004 – Reword

- Message: `"{wp} cannot move to {lane}: no implementation commit on the single_branch mission branch touches its owned_files …"`. Keep the remedy sentence.

### Subtask T005 – Audit fold-in

- Fold in the background audit's in-scope findings; report the rest in the PR.
- Add a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry.

## Test Strategy

- `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py tests/integration/test_5939_single_branch_autowalk_guards.py tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py -q`
- Shell port of scenario 6 (session scratchpad), plus `make test-fast`.
- `ruff check`, `ruff format --check --force-exclude` and `mypy` on changed files.

## Risks & Mitigations

- Docs and scenarios asserting the old prose: a grep found none.

## Review Guidance

- Message-only diff in `src/`. The unit test is non-vacuous (red on old wording) and has a positive control.
