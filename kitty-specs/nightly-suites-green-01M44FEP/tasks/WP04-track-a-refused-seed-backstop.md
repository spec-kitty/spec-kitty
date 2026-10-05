---
work_package_id: WP04
title: 'Track A: refused seed commit stops consolidate with its real cause'
dependencies:
- WP01
requirement_refs:
- FR-006
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:58:57.386422+00:00'
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 1 - Track A (bare-slug consolidation)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_refused_seed_commit_backstop.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/_constants.py
- tests/consolidation/test_preflight_seam.py
- tests/consolidation/test_constants_seam.py
- tests/consolidation/test_refused_seed_commit_backstop.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP04 – Track A: refused seed commit stops consolidate with its real cause

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

When the coordination seed commit is refused, `spec-kitty consolidate` stops before any branch moves, with exit 1 and `Error code: COORD_SEED_COMMIT_REFUSED.`, naming the seeded files and saying they are kept so that re-running retries the commit (FR-006; User Story 1, scenario 5).

- The refusal is read from the structured field `SeedReport.commit_refused` (delivered by WP01), never from warning text.
- Nothing is deleted: the seeded files stay in the coordination worktree and the next run retries the commit (I-SEED-10).
- The message does not claim "aborted before any state change", because the seeded files exist.
- A consolidate whose seed commit lands, or that needs no seed, behaves exactly as before.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 1, FR-001 to FR-006, FR-018, FR-019, C-001, C-002, C-005), `plan.md` (section "Design notes / Track A" and the Implementation Concern Map), `research.md` (D1 to D3), `research/code-grounding.md` (sections 3, 6 and 9.1 to 9.4).

