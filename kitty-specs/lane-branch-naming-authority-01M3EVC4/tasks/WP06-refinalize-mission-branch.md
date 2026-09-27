---
work_package_id: WP06
title: Re-finalize preserves the recorded Mission branch
dependencies: []
requirement_refs:
- FR-010
- FR-011
- FR-012
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 1 - Mission branch stability (wave 1)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/compute_and_persist.py
- src/specify_cli/status/aggregate.py
- tests/lanes/test_refinalize_mission_branch.py
authoritative_surface: src/specify_cli/lanes/compute_and_persist.py
create_intent:
- tests/lanes/test_refinalize_mission_branch.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP06 – Re-finalize preserves the recorded Mission branch

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
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

The spec's post-spec audit found that the **Mission branch** recorded in `lanes.json` drifts the same way lane names do:

1. An operator backfills a legacy Mission's identity (`spec-kitty migrate backfill-identity`).
2. The operator re-runs `finalize-tasks`.
3. `compute_lanes` recomputes `mission_branch` *with* the identity, for example `kitty/mission-057-foo` → `kitty/mission-foo-<mid8>`.
4. `allocate_lane_worktree` → `_ensure_mission_branch` then **creates** that phantom branch off the target, and later lanes fork from an empty Mission branch (research Part A §4).

Success means:

1. **FR-011 / PD-6 / PD-13.** `lanes/compute_and_persist.py::compute_and_write_lanes` keeps `previous_lanes.mission_branch` when a prior manifest exists. The first-time finalize is unchanged: the manifest defines the Mission branch that creation later creates (US3 AS1 + AS2, SC-007).
2. **PD-6 / ADJ-5.** `status/aggregate.py` (`MissionStatus.save`, the `destination_ref` composition) prefers the recorded manifest `mission_branch` before recomposing via `mission_branch_name_required`. When it must recompose from an invalid identity (shorter than 8 characters → `_mid8` `ValueError`), it raises a **typed** refusal (`BranchIdentityUnresolved`) instead of crashing.
3. **FR-010 re-verification.** Lane ids stay stable across re-finalize, and a fresh lane prefers an existing `origin/<lane>`. `tests/lanes/test_lane_identity.py` stays green, **unedited** (US5 AS2).
4. `compute_lanes` (CC34, behind a `ruff.toml` per-file ignore) is **not edited** (plan Complexity Tracking).

## Context & Constraints

- **Spec**:
  - US3 (AS1, AS2) and US5 AS2.
  - FR-010, FR-011 and FR-012.
  - SC-007.
  - Assumptions: backfill does not rewrite `lanes.json`; the slug is stable across backfill.
- **Plan**: PD-6 and PD-13 (preserve-only; the first finalize defines the branch), plus Complexity Tracking (do not edit `compute_lanes`).
- **Research**:
  - Part A §4 is the FR-011 analysis. The single writer is `compute_and_write_lanes`; the creator is `_ensure_mission_branch`.
  - ADJ-5 folds `status/aggregate.py`.
- **Data model**: `LanesManifest.mission_branch` is "preserved across re-finalize: `previous.mission_branch` wins over the recomputed value".
- **Constraints**:
  - C-002: no schema change.
  - C-004: no probing. Never ask git which Mission branch exists; prefer the recorded value.
- **Out of scope** (follow-up): the `migration/mission_state.py` rebuild with no prior manifest.

**Implementation command**: `spec-kitty agent action implement WP06 --agent <name>`. The dependency list is empty.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T020 – Red-first re-finalize test

