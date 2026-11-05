---
work_package_id: WP01
title: The cap is derived from measurement, and a budget expiry is legible
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7206-corpus-advisory-budget
merge_target_branch: issue-7206-corpus-advisory-budget
branch_strategy: Planning artifacts for this mission were generated on issue-7206-corpus-advisory-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7206-corpus-advisory-budget unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Workflow change and proof
history:
- at: '2026-11-05T15:16:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_corpus_suite_budget.py
execution_mode: code_change
owned_files:
- .github/workflows/packs.yml
- tests/ci/test_nightly_timeout_headroom.py
- tests/ci/test_corpus_suite_budget.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7206'
---

# Work Package Prompt: WP01 – The cap is derived from measurement, and a budget expiry is legible

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

The advisory Packs corpus job (`built-in-corpus-suite`, display name
`built-in / -m corpus suite (advisory)`) runs at `timeout-minutes: 20` while its measured p95 is
20.3 min — 102 % of the cap. A lander therefore sees a red advisory check on PRs whose diff has
nothing to do with packs, and the log ends at `The operation was canceled.` with 97 % of the suite
done and no failing test.

This WP replaces the picked cap with the value the measurement implies, using the repository's own
recorded-headroom convention, and makes the residual failure mode say what it is. It does **not**
change what the job selects.

Definition of Done:

- `tests/ci/test_nightly_timeout_headroom.py` pins `packs.yml::built-in-corpus-suite` as a third
  target and fails on `timeout-minutes: 20` (`timeout-minutes 20 < required 31`); the nightly and
  module-tests targets keep their exact current behaviour.
- `tests/ci/test_corpus_suite_budget.py` (new) fails on the current job and passes after, and carries
  a mutation control for each property it asserts.
- `.github/workflows/packs.yml` carries the headroom record directly above a `timeout-minutes: 31`,
  a rationale comment with the measured decomposition and the rejected shard, a suite-step
  `timeout-minutes` strictly below the job cap, and a notice step that calls a killed run
  INCOMPLETE/advisory/not-a-test-failure.
- The job's pytest command line, `if:`, `continue-on-error`, `needs:` and the exclusion from
  `packs-gate.needs` are byte-identical to `main`.
- Every existing live guard over the lane stays green (see T005).

## Context

- `research.md` has the measurement: 55 advisory-job runs, p95 20.3 min, four budget-expiry
  cancellations, and the per-step decomposition (collection ≈ 8 min, policy scan ≈ 3.5 min on PRs,
  execution ≈ 6.3 min).
- `tests/ci/test_nightly_timeout_headroom.py` already owns this convention for `ci-nightly.yml` and
  `module-tests.yml`: a structured `# headroom (#5378): max-suite(>=|=)MM:SS runs=... formula=...`
  comment directly above the job-level `timeout-minutes`, and `cap >= ceil((max + 0:30) * 1.5)`.
- `tests/ci/test_corpus_blocking_home.py` and `tests/ci/test_contracts_routing.py` are why a path
  shard is out of scope (C-001). Do not "fix" them.

## Detailed Guidance

### T001 — Extend the cap guard, red first

Generalize the target selection in `tests/ci/test_nightly_timeout_headroom.py` so a third target can
be checked against its own file: keep `_is_nightly_target` and `_is_module_tests_target` exactly as
they are, add `_PACKS_PATH` / `_PACKS_CORPUS_JOB = "built-in-corpus-suite"` /
`_is_packs_corpus_target`, and add:

- `test_packs_corpus_timeout_cap_meets_recorded_headroom()` — non-vacuity (`list(blocks) ==
  [_PACKS_CORPUS_JOB]`) plus `_cap_violations(text, _is_packs_corpus_target) == []`.
- A mutation control in the file's existing style that proves the new target's check is load-bearing
  (e.g. a synthetic block with `max-suite>=19:55` and `timeout-minutes: 30` is reported).

Run it now — it must fail against the current `timeout-minutes: 20`. Record the exact failure text in
your notes and in the PR's red-first paragraph.

### T002 — The budget-legibility module, red first

New `tests/ci/test_corpus_suite_budget.py` (`pytestmark = pytest.mark.fast`). Parse
`.github/workflows/packs.yml` with `yaml.safe_load`, select the `built-in-corpus-suite` job, and
assert, each with a mutation control built from a shared fixture (tactic
`acceptance-criteria-non-vacuity`):

1. **Step budget**: the step whose `run` contains `-m "corpus and not windows_ci"` has an int
   `timeout-minutes` with `0 < step < job_cap` and `step >= 20` (no new tight budget that would kill
   normal runs). Controls: missing step budget reported; `step >= job_cap` reported; a step budget
   below the measured max reported.