**The defect (#5651, tracked by #5611).** A coordination Mission whose primary directory is the bare slug (`kitty-specs/<slug>`) while its coordination branch and coordination directory use the composed `<slug>-<mid8>` name cannot consolidate onto a protected target. It regressed with `5b5699e500`. The red has three layers, each proven by an in-memory probe:

1. The seed commit groups the composed-directory status files to the PRIMARY partition, is refused on the protected branch and leaves them untracked.
2. With layer 1 fixed, the reconciliation gate fails on `kitty-specs/<slug>-<mid8>/status.events.jsonl` because `_is_bookkeeping` anchors on the bare slug.
3. With layers 1 and 2 fixed, teardown reads `meta.json` from the status directory, which has none, so `mid8` is empty and the coordination worktree is never destroyed.

**Operator rulings (2026-10-05).** (a) Alias authority: keep the composed coordination directory and add one exact alias set `{primary directory name, composed <slug>-<mid8> name}`, with `mid8` read from recorded identity and never prefix-matched. (b) One directory on the target: the consolidated Mission leaves exactly one Mission directory on the target, the primary one, with the complete event log.

**Track A work packages.** WP01 enablers, WP02 alias authority and partition classification, WP03 consolidation consumers and the one-directory end state, WP04 refused-seed backstop. Tracks B and C share no file with Track A.

**Fix at the seam (C-002).** Fix on the callee side. Do not change a fixture to make a test pass; the sibling test `test_explicit_delete_override_still_reachable` is green today only because `c5f1280aeb` re-keyed its fixture.

**Why a backstop when WP02 fixes the misroute.** WP02 removes the one known cause of a refused seed commit. Other causes remain (a rejecting commit hook, a protection policy, a transient git failure). Today each of them ends in the misleading `MERGE_UNSAFE_WORKTREE_DIRTY` refusal with a "Commit, stash, or revert" remedy, pointing the operator at files the tool planted itself.

**Verified code facts for this work package (base `9adc68803f`).**

- `src/specify_cli/consolidation/entry_preflight.py:433 _resolve_run_status_dir(seam) -> Path`: returns `seam.write_dir(MissionArtifactKind.STATUS_STATE).path` and discards the rest of the `WriteLocation`. It already maps four exceptions to `_abort_before_state_change` (`:426`), which prints `_MERGE_ABORT_NOTICE` (`:423`, "Merge aborted before any state change.") and returns `typer.Exit(1)`. Its single caller is `executor.py:487`, in the unlocked pre-phase, before the merge lock and both pre-mutation captures.
- `seam.write_dir` is `PlacementSeam.write_dir` (`src/mission_runtime/resolution.py:2426`) and returns a `WriteLocation` (`src/mission_runtime/write_location.py:76`) whose `.seed` is a `SeedReport | None`.
- `src/specify_cli/consolidation/_constants.py`: the pattern to follow is `COORD_MOVED_AFTER_LANDING = "COORD_MOVED_AFTER_LANDING"` (`:52`) with `COORD_MOVED_AFTER_LANDING_SUFFIX = f" Error code: {COORD_MOVED_AFTER_LANDING}."` (`:55`).
- The seed's refusal branch and its retry design: `coordination/coord_seed.py:619 _commit_and_restore` (refusal at `:655`), I-SEED-10 at `:626-643` and `:725`. The existing unit-level refusal tests are `tests/coordination/test_coord_seed.py:558`, `:603`, `:632` (owned by WP01; read them, do not edit them).
- Real-consolidation test helpers you may import but not edit: `tests/integration/test_merge_lane_planning_data_loss.py` `_invoke_merge_cli` (`:1473`), `_real_merge_external_mocks` (`:400`), `_write_coord_retaining_meta` (`:1450`), and the fixture helpers in `tests/integration/conftest.py`. That test file is owned by WP03.
- Existing seam tests for these modules: `tests/consolidation/test_preflight_seam.py`, `tests/consolidation/test_constants_seam.py`.
- The hook trigger is real: the seed commit goes through `safe_commit`, which runs `git -c commit.gpgsign=false commit --only -m <message> -- <files>` without `--no-verify` (`src/specify_cli/git/commit_helpers.py:869`), so `pre-commit` and `commit-msg` hooks run.
- WP01 delivers `SeedReport.commit_refused` (the reason) and `SeedReport.uncommitted_paths` (repository-relative paths of the files left uncommitted, also populated on a retry where `carried` is empty).

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
- **Dependencies**: WP01

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP04 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T018 – Red test through the CLI: a hook rejects the seed commit

- **Purpose**: Reproduce the misleading refusal through the real entry point, with a trigger that does not depend on the bare-slug misroute.
- **Steps**:
  1. Create `tests/consolidation/test_refused_seed_commit_backstop.py`. Build a coordination Mission whose primary directory carries the composed name (so WP02's fix is irrelevant to the outcome) and whose coordination worktree lacks the Mission directory, so consolidate has to seed it. Verify with a first assertion-free run that a seed actually happens in your fixture (the log line "coordination seed for mission" or a non-`None` `WriteLocation.seed`); if no seed runs, the test proves nothing.
  2. Install a git hook in the test repository that rejects only the seed commit: a `commit-msg` hook that exits non-zero when the message contains `seed coordination surface` (the subject built at `coord_seed.py:594`). Hooks do run on this commit (`git/commit_helpers.py:869`, no `--no-verify`).
  3. Run consolidate through `_invoke_merge_cli`. Assert: exit code 1; output contains `Error code: COORD_SEED_COMMIT_REFUSED.`; output names both seeded files; output says the files are kept and that re-running retries; output does not contain `MERGE_UNSAFE_WORKTREE_DIRTY` or "Commit, stash, or revert"; the target branch, the mission branch and the coordination branch are at their pre-run commits; the seeded files still exist in the coordination worktree.
  4. Control in the same file: the same fixture without the hook consolidates with exit 0 and prints no `COORD_SEED_COMMIT_REFUSED`. **STOP condition:** if this control cannot exit 0 on your base (WP01 only) with a composed-primary fixture, do not weaken the control and do not switch to a bare-slug fixture on this base; stop and report to the orchestrator with the output. The fallback is the orchestrator's to choose: make this work package depend on WP03 and reuse the reproduction's shape.
  5. Commit the file red (the hook test fails on the error-code assertion; the control passes). Record the output the base produces.
- **Files**: new `tests/consolidation/test_refused_seed_commit_backstop.py` (about 180 lines).
- **Parallel?**: No; first.
- **Notes**: Mark the hook test `regression` plus the markers its directory siblings use; no `p0_repro`. Make the hook script portable (`#!/bin/sh`) and executable; skip the hook test on Windows if the directory's other hook tests do.

### Subtask T019 – The refusal in `_resolve_run_status_dir`

- **Purpose**: Refuse with the real cause.
- **Steps**:
  1. Add `COORD_SEED_COMMIT_REFUSED` and its `..._SUFFIX` to `_constants.py`, following the `COORD_MOVED_AFTER_LANDING` pattern, with a comment naming FR-006 and the exit code (1).
  2. In `_resolve_run_status_dir`, keep the `WriteLocation`, and when `location.seed is not None and location.seed.commit_refused is not None`, print the refusal and raise `typer.Exit(1)`.
  3. Message content, in this order: what happened (the coordination seed commit was refused, with the structured reason); which files are uncommitted (from `location.seed.uncommitted_paths`, never from `carried`, printed as paths an operator can open in the coordination worktree); that they are kept and nothing was removed; that re-running `spec-kitty consolidate` retries the commit once the cause is fixed; the error-code suffix. Do not print `_MERGE_ABORT_NOTICE`: it says no state changed, which is untrue here. Say instead that no branch was moved.
  4. Extract the rendering into a small private function so `_resolve_run_status_dir` stays under the complexity ceiling and the message is unit-testable.
  5. The return type stays `Path`; `executor.py:487` is not edited.
- **Files**: `src/specify_cli/consolidation/_constants.py` (about 6 lines), `src/specify_cli/consolidation/entry_preflight.py` (about 30 lines).
- **Parallel?**: No.
- **Notes**: `orchestrator-api consolidate-mission` has its own entry; do not widen scope to it. If you find it reaches `_resolve_run_status_dir` too, say so in the hand-back.

### Subtask T020 – Branch coverage and the no-delete proof

- **Purpose**: Cover every branch of the new code and pin I-SEED-10.
- **Steps**:
  1. In `tests/consolidation/test_preflight_seam.py`, add unit tests with a stub seam whose `write_dir` returns a `WriteLocation`: `seed is None` returns the path; `seed` present with `commit_refused is None` returns the path; `commit_refused` set raises `typer.Exit` with code 1 and prints the code and the file names. Assert the four existing exception mappings still render as before.
  2. In `tests/consolidation/test_constants_seam.py`, pin the constant and its suffix the way the file pins its neighbours.
  3. In the backstop file, add a retry test: after the refused run, remove the hook and run consolidate again; it exits 0 and the seeded files are committed on the coordination branch. This proves nothing was deleted and the retry works.
  4. In the backstop file, add a twice-refused test: run consolidate twice with the hook in place. The second run also exits 1 with the error code and still names both seeded files (on the second run the seed carries nothing new, so a message built from `carried` would name none).
- **Files**: the three test files.
- **Parallel?**: Yes, alongside T019 once the constant exists.

### Subtask T021 – Gates, lint and hand-back

- **Purpose**: Close with evidence.
- **Steps**:
  1. Run every command in the Test Strategy section.
  2. Hand-back: commits, counts, the base output of the hook test, the trigger used, tracer notes, any out-of-map edit with rationale.
- **Files**: none.
- **Parallel?**: No.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  tests/consolidation/test_refused_seed_commit_backstop.py \
  tests/consolidation/test_preflight_seam.py \
  tests/consolidation/test_constants_seam.py \
  tests/coordination/test_coord_seed.py \
  tests/mission_runtime/test_placement_seam_write_dir.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_write_surface_placement_guard.py \
  tests/architectural/test_coord_read_residuals_closeout.py \
  tests/architectural/test_mission_runtime_surface.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_no_legacy_terminology.py \
  tests/architectural/test_spec_kitty_home_pin_census.py \
  tests/architectural/test_no_manual_global_state_mutation.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check src/specify_cli/consolidation/entry_preflight.py src/specify_cli/consolidation/_constants.py tests/consolidation/test_preflight_seam.py tests/consolidation/test_constants_seam.py tests/consolidation/test_refused_seed_commit_backstop.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude src/specify_cli/consolidation/entry_preflight.py src/specify_cli/consolidation/_constants.py tests/consolidation/test_preflight_seam.py tests/consolidation/test_constants_seam.py tests/consolidation/test_refused_seed_commit_backstop.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict src/specify_cli/consolidation/entry_preflight.py src/specify_cli/consolidation/_constants.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

`tests/architectural/test_layer_rules.py` references `entry_preflight` and is a do-not-touch file: you may run it, never edit it.

`tests/architectural/test_spec_kitty_home_pin_census.py` and `test_no_manual_global_state_mutation.py` are run-only. A new test that sets `SPEC_KITTY_HOME` or mutates process-global state may trip the hash-pinned census; that census file is not owned here. If it goes red, STOP and report; do not edit the census.

### Non-vacuity controls (as test cases)

- The refusal is triggered through the CLI by a hook that rejects the seed commit (T018 step 3), not by calling the function with a hand-built report alone.
- The no-hook control on the same fixture exits 0 (T018 step 4): the refusal fires only when a commit was refused.
- The retry test (T020 step 3): the seeded files survive the refusal and are committed on the next run.
- A message assertion that the output does not contain the old dirty-worktree remedy.
- The twice-refused test (T020 step 4): the file names are still reported on the second refusal.

## Definition of Done

- The hook test was committed red and is green at the end, with the control and the retry test.
- `COORD_SEED_COMMIT_REFUSED` is defined once in `_constants.py`; the refusal exits 1 and names the kept files.
- The refusal reads `SeedReport.commit_refused`; no code matches on warning text.
- Nothing is deleted on the refusal path; `executor.py` is unchanged.
- All Test Strategy commands pass with counts recorded.
- Subtasks T018 to T021 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **The control cannot go green on a WP01-only base.** STOP and report (T018 step 4); the fallback is a dependency on WP03, decided by the orchestrator.
- **File names taken from `carried`.** Empty on a retry; use `uncommitted_paths`.
- **No seed runs in the fixture.** A fixture whose coordination worktree already holds the Mission directory never seeds. Prove a seed happens before asserting on its refusal.
- **Message promises too much.** "No branch was moved" is true; "no state changed" is not.
- **Parallel lane with WP03.** WP03 owns `executor.py` and the integration test file. This work package edits neither.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **Warning-text matching.** Grep the diff for "seed commit not applied"; the condition must be on `commit_refused`.
- **Helper-only proof.** The CLI-level test must run consolidate with a real rejecting trigger; a test that only calls `_resolve_run_status_dir` with a stub is necessary but not sufficient.
- **Cleanup instead of refusal.** No `unlink`, `rmtree`, `git clean`, `git reset` or `git checkout --` in the diff. The retry test must pass.
- **Wrong-reason pass.** In this lane (without WP02) a bare-slug fixture is refused by the misroute, not by the hook. The fixture must use a composed primary directory, and the no-hook control must exit 0.
- **Reused abort notice.** The output must not say "before any state change".
- **Exit code.** 1, asserted.
- **File names from `carried`.** The twice-refused test must exist and pass.

Confirm red then green from the commit sequence, the trailer on every commit, and no AI or model identifier.

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
