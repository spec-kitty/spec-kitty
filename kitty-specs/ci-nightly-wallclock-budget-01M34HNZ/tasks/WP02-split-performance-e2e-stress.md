---
work_package_id: WP02
title: Split performance-and-e2e into Three Jobs (Commit B, FR-001-FR-005, FR-010)
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-010
- NFR-001
- NFR-005
- C-001
- C-005
planning_base_branch: issue-4865-ci-nightly-wallclock-budget
merge_target_branch: issue-4865-ci-nightly-wallclock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4865-ci-nightly-wallclock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4865-ci-nightly-wallclock-budget unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Job Split (Functional)
history:
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- tests/architectural/test_performance_marker_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Split performance-and-e2e into Three Jobs (Commit B)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (unset — select per `spec-kitty agent profile list` if not pre-assigned)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*None yet.*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````yaml`, ````python`, ````bash`

---

## Objectives & Success Criteria

Replace `ci-nightly.yml`'s single `performance-and-e2e` job (already campsite-cleaned by WP01)
with **three independent jobs** — `performance`, `e2e`, `stress` — each with its own
`timeout-minutes`, own verdict, own checkout+sync+suite-step+artifact-upload+fail-loud shape.
Update `nightly-summary`'s `needs:` list. Update the three
`tests/architectural/test_performance_marker_guard.py` tests that hardcode the literal
`"performance-and-e2e"` job key (FR-010).

This is the mission's P1 core deliverable — spec.md's User Story 1, FR-001 through FR-005 and
FR-010. Success = spec.md's Acceptance Scenarios AC1 (three jobs, no shared marker selection),
AC2 (three separate job entries + updated `needs:`, verified live in WP03), AC3 (stress no longer
truncated by another suite's budget, verified live in WP03), and AC4 (guard tests keep passing,
with zero new `pull_request`-trigger violations).

## Context & Constraints

- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md` — User Story 1, FR-001–FR-005,
  FR-010, NFR-001, NFR-002, NFR-005, C-001, "Binding operator decision #1" (SPLIT, do not raise
  the cap — explicitly rejected as a half-fix).
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` — "Real evidence used to size the new
  budgets" (the exact timeout values below, pulled from `gh run view 35683539593 --json jobs`),
  Phasing § Phase 1 steps 1a-1d, "Gate set" section (which two of the five guard-file tests are
  the actual C-001/FR-005 enforcement mechanism).
- **Operator decision, binding, do not re-litigate**: split into three jobs, never raise the
  single job's timeout. Raising the cap was explicitly considered and rejected — it would still
  blend three suites' verdicts into one, the exact harm #4865 exists to fix.
- **Real, already-pulled timing data** (plan.md table, from run `35683539593`,
  `spec-kitty/spec-kitty`):

  | Step | Duration | Conclusion |
  |---|---|---|
  | `performance`-marked suite | 23m41s | success |
  | `e2e`-marked suite | 24m44s | success |
  | `stress`-marked suite | >=16m18s (truncated, never completed) | cancelled mid-run |

  Derived timeout values (NOT guessed — derived from the table above with ~1.5x headroom,
  rounded):
  - `performance`: `timeout-minutes: 35`
  - `e2e`: `timeout-minutes: 40`
  - `stress`: `timeout-minutes: 90` — **Stage A, deliberately generous, MEASUREMENT-ONLY. This is
    NOT the shipped value.** WP03 unconditionally re-derives the real, tightened Stage B value
    from a completed dispatch. Use `90` here exactly; do not tune it.

- **Preserve, in each new job**: `actions/checkout@<pinned sha>`, `astral-sh/setup-uv@<pinned
  sha>`, `uv sync --frozen --all-extras`, the job's own `-m <marker>` pytest step (only
  `performance` needs `SPEC_KITTY_RUN_PERFORMANCE: "1"` in `env:` — that variable exists
  specifically because conftest.py skips `performance`-marked tests unless it is set; `e2e` and
  `stress` do not need it), `PWHEADLESS: "1"` (all three, if the current job sets it broadly —
  re-read the live file to confirm exact current scope before splitting), the xunit
  artifact-upload step, and the terminal `if: always()` fail-loud step that treats pytest exit
  code `0` (pass) and `5` (marker-empty/no-tests-collected) as non-failing, only a genuine failure
  exit as failing.
- **Hard constraint (C-001/FR-005)**: none of the three new jobs, and no workflow-level trigger
  change, may introduce a `pull_request` trigger anywhere in this workflow. Enforced by
  `tests/architectural/test_performance_marker_guard.py`'s
  `test_nightly_workflow_never_triggers_on_pull_request` and
  `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` — these two tests are
  the REAL enforcement mechanism for this constraint; do not treat the other three (FR-010's
  targets) as guarding the same thing.

## Branch Strategy

- **Strategy**: `single_branch`.
- **Planning base branch**: `issue-4865-ci-nightly-wallclock-budget`
- **Merge target branch**: `issue-4865-ci-nightly-wallclock-budget`

> Populated automatically by `spec-kitty agent mission tasks`. Do NOT change manually.

## Subtasks & Detailed Guidance

### Subtask T007 – Replace the single job with three independent jobs

- **Purpose**: FR-001 — each suite gets its own job, its own verdict, its own budget.
- **Steps**:
  1. Remove the `performance-and-e2e:` job (already campsite-clean, no `fail-fast` key, per WP01).
  2. Add three sibling jobs: `performance:` (`timeout-minutes: 35`), `e2e:` (`timeout-minutes:
     40`), `stress:` (`timeout-minutes: 90`). No `needs:` dependency chain BETWEEN these three —
     only `nightly-summary` depends on all three (plan.md: they run in parallel where runners are
     available).
  3. Each job: same `runs-on: ubuntu-latest`, its own `steps:` copying the checkout/uv-sync
     preamble, its own single `-m <marker>` pytest invocation (`performance`, `e2e`, `stress`
     respectively — never more than one marker selection per job body), its own artifact upload
     naming the suite (e.g. `out/reports/xunit-nightly-<suite>.xml`), its own terminal fail-loud
     step.
  4. `env:` — only the `performance` job needs `SPEC_KITTY_RUN_PERFORMANCE: "1"`.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No.
- **Notes**: FR-002/NFR-002's falsification: "a `grep` for `uv run --frozen pytest -m` inside one
  job's `steps:` finds more than one marker selection" — self-check this with `grep` after
  editing, per job.

### Subtask T008 – Update `nightly-summary`'s `needs:` list

- **Purpose**: FR-003 — the terminal aggregator must never silently drop a suite's result.
- **Steps**:
  1. Locate `nightly-summary:`'s `needs:` list — currently `[performance-and-e2e,
     interpreter-matrix, full-module-matrix]`.
  2. Change to `[performance, e2e, stress, interpreter-matrix, full-module-matrix]`.
  3. Update the echoed report step to print a result line for each of `performance`, `e2e`,
     `stress` (replacing the single `performance-and-e2e` line) in addition to
     `interpreter-matrix` and `full-module-matrix`.
- **Files**: `.github/workflows/ci-nightly.yml`
- **Parallel?**: No.
- **Notes**: FR-003's falsification: "`nightly-summary`'s `needs:` still lists fewer than the
  three new job names" — re-read the edited `needs:` list literally after editing.

### Subtask T009 – Update the three hardcoded-job-name tests (FR-010)

- **Purpose**: `tests/architectural/test_performance_marker_guard.py` currently hardcodes the
  literal `"performance-and-e2e"` in three tests. FR-001 removes that job key, so these three
  tests will fail once T007 lands unless updated — this is expected, in-scope maintenance
  (spec.md AC4), not evidence of a regression.
- **Steps**:
  1. Locate the three tests: `test_nightly_suite_steps_are_fail_loud`,
     `test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing` (both iterate `for
     job_name in ("performance-and-e2e", "interpreter-matrix")`), and
     `test_nightly_workflow_houses_performance_and_interpreter_jobs` (`assert
     "performance-and-e2e" in jobs`).
  2. Update the first two to iterate `for job_name in ("performance", "e2e", "stress",
     "interpreter-matrix")` (or refactor to dynamically discover the job list — either satisfies
     FR-010's intent) so the fail-loud/exit-5-non-failing guarantee is checked against all three
     new jobs, not silently dropped.
  3. Update the third to assert all three of `"performance"`, `"e2e"`, `"stress"` are present in
     `jobs` (in place of the single `"performance-and-e2e"` check).
  4. Leave `test_nightly_workflow_never_triggers_on_pull_request` and
     `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` UNCHANGED — these are
     not FR-010's targets; they must keep passing unmodified against the new job shape.
- **Files**: `tests/architectural/test_performance_marker_guard.py`
- **Parallel?**: No — depends on T007's job names existing.
- **Notes**: This is FR-010's ENTIRE scope. Do not touch any other test in this file.

### Subtask T010 – `ruff format --check` on the edited Python file

- **Purpose**: `ruff format --check .` is enforced repo-wide (`ci-quality.yml`, `ci-router.yml`,
  `tests/architectural/test_ruff_format_enforcement.py`) — confirmed clean on this file before
  this mission's edit (plan.md "Gate set" section).
- **Steps**: `uv run ruff format --check tests/architectural/test_performance_marker_guard.py` —
  must report clean (no reformatting needed) or run `uv run ruff format
  tests/architectural/test_performance_marker_guard.py` to fix, then re-check.
- **Files**: `tests/architectural/test_performance_marker_guard.py`
- **Parallel?**: `[P]` relative to T011 — both depend on T009 but not on each other (see tasks.md's
  "Dependency & Execution Summary" intra-WP parallelism note).

### Subtask T011 – Run the guard tests, confirm 5/5 pass

- **Purpose**: This is the ONE real pytest-observable proof available for this WP — that no
  `pull_request` trigger was introduced (C-001/FR-005), and that FR-010's edit is internally
  consistent.
- **Steps**:
  1. Run `uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q`.
  2. Confirm all 5 tests pass, specifically confirm
     `test_nightly_workflow_never_triggers_on_pull_request` and
     `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` pass with ZERO new
     violations naming any of `performance`/`e2e`/`stress` or a new workflow-level trigger — that
     would be the genuine regression AC4 guards against.
- **Files**: None edited; verification only.
- **Parallel?**: `[P]` relative to T010 — both depend on T009 but not on each other (see tasks.md's
  "Dependency & Execution Summary" intra-WP parallelism note).
- **Notes**: A failure in the other three tests (the FR-010 targets) at this point means T009 is
  incomplete, not that AC4 is violated — distinguish the two failure modes explicitly if
  anything fails.

### Subtask T012 – Commit as `feat(ci)`

- **Purpose**: One functional commit covering FR-001–FR-005 and FR-010 together — plan.md's
  explicit reasoning: the guard-test edit is the only diff-cover-measurable Python edit paired
  with this behavior change, so it is folded into this same commit rather than split out.
- **Steps**:
  1. Stage `.github/workflows/ci-nightly.yml` and
     `tests/architectural/test_performance_marker_guard.py` together.
  2. Commit with a message like: `feat(ci): split performance-and-e2e into independent
     performance/e2e/stress jobs` — body should reference FR-001–FR-005/FR-010 and note Stage A's
     `stress` timeout (90) is provisional, re-derived by the next WP.
- **Files**: `.github/workflows/ci-nightly.yml`, `tests/architectural/test_performance_marker_guard.py`
- **Parallel?**: No.

## Red-first / revert discipline (concrete, for this WP)

A pytest RED is structurally impossible for this WP's central live-topology claim ("three
independent jobs actually run and report independently") — a pytest process parses YAML statically,
it cannot observe a live GitHub Actions run's job list or verdicts. **The falsification mechanism**
is WP03's pre-merge `workflow_dispatch`: the ALREADY-CITED run `35683539593` (2026-09-22, single
blended `performance-and-e2e` verdict, `cancelled` at 65m01s) IS the "red" baseline — no fresh
revert-and-redispatch cycle is needed. WP03's post-split dispatch is the "green." **What T011 DOES
prove, and is real**: no `pull_request` trigger was introduced by this split (C-001/FR-005), which
IS a pytest-observable claim.

## Test Strategy

- `uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q` — mandatory,
  T011.
- `uv run ruff format --check tests/architectural/test_performance_marker_guard.py` — mandatory,
  T010.
- No compiler/typecheck applies (workflow YAML + one test file edit; `mypy --strict` scope is
  `src/**`, not touched here).

## Risks & Mitigations

- **Risk**: dropping `SPEC_KITTY_RUN_PERFORMANCE: "1"` from the split `performance` job (it would
  silently skip the entire suite — a vacuous lane). **Mitigation**: T007 explicit callout; T011's
  guard tests will not catch a skipped-but-not-failing suite, so double-check this env var
  manually.
- **Risk**: `nightly-summary`'s echoed report step is updated for `needs:` but the print
  statements are forgotten. **Mitigation**: T008 explicitly requires both.

## Review Guidance

- Confirm exactly one `-m <marker>` pytest invocation per new job (`grep` check).
- Confirm `needs:` list and echoed report both name all three new jobs.
- Confirm the two pull_request-trigger-detection tests are UNCHANGED in this diff (only the three
  FR-010 targets should show a diff).
- Confirm `stress`'s timeout is exactly `90` in this commit (Stage A) — a different value here
  means WP03's Stage B logic was pulled forward prematurely.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-22T14:15:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP02 --to
<status>` to change WP status.
