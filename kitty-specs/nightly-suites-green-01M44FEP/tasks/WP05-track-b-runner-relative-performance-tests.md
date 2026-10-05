---
work_package_id: WP05
title: 'Track B: runner-relative performance tests'
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- FR-012
- FR-017
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:36:16.502444+00:00'
subtasks:
- T022
- T023
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 2 - Track B (performance budgets)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/performance/
create_intent:
- tests/architectural/test_perf_limit_authority.py
- docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/_perf_helpers.py
- tests/performance/test_owned_checkout_perf.py
- tests/performance/test_cli_startup_budget_4409.py
- tests/performance/test_cli_startup_agent_commands_freshness.py
- tests/architectural/test_perf_limit_authority.py
- docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md
- docs/development/testing/testing-flakiness.md
role: implementer
task_type: implement
---

# Work Package Prompt: WP05 – Track B: runner-relative performance tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then read `.kittify/charter/charter.md` (sections "Quality & Tech-Debt Standing Orders" and "ATDD-First Discipline") and run `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission nightly-suites-green-01M44FEP` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- The three owned-checkout performance tests assert the ratio of the command median to a start-up floor median taken interleaved in the same run (FR-007).
- The ratio limit is set from recorded data: six nightly runs, 30 idle and 30 throttled clean local ratios, and 10 planted ratios in each condition; its headroom over the largest clean value is stated (FR-008).
- A committed test plants CPU-bound work in the spawned CLI process from the test side, with no product hook, and expects the relative assertion to fail (FR-009).
- CLI start-up itself is guarded by a median against a fixed interpreter workload measured in the same run, for the bare start-up test and the warm second-call test; no absolute wall-clock limit remains for start-up (FR-010).
- Every start-up and owned-checkout limit and the measuring helper live in `tests/_perf_helpers.py`, and a check fails if another test file defines a start-up limit (FR-012).
- The Track B decision record exists with every measured figure, and the flakiness guidance matches it (FR-017, in part).
- NFR-001: 30 of 30 green at a throttle level where the start-up floor is at least 1.9 s and the previous absolute assertion is red. NFR-002: planted work worth about half the floor is red 10 of 10, idle and throttled. NFR-003: the owned-checkout tests, fixture and planted-work test take at most 90 s idle.

**STOP condition.** If the clean ratio range and the planted ratio range overlap in the calibration spike, stop and report to the orchestrator with the figures; do not pick a limit inside an overlap.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 2, FR-007 to FR-012, FR-017, NFR-001 to NFR-003, C-003, C-004, C-005), `plan.md` (section "Design notes / Track B"), `research.md` (D4, D5), `research/code-grounding.md` (sections 4 and 9.5).

