---
work_package_id: WP01
title: 'Track A enablers: teardown identity read and structured seed refusal'
dependencies: []
requirement_refs:
- FR-001
- FR-006
- C-005
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:35:55.344130+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Track A (bare-slug consolidation)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/phase_teardown.py
- src/mission_runtime/write_location.py
- src/specify_cli/coordination/coord_seed.py
- tests/coordination/test_coord_seed.py
- tests/consolidation/test_coord_teardown_order_3926.py
- tests/mission_runtime/test_placement_seam_write_dir.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP01 – Track A enablers: teardown identity read and structured seed refusal

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

Two tidy-first enablers that the rest of Track A builds on. Neither changes what an operator sees for a Mission whose primary directory already carries the composed name.

- The coordination teardown reads Mission identity (`mid8`) from `run.target_feature_dir` (the primary metadata), as its two neighbours in the same file already do. A status directory without `meta.json` no longer yields an empty `mid8`.
- `SeedReport` carries two defaulted structured fields, set exactly where the seed commit is refused: `commit_refused: str | None` (the reason) and `uncommitted_paths: tuple[str, ...]` (the repository-relative paths left uncommitted). WP04 reads both; nothing reads them yet.
- Every named test file and gate file in the Test Strategy section passes; `mypy --strict` and `ruff` are clean.

This work package covers FR-001 and FR-006 in part: it prepares the seams, it does not make the reproduction green.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 1, FR-001 to FR-006, FR-018, FR-019, C-001, C-002, C-005), `plan.md` (section "Design notes / Track A" and the Implementation Concern Map), `research.md` (D1 to D3), `research/code-grounding.md` (sections 3, 6 and 9.1 to 9.4).

