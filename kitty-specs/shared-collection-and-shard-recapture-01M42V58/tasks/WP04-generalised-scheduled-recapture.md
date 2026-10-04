---
work_package_id: WP04
title: Generalised scheduled recapture
dependencies: []
requirement_refs:
- C-008
- FR-017
- FR-018
- FR-019
- FR-020
- FR-021
- NFR-007
- SC-006
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: 46d023549daccdbe2a7ce9f3a26a6f89ef11a8c4
created_at: '2026-10-04T07:30:00.567122+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Shard-timing provenance
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/recapture_shard_timings.py
- tests/ci/test_recapture_shard_timings.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/recapture_shard_timings.py
- scripts/ci/recapture_charter_shard_timings.py
- tests/ci/test_recapture_shard_timings.py
- tests/ci/test_recapture_charter_shard_timings.py
- .github/workflows/ci-charter-shard-recapture.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Generalised scheduled recapture

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

The scheduled recapture stops being charter-only. It finds drifted modules with a count-only pass, captures only those (each in its own subprocess, through the canonical producer), respects a time budget, refreshes an open proposal with a follow-up commit, and reports a rejected push in words the operator can act on.

Done when `contracts/scheduled-recapture.md` holds and `uv run --no-sync pytest tests/ci/test_recapture_shard_timings.py -q` passes. Requirements: FR-017, FR-018, FR-019, FR-020, FR-021, NFR-007, C-008.

## Context & Constraints

