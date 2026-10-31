---
work_package_id: WP02
title: Accept guidance follows the landing path
dependencies: []
requirement_refs:
- FR-003
- FR-004
- C-002
- SC-002
planning_base_branch: issue-6450-consolidate-run-gap-truthfulness
merge_target_branch: issue-6450-consolidate-run-gap-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6450-consolidate-run-gap-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6450-consolidate-run-gap-truthfulness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-run-gap-truthfulness-01M68ZR2
base_commit: 3f802bc1a04cbe1d4ea64217180072b3b75fce17
created_at: '2026-10-31T13:26:42.241899+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Message truthfulness
history:
- at: '2026-10-31T12:46:28Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/acceptance/__init__.py
- tests/specify_cli/test_acceptance_regressions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Accept guidance follows the landing path

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Load the PM profile first: `spec-kitty agent profile show python-pedro`, then
`spec-kitty charter context --action implement`.

---

## Objectives & Success Criteria

Fix #6450 item (6): on coordination topology `accept` prints "Acceptance recorded on integration
branch `<branch>`. Push and open a pull request if needed."
(`src/specify_cli/acceptance/__init__.py:1951`). A coordination-topology Mission is landed by
`spec-kitty consolidate`; there is no pull request to open, and the sentence contradicts the
consolidation instruction the rest of the tool gives.

Done when:

- `_build_acceptance_instructions` emits, for a coordination-topology Mission in `pr` mode on its
  integration/target branch, an instruction that names `spec-kitty consolidate --mission <slug>` and
  contains no "pull request" text.
- Every other arm is byte-identical: non-coordination integration branch in `pr` mode keeps the
  existing sentence (positive control), and the `local`/`checklist` arms are untouched.

## Context & Constraints

Read first:

- `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md` — FR-003, FR-004, SC-002 and the
  edge cases.
- `src/specify_cli/acceptance/__init__.py` — `_build_acceptance_instructions` (the message builder)
  and `perform_acceptance` (where `is_integration_branch` and `_target_branch` are computed).
- `tests/specify_cli/test_acceptance_regressions.py` — the existing instruction/cleanup assertions
  (including the "should not suggest deleting integration branch" family) to extend.
- `src/specify_cli/mission_metadata.py::load_meta_or_empty` — the existing meta read already used by
  `_consolidate_lands_branch`; reuse it for the topology fact.

Constraints that matter:

- **C-002**: no gate, protection-policy or ref-destination change; this is a message fix.
- Do not add a second `target_branch` read authority or a new topology resolver.
- The misleading sentence must survive for non-coordination topologies (FR-004 is the positive
  control on the same helper).

## Branch Strategy

- **Strategy**: workspace-per-work-package on a lanes-topology Mission; the WP executes in its
  computed lane worktree and merges back into the mission target branch.
- **Planning base branch**: `issue-6450-consolidate-run-gap-truthfulness`
- **Merge target branch**: `issue-6450-consolidate-run-gap-truthfulness`

> Populated by `specify_cli`. Do not edit by hand.

## Subtasks & Detailed Guidance

### T005 — Red-first tests

Add to `tests/specify_cli/test_acceptance_regressions.py`:

1. **Coord topology, `pr` mode, integration branch**: a `meta.json` with `topology: coord` and a
   `coordination_branch`, `branch == target_branch`, `mode="pr"`. Assert the rendered instructions
   contain `spec-kitty consolidate` and that no instruction matches `pull request` (case-insensitive).
2. **Positive control, same helper**: a `lanes`/`single_branch` meta with `branch == target_branch`,
   `mode="pr"` → the existing "Push and open a pull request if needed." sentence is still present.

Both must be runnable without a real git repo (the helper is pure); if a `perform_acceptance`-level
test is cheap to add, prefer it, but the helper-level assertions are the required ones.

Record the failing output before the fix.

### T006 — One topology fact

Compute the topology fact once in `perform_acceptance` beside the existing `_target_branch` read
(e.g. `meta = load_meta_or_empty(summary.feature_dir)` once, reuse for both), and pass a keyword
argument such as `lands_by_consolidation: bool` into `_build_acceptance_instructions`. Do not
re-read meta inside the builder.

### T007 — The topology-aware `pr` arm

In the `mode == "pr"` / `is_integration_branch` arm:

- when `lands_by_consolidation` is true, emit something like
  `f"Acceptance recorded on `{branch}`; this Mission lands through `spec-kitty consolidate --mission {summary.feature}` — the coordination branch is internal, so there is no pull request to open."`
  (keep it one line, no trailing period duplication);
- otherwise emit the existing sentence unchanged.

Leave the non-integration `pr` arm, both `local` arms and the `checklist` arm untouched.

## Test Strategy

Helper-level unit tests with hand-built `AcceptanceSummary`/`meta.json` fixtures, plus the existing
acceptance-regression suite as the regression net. No mocks of the message builder.

## Definition of Done

- Red proof recorded, then green.
- `uv run pytest tests/specify_cli/test_acceptance_regressions.py -q` and the wider
  `tests/specify_cli -k acceptance` selection pass.
- `uv run ruff check` / `ruff format --check` / `mypy` clean on the touched files.

## Risks

- Rewording the shared arm for flat topologies → the positive-control test pins the old sentence.
- Emitting the consolidate instruction twice (the non-integration arm already has one) → the coord
  case must stay one instruction.

## Reviewer Guidance

Check that the coord case cannot be reached for a flat topology, that the branch name printed is the
one the operator is on, and that `local`/`checklist` output is untouched.
