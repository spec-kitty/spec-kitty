---
work_package_id: WP02
title: Refusal text for an unresolvable window
dependencies:
- WP01
requirement_refs:
- FR-003
- SC-004
- C-001
- C-002
planning_base_branch: issue-7209-skip-lanes-planning-commit
merge_target_branch: issue-7209-skip-lanes-planning-commit
branch_strategy: Planning artifacts for this mission were generated on issue-7209-skip-lanes-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7209-skip-lanes-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
phase: Phase 2 - The refusal
history:
- at: '2026-11-05T15:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/wp_evidence.py
- tests/consolidation/test_evidence_window_refusal_text.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- tests/consolidation/test_evidence_window_refusal_text.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7209'
- '#7210'
---

# Work Package Prompt: WP02 – Refusal text for an unresolvable window

## Do This First: Load Agent Profile

Load `python-pedro` (implementer, `skills/spk-charter-profile-load`).

## Review Feedback

Check the `review_ref` in the status event log; address every item.

## Objectives & Success Criteria

Keep `EVIDENCE_WINDOW_UNCOMPUTABLE` refusing when no base can be resolved, and make its recovery
honest for both shapes (FR-003, SC-004):

1. The refusal line stops asserting "lanes.json records no planning commit" — a `--skip-lanes`
   Mission need have no `lanes.json` — while the code still leads the line.
2. `_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]` keeps the `finalize-tasks` advice for a recorded but
   unpinned `lanes.json` (#7210) and adds the remedy that works for a Mission with no
   `lanes.json`: commit the Mission's planning artifacts (`kitty-specs/<slug>/`) on the target
   branch so its start is in history, then re-run.
3. Nothing else changes: no new code, no new attestation, no different verdict.

## Context & Constraints

- `_lanes_refusal_text` renders one recovery line per code that leads a line; `_RECOVERY` is the
  only recovery authority for this code on the consolidate/accept surfaces.
- `tests/consolidation/test_wp_evidence.py`, `test_lane_evidence_axis.py` and
  `test_single_branch_evidence_axis.py` assert the code prefixes and `_refusal_codes`; keep the
  line-leading `EVIDENCE_WINDOW_UNCOMPUTABLE: ` shape.
- `tasks_move_task`'s own refusal text is a different surface and stays untouched.
- WP01 owns `entry_preflight.py` and the CLI fixture; do not edit them.

## Branch Strategy

- Planning base and merge target: the branch the CLI reports for this mission; the PR targets
  `spec-kitty/spec-kitty` `main`, which only the operator merges.

## Subtasks

### T005 – Red-first: pin the line and the recovery

Create `tests/consolidation/test_evidence_window_refusal_text.py`:

- Build a no-lane manifest with `planning_commit_sha=None` (a synthesized manifest from
  `_synthesize_no_lane_manifest` over a repo whose Mission directory is not committed, or a
  hand-built equivalent for the text-only case) and an approved work package whose
  `owned_files` resolve.
- Assert `evaluate_evidence(...).refusal` leads with `EVIDENCE_WINDOW_UNCOMPUTABLE: <WP>` and the
  recovery line names committing the Mission's planning artifacts on the target branch.
- Pair it with a positive control on the same fixture family: once the base resolves (WP01), the
  same helper produces no refusal — so the test proves the probe discriminates, not that it
  always returns the refusal text.
- Assert the `finalize-tasks` advice survives for the recorded-but-unpinned case (a `lanes.json`
  with no `planning_commit_sha`), so #7210's remedy is not lost.

Commit RED.

### T006 – Implement

In `src/specify_cli/consolidation/wp_evidence.py`:

- `_scan_lane`: when `lane_evidence_window` is `None`, the line says no planning commit is
  *recorded or resolvable* (drop the lanes.json-specific claim), keeping
  `EVIDENCE_WINDOW_UNCOMPUTABLE` first.
- `_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]`: keep `finalize-tasks`, then add the no-`lanes.json`
  remedy. Keep it one line of prose, under the changelog-style limit, and name
  `kitty-specs/<slug>/` and the target branch.
- Update the module docstring's first verdict sentence to match.

Run:

```bash
uv run --frozen pytest tests/consolidation/test_evidence_window_refusal_text.py tests/consolidation/test_wp_evidence.py tests/consolidation/test_lane_evidence_axis.py tests/consolidation/test_single_branch_evidence_axis.py tests/consolidation/test_evidence_code_literals.py -q
uv run --frozen ruff check src/specify_cli/consolidation/wp_evidence.py tests/consolidation/test_evidence_window_refusal_text.py
uv run --frozen ruff format --check src/specify_cli/consolidation/wp_evidence.py tests/consolidation/test_evidence_window_refusal_text.py
```

## Definition of Done

- The refusal code, its precedence and its liftability are unchanged.
- Both shapes have a remedy an operator can perform.
- No test that pins the code prefix needed loosening.