- Mission documents: `kitty-specs/shared-collection-and-shard-recapture-01M42V58/spec.md`, `plan.md`, `research.md` (decisions D-01..D-15, brownfield findings B-01..B-09), `data-model.md`, `contracts/`, `quickstart.md`.
- Charter: `.kittify/charter/charter.md`. Load action doctrine with `spec-kitty charter context --action implement`.
- **ATDD-first (binding)**: the failing test is committed before the implementation, as its own commit.
- **No heavy suites**: run only the files named under "Test Strategy". Never run `tests/architectural/` or `tests/ci/` as a whole directory, `make test-fast` or `make test-full`.
- Run tools as `uv run --no-sync <cmd>` (a bare `uv run` rewrites `uv.lock` on this machine; if `uv.lock` shows as modified, `git checkout uv.lock`).
- Formatting: check with `uv run --no-sync ruff format --check --force-exclude <files>`; never format a file on the ruff-format exclude list by explicit path without `--force-exclude`.
- Complexity ceiling is 15 per function. No `# noqa`, no `# type: ignore`, no new allowlist or baseline entry (C-006).
- Use `kernel.clock` for timestamps in `scripts/` (clock-door gate); in tests use `monkeypatch`, never direct `os.environ` / `sys.argv` / cwd mutation (global-state gate).
- Terminology: "Mission" (never "feature"), "primary branch (`main`)", "repository root checkout".
- Tracer notes: the mission's tracer files live on the coordination branch, not in your lane. Put any tooling friction or design choice in your final hand-back under a heading `Tracer notes`; the orchestrator records them.
- Current script: `scripts/ci/recapture_charter_shard_timings.py` (590 lines). Landmarks: `MODULE = "charter"` (:120), `RECAPTURE_BRANCH` (:125), `SECRET_NAME = "CHARTER_SHARD_RECAPTURE_TOKEN"` (:129), `run_capture_or_die` (:181), `capture_is_trustworthy` (:203; exit status 0 or 1 and at least one duration), `has_drift` (:220), `find_open_recapture_pr` (:226), `_push_and_open_pr` (:407; `git push --force` then `gh pr create`), `run_capture_phase` (:509; in-process `capture_shard_timings.main`, writes `drift`/`before`/`after` to `$GITHUB_OUTPUT`), `run_publish_phase` (:542; an open proposal means skip), `main` (:569; positional `capture|publish`). Read the whole file and its test before changing anything.
- Canonical producer: `scripts/ci/capture_shard_timings.py`. Flags `--module` (repeatable), `--run-id`, `--write`, `--suite`, `--from-junit`, `--output`. It writes `module_test_durations`, `module_test_count` and `module_capture_provenance` into `.github/ci-shard-timings.json`. It exits 1 when any captured test failed. **Do not edit the producer** (C-004).
- Per-module collected count: see `tests/architectural/test_module_length_agreement.py` `_live_collected_count` (:237), `_collected_counts` (:299), `_resolve_test_dirs` (:217), and `scripts/ci/shard_select.py`. Reuse the selection the producer itself uses so "collected" means the same thing in both places; do not write a third resolver.
- **Do not rename the workflow file or its job key in this package.** `WORKFLOW_FILES` and other pins name the file; WP06 renames it. Change only its content.
- **Do not rename the secret** (`CHARTER_SHARD_RECAPTURE_TOKEN`); it is a repository secret only the operator can change.
- The reported failure (see #5536): the publish step's `git push --force origin HEAD:refs/heads/ci/recapture-charter-shard-timings` is rejected with HTTP 403, `Permission ... denied` (runs 37182764995 and 37097776055). The token cannot write to the repository. Code cannot fix the token; this package makes the failure explicit. Three recent runs also hit the 30-minute job cap.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP04 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T016 – Rename and campsite

- **Purpose**: a behaviour-preserving first commit.
- **Steps**:
  1. `git mv scripts/ci/recapture_charter_shard_timings.py scripts/ci/recapture_shard_timings.py` and `git mv tests/ci/test_recapture_charter_shard_timings.py tests/ci/test_recapture_shard_timings.py`. Update imports in the test and the script path in the workflow (`ci-charter-shard-recapture.yml:155,170`). Switch the workflow invocations to `python -m scripts.ci.recapture_shard_timings`.
  2. Lift the single-module assumption into parameters: functions that read `MODULE` take a module argument. Behaviour stays charter-only in this commit.
  3. The existing test pins the job key `recapture-charter-shard-timings` (:966) and paths (:27-28, :881, :959); keep the job key, update only the script paths.
  4. Search for other references to the old script name outside `kitty-specs/` and `tests/docs/fixtures/` (`git grep -n recapture_charter_shard_timings -- . ':!kitty-specs' ':!tests/docs/fixtures'`). Documentation that mentions it belongs to WP06. List what you found in your hand-back; do not edit files you do not own unless a test goes red because of the rename, in which case make the one-line fix and record it.
- **Validation**: the renamed test file passes unchanged in behaviour.

### Subtask T017 – Red-first tests

- **Purpose**: pin the new contract through `main(argv)`. Commit failing, before T018.
- **Fixtures**: a temporary repository with a small registry and timings file; a fake producer (patch the subprocess runner) that writes plausible data and returns a chosen exit status; a fake count function. No real captures.
- **Cases**:
  1. One non-charter module drifted (count differs) → exactly that module is captured; others untouched (SC-006).
  2. A module with missing provenance, and one with invalid provenance (exit status 2, or zero durations), are both treated as drifted.
  3. Nothing drifted → nothing captured, exit 0, `drift=false` in the outputs.
  4. Capture of one module returns an invalid result → that module's committed data is byte-identical afterwards, the remaining drifted modules are still captured, the result lists it under `failed`, exit 1 (FR-018). **Paired control**: on the same fixture a valid capture updates the data.
  5. Budget: with a fake clock and a budget smaller than two captures, the first is captured, the second is listed under `deferred`, exit 0 (FR-019).
  6. `--module` restricts candidates.
  7. Publish with no open proposal → pushes the branch and opens a pull request (existing behaviour, re-pinned).
  8. Publish with an open proposal → fetches the proposal branch, commits on top, pushes **without** `--force`; never `gh pr create` (FR-020). Assert the exact git argument lists.
  8b. Carry-over with an open proposal: modules A and B have drifted on the primary branch, the open proposal branch already holds a valid recapture of A whose count matches → only B is captured this run. Without this, every night recaptures the same first modules and defers the same tail.
  9. Push rejected with a 403 / `Permission ... denied` message → exit non-zero and the output names the missing repository write permission and the secret name (FR-021). **Paired control**: a successful push on the same fixture exits 0.
  10. The valid-capture predicate: exit 0 with durations → valid; exit 1 with durations → valid; exit 0 with none → invalid; exit 2 → invalid.

### Subtask T018 – Count-only drift pass and shared predicate

- **Steps**:
  1. `is_valid_capture(provenance: Mapping | None) -> bool`: the record's `exit_code` field in {0, 1} and `unique_tests_measured` above zero (provenance fields are `run_id, command, captured_at, test_dirs, selection, unique_tests_measured, exit_code, producer`). This is the single authority (research D-11); WP05's provenance test imports it. Refactor `capture_is_trustworthy` to call it.
  2. `drifted_modules(registry, timings, counts) -> list[str]`: a module is drifted when its collected count differs from `module_test_count`, or its provenance is missing or invalid.
  0. **Overlay an open proposal first**: when a recapture proposal is open, read the timings file from the proposal branch (`git show origin/<branch>:.github/ci-shard-timings.json` after a fetch) and use it as the committed baseline for drift and as the starting data for this run's captures. Otherwise use the working tree's file.
  3. Collected counts come from one `--collect-only` pass per module using the producer's own selection. Run each as a subprocess with an argument list. If a count pass fails for a module, treat that module as failed for this run (reported, data untouched) rather than as clean.
- **Notes**: keep functions pure where possible and pass the runner in, so tests need no global patching.

### Subtask T019 – Per-module subprocess capture with isolation

- **Steps**:
  1. For each drifted module run `python -m scripts.ci.capture_shard_timings --module <m> --run-id <id> --write` as its own subprocess, with a `timeout` so one hung capture cannot consume the whole job (a timed-out capture is a failed module: data restored, reported). The producer runs pytest in-process once per process, so modules cannot share a process.
  2. Before each capture keep the module's three committed entries in memory; if the result is not valid, restore exactly those entries (FR-018) and record the module under `failed`.
  3. Capture runs must not fail the whole script when the producer exits 1 (some tests failed): that is a valid capture when durations exist.

### Subtask T020 – Time budget

- **Steps**: `--budget-seconds`; use `kernel.clock` (not `time.time` directly; the clock-door gate applies to `scripts/`). The budget clock starts when the script starts, so the count-only pass is inside it. Before starting a capture, stop if elapsed is at or beyond the budget. Order candidates so the module with the oldest provenance `captured_at` goes first (missing provenance first of all). Report `deferred`.
- **Workflow default**: choose a budget that leaves headroom under the job's `timeout-minutes` for setup and publishing. `charter` alone takes about 18 minutes; raise the job timeout if a single module could not fit, and set the budget so that at most one capture can start late. State the two numbers and the reasoning in the workflow comment.

### Subtask T021 – Publish phase

- **Steps**:
  1. No open proposal: keep today's behaviour (push the fixed branch, open a pull request). The force push stays only on this path, where the branch has no open pull request, as the existing design note requires.
  2. Open proposal: `git fetch origin <branch>`, create the commit on top of `FETCH_HEAD`, plain `git push origin HEAD:refs/heads/<branch>`. If the fast-forward push is refused because the branch moved, exit non-zero with a clear message; never force.
  3. Rejected push: detect HTTP 403 or `Permission to ... denied` in git's stderr and exit non-zero with a message that states: the token in secret `CHARTER_SHARD_RECAPTURE_TOKEN` lacks write access to repository contents, the capture succeeded, and nothing was published. Other push failures keep their original stderr.
  4. The proposal's title and body list the captured, failed and deferred modules.

### Subtask T022 – Workflow content

- **Steps**: in `.github/workflows/ci-charter-shard-recapture.yml`, update the capture and publish steps for all modules (budget flag, `python -m` invocation, summary output), update the header comments that describe charter-only behaviour, and keep: the file name, the job key, the primary-branch gate (`:116`), the permissions block, the cron, the strict-check job (it runs after the recapture job).
- **Validation**: `tests/ci/test_recapture_shard_timings.py` workflow assertions, plus `uv run --no-sync pytest tests/architectural/test_no_duplicate_suite_execution.py -q` (the file is in `NON_CHANGE_TRIGGERED_WORKFLOWS`).

## Test Strategy

```bash
uv run --no-sync pytest tests/ci/test_recapture_shard_timings.py tests/ci/test_capture_shard_timings.py -q
uv run --no-sync pytest tests/architectural/test_no_duplicate_suite_execution.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_fork_guard.py -q
uv run --no-sync ruff check scripts/ci/recapture_shard_timings.py tests/ci/test_recapture_shard_timings.py
uv run --no-sync ruff format --check --force-exclude scripts/ci/recapture_shard_timings.py tests/ci/test_recapture_shard_timings.py
uv run --no-sync python -m scripts.ci.recapture_shard_timings --help
```

Do **not** run a real capture in this package; WP05 does that.

## Risks & Mitigations

- The count pass and the producer disagreeing on selection would make every module look drifted. Use the producer's own selection function.
- A follow-up commit on the proposal branch conflicts if the primary branch changed the timings file meanwhile. The fast-forward refusal path reports it; the next run starts from the new base.
- `git mv` plus heavy edits can hide the rename from git. Keep the rename commit separate from the functional commits.

## Review Guidance

- Verify red→green on the T017 commit.
- Confirm the producer file is unchanged (`git diff --stat` shows no change to `scripts/ci/capture_shard_timings.py`).
- Confirm there is exactly one valid-capture predicate.
- Confirm no forced push can reach a branch with an open pull request, and that the workflow file name and job key are unchanged.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