**The defect (#5419, #5614).** Three owned-checkout tests compare a wall-clock median against an absolute 2.5 s. The shared nightly runner measured 2.52 to 2.59 s with no product regression; the job has been red on 4 of the last 6 nightlies. A bare `--help` alone moves from 1.14 to 1.95 s between nightly runs. The ratio of an owned command to a start-up floor measured in the same run stays between 1.35 and 1.51 across the same runs.

**Decision (research D4, D5).** Assert a runner-relative measure: the command median divided by a start-up floor median, sampled interleaved in the same run. Guard start-up itself against a fixed interpreter workload measured in the same run. Add a clock-free signal: a pin on the number of git subprocesses each owned command spawns (WP06). Limits are calibrated, not chosen in advance.

**Binding rules.** `docs/development/testing/testing-flakiness.md`: tier 1 says tune a budget only with evidence and never retry; the audit table (line 126) says shared-runner wall clock is not accepted as evidence. `tests/architectural/test_performance_marker_guard.py` requires every `assert` statement inside a `performance`-marked test to use timing vocabulary (`elapsed`, `duration`, `wall_clock`, `perf_counter`, `monotonic`, `budget`, `benchmark`, `seconds`, `timeout`), so assertions in such tests go through `tests/_perf_helpers.assert_timing_budget`. `tests/ci/test_no_blocking_latency_gate.py` forbids a wall-clock ceiling on the per-pull-request path.

**No loosening without evidence (C-003), no new size gate or ratchet (C-004).** Tracks A and C share no file with Track B.

**Verified code facts for this work package (base `9adc68803f`).**

- `tests/_perf_helpers.py` (55 lines): `CLI_COLD_START_BUDGET_SECONDS = 2.5` at `:37`, `assert_timing_budget(measured, budget, *, name="elapsed")` at `:40`. **53 test files import `assert_timing_budget` from this module** (51 import it alone; two also import the constant). Its name, signature and behaviour must not change. Only two files import `CLI_COLD_START_BUDGET_SECONDS`: `tests/performance/test_owned_checkout_perf.py:40` and `tests/performance/test_cli_startup_budget_4409.py:32`, both owned here, so the constant can be removed once both are rewritten.
- `tests/performance/test_owned_checkout_perf.py` (136 lines): `_RUNS = 5` (`:44`), `_BUDGET_SECONDS` (`:45`), `_cli` (`:58`, sets `PYTHONPATH`, an isolated `SPEC_KITTY_HOME`, `SPEC_KITTY_ENABLE_SAAS_SYNC=0`), `_median_wall_clock` (`:71`), module-scoped fixture `owned_mission` (`:83`, built from `tests.integration.conftest` helpers and one `finalize-tasks` subprocess), and the three tests at `:117`, `:123`, `:129` with their assertions at `:119`, `:125`, `:132`.
- `tests/performance/test_cli_startup_budget_4409.py` (300 lines): `_HELP_BUDGET_SECONDS = CLI_COLD_START_BUDGET_SECONDS` at `:36`; the timed test `test_help_stays_inside_its_startup_budget` at `:283-300` runs `python -m specify_cli.__init__ --help` once, single shot. The file also holds unmarked functional tests (the jsonschema import scans, `:159-281`); leave them as they are.
- `tests/performance/test_cli_startup_agent_commands_freshness.py` (147 lines): its own `_LEAF_COMMAND_BUDGET_SECONDS = 5.0` at `:66`; the timed test at `:110-147` runs `context list --json` twice against one isolated home and times the second call.
- `performance` tests are skipped unless `SPEC_KITTY_RUN_PERFORMANCE=1` (`tests/conftest.py:335-348`).
- No job runs an unmarked test in `tests/performance`: the directory is listed in the registry as nightly-only by marker (`.github/ci-module-registry.yml:716-725`: "no per-PR lane selects this directory"), module shards select with `not performance and not stress` (`scripts/ci/shard_select.py:71`) over their own directories, and the nightly job runs `-m performance`. A functional (unmarked) test placed there would never run in CI. The functional tests of this work package therefore live in a new architectural file, `tests/architectural/test_perf_limit_authority.py` (`pytestmark = [pytest.mark.architectural]`, repository root at `parents[2]`), which the always-on architectural jobs run on every pull request.
- Measurement trap (grounding 4.3): two source trees sharing one `SPEC_KITTY_HOME` pushed every `context list` to 4.3 s. Every measurement uses one isolated home.
- Grounding probe, `--version` as floor: idle floor 0.987 s, ratio 1.34 to 1.37; 40 CPU burners floor 1.522 s, ratio 1.43 to 1.51 (and the old absolute test still passed there, so that load level proves nothing); a fixed 0.5 s sleep gave 1.82 to 1.87 idle but only about 1.65 to 1.77 on a 1.9 s floor by arithmetic, so the plant must scale with the machine. `--version` loaded 1552 modules against 1282 to 1284 for the owned commands, so it may not be a clean floor.

### Paths owned by running missions (do not edit)

Copied from `research/code-grounding.md` section 6. Paths are relative to `src/specify_cli/` unless they start with `tests/` or are a root file.

| Running mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_wp_integrity_partition_call_shape.py`, `tests/architectural/dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `lanes/compute_and_persist.py`, `lanes/frozen_membership.py`, `lanes/lane_tip.py`, `lanes/models.py`, `cli/commands/agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `lanes/auto_rebase.py`, `lanes/stale_check.py`, `lanes/worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound. Only the body of `_is_bookkeeping` may change, and only in WP03. |
| #3931 | `cli/commands/agent/tasks_move_task*.py`, `cli/commands/_git_remedies.py`, `cli/commands/agent/tasks_parsing_validation.py` |

Also off limits for every work package of this mission: `src/mission_runtime/artifacts.py`, any `.github/workflows/*.yml`, `.github/ci-module-registry.yml`, and `kitty-specs/**`.

**Rule.** An edit outside this work package's `owned_files` needs a one-line rationale in your hand-back. An edit in a path listed above is a STOP: make no such edit, and report to the orchestrator what you found and why the listed path seems to need a change.

### Commit order and commit hygiene (charter C-011, spec C-005)

1. Tidy-first enabler commit(s): behaviour-preserving, with their focused tests.
2. Failing-test commit: the test goes through the pre-existing entry point and is red on this work package's base for the reason named in the subtask. Record the red output (test id plus the failing assertion line) in your hand-back.
3. Fix commit(s): the failing test turns green; new branches are covered by tests in the same commit.

Marker convention (ADR `docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`, amendment at line 70): `p0_repro(issue=N)` is only for a reproduction of an OPEN P0 that must stay off the per-pull-request path; `regression` is the marker for an issue-pinned guard of a bug that is fixed, and it runs per pull request. Tests added here guard bugs fixed in the same pull request, so they never carry `p0_repro`.

Every commit message ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No commit message, code comment, docstring or document names an AI tool or a model.

### Quality bar (spec NFR-005)

- Cyclomatic complexity at most 15 per function (`ruff` C901). Extract a helper before a function reaches 16.
- `mypy --strict` clean for every changed source file; no new `# type: ignore`, no new `# noqa`.
- A string literal used three or more times in one module becomes a named module constant.
- Every new branch and helper has a test in the same commit.
- No empty or effect-free `except` block.

### Tracer files

Do not edit anything under `kitty-specs/`, including `kitty-specs/nightly-suites-green-01M44FEP/traces/`. Put tooling friction, approach changes and design choices in your hand-back as three short lists; the orchestrator appends them to the tracer files.

## Branch Strategy

- **Strategy**: lane worktree per computed lane (`lanes.json`); this mission's topology is `lanes`.
- **Planning base branch**: `issue-5611-5419-nightly-green`
- **Merge target branch**: `issue-5611-5419-nightly-green`
- **Dependencies**: none

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP05 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T022 – Calibration spike

- **Purpose**: Choose the floor command, the throttle method and the limits from data (FR-008, research D5). The spike script is a scratch tool and is not committed; its figures go into the decision record (T028).
- **Steps**:
  1. Build the real `owned_mission` fixture once (import it or copy its body into a scratch script outside the repository) and use one isolated `SPEC_KITTY_HOME`.
  2. Floor command: compare `--version`, `agent --help` and `python -c "import specify_cli"` by the spread of the ratio (owned command median / floor median) between idle and throttled runs. Pick the one with the lowest spread and say why; record module counts if they explain a difference.
  3. Throttle: find a method that gives a floor of at least 1.9 s (the slowest nightly value) on this machine, for example CPU-affinity pinning (`taskset` or `os.sched_setaffinity`) plus burner processes. Confirm and record that at this level the OLD absolute assertion (median against 2.5 s) is red. This recorded red, together with nightly run 37225822329, is the "red first" evidence for this track (spec C-005).
  4. Record 30 idle and 30 throttled clean ratios per owned command with the sampling the tests will use (5 floor and 5 command spawns, interleaved).
  5. Plant CPU-bound work worth about half the floor (the T025 mechanism) and record 10 planted ratios idle and 10 throttled.
  6. Set the ratio limit between the largest clean and the smallest planted value. State the headroom over the largest clean value. **If the two ranges overlap, STOP and report.**
  7. Repeat steps 4 to 6 for the start-up measure of T026 (start-up median / fixed-workload median) with planted start-up work.
- **Files**: none in the repository.
- **Parallel?**: No; everything else depends on it.
- **Notes**: Do not run other heavy processes during the idle series. Record machine, core count, Python version and commit.

### Subtask T023 – Limit authority and `measure_interleaved`

- **Purpose**: One module for every limit and the measuring helper (FR-012).
- **Steps**:
  1. In `tests/_perf_helpers.py`, add named constants for the owned-checkout ratio limit and the start-up ratio limit(s), each with a comment citing the decision record and the headroom. Add the sample counts as constants.
  2. Add `measure_interleaved(...)`: it takes a callable (or argv) for the command and one for the floor, the number of runs, and returns both medians (and the raw samples for the failure message). It alternates floor and command spawns so drift during the run affects both. A non-zero exit of either makes the result fail with the stderr tail in the name, as `_median_wall_clock` does today.
  3. Add the fixed interpreter workload for T026 as a helper: a fresh interpreter importing a fixed list of standard-library modules.
  4. Keep `assert_timing_budget` byte-identical. Update the module docstring to describe the relative measures.
  5. Make the timing source injectable (a clock or a "run once and return seconds" callable), so the pure parts can be tested without a subprocess.
  6. Give the pure parts (median pairing, ratio computation, failure-name formatting, non-zero-exit handling) direct unit coverage with injected timings in the new `tests/architectural/test_perf_limit_authority.py`. Not in `tests/performance`: an unmarked test there is run by no job (see the verified facts).
  7. In the same new file, commit the FR-007 positive control as a test, not as hand-back prose: feed the six nightly rows of `research/code-grounding.md` section 4.2 (`--help` floor and owned medians per run: 1.95 / 2.71, 2.85, 2.76; 1.83 / 2.65, 2.72, 2.62; 1.14 / about 1.54; 1.76 / about 1.88; 1.94 / 2.60, 2.70, 2.60; 1.72 / 2.52, 2.59, 2.54) through the helper as injected timings. Assert, row by row: the previous absolute assertion (median against 2.5 s) is red on the four rows the nightly reported red and green on the two it reported green; the ratio assertion against the calibrated limit is green on all six. Keep the 2.5 s figure in that test as a named local historical constant with a comment; it is test data, not a live limit.
- **Files**: `tests/_perf_helpers.py` (about 90 added lines), new `tests/architectural/test_perf_limit_authority.py`.
- **Parallel?**: No.
- **Notes**: The helper lives in a test-support module, so no product code changes and diff-cover is unaffected. Keep each function under complexity 15.

### Subtask T024 – Owned-checkout tests assert the ratio

- **Purpose**: FR-007.
- **Steps**:
  1. Rewrite the three tests in `tests/performance/test_owned_checkout_perf.py` to call `measure_interleaved` and assert `assert_timing_budget(command_median / floor_median, <ratio limit>, name=...)`. The name carries both medians, the ratio and the limit, so a nightly failure is diagnosable without a re-run (User Story 2, scenario 2).
  2. Remove `_BUDGET_SECONDS` and the import of `CLI_COLD_START_BUDGET_SECONDS`; keep `_cli`, the fixture and `_owned_args`.
  3. Rewrite the module docstring: what is measured, why it is relative, where the limit lives.
  4. Keep the `performance` marker and keep every assertion inside the tests on timing vocabulary.
- **Files**: `tests/performance/test_owned_checkout_perf.py`.
- **Parallel?**: After T023.

### Subtask T025 – Planted-work test

- **Purpose**: FR-009 and NFR-002: prove the relative assertion can fail.
- **Steps**:
  1. In the same file, add a test that runs one owned command with planted work and expects the ratio assertion to fail (`pytest.raises(AssertionError)` around `assert_timing_budget`, or an equivalent that keeps every `assert` statement on timing vocabulary).
  2. Plant from the test side only: write a `sitecustomize.py` into a temporary directory and put it first on the child's `PYTHONPATH`. It runs a fixed-iteration CPU-bound loop when the child is an `agent` command (inspect `sys.argv`), and does nothing for the floor command. The iteration count is calibrated in T022 so the work is worth about half the floor on the calibration machine; because it is CPU-bound it scales with the runner.
  3. No environment variable, flag or hook is added to product code.
  4. Assert through the same helper and the same limit constant as the clean tests, so a widened limit makes this test fail.
  5. Bound the plant: in the same test, measure the plant's own cost (planted command median minus clean command median, taken interleaved in the same run) and assert through `assert_timing_budget` that it lies between 0.3 and 0.7 of the floor median (two calls: cost at most 0.7 of the floor, and 0.3 of the floor at most the cost). An oversized plant would pass NFR-002 under any limit; this bound makes "about half the floor" a checked fact on every machine. Put the two fractions in the authority module as named constants.
- **Files**: `tests/performance/test_owned_checkout_perf.py`.
- **Parallel?**: After T024.
- **Notes**: Check an existing `sitecustomize` on the path is not shadowed in a way that breaks the child (coverage tooling uses one); chain to it if present.

### Subtask T026 – Start-up tests against a fixed interpreter workload

- **Purpose**: FR-010: keep the cold-start signal without an absolute wall-clock limit.
- **Steps**:
  1. `test_help_stays_inside_its_startup_budget` (`test_cli_startup_budget_4409.py:283-300`): replace the single shot with interleaved samples of `--help` and the fixed workload; assert the ratio of medians against the start-up limit from the authority.
  2. `test_repeated_leaf_command_invocation_stays_inside_its_startup_budget` (`test_cli_startup_agent_commands_freshness.py:110-147`): keep the warm-up call and the isolated home; measure the warm call as a median against the fixed workload and assert against a limit from the authority. Delete `_LEAF_COMMAND_BUDGET_SECONDS` (`:66`) and its comment block; move the rationale (what regression this catches: the ~11 s from-scratch render returning on a warm call) to the authority constant's comment.
  3. Add a planted start-up test: the `sitecustomize` plant applied to the start-up command turns the start-up assertion red.
  4. Remove `CLI_COLD_START_BUDGET_SECONDS` from `tests/_perf_helpers.py` once nothing imports it.
- **Files**: `tests/performance/test_cli_startup_budget_4409.py`, `tests/performance/test_cli_startup_agent_commands_freshness.py`, `tests/_perf_helpers.py`.
- **Parallel?**: After T023; independent of T024 and T025.
- **Notes**: The regression the warm test exists for is a factor of about 10; calibrate its limit from data like the others, do not carry 5.0 s over as a ratio by arithmetic.

### Subtask T027 – One authority, checked

- **Purpose**: FR-012: a check that no other test file defines a start-up limit.
- **Steps**:
  1. In the new `tests/architectural/test_perf_limit_authority.py`, add a test that scans the test files spawning a fresh CLI interpreter for timing (`sys.executable, "-m", "specify_cli"` together with a timing assertion) and fails when one defines a module-level numeric limit instead of importing it from `tests._perf_helpers`. Define the scan precisely in the docstring: which files, which pattern.
  2. Give it a floor (it must scan at least the three owned performance files) and a self-test on source text: a planted module-level `_X_BUDGET_SECONDS = 3.0` beside a CLI spawn is flagged; an import from the authority is not.
  3. This is a check on one fact, not a size gate and not a shrink-only ratchet (C-004). It has no allowlist. If an existing file outside this work package trips it, report the file; do not add an exemption.
  4. Confirm with `select_gates` for one `tests/_perf_helpers.py` change and one `tests/performance/...` change that an architectural job is selected, and record the output. If a battery, naming or duration-seed gate objects to the new architectural file, stop and report; do not edit a registry or timing file.
- **Files**: `tests/architectural/test_perf_limit_authority.py`.
- **Parallel?**: After T026.

### Subtask T028 – Decision record and flakiness guidance

- **Purpose**: FR-017 (Track B half), FR-008's "figures written down".
- **Steps**:
  1. Write `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md` from the shared template `docs/architecture/adr-template.md`, with the frontmatter shape of `docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md` (title, description, status, date, updated). Content: context (the nightly table from grounding 4.2), the decision, the floor command and why, the throttle method, all measured figures from T022 (clean and planted ranges, idle and throttled, per command), each limit with its headroom, the sample counts and the measured suite cost, the old absolute assertion's red at the throttle level, rejected alternatives (delta over the floor, one wider absolute budget, count proxies alone), and residuals (the ratio is blind to a regression that slows the floor and the command alike; the start-up guard and the WP06 count pin cover part of that).
  2. Update `docs/development/testing/testing-flakiness.md`: in the tier-1 row and the audit table, state the runner-relative policy for tests that pay interpreter cold start, and add an audit row for the three owned-checkout tests and the two start-up tests with their disposition. Follow the page's existing voice; do not rewrite unrelated rows.
  3. Do not register the record in `docs/adr/4.x/index.md`, `docs/development/page-inventory.yaml` or `docs/development/docs-retrieval-index.yaml`, and do not edit `docs/changelog/CHANGELOG.md`: WP08 owns those four files and registers both records.
- **Files**: the ADR (new, about 150 lines), `docs/development/testing/testing-flakiness.md`.
- **Parallel?**: After T022; can run alongside T024 to T027.
- **Notes**: Plain, direct prose. Use the spec's domain terms ("start-up floor", "runner-relative measure"); do not use "baseline" for the floor. Run `tests/architectural/test_no_legacy_terminology.py` after editing docs.

### Subtask T029 – Robustness runs, cost, gates and hand-back

- **Purpose**: NFR-001, NFR-002, NFR-003 with evidence.
- **Steps**:
  1. With the final code: 30 consecutive runs of the three owned tests at the T022 throttle level, all green (NFR-001). 10 runs of the planted test idle and 10 throttled, all showing the assertion failing as expected (NFR-002).
  2. Time the owned-checkout file idle (fixture, three tests, planted test): at most 90 s (NFR-003). If it exceeds 90 s, reduce cost without dropping below the sample counts the calibration used, or stop and report.
  3. Run every command in the Test Strategy section.
  4. Add the final figures to the decision record if they differ from the spike.
  5. Hand-back: commits, counts, the 30/30 and 10/10 tallies, the timing, the floor and throttle choices, tracer notes.
- **Files**: none new.
- **Parallel?**: No; last.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  tests/performance/test_owned_checkout_perf.py \
  tests/performance/test_cli_startup_budget_4409.py \
  tests/performance/test_cli_startup_agent_commands_freshness.py \
  tests/architectural/test_perf_limit_authority.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_performance_marker_guard.py \
  tests/architectural/test_battery_partition_proof.py \
  tests/architectural/test_spec_kitty_home_pin_census.py \
  tests/architectural/test_no_manual_global_state_mutation.py \
  tests/architectural/test_timing_coverage_invariant.py \
  tests/architectural/test_marker_job_completeness.py \
  tests/architectural/test_fast_tier_marker_completeness.py \
  tests/architectural/test_no_legacy_terminology.py \
  tests/ci/test_no_blocking_latency_gate.py \
  tests/ci/test_nightly_timeout_headroom.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check tests/_perf_helpers.py tests/performance/test_owned_checkout_perf.py tests/performance/test_cli_startup_budget_4409.py tests/performance/test_cli_startup_agent_commands_freshness.py tests/architectural/test_perf_limit_authority.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude tests/_perf_helpers.py tests/performance/test_owned_checkout_perf.py tests/performance/test_cli_startup_budget_4409.py tests/performance/test_cli_startup_agent_commands_freshness.py tests/architectural/test_perf_limit_authority.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict tests/_perf_helpers.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

The performance tests are skipped unless the opt-in variable is set, and they must run serially:

```bash
SPEC_KITTY_RUN_PERFORMANCE=1 $PY -m pytest \
  tests/performance/test_owned_checkout_perf.py \
  tests/performance/test_cli_startup_budget_4409.py \
  tests/performance/test_cli_startup_agent_commands_freshness.py \
  -n0 -p no:cacheprovider -q --durations=10
```

Because 53 files import `assert_timing_budget`, also run a small sample of those importers unchanged to confirm the module still imports and behaves: `tests/status/test_tail_reader.py`, `tests/zeitgeist_client/test_budget.py`, `tests/specify_cli/charter_preflight/test_performance.py`.

### Non-vacuity controls (as test cases)

`tests/architectural/test_spec_kitty_home_pin_census.py` and `test_no_manual_global_state_mutation.py` are run-only. A new `SPEC_KITTY_HOME` write site in a test may trip the hash-pinned census; that census file is not owned here. If it goes red, STOP and report; do not edit the census.

- FR-007: a committed injected-timings test over the six nightly rows (T023 step 7): the previous absolute assertion is red where the ratio assertion is green. The live throttled run (T022, T029) is supporting evidence in the decision record.
- FR-009 and NFR-002: the committed planted-work test, asserting through the same helper and the same limit constant as the clean tests, with the plant's measured cost asserted between 0.3 and 0.7 of the floor.
- FR-010: the committed planted start-up test.
- FR-012: the self-test of the single-authority check on planted source text.

## Definition of Done

- The three owned tests and the two start-up tests assert relative measures through `assert_timing_budget`; no absolute start-up limit remains in the three files or the helper.
- The planted-work and planted start-up tests are committed and show the assertion failing.
- Limits and `measure_interleaved` live only in `tests/_perf_helpers.py`; the single-authority check and the helper unit tests live in `tests/architectural/test_perf_limit_authority.py`, which a per-pull-request job runs; the check's self-test proves it can fail.
- The six-nightly-row positive control is a committed test; the planted-work test bounds the plant between 0.3 and 0.7 of the floor.
- `assert_timing_budget` is unchanged; sampled importers pass.
- The decision record holds every figure; the flakiness page matches.
- 30/30 throttled green, 10/10 planted red in both conditions, owned file at most 90 s idle; tallies in the hand-back.
- All Test Strategy commands pass.
- Subtasks T022 to T029 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **Ranges overlap.** STOP and report; the measure or the sampling needs a different design.
- **The floor command is not clean.** `--version` loaded more modules than the owned commands in the probe; T022 step 2 decides.
- **The marker guard.** A bare `assert` on a ratio variable inside a `performance` test trips `test_performance_marker_guard.py`. Assert through the helper.
- **Suite cost.** Interleaved floor samples add time; NFR-003 caps the owned file at 90 s.
- **`sitecustomize` collisions.** Coverage or the environment may already install one; chain, do not replace.
- **53 importers.** Any change to `assert_timing_budget` breaks unrelated suites.
- **A widened limit as a shortcut.** The planted tests share the limit constant so widening it turns them red.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **Widened limit.** A ratio limit above the smallest planted value, or an absolute budget raised and renamed. Compare the constants with the figures in the decision record; the planted tests must use the same constants.
- **Helper-only planted number.** A "planted" test that feeds fake timings to the helper instead of slowing a real child process. The planted test must spawn the CLI with the `sitecustomize` on `PYTHONPATH`; fake-timing tests are only for the pure helper parts.
- **A sleep as the plant.** `time.sleep` does not scale with the machine; the plant must be a CPU-bound fixed-iteration loop.
- **A product hook.** No change under `src/`. `git diff --stat` must show none.
- **Floor not interleaved.** Floor samples taken before or after the command samples instead of alternating.
- **Absolute limit left behind.** Grep the three performance test files and the helper for `2.5`, `5.0` and `_BUDGET_SECONDS`. The only allowed `2.5` is the historical constant inside the six-nightly-row test.
- **Functional tests where no job runs them.** No unmarked test may be added under `tests/performance`; the authority check and the helper unit tests must be in `tests/architectural/test_perf_limit_authority.py`.
- **An oversized or unbounded plant.** The planted-work test must assert the plant's cost is between 0.3 and 0.7 of the floor.
- **Positive control only in prose.** The six-nightly-row test must exist and must show the old assertion red on four rows.
- **Figures asserted but not recorded.** The decision record must contain the raw ranges, not only the chosen limit.
- **Retry or rerun logic.** None is allowed.

Re-run the planted tests and one throttled series yourself if the machine allows. Confirm the trailer on every commit and no AI or model identifier.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Append the new entry at the END of this section; never prepend or insert in the middle.
2. Use the format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>`.
3. The timestamp is the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`), never a future one.

The acceptance system reads the LAST entry as the current state, so order matters.

**Initial entry**:

- 2026-10-05T04:58:23Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done` to record a finished subtask.