- **Purpose**: Reproduce US3 AS1 through the pre-existing entry point: `compute_and_write_lanes(planning_dir=..., repo_root=..., mission_slug=..., wp_manifests=..., wp_dependencies=..., wp_frontmatters=..., wp_bodies=..., target_branch=..., planning_commit_sha=..., mission_id=...)`. Check the exact signature in the module. If the CLI `spec-kitty agent mission finalize-tasks` path is cheap to drive in a tmp repo, add one CLI-level test as well; the function-level test is mandatory.
- **File**: `tests/lanes/test_refinalize_mission_branch.py` (new).
- **Steps**:
  1. Tmp repo with `kitty-specs/057-foo/`, containing `meta.json` **without** `mission_id` (legacy), two WP prompt files with ownership, and real owned paths so glob validation passes.
  2. First finalize with `mission_id=None`. Record `manifest.mission_branch` (expected `kitty/mission-057-foo`; assert that value).
  3. Backfill: write a valid ULID into `meta.json`. Prefer the canonical backfill helper (`migration/backfill_identity.py::backfill_mission`) over hand-writing.
  4. Re-finalize with `mission_id=<the ULID>`.
  5. Assert that `lanes.json` `mission_branch` is **byte-identical** to step 2 (red on HEAD: it becomes `kitty/mission-foo-<mid8>`).
  6. Second test (US3 AS2): a first-time finalize of a modern Mission, with its identity present from the start, produces the same `mission_branch` as today. Compute the expected value by calling the current finalize at the start of the test run is **not** allowed, since that is the code under test. Use a literal golden of today's output (for example `kitty/mission-foo-01KV6510` for slug `foo-01KV6510`).
  7. Third test: after the re-finalize, `allocate_lane_worktree` creates lanes whose parent is the **recorded** Mission branch. Assert that `git rev-parse --verify refs/heads/kitty/mission-057-foo` succeeds, and that no `kitty/mission-foo-<mid8>` branch was created. The absence check is a literal assertion, not a probe used to choose a name.
- **Validation**: red run recorded (test 1 and test 3 fail on HEAD).

### Subtask T021 – `_preserved_mission_branch` in `compute_and_write_lanes`

- **File**: `src/specify_cli/lanes/compute_and_persist.py`.
- **Steps**:
  1. Add a pure helper:
     ```python
     def _preserved_mission_branch(previous: LanesManifest | None, computed: str) -> str:
         """FR-011: a re-finalize keeps the Mission branch the first finalize recorded.

         The first finalize defines the Mission branch that lane creation later
         creates from the manifest (``_ensure_mission_branch``); recomputing it from a
         since-backfilled identity would name a branch that was never created.
         """
         if previous is not None and previous.mission_branch:
             return previous.mission_branch
         return computed
     ```
  2. In `compute_and_write_lanes`, right after `lanes_manifest = compute_lanes(...)` and next to the existing `lanes_manifest.planning_commit_sha = planning_commit_sha` post-assignment, set `lanes_manifest.mission_branch = _preserved_mission_branch(previous_lanes, lanes_manifest.mission_branch)`. Check whether `LanesManifest` is frozen (`dataclasses.replace` if so).
  3. Do **not** touch `compute_lanes`.
  4. Unit-test the helper directly: previous None; previous with an empty `mission_branch`; previous with a value.
- **Validation**:
  - [ ] T020 is green.
  - [ ] `compute_and_write_lanes` stays ≤ CC 4.
  - [ ] `tests/lanes/test_compute*.py` and `tests/lanes/test_persistence.py` are green, unedited.

### Subtask T022 – `status/aggregate.py` destination ref prefers the recorded Mission branch

- **File**: `src/specify_cli/status/aggregate.py`, `MissionStatus.save` (HEAD ≈L751): `destination_ref = self.coordination_branch or mission_branch_name_required(self.mission_slug, self.mission_id)`.
- **Steps**:
  1. Read the recorded `mission_branch` from the Mission's `lanes.json` through the canonical reader. Use `read_lanes_json` on the **LANE_STATE** read dir via `placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE)`, the same pattern as `lanes/lifecycle_sync.py`. If `MissionStatus` already holds a resolved primary/planning dir, reuse it.
  2. The order becomes: `coordination_branch` → recorded `mission_branch` → `mission_branch_name_required(...)`.
  3. Wrap the recomposition: catch `ValueError` from `_mid8` (an identity shorter than 8 characters) and raise `BranchIdentityUnresolved(self.mission_slug, next_step=…)` `from exc`, naming `spec-kitty doctor identity --json` / `spec-kitty migrate backfill-identity`. Keep the existing `MissionMetadataUnavailable` guard above it unchanged.
  4. If the logic grows `save` past CC 10, extract `_destination_ref(self) -> str`, and test it directly.
