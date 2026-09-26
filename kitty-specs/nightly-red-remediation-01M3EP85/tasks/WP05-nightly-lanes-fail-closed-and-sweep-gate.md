---
work_package_id: WP05
title: Nightly lanes fail closed + sweep gate re-aim
dependencies: []
requirement_refs:
- FR-010
- FR-011
planning_base_branch: claude/lucid-ptolemy-fjtzep
merge_target_branch: claude/lucid-ptolemy-fjtzep
branch_strategy: Planning artifacts for this mission were generated on claude/lucid-ptolemy-fjtzep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/lucid-ptolemy-fjtzep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-red-remediation-01M3EP85
base_commit: 9810f2cfa014b77704d58b99c93a915717d7f6ba
created_at: '2026-09-26T11:15:02.158978+00:00'
subtasks:
- T017
- T018
- T019
- T020
phase: Phase 2 - CI honesty
history:
- at: '2026-09-26T11:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_nightly_overrun_fail_closed.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- tests/ci/test_nightly_overrun_fail_closed.py
- tests/specify_cli/invocation/test_doctor_ops.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Nightly lanes fail closed + sweep gate re-aim

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing.

---

## Objectives & Success Criteria

- An overrunning interpreter-matrix suite step fails *that step*, so upload, escalation (conclusion `failure`) and the fail-loud step still run.
- `nightly-summary` exits 1 when any `needs.*.result` is not `success`.
- The doctor-ops large-spine sweep gate measures only the close loop and detects spine-proportional per-close cost.

## Context & Constraints

- Research R-4 and R-5.
- `ci-nightly.yml:369` (`timeout-minutes: 45` at job level); the suite step at ~411; `nightly-summary` at ~651.
- Existing shape tests: `tests/ci/test_nightly_exit_code_honesty.py` (reuse its YAML-loading approach).
- `tests/integration` stays nightly-only (C-003).

## Subtasks & Detailed Guidance

### Subtask T017 – Bound the interpreter suite step

- **Steps**:
  - Add `timeout-minutes: 60` on the "Run fast/unit suite" step and raise the job `timeout-minutes` to 75, so the step cap is below the job cap with room for upload and escalation.
  - Add `--timeout=600` to the pytest invocation so a genuine deadlock fails one test.
  - A comment derives the numbers: a local 4-worker 3.13 run took 29m42s, and ceil(~40 × 1.5) = 60. Note that they should be re-derived from the first honest run.
  - A step timeout leaves `INTERPRETER_EXIT` unset, so the existing `:-1` sentinel yields a failure conclusion.

### Subtask T018 – Summary fails closed

- **Steps**: After the echo lines, loop over the six results. If any is not `success`, `echo "::error::…"` and `exit 1`. Pass the results through `env:` rather than interpolating `${{ }}` into the script body.

### Subtask T019 – Shape tests

- **Steps**: Create `tests/ci/test_nightly_overrun_fail_closed.py`. Parse the real `ci-nightly.yml` and assert:
  1. The interpreter suite step has `timeout-minutes` strictly below the job `timeout-minutes`.
  2. The upload, escalate and fail-loud steps after it are `if: always()`.
  3. The pytest command carries `--timeout=`.
  4. The `nightly-summary` run script exits non-zero on a non-success result: render the script with a `cancelled` result substituted and run it through `bash`, as `test_nightly_exit_code_honesty.py` does where applicable.
- Mark the tests `fast`.

### Subtask T020 – Re-aim the sweep gate

- **Test**: `tests/specify_cli/invocation/test_doctor_ops.py::test_sweep_real_closes_against_large_spine_under_2s` (~line 575).
- **Steps**:
  - Construct the executor or registry outside the timed window, via a warm-up call or by building it before `perf_counter`.
  - Add a companion scaling check: time the same 100 closes against a 1k spine and a 10k spine, and assert `t10k / max(t1k, ε) < 3`.
  - Keep an absolute budget re-derived with headroom (5.0s, matching the siblings' rationale docstring).
  - Keep the test name's semantics, or rename it to drop "under_2s" if the budget changes, and update references.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/ci -q
SPEC_KITTY_RUN_PERFORMANCE=1 .venv/bin/python -m pytest -m performance tests/specify_cli/invocation/test_doctor_ops.py -q   # x3
```

## Risks & Mitigations

- `actionlint` is not available locally: keep the YAML minimal and validate that it parses in the shape test.

## Branch Strategy

- **Strategy**: single_branch mission; the execution workspace is resolved per computed lane from `lanes.json`.
- **Planning base branch**: `claude/lucid-ptolemy-fjtzep`
- **Merge target branch**: `claude/lucid-ptolemy-fjtzep`

## Definition of Done

- Every listed test passes locally.
- No test is skipped, xfailed, deleted or retried (C-001).
- `ruff check` and `ruff format --check` are clean on the touched files.
- Every re-pin carries a docstring or comment citing the product change that moved the contract.

## Activity Log

- 2026-09-26T11:30:00Z – system – Prompt created.
