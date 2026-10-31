---
work_package_id: WP03
title: 'Repository-scale regression tests: round-trip count and runner-relative timing'
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-002
- NFR-004
planning_base_branch: issue-6506-charter-write-roundtrip-latency
merge_target_branch: issue-6506-charter-write-roundtrip-latency
branch_strategy: Planning artifacts for this mission were generated on issue-6506-charter-write-roundtrip-latency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6506-charter-write-roundtrip-latency unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-write-roundtrip-latency-01M68ZVK
base_commit: deadeb01a90e26da1aedea436321aabdac1fb928
created_at: '2026-10-31T15:36:55.132323+00:00'
subtasks:
- T008
- T009
phase: Phase 3 - Regression tests
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/performance/
create_intent:
- tests/performance/test_charter_write_roundtrips.py
- tests/performance/test_charter_write_repo_scale_timing.py
execution_mode: code_change
model: ''
owned_files:
- tests/performance/test_charter_write_roundtrips.py
- tests/performance/test_charter_write_repo_scale_timing.py
- tests/_perf_helpers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Repository-scale regression tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

This work package is what makes the fix durable. Two tests, both at the scale of this repository
rather than at fixture scale:

1. a **structural count** — how many times one compiled-charter refresh reads and re-emits the
   whole governed document. Exact, load-independent, runs on every pull request. It must be
   proved red against the pre-fix implementation (10 round trips) and green after (2).
2. a **runner-relative timing measure** — the command's median over a floor sampled interleaved
   in the same run. **No absolute number of seconds anywhere.**

Done means both files pass, the count test has been demonstrated red on the two-cycle
implementation, and `tests/architectural/test_perf_limit_authority.py` is green with **no
allowlist entry added**.

## Context & Constraints

Read first — these are binding, not background:

- `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md`. The repository already
  decided that absolute wall-clock budgets on shared runners false-red (a bare `--help` moved
  1.14 s → 1.95 s between nightlies with no product change) and that every limit, sample count
  and measuring helper lives in `tests/_perf_helpers.py`.
- `tests/_perf_helpers.py` — `Sample`, `measure_interleaved`, `assert_timing_budget`,
  `SAMPLE_RUNS`, and the existing limits. Reuse them; do not re-implement any of it.