2. **Legible expiry**: a step with `if` containing `failure()` exists after the suite step, and its
   `run` text says the run is incomplete/advisory and is not a test failure (assert on the wording
   you actually write, e.g. `INCOMPLETE` and `not a test failure`). Controls: drop the step; drop the
   wording.
3. **The issue's acceptance rule**: parse the headroom record's `max-suite` from the comment directly
   above the job-level `timeout-minutes` and assert `max_suite_minutes / cap <= 0.75` (with cap 31
   and `>=19:55` this is 0.64). Control: a recorded `24:00` against cap 31 is reported.

Run it now — it must fail against the current job. Record the failure.

### T003 — Record the headroom and derive the cap

In `.github/workflows/packs.yml`, directly above the corpus job's `timeout-minutes:` add the last
line as the structured record and the preceding lines as the rationale:

```
    # headroom (#5378): max-suite>=19:55 runs=55 window=2026-11-04..05 formula=ceil((max+0:30)*1.5)
```

Set `timeout-minutes: 31`. The rationale comment must state: the measured p95 and that it was 102 %
of the old cap; the decomposition (collection / policy scan / execution); that both fixed costs are
architectural (naming the two guards); that a path shard or matrix was measured and rejected; and
which two tests hold the derivation in place. Keep it under ~14 lines.

### T004 — A budget expiry that explains itself

- Give the suite step `timeout-minutes: 28` with a short comment: below the job cap so a killed suite
  still reaches the notice (a job-cap expiry runs no further steps).
- Rewrite the `if: failure()` notice step's `run` so it emits a `::warning::` stating the suite did
  not finish, that the lane is advisory and blocks nothing, and that this is not a test failure;
  reference #7206 (and #4437 for the honesty rule). Keep the step name
  `Advisory corpus failure notice` (operators search for it).

### T005 — Prove it green

```
uv run --frozen pytest tests/ci/test_nightly_timeout_headroom.py tests/ci/test_corpus_suite_budget.py -q
uv run --frozen pytest tests/ci/test_corpus_blocking_home.py tests/ci/test_contracts_routing.py tests/ci/test_xdist_worker_policy.py -q
uv run --frozen pytest tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_no_duplicate_suite_execution.py -q
uv run --frozen ruff check . && uv run --frozen ruff format --check .
```

`tests/ci/test_corpus_blocking_home.py` contains one `slow` live-collection test; run the file as CI
does and report per-test results. If a heavy test is impractical locally, say so explicitly instead
of claiming it passed.

### T006 — Prove the selection did not move

`git diff origin/main -- .github/workflows/packs.yml` must show no change inside the pytest command
line, and no change to `if:`, `continue-on-error:`, `needs:`, the job key or the job name. Paste that
diff summary into the PR body's `## Change` and `## Blast radius` sections.

## Branch Strategy

Planning artifacts were generated on `issue-7206-corpus-advisory-budget`. During
`/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes
must merge back into `issue-7206-corpus-advisory-budget` unless the human explicitly redirects the
landing branch. Execution worktrees are allocated per computed lane from `lanes.json`; never build a
workspace path by hand. The pull request targets `main`; nothing is ever pushed to `main`.

## Test Strategy

Red-first: T001 and T002 are written and run red before T003/T004 change the workflow, so the
red-first receipt is a real failure of the real guards on the real pre-fix file. Mutation controls
prove each assertion can fail. No test is skipped, xfailed or weakened; no gate is touched.

## Definition of Done

- [ ] T001 and T002 were red on the pre-fix workflow, with the failure text recorded.
- [ ] All three cap-guard targets pass; the new module passes with its controls.
- [ ] The lane's existing invariants pass unchanged.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] The pytest command line and the advisory wiring are byte-identical to `main`.
- [ ] `research.md`'s numbers match what the comment claims (no invented figures).

## Risks & Mitigations

- **Guard block parsing is indentation/neighbour sensitive.** Put the record directly above the
  4-space `timeout-minutes:` and run the guard's own mutation tests.
- **A step timeout at or above the job cap is dead config.** The new module rejects it.
- **The recorded max could drift from reality.** The 75 % rule forces a cap bump whenever the
  recorded max grows, and the rationale says where to re-measure.
- **Accidentally changing the selection while editing the step.** T006's diff review is the check.

## Reviewer Guidance

Check, in order: (1) the guard generalization did not alter the nightly/module targets' behaviour;
(2) the new module's controls fail when their property is broken; (3) the headroom comment sits
directly above a 31-minute job cap and the arithmetic in it is right
(`ceil((19:55 + 0:30) × 1.5) = 31`); (4) the notice cannot be read as "tests failed"; (5) the pytest
command line, deselects, `continue-on-error` and trigger are untouched.
