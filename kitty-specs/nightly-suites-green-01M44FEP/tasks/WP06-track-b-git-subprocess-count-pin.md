---
work_package_id: WP06
title: 'Track B: git-subprocess count pin for owned-checkout commands'
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:36:24.941308+00:00'
subtasks:
- T030
- T031
- T032
- T033
phase: Phase 2 - Track B (performance budgets)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/specify_cli/workspace/test_owned_checkout_git_calls.py
- tests/architectural/test_owned_checkout_git_calls.py
- tests/cli/commands/test_owned_checkout_git_calls.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/workspace/test_owned_checkout_git_calls.py
- tests/architectural/test_owned_checkout_git_calls.py
- tests/cli/commands/test_owned_checkout_git_calls.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP06 – Track B: git-subprocess count pin for owned-checkout commands

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

A deterministic, clock-free signal that an owned-checkout command started doing more work (FR-011; User Story 2, scenario 4).

- A new test file pins the number of git subprocesses spawned by `agent tasks status`, `agent mission setup-plan` and `agent context resolve` against an owned checkout, counted in-process.
- Each count is pinned only after at least three agreeing samples.
- A planted extra git call turns the pin red.
- The tests carry no `performance` marker, so they can run on pull requests. The file is hosted where the job-selection dry run shows it IS selected for a change to the source files that implement the three commands; the decision and any residual gap are recorded.

**One file, three candidate homes.** `owned_files` and `create_intent` list three candidate paths for the same test file. Exactly one is created; T030 step 1 decides which, from the dry run.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 2, FR-007 to FR-012, FR-017, NFR-001 to NFR-003, C-003, C-004, C-005), `plan.md` (section "Design notes / Track B"), `research.md` (D4, D5), `research/code-grounding.md` (sections 4 and 9.5).