**The defect (#5651, tracked by #5611).** A coordination Mission whose primary directory is the bare slug (`kitty-specs/<slug>`) while its coordination branch and coordination directory use the composed `<slug>-<mid8>` name cannot consolidate onto a protected target. It regressed with `5b5699e500`. The red has three layers, each proven by an in-memory probe:

1. The seed commit groups the composed-directory status files to the PRIMARY partition, is refused on the protected branch and leaves them untracked.
2. With layer 1 fixed, the reconciliation gate fails on `kitty-specs/<slug>-<mid8>/status.events.jsonl` because `_is_bookkeeping` anchors on the bare slug.
3. With layers 1 and 2 fixed, teardown reads `meta.json` from the status directory, which has none, so `mid8` is empty and the coordination worktree is never destroyed.

**Operator rulings (2026-10-05).** (a) Alias authority: keep the composed coordination directory and add one exact alias set `{primary directory name, composed <slug>-<mid8> name}`, with `mid8` read from recorded identity and never prefix-matched. (b) One directory on the target: the consolidated Mission leaves exactly one Mission directory on the target, the primary one, with the complete event log.

**Track A work packages.** WP01 enablers, WP02 alias authority and partition classification, WP03 consolidation consumers and the one-directory end state, WP04 refused-seed backstop. Tracks B and C share no file with Track A.

**Fix at the seam (C-002).** Fix on the callee side. Do not change a fixture to make a test pass; the sibling test `test_explicit_delete_override_still_reachable` is green today only because `c5f1280aeb` re-keyed its fixture.

**Verified code facts for this work package (base `9adc68803f`).**

- `src/specify_cli/consolidation/phase_teardown.py:393`: `_meta_for_teardown = _load_meta(run.feature_dir)`, where `_load_meta` is `specify_cli.core.paths.load_meta_fail_closed` (imported at `:388`). `run.feature_dir` is the status directory resolved by the write accessor; under a bare-slug coordination Mission it is the composed directory in the coordination worktree, which holds no `meta.json`.
- The same file reads `run.target_feature_dir` at `:127` (`_flatten_coordination_metadata_after_branch_delete`) and `:502`; `run_state.py:455` does too. `target_feature_dir` is a field of `_MergeRunState` (`run_state.py:183`), filled at `executor.py:227` from `placement_seam(...).read_dir(MissionArtifactKind.PRIMARY_METADATA)`.
- `src/mission_runtime/write_location.py`: `SeedReport` ends with `coord_commit: str | None = None` (`:70`) and `warnings: tuple[str, ...] = ()` (`:73`). `WriteLocation` (`:76`) is `kw_only=True` and carries `seed: SeedReport | None = None`.
- `src/specify_cli/coordination/coord_seed.py:619` `_commit_and_restore`: the refusal branch is `elif result.status != _STATUS_UNCHANGED:` at `:655`; it clears `restore_relpaths` and appends the warning text "seed commit not applied (status=...)". The report is built at `:673` (`return SeedReport(`). `_commit_seed` is at `:585`. Today a refusal is visible only as warning text.
- Existing coverage of the refusal: `tests/coordination/test_coord_seed.py:558` `test_refused_seed_commit_then_retried`, `:603` `test_refused_seed_commit_keeps_the_root_copy`, `:632` `test_refused_seed_commit_retry_is_config_independent`.
- `tests/consolidation/test_coord_teardown_order_3926.py` builds a `_MergeRunState` through `_run_state` (`:108`) on the fixture `coord_repo_with_live_worktree` (`:82`).

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

Start with `spec-kitty agent action implement WP01 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T001 – Record the baseline

- **Purpose**: Know what is green and red before any edit, so a later failure is attributed correctly.
- **Steps**:
  1. Run the three owned test files and the gate files listed under Test Strategy on your lane's base commit. Record passed and failed counts.
  2. Run the reproduction once and confirm it is red with `MERGE_UNSAFE_WORKTREE_DIRTY`: `$PY -m pytest "tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target" -n0 -p no:cacheprovider -q`. It stays red after this work package; that is expected.
- **Files**: none changed.
- **Parallel?**: No.
- **Notes**: A failure you did not cause goes in your hand-back, classified per the baseline-red rule in `CLAUDE.md`.

### Subtask T002 – Teardown reads identity from the primary metadata

- **Purpose**: Layer 3 of the red. The teardown must learn `mid8` from the directory that holds `meta.json`.
- **Steps**:
  1. In `tests/consolidation/test_coord_teardown_order_3926.py`, add a focused test built on `coord_repo_with_live_worktree` and `_run_state`: give the run a `feature_dir` that has no `meta.json` (a status-only directory, the bare-slug shape) while `target_feature_dir` holds the `meta.json` with the `mid8`. Assert the coordination branch, worktree and marker are torn down. Confirm it fails before the source edit and note the failure line.
  2. Change `phase_teardown.py:393` to read from `run.target_feature_dir`. Keep the fail-closed reader and the comment about `MissionMetaReadError` propagation; update the comment so it says which directory is read and why.
  3. Check every other use of `_meta_for_teardown` and `_mid8_for_teardown` below `:393` still means the same thing; if the same function reads the status directory for another purpose, leave that read alone.
  4. Keep the two existing tests in the file green unchanged (`:142`, `:164`).
- **Files**: `src/specify_cli/consolidation/phase_teardown.py` (one read site plus its comment), `tests/consolidation/test_coord_teardown_order_3926.py`.
- **Parallel?**: Yes, independent of T003.
- **Notes**: For a Mission whose primary directory carries the composed name the two directories resolve to the same identity, so its behaviour is unchanged; your new test and the two existing ones together prove both shapes. Commit the new test on its own, red, before the source change (step 1), and the one-line change as the next commit; record the red output in the hand-back.

### Subtask T003 – `SeedReport.commit_refused`

- **Purpose**: Give the refused seed commit a structured signal so a consumer never parses warning text (FR-006).
- **Steps**:
  1. Add `commit_refused: str | None = None` to `SeedReport` in `src/mission_runtime/write_location.py`, after `coord_commit`, with a `#:` comment in the style of its neighbours: `None` when the commit was applied, unchanged or not attempted; otherwise a short reason built from the router result (status and, when present, its reason).
  2. Do not add a new export to `mission_runtime/__init__.py`. `SeedReport` is already on the surface; a defaulted field changes no caller. Run `tests/architectural/test_mission_runtime_surface.py` to confirm.
  3. In `coord_seed._commit_and_restore`, set the field in the refusal branch (`:655`) and pass it into the `SeedReport(...)` built at `:673`. Build the reason string once and reuse it for the existing warning text so the two cannot drift; the warning text itself stays byte-identical.
  4. Add a second defaulted field `uncommitted_paths: tuple[str, ...] = ()`: the repository-relative (posix) paths of the files the refused commit left uncommitted. Set it in the same refusal branch from `commit_relpaths` (`:648`, the COORD-kind files on disk under `final_dir`), converted to repository-relative paths of the coordination checkout. Do not derive it from `merge.carried`: on a retry of a refused commit `carried` is empty (`:627-633`) while the files are still uncommitted, so `carried` cannot name them. Empty tuple whenever `commit_refused is None`.
  5. Extend the three existing refusal tests in `tests/coordination/test_coord_seed.py` (`:558`, `:603`, `:632`) with assertions on both fields: set on the refused attempt, `None` / `()` on the retried attempt that commits. Add one test that a seed whose commit result is `unchanged` leaves both at their defaults, and one test that a commit refused twice in a row reports the same non-empty `uncommitted_paths` on the second refusal although `carried` is empty then.
  6. In `tests/mission_runtime/test_placement_seam_write_dir.py`, add assertions on an existing `write_dir` seed case that `location.seed.commit_refused is None` and `location.seed.uncommitted_paths == ()` when the seed commit lands.
- **Files**: `src/mission_runtime/write_location.py` (about 8 lines), `src/specify_cli/coordination/coord_seed.py` (about 10 lines), the two test files.
- **Parallel?**: Yes, independent of T002.
- **Notes**: Do not change what the seed deletes, restores or logs (I-SEED-8 and I-SEED-10, `coord_seed.py:626-643`, `:725`). `coord_seed.py` has a second caller in `core/mission_creation.py`, a do-not-touch path; the field is defaulted so that caller needs no edit.

### Subtask T004 – Gates, lint and hand-back

- **Purpose**: Prove the enablers are behaviour-preserving for everything else.
- **Steps**:
  1. Run every command in the Test Strategy section.
  2. Confirm `git diff --stat` touches only owned files.
  3. Write the hand-back: commits (hash and subject), test commands with counts, tracer notes, any out-of-map edit with its rationale.
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
  tests/coordination/test_coord_seed.py \
  tests/consolidation/test_coord_teardown_order_3926.py \
  tests/mission_runtime/test_placement_seam_write_dir.py \
  tests/consolidation/test_coordination_flatten_on_branch_delete.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_mission_runtime_surface.py \
  tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_write_surface_placement_guard.py \
  tests/architectural/test_coord_read_residuals_closeout.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_exemption_registry_ratchet.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check src/specify_cli/consolidation/phase_teardown.py src/mission_runtime/write_location.py src/specify_cli/coordination/coord_seed.py tests/coordination/test_coord_seed.py tests/consolidation/test_coord_teardown_order_3926.py tests/mission_runtime/test_placement_seam_write_dir.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude src/specify_cli/consolidation/phase_teardown.py src/mission_runtime/write_location.py src/specify_cli/coordination/coord_seed.py tests/coordination/test_coord_seed.py tests/consolidation/test_coord_teardown_order_3926.py tests/mission_runtime/test_placement_seam_write_dir.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict src/specify_cli/consolidation/phase_teardown.py src/mission_runtime/write_location.py src/specify_cli/coordination/coord_seed.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

### Non-vacuity controls (as test cases)

- Teardown: the new test fails when `:393` is reverted to `run.feature_dir` (you saw it red in T002 step 1).
- Seed refusal: on the refused attempt `commit_refused` is a non-empty string, `uncommitted_paths` names the seeded files and `coord_commit is None`; on the retry that commits, `commit_refused is None`, `uncommitted_paths == ()` and `coord_commit` is set. Both halves sit in the same test, so a field that is always empty or always set fails it.
- Twice refused: the second refusal still names the files, with `carried` empty.

`tests/architectural/test_destructive_op_routing.py` and `test_exemption_registry_ratchet.py` are run-only here; the first is a do-not-touch file.

## Definition of Done

- `phase_teardown.py:393` reads `run.target_feature_dir`; the new teardown test and the two existing ones pass.
- `SeedReport.commit_refused` and `SeedReport.uncommitted_paths` exist, are defaulted, and are set only in the refusal branch; the warning text is unchanged.
- The teardown test was committed red before the `:393` change.
- No new `mission_runtime` root export; no edit outside owned files.
- All Test Strategy commands pass; counts are in the hand-back.
- Subtasks T001 to T004 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **`SeedReport` is on the `mission_runtime` surface.** A non-defaulted field or a new root export trips `test_mission_runtime_surface.py`. Keep the field defaulted and add no export.
- **The teardown function reads the status directory for more than identity.** Change only the identity read; if another statement needs the status directory, keep it on `run.feature_dir`.
- **Warning text drift.** Tests and log scrapers read the existing text; build the reason once and keep the sentence byte-identical.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **The field is added but never set.** Check the refusal test asserts a non-empty `commit_refused` on the refused attempt, and revert the assignment locally to see the test go red.
- **`uncommitted_paths` taken from `carried`.** The twice-refused test must exist and must show a non-empty tuple while `carried` is empty.
- **The field is derived from the warning text.** It must be set from the router result in the same branch that appends the warning; grep for string matching on "seed commit not applied".
- **The teardown test passes without the source change.** Check out the test at the commit before the source edit, or revert `:393` locally; the new test must be red.
- **Behaviour change smuggled in.** `git diff` of `coord_seed.py` must not touch `_restore_root_files`, the restore tuple logic or the log call beyond passing the new field.

Also confirm: commit order (enablers with their tests), trailer present, no AI or model identifier, `mypy --strict` output in the hand-back, and that the reproduction is still red (it must be, until WP03).

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