- **Tests** (in `tests/lanes/test_refinalize_mission_branch.py`, or a focused section of it):
  - A backfilled legacy Mission with no coordination branch and a recorded `mission_branch` returns the recorded value (red on HEAD: the phantom mid8 branch).
  - `mission_id="abc"` with no recorded branch raises `BranchIdentityUnresolved`, not `ValueError`.
  - A coordination Mission returns `coordination_branch`, as before.
  - Drive the pre-existing entry point: construct `MissionStatus` the way the existing tests in `tests/status/test_aggregate_surface_resolution.py` do, and exercise `save` or the extracted helper.
- **Note**: C-004 is satisfied: the recorded value is data, not an existence probe.

### Subtask T023 – FR-010 re-verification, quality gates and blast radius

- Run `tests/lanes/test_lane_identity.py` **unedited**. Those tests cover surviving lane ids after a WP removal, a fresh lane getting an unused id, and a preference for `origin/<lane>`. Record the counts.
- Run the Test Strategy commands and record commands plus counts in the Activity Log.

## Test Strategy

- **Red-first**: T020 tests 1 and 3 and the first T022 test fail on HEAD through `compute_and_write_lanes` and `MissionStatus.save` (or its extracted helper).
- **Real git**: tmp repos. Lanes are created via `allocate_lane_worktree` in test 3.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/lanes/test_refinalize_mission_branch.py tests/lanes/test_lane_identity.py -q
.venv/bin/python -m pytest tests/lanes/ tests/status/ -q
.venv/bin/python -m pytest $(grep -rl "compute_and_write_lanes\|compute_and_persist\|MissionStatus" tests --include=*.py | tr '\n' ' ') -q
make test-fast
```

- **NFR gates**:

```bash
.venv/bin/ruff check src/specify_cli/lanes/compute_and_persist.py src/specify_cli/status/aggregate.py tests/lanes/test_refinalize_mission_branch.py
.venv/bin/ruff check --select C901 src/specify_cli/lanes/compute_and_persist.py src/specify_cli/status/aggregate.py
.venv/bin/ruff format --check src/specify_cli/lanes/compute_and_persist.py src/specify_cli/status/aggregate.py tests/lanes/test_refinalize_mission_branch.py
.venv/bin/mypy src/specify_cli/lanes/compute_and_persist.py src/specify_cli/status/aggregate.py
```

## Definition of Done

- [ ] U1 (analysis finding): a Mission whose manifest identity is invalid (< 8 characters) must not surface a raw `ValueError` from the untouched `compute_lanes` (`lanes/compute.py`, which calls `mission_branch_name(..., mission_id=…)`) on first finalize or re-finalize. In `compute_and_write_lanes` catch that `ValueError` at the `compute_lanes` call and raise a typed, operator-legible refusal (reuse an existing lanes error type, e.g. `LaneComputationError`, naming the invalid identity and the remedy `spec-kitty migrate backfill-identity`); do not edit `compute_lanes`. Red-first test: finalize with a 7-character identity raises the typed error (HEAD: bare `ValueError`).

- [ ] NFR-004: diff coverage on this WP's changed lines ≥ 90% (e.g. `.venv/bin/python -m pytest <targeted tests> --cov=<touched modules> --cov-report=xml` then `diff-cover coverage.xml --compare-branch=<lane base> --fail-under=90`; record the number in the handoff note).

- [ ] Re-finalize keeps `mission_branch` byte-identical, and the first finalize is unchanged (SC-007).
- [ ] `MissionStatus.save` prefers the recorded branch and raises a typed refusal for an invalid identity.
- [ ] `compute_lanes` is untouched (`git diff` shows no change in `lanes/compute.py`).
- [ ] FR-010 tests are green, unedited.
- [ ] Gates are clean; `make test-fast` is green.

## Risks & Mitigations

- **`LanesManifest` immutability**: use `dataclasses.replace`.
- **Reading `lanes.json` inside `aggregate.py` could add an import-cycle risk or cold-import cost**: use a function-local import with a rationale, and run `tests/architectural/test_cold_import_status_boundary.py` if it exists.
- **A Mission whose manifest legitimately lacks `mission_branch`**: it falls through to the existing compose, so behaviour is unchanged.

## Review Guidance

- Confirm the preservation happens in `compute_and_write_lanes`, not in `compute_lanes`.
- Confirm the recorded-first order in `aggregate.py`, and the typed refusal.
- Confirm the golden in T020 test 2 is a literal, not computed by the code under test.
- Confirm mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