**The defect (#5419, #5614).** Three owned-checkout tests compare a wall-clock median against an absolute 2.5 s. The shared nightly runner measured 2.52 to 2.59 s with no product regression; the job has been red on 4 of the last 6 nightlies. A bare `--help` alone moves from 1.14 to 1.95 s between nightly runs. The ratio of an owned command to a start-up floor measured in the same run stays between 1.35 and 1.51 across the same runs.

**Decision (research D4, D5).** Assert a runner-relative measure: the command median divided by a start-up floor median, sampled interleaved in the same run. Guard start-up itself against a fixed interpreter workload measured in the same run. Add a clock-free signal: a pin on the number of git subprocesses each owned command spawns (WP06). Limits are calibrated, not chosen in advance.

**Binding rules.** `docs/development/testing/testing-flakiness.md`: tier 1 says tune a budget only with evidence and never retry; the audit table (line 126) says shared-runner wall clock is not accepted as evidence. `tests/architectural/test_performance_marker_guard.py` requires every `assert` statement inside a `performance`-marked test to use timing vocabulary (`elapsed`, `duration`, `wall_clock`, `perf_counter`, `monotonic`, `budget`, `benchmark`, `seconds`, `timeout`), so assertions in such tests go through `tests/_perf_helpers.assert_timing_budget`. `tests/ci/test_no_blocking_latency_gate.py` forbids a wall-clock ceiling on the per-pull-request path.

**No loosening without evidence (C-003), no new size gate or ratchet (C-004).** Tracks A and C share no file with Track B.

**Verified code facts for this work package (base `9adc68803f`).**

- Candidate home 1, `tests/specify_cli/workspace/`, is enrolled for per-pull-request execution in `.github/ci-module-registry.yml:316-324` under the module `core_misc`. **But a change under `src/specify_cli/cli/commands/agent/` selects only the modules `cli` and `execution_context`** (dry run on the base for `agent/tasks.py`, `agent/context.py` and `agent/mission.py`: `select_modules` returns `{cli, execution_context}`; `select_gates` includes `architectural-fast` and `architectural-heavy`). `core_misc` is not selected, so a pin hosted there would not run on the pull request that changes those commands.
- Candidate home 2, `tests/architectural/`: the architectural jobs are selected for every path tried. A file there needs `pytestmark = [pytest.mark.architectural]`, finds the repository root at `parents[2]`, and must respect the battery's conventions (`tests/architectural/test_battery_partition_proof.py`, `test_marker_job_completeness.py`); it is a behavioural test with a fixture costing several seconds, so time it and report.
- Candidate home 3, `tests/cli/commands/`: the `cli` module's own test directory (the `cli` registry row runs `tests/cli`), selected for the three `agent/` paths above. Confirm in the dry run that the row's selection really covers this directory.
- Not usable: `tests/specify_cli/cli/commands/agent/` is claimed by `execution_context` but is a do-not-touch path of a running mission (#5573).
- Per-process caches can change counts: `src/specify_cli/workspace/context.py:434` reads `_FEATURE_CONTEXT_INDEX_CACHE`, keyed on repository root and Mission slug; a test that ran earlier in the same process may have warmed it or other module-level caches.
- Sibling files in candidate home 1 use `pytestmark = [pytest.mark.unit, pytest.mark.fast]` (`test_resolver_arms.py:33`, `test_single_branch_resolution.py:27`) or per-test `git_repo` markers (`test_owned_workspace_resolution.py:192`).
- Precedent for counting: `tests/integration/test_owned_lifecycle_acceptance_e2e.py:611 _install_git_call_counter` wraps `subprocess.Popen` and records every child whose `argv[0]` basename is `git` or `git.exe`. That file is in `tests/integration`, which runs nightly only; read it, do not edit it.
- Precedent for the fixture: `tests/performance/test_owned_checkout_perf.py:83 owned_mission` builds a repository root, an owned checkout as a worktree, a finalized one-work-package `single_branch` Mission, using `_git`, `_init_repo`, `_write_mission`, `_write_single_lane_manifest` from `tests/integration/conftest.py` and `provision_test_charter` from `tests/_factories`. That file is owned by WP05; import helpers from the conftest, do not edit either file.
- Owned commands and their arguments: `["agent", <command...>, "--owned-checkout", <owned_root>, "--mission", <slug>, "--json"]`; `context resolve` also takes `--action implement --wp-id WP01` (`test_owned_checkout_perf.py:113`, `:131`).
- Grounding sample (one run each, subprocess-based): tasks status 7, setup-plan 14, context resolve 7, `--version` 0. Treat these as a hint; pin what you measure.
- Job selection: `scripts/ci/gate_selection.py` `select_gates` (`:134`) and `select_modules` (`:270`).

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

Start with `spec-kitty agent action implement WP06 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T030 – Fixture, in-process runner and counter

- **Purpose**: Count git child processes of one CLI invocation without a clock.
- **Steps**:
  1. Choose the home first. Run the dry run below on your base and record its output:
     ```bash
     $PY -c "from scripts.ci.gate_selection import select_gates, select_modules
     for p in (['src/specify_cli/cli/commands/agent/tasks.py'], ['src/specify_cli/cli/commands/agent/context.py'], ['src/specify_cli/cli/commands/agent/mission.py']):
         print(p, sorted(select_gates(p).selected_jobs), sorted(select_modules(p)))"
     ```
     Replace a path with the file that really implements the command if it differs (find it from the typer registration). Host the pin in the candidate whose job is selected for all three: candidate 1 only if `core_misc` is selected (on the base it is not); otherwise candidate 3 if the `cli` row covers `tests/cli/commands`, otherwise candidate 2. Create exactly one of the three files and record the decision, the evidence and the residual gap (which source changes would still not run the pin on their pull request) in the hand-back.
  2. Create the chosen file with a small fixture of its own that builds the same shape as `owned_mission` (repository root, owned checkout, finalized `single_branch` Mission with one work package), importing `_git`, `_init_repo`, `_write_mission`, `_write_single_lane_manifest` from `tests.integration.conftest` and `provision_test_charter` from `tests._factories`. Use an isolated `SPEC_KITTY_HOME` and remove `SPECIFY_REPO_ROOT` from the environment via `monkeypatch`.
  3. Invoke the CLI in-process with typer's `CliRunner` against the application object the real entry point uses (find it in `src/specify_cli/__init__.py`; do not build a private app). Set the working directory to the owned checkout with `monkeypatch.chdir`.
  4. Count with a `subprocess.Popen` wrapper as in the precedent (`argv[0]` basename `git` or `git.exe`); keep the recorded argv prefix so a failure message lists the calls.
  5. Finalize the Mission in the fixture before counting, so fixture work is not counted; install the counter only around the measured invocation.
- **Files**: one new `test_owned_checkout_git_calls.py` in the chosen home (about 200 lines).
- **Parallel?**: No.
- **Notes**: In-process state can leak between invocations (module caches may skip git calls on a second run in the same process). Decide and document what is pinned: the count of a first invocation in a fresh fixture, with caches reset if the product offers a reset. If counts differ between the first and later invocations, pin the first and explain why in the docstring.

### Subtask T031 – Sample and pin

- **Purpose**: Pin exact counts with evidence (C-003: no pin without measured data).
- **Steps**:
  1. Take at least three samples per command in separate pytest processes (run the file three times, or more). Only pin a count when all samples agree.
  2. Cache sensitivity: also sample with `-n0` in ONE process together with the chosen directory's sibling test files, in both orders (siblings first, then the new file; and the new file first), because per-process caches (`workspace/context.py:434`) can change the count. The pinned counts must be identical in all of: alone, siblings-first, siblings-last. If they differ, reset the cache in the fixture through whatever reset the product or the sibling tests already use, or isolate the invocation; if no clean reset exists, stop and report.
  3. If a command's count is not stable, find the cause (cache state, environment, git version) and remove the nondeterminism from the test setup. If it cannot be made stable, do not pin that command; report it and stop.
  4. Write one parametrised test asserting the exact count per command. The failure message lists the recorded git calls, so a contributor sees which call is new.
  5. Put the sampled counts, the number of samples and the three orderings in the module docstring and the hand-back. Note any difference from the grounding's 7 / 14 / 7 and the likely reason (in-process against subprocess).
- **Files**: the same file.
- **Parallel?**: No.
- **Notes**: An exact pin is intended (spec C-004 allows pinning exact counts); it is not a ratchet and has no allowlist. Lowering a count because the product got cheaper is a deliberate one-line edit.

### Subtask T032 – Planted extra call

- **Purpose**: Prove the pin can fail (the spec's non-vacuity control for FR-011).
- **Steps**:
  1. Add a test that wraps one function on the measured path so it performs one additional `git` subprocess (for example a `monkeypatch` wrapper that runs `git --version` before delegating), runs the command, and asserts the count is the pinned count plus one and that the pin comparison fails for it.
  2. Choose a wrapped function that the command really calls; assert the wrapper ran, so the test cannot pass because the wrapper was never reached.
- **Files**: the same file.
- **Parallel?**: After T031.

### Subtask T033 – Selection dry run, marker gates, lint and hand-back

- **Purpose**: Show the test runs on pull requests, and close.
- **Steps**:
  1. Markers: follow the chosen directory's convention (`architectural` in `tests/architectural/`; `unit`/`fast` or `git_repo` elsewhere, as the marker gates require for a test that creates real repositories); never `performance`. Let `tests/architectural/test_fast_tier_marker_completeness.py` and `test_marker_job_completeness.py` decide; do not edit them.
  2. Re-run the T030 dry run on the final tree for the three command-implementing source paths, plus `src/specify_cli/workspace/context.py` and the new test file's own path, and record the output. Show that the job owning the chosen home is selected for all three command paths. State the residual gap honestly: which source changes on the commands' call path would still not select that job, so reach the pin only in the nightly.
  3. Run every command in the Test Strategy section; time the file and report it.
  4. Hand-back: commits, counts, sampled values, dry-run output, tracer notes.
- **Files**: none new.
- **Parallel?**: No.
- **Notes**: Do not edit `.github/ci-module-registry.yml` or any workflow (spec C-006). `src/specify_cli/workspace/context.py` is a do-not-touch path; you only name it in a dry run.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  <the one test_owned_checkout_git_calls.py you created> \
  <its directory's sibling files used for the ordering samples> \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_fast_tier_marker_completeness.py \
  tests/architectural/test_marker_job_completeness.py \
  tests/architectural/test_performance_marker_guard.py \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_battery_partition_proof.py \
  tests/architectural/test_spec_kitty_home_pin_census.py \
  tests/architectural/test_no_manual_global_state_mutation.py \
  tests/ci/test_no_blocking_latency_gate.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check <the created test file>
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude <the created test file>
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict <the created test file>
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

Replace the placeholders with the one file you created and the sibling files of its directory. Run the new file three or more times in separate processes for the samples (`-n0`), then with its siblings in one `-n0` process in both orders.

`tests/architectural/test_spec_kitty_home_pin_census.py` and `test_no_manual_global_state_mutation.py` are run-only. A new `SPEC_KITTY_HOME` write site in a test may trip the hash-pinned census; that census file is not owned here. If it goes red, STOP and report; do not edit the census. If `mypy --strict` is not applied to test files by the project's configuration, run the project's configured check for tests instead and say which.

### Non-vacuity controls (as test cases)

- The planted extra call (T032): pinned count plus one, and the wrapper is asserted to have run.
- The job-selection dry run (T030 step 1, T033 step 2) showing the job that owns the chosen home is selected for a change to each of the three command-implementing source files.
- At least three agreeing samples per command, plus the siblings-first and siblings-last single-process samples, all identical, recorded.

**Red first for this work package.** It adds a test and no product change, so there is no product defect to reproduce. The red evidence is the planted-extra-call test: commit the fixture and counter first, then the pins together with the planted test.

## Definition of Done

- Exactly one of the three candidate files exists; the home was chosen from the dry run and the decision and residual gap are in the hand-back.
- The file pins three counts, each backed by at least three agreeing samples and by identical counts in both sibling orderings, recorded in the docstring.
- The planted-extra-call test proves the pin goes red.
- No `performance` marker; marker gates pass unedited.
- The dry-run output is in the hand-back; no registry or workflow edit.
- All Test Strategy commands pass.
- Subtasks T030 to T033 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **In-process counts differ from subprocess counts.** Pin what the in-process run measures and explain the difference; do not copy 7 / 14 / 7.
- **Cache-dependent counts.** A second in-process invocation may skip calls. Pin the first invocation in a fresh fixture.
- **Git or platform differences.** A count that differs by git version is not pinnable; find out with the samples, and report rather than widening to a range.
- **Fixture cost.** One finalized Mission per module is enough; keep the file fast, since it runs per pull request. In `tests/architectural/` a fixture of several seconds is unusual: time it, and if a battery gate objects, stop and report.
- **The wrong home.** Hosted under `core_misc`, the pin does not run when the commands themselves change. The dry run decides.
- **Helpers imported from another directory's conftest.** Importing is allowed (the performance test does it); editing is not.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **A range or an upper bound instead of an exact pin.** `<=` in the count assertion. The pin is exact.
- **Counts copied from the grounding.** Ask for the three samples; run the file yourself three times.
- **A counter that misses calls.** A wrapper on `subprocess.run` only; the precedent wraps `Popen`. Check `git.exe` handling and that the counter is active during the invocation, not during fixture setup.
- **A planted call that is never reached.** The wrapper must be asserted to have run.
- **A private CLI app.** The runner must drive the application object the entry point uses.
- **The `performance` marker, or a clock.** No `time.` call and no timing assertion in the file.
- **A registry or workflow edit.** None is allowed.
- **A home chosen without the dry run, or more than one candidate file created.** Re-run the dry run for the three command paths yourself and check the owning job is in the output.
- **Order-dependent counts.** Run the file after its siblings and before them in one `-n0` process.

Confirm the trailer on every commit and no AI or model identifier.

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