- `tests/specify_cli/cli/commands/charter/test_deactivate_cli_timing.py` — the existing
  fixture-scale ratio test. Its docstring already names this gap ("the repository-scale latency
  is the pre-existing gap #6506"). Follow its shape, do not modify it.
- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/research.md` — Decision 6, and the step
  breakdown of `render_yaml_document` that tells you which boundary to count at.

Hard constraints:

- **NFR-004 / C-003**: no absolute seconds in any test or constant.
- `tests/architectural/test_performance_marker_guard.py`: every `assert` in a
  `@pytest.mark.performance` test must be a timing assertion; use `assert_timing_budget`.
- `tests/architectural/test_perf_limit_authority.py`: no test file other than
  `tests/_perf_helpers.py` may define a numeric limit. Put any new constant in the helper, with a
  comment that states the calibration method and the sample count.
- **C-004**: do not change production code in this WP. If a test cannot be written without a
  production hook, stop and report — do not add instrumentation to `src/`.

## Branch Strategy

- **Strategy**: single-lane mission on the mission branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T008 – Round-trip count test (write it FIRST, and prove it red)

- **Purpose**: Pin "one cycle, at most two whole-document round trips" so the redundancy cannot
  come back. A count is exact, deterministic and cheap — it is the one measure that belongs on the
  pull-request path.
- **Steps**:
  1. Create `tests/performance/test_charter_write_roundtrips.py`.
  2. Build a **repository-scale fixture**: copy this repository's own `.kittify/` and `packs/`
     into `tmp_path` (a plain `shutil.copytree`, `git init` the copy, and skip with
     `pytest.skip` if `.kittify/charter/charter.yaml` is absent — e.g. an sdist install). Nothing
     in the checkout is mutated, and no test asserts an absolute path.
  3. Count at a boundary that catches a redundant **parse**, not merely a redundant call. The
     recommended seam: monkeypatch `charter.activation.charter_yaml_io._yaml_loader` with a
     wrapper whose returned `YAML` object increments a counter whenever `load`, `compose` or
     `scan` is handed text whose length equals the fixture `charter.yaml`'s byte length. That
     catches a whole-document parse wherever it happens inside the module.
  4. Driver: invoke the **real production entry point** for the write path — not a helper.
     Preferred: `CliRunner().invoke(app, ["charter", "activate", "--repo-root", str(fixture),
     "tactic", <id>])` so the count covers `recompile_catalog` → `write_compiled_charter` end to
     end. If the CLI's global-state/caching makes that unreliable inside one process, fall back to
     calling `write_compiled_charter(...)` directly with a `CompiledCharter` obtained from
     `compile_charter(...)` on the same fixture, and say so in the docstring.
  5. Assert the whole-document round-trip count is `<= 6` for one refresh, and assert it is
     `>= 1` (a zero count would mean the probe is blind — non-vacuity, per tactic
     `acceptance-criteria-non-vacuity`). Calibrate the constant from the measurement, not from
     an estimate: the measured value for one merged write is 6, and 18 for the two-cycle shape.
  6. **Prove the test can fail.** Record the evidence in the test module docstring and in your WP
     history note: on the pre-fix implementation the same measurement yields ~10. Reconstruct it
     by running the same probe against `git stash`ed production code, or by temporarily
     monkeypatching `write_compiled_charter` back to its two-call form inside a scratch run (do
     not commit a two-cycle path into `src/`).
- **Files**: `tests/performance/test_charter_write_roundtrips.py`
- **Parallel?**: yes — independent of T009.
- **Notes**: This test is deliberately **not** `@pytest.mark.performance` if it contains no
  timing assertion — a count is a structural property, and marking it `performance` would put it
  on the heavy path and subject it to the marker guard. Choose the marker set that matches the
  content and say why in the docstring.

### Subtask T009 – Repository-scale ratio timing test

- **Purpose**: Measure the thing the issue is about, at the scale the issue is about, without
  encoding a machine-dependent number.
- **Steps**:
  1. Create `tests/performance/test_charter_write_repo_scale_timing.py`, marked
     `@pytest.mark.timing` and `@pytest.mark.performance` (matching the existing fixture-scale
     test's markers).
  2. Fixture: same repository-scale copy as T008. Each sample runs against a **fresh copy** so a
     previous run cannot warm anything the next one would not see (the existing test's
     `_timed_deactivate` is the pattern).
  3. Measure with `measure_interleaved(...)` from `tests/_perf_helpers.py`: the command under
     test, interleaved with a floor sampled in the same run. Two series:
     - `charter activate` vs the floor,
     - `charter deactivate` vs the floor.
  4. Floor choice: a **pure read that does not write** — `charter list` — because the regression
     this test exists for is in the write path, and a floor that shared the write path would hide
     it. Justify the choice in the docstring and state explicitly that the ratio is
     write-cost-over-read-floor, not command-over-interpreter-start-up.
  5. Add the limit to `tests/_perf_helpers.py` as `CHARTER_WRITE_RATIO_LIMIT`, with a comment
     that states: what is measured, the floor, the calibration method, the sample count, and the
     measured pre-fix ratio (ratio ≈ 6.7 = 17.5 s over 2.6 s) and post-fix ratio. Calibrate the
     limit from your own measurements with the same headroom discipline the existing limits use
     (comfortably above the largest clean value, comfortably below the regressed one); do **not**
     pick a round number that the pre-fix code would also pass.
  6. Assert through `assert_timing_budget(ratio, CHARTER_WRITE_RATIO_LIMIT, name=...)`, never a
     bare `assert`.
  7. Record the floor median, the command median and the ratio as the assertion name / message so
     a nightly report is readable without a re-run.
- **Files**: `tests/performance/test_charter_write_repo_scale_timing.py`,
  `tests/_perf_helpers.py`
- **Parallel?**: yes — independent of T008.
- **Notes**: Keep the wall clock of the file reasonable (it is an off-PR nightly measure). If five
  interleaved samples per series is too slow at repository scale, reduce the sample count via the
  helper's existing mechanism rather than inventing a second sampler, and record the cost of the
  file in the docstring.

## Test Strategy

```bash
uv run pytest tests/performance/test_charter_write_roundtrips.py -q
uv run pytest tests/performance/test_charter_write_repo_scale_timing.py -q -n0
uv run pytest tests/architectural/ -q -k "perf_limit or performance_marker"
uv run mypy tests/performance/test_charter_write_roundtrips.py \
            tests/performance/test_charter_write_repo_scale_timing.py
uv run ruff check tests/performance/ tests/_perf_helpers.py
```

The timing file is run serially (`-n0`), like the existing fixture-scale timing test.

## Risks & Mitigations

- **A count probe that cannot see the thing it counts.** Non-vacuity: assert `>= 1` as well as
  `<= 2`, and prove the probe red against the pre-fix path before declaring done.
- **A ratio that hides the regression** because floor and command share the slow path. Use a
  read-only floor, and state the choice.
- **Flaky timing on a shared machine.** Twenty other agents share this host. The ratio is
  interleaved in one run for exactly this reason; do not add retries or widen the limit to make a
  noisy local run pass — record the samples instead.
- **Marker-guard trip.** A `performance`-marked test with a structural `assert` fails
  `test_performance_marker_guard.py`. Keep the count test out of that marker set.
- **Heavy fixture in CI.** 13 MB copytree per sample is cheap; 5 samples × two commands at
  repository scale is not. Keep the file off the PR path and say so.

## Review Guidance

- Confirm no absolute seconds constant or assertion was added.
- Confirm the new limit lives in `tests/_perf_helpers.py` and the authority test needs no
  allowlist entry.
- Confirm the red-first evidence for T008 is recorded (pre-fix count ≈ 10) and is reproducible from
  the committed test.
- Confirm the fixtures copy into `tmp_path` and never touch the checkout.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
