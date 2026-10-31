---
work_package_id: WP02
title: The verdict states what the candidate command did
dependencies:
- WP01
requirement_refs:
- FR-004
- C-001
- SC-004
planning_base_branch: issue-6751-opaque-failure-identity
merge_target_branch: issue-6751-opaque-failure-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6751-opaque-failure-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6751-opaque-failure-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-opaque-failure-identity-01M67HQA
base_commit: 9f4e2411f086c00304e3615e3e1d8bcbf0718f90
created_at: '2026-10-31T00:18:23.885105+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Verdict surface
history:
- timestamp: '2026-10-30T23:30:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/pre_review_gate.py
create_intent:
- src/specify_cli/review/pre_review_gate.py
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/review/test_verdict_candidate_exit.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/pre_review_gate.py
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/review/test_verdict_candidate_exit.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6751'
---

# Work Package Prompt: WP02 – The verdict states what the candidate command did

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and run
`spec-kitty charter context --action implement --json`; apply both before coding.

## Objectives & Success Criteria

A baseline-relative `no_new_failures` must never be readable as "the candidate command
exited 0". Carry the candidate run's observed exit status into the verdict and say what the
verdict is relative to — without adding a metadata key the transition-gate parity oracle
would reject (see `research.md`, "Constraint discovered").

1. **Verdict field and reason (T005).** In `src/specify_cli/review/pre_review_gate.py`:
   - `GateVerdict` gains `candidate_exit_code: int | None = None`.
   - `_classify_current_failures` gains `candidate_exit_code: int | None = None` and records
     it on every `GateVerdict` it returns. For `NO_NEW_FAILURES` with a known exit status it
     sets `reason` to a baseline-relative statement naming the observed exit, the
     pre-existing count and the new count, and stating explicitly that the verdict does not
     assert a clean candidate exit. When the pre-existing set contains an opaque failure,
     the reason names the matched opaque identity (exit status + summary) so a reader can
     tell an identity match from a guess. `NEW_FAILURES`, `UNVERIFIED_BASELINE` and
     `SOURCE_MISMATCH` reasons stay unchanged.
   - `_evaluate_via_scope_source` passes `raw.returncode`. The legacy JUnit branch
     (`evaluate_with_scope` without `scope_source`) passes nothing — JUnit parsing yields
     real test names, never the opaque placeholder, so `candidate_exit_code` stays `None`
     there.
   - Do **not** add a `candidate_exit_code` key to `_mt_pre_review_gate_metadata`: the
     verdict's `reason` is already recorded in that payload.

2. **Renderer (T006).** In `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`,
   `_mt_pre_review_gate_console_warning` appends the reason to the existing
   `NO_NEW_FAILURES` dim line **only when the verdict carries one**: with `reason is None`
   the line stays byte-identical (`[dim]Pre-review regression gate: no new failures[/dim]`),
   so every `tests/review/fixtures/parity/*.json` fixture still matches exactly (metadata
   and console). The `NEW_FAILURES` line and `_mt_pre_review_gate_block_message` are
   untouched.

3. **Integration tests (T007).** Create `tests/review/test_verdict_candidate_exit.py`,
   driving `evaluate_with_scope(scope=..., baseline=..., scope_source=…)` (or the narrowest
   existing seam that exercises `_evaluate_via_scope_source`) with a stub/synthetic
   declared command source where the real `RawRunResult.returncode` is observable:
   - candidate exits `2` with a failure present in the baseline → `NO_NEW_FAILURES`,
     `candidate_exit_code == 2`, reason names the exit and says baseline-relative;
   - candidate exits `0` with no failures → `NO_NEW_FAILURES`, `candidate_exit_code == 0`,
     no new and no pre-existing failures;
   - candidate exits `1` with an opaque failure differing from the baseline's → 
     `NEW_FAILURES` (the WP01 identity rule proved through the gate, not the helper alone);
   - the same two verdicts rendered through `_mt_pre_review_gate_metadata` /
     `_mt_pre_review_gate_console_warning`: metadata keys are exactly the incumbent set, and
     a `reason is None` verdict still renders the incumbent dim string.

## Constraints

- Never weaken the opt-in block predicate (`block_enabled AND any(NEW_FAILURES) AND not
  force`) or the terminal precedence; assert them unchanged (C-001).
- Parity fixtures under `tests/review/fixtures/parity/` are an oracle captured from the base
  commit: do not regenerate or edit them.
- Only the four owned files above; no unrelated refactor.

## Validation (targeted test surface)

- `.venv/bin/python -m pytest tests/review/test_verdict_candidate_exit.py tests/review/test_transition_gate_parity.py tests/review/test_pre_review_gate_engine.py tests/review/test_pre_review_gate_source_mismatch.py -q`
- `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py -q`
- `make format-check-files FILES=src/specify_cli/review/pre_review_gate.py src/specify_cli/cli/commands/agent/tasks_move_task_gates.py tests/review/test_verdict_candidate_exit.py`
- mypy on the two product modules.
- Record the red-first vector for this WP in the completion note: before T005, a
  `NO_NEW_FAILURES` verdict from a nonzero candidate carries `candidate_exit_code is None`
  and no reason (assert it in the test, watch it fail, then fix).
