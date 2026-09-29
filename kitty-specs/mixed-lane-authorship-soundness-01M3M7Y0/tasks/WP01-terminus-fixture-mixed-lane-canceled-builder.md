---
work_package_id: WP01
title: Terminus fixture tidy + committed-then-canceled mixed-lane builder
dependencies: []
requirement_refs:
- FR-007
- FR-008
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T15:37:38.207242+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: 'Phase 1 - Enablers (tidy-first, #5047)'
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_fixture_mixed_lane_canceled.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/terminus/conftest.py
- tests/terminus/test_fixture_mixed_lane_canceled.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Terminus fixture tidy + committed-then-canceled mixed-lane builder

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission mixed-lane-authorship-soundness-01M3M7Y0`). All feedback items are your TODO list.

---

## Objectives & Success Criteria

1. **Tidy first (Standing Order #2, behaviour-preserving):** the three builders `build_coord_mission` (`tests/terminus/conftest.py:314`), `build_coord_mission_mixed_lane` (`:442`) and `build_coord_mission_shared_file` (`:550`) repeat the same repo-init → README/init commit → meta/manifest/WP files → coord-branch cut → per-lane branch cut → `CoordinationWorkspace.resolve` scaffolding. Extract that into small private helpers. **No existing builder's observable output may change** (same branches, same files, same events, same commit graph shape).
2. **Fixture hygiene:** the init commit carries a `.gitignore` containing `.worktrees/` (merged with any caller-supplied `.gitignore` in `extra_base_files` — `tests/terminus/test_resume_phantom_only.py:82` passes one); prefer explicit-path `git add` (today every builder `git add .` runs before `CoordinationWorkspace.resolve`, so none stages the coord worktree yet — the gitlink hazard only bites a POST-build `git add .`, which then trips the dirty-target refusal raised in `src/specify_cli/git/ref_advance.py` ~L130-150). `_event(...)` (`:292`) **and** `_cancel_event(...)` (`:414`) gain an optional keyword `policy_metadata: dict[str, object] | None = None`, emitted only when provided (existing call sites unchanged byte-for-byte). `run_terminus(mission, args, *, env: Mapping[str, str] | None = None)` (`:819`, a `subprocess.run` of the CLI) gains an optional env overlay for WP06.
3. **New builder** `build_coord_mission_mixed_lane_canceled(...)` (see T003) — one call, no post-build mutation, default squash and merge both reach the reconciliation verdict (SC-005, FR-007).
4. **Correct the record (FR-008):** a test shows (a) a post-build lane `update-ref` still consolidates, (b) removing the coord worktree dir yields the "unmaterialized" abort. Docstrings retract the #5047 claims.

## Context & Constraints

- Spec: `kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/spec.md` (FR-007, FR-008, SC-005, Domain Language). Plan: `plan.md` Design D-5. Research: `research.md` R-6 (fixture probe findings).
- A prototype (orchestrator scratchpad; you may not be able to read it) proved the shape: one `ExecutionLane(lane_id="lane-a", wp_ids=("WP01","WP02"), write_scope=(...both paths...))`; WP01 gets `_approve_events`; WP02 gets `planned→claimed→in_progress` then `_cancel_event(mission, "WP02", from_lane="in_progress")`; on the lane branch commit WP01's file, then WP02's file(s), optionally a superseding WP01 commit, each `git add <explicit path>`; only then resolve the coord workspace. Under the default squash it reached the verdict: exit 0, `squash content attribution verified`, WP02's file on main (the #5046 bug).
- The prototype observed the #5046 bug live: default squash, exit 0, canceled `src/pkg/wp02.py` present on main. That is expected today; WP02 turns it into red-first tests. **Do not write the #5046 assertions here** — this WP only builds the fixture.
- Do NOT touch `tests/integration/**` or any `src/` file (C-004). Do not run whole directories (C-005).
- Terminology: Mission, WP, execution lane — never "feature" in new prose.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-5046-mixed-lane-authorship`
- **Merge target branch**: `issue-5046-mixed-lane-authorship`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude` and work only in the resolved workspace.

## Subtasks & Detailed Guidance

### Subtask T001 – Extract shared scaffolding (behaviour-preserving)

- **Purpose**: stop the fourth copy of ~100 lines of builder boilerplate before it is written.
- **Steps**:
  1. Before editing, record the baseline: run each terminus test that imports one of the three builders (grep: `grep -l "build_coord_mission" tests/terminus/test_*.py`) — at least `test_repro_5018.py`, `test_repro_5022.py` and one `build_coord_mission_shared_file` user. They are slow (~1–3 min each); run them file by file, not the directory.
  2. Extract e.g. `_init_fixture_repo(tmp_path, *, mid8, slug, target_branch) -> CoordMission` (repo init, git config, README + `.gitignore` init commit, `CoordMission` construction) and `_cut_lane_branch(mission, lane_id, commits: Sequence[Callable[[Path], None]] | ...)` / `_finish_coord_mission(mission) -> CoordMission` (coord branch cut + `CoordinationWorkspace.resolve`). Pick names matching the file's idiom.
  3. Rewrite the three builders on top of the helpers.
  4. Re-run the same tests; they must pass unchanged.
- **Files**: `tests/terminus/conftest.py`.
- **Notes**: if a builder's order of operations differs in a way the helper cannot express without a behaviour change, keep that step inline — preserving behaviour wins over maximal dedup.

### Subtask T002 – Fixture hygiene + `_event` policy_metadata

- **Steps**:
  1. Add `.worktrees/` to the init commit's `.gitignore` in the shared init helper, **merging** with an `extra_base_files[".gitignore"]` if given. Ignoring `.worktrees/` changes `git status --porcelain` output for every builder: re-run `tests/terminus/test_resume_phantom_only.py`, every other `tests/terminus/test_resume_*.py`, `test_repro_4997.py` and `test_merge_noop_adjudication.py` file by file and record results.
  2. Replace any `git add .` / `git add -A` in the builders with explicit paths.
  3. `_event(mission, wp_id, from_lane, to_lane, *, policy_metadata=None)` and `_cancel_event(..., from_lane=..., policy_metadata=None)` — add the key `"policy_metadata"` to the dict **only** when not `None`.
  4. `run_terminus(..., env=None)`: when given, overlay onto the environment the helper builds today.
- **Validation**: existing tests unchanged; a tiny test that `_event(..., policy_metadata={"lane_head": "a"*40})` round-trips through `specify_cli.status.read_events` (write a one-line jsonl in `tmp_path`).

### Subtask T003 – `build_coord_mission_mixed_lane_canceled`

- **Purpose**: one call builds the #5046 shapes (FR-007, SC-005).
- **Signature (suggested)**:
  ```python
  def build_coord_mission_mixed_lane_canceled(
      tmp_path: Path,
      *,
      canceled_changes: Sequence[PlantedChange],          # WP02's commits (add/modify/delete)
      survivor_after: Sequence[PlantedChange] = (),        # WP01 commits AFTER WP02 (supersede / undo)
      survivor_before: Sequence[PlantedChange] = (),       # WP01 commits BEFORE WP02 (to set up survivor-undone shapes)
      lane_sync_merge_in_canceled_session: bool = False,   # a merge commit on the lane inside WP02's window
      stamp_attribution: bool = True,                      # write policy_metadata.lane_head on the events
      canceled_entered_implementation: bool = True,        # False → cancel from planned, no commits
      canceled_lifecycle: Literal["synthetic", "none"] = "synthetic",  # "none": WP02 left `planned`, no WP02 events/commits (WP06 drives them through the production shells)
      wp02_final: Literal["canceled", "approved"] = "canceled",  # "approved": all-approved lane (SC-004 legacy twin)
      mid8: str = "01M5046A",
  ) -> CoordMission
  ```
  with a small frozen dataclass `PlantedChange(path: str, content: str | None)` (`None` = delete).
- **Shape**: one execution lane `lane-a` with `wp_ids=("WP01", "WP02")` and a write scope covering the planted paths; WP01 goes through `_approve_events`; WP02 goes `planned→claimed→in_progress` (stamped with the lane head at that moment when `stamp_attribution`), its commits are planted on the lane branch, then `in_progress→canceled` via `_cancel_event(..., from_lane="in_progress")` stamped with the lane head after its last commit. Survivor-after commits go after the cancel stamp but WP01 must then be inside an implementation window for them (emit a WP01 rework window `approved→in_progress→for_review→in_review→approved` stamped at open/close) — otherwise the commit belongs to no window (that is a legitimate "commit outside any window" shape; keep it available but not the default).
- **Stamping**: `lane_head` must be the real `git rev-parse refs/heads/<lane branch>` at the moment the event is appended (planting order: event → commits → event). When `stamp_attribution=False`, omit the key everywhere (legacy / REFUSE shape).
- **Lane-sync merge**: when requested, inside WP02's window create a side commit on a temp branch touching a bookkeeping path (e.g. the mission's `status.events.jsonl` copy is NOT safe — use a harmless non-content path under the mission's planning dir) and `git merge --no-ff` it into the lane, so the spine has a merge commit inside the canceled window.
- **Resolve last**: call the shared finish helper (`CoordinationWorkspace.resolve`) only after all planting.
- **Event surface**: document in the docstring which `status.events.jsonl` the builder writes (primary feature dir vs the coord worktree after resolve) and which one `spec-kitty consolidate` reads for the claim (`build_approved_wp_set(..., feature_dir=run.feature_dir, ...)`), so WP06 can append events to the right surface after the build.
- **Docstring**: explain each parameter in terms of the spec's scenarios (US1/US2/US3/SC-007).

### Subtask T004 – Fixture behaviour test (FR-008) [P]

- **File**: `tests/terminus/test_fixture_mixed_lane_canceled.py` (new).
- **Tests** (mark as the existing terminus tests are marked; check `pytest.ini` markers used in `test_repro_5018.py`):
  1. `test_post_build_lane_update_ref_still_consolidates`: build via the new builder (default args), plant one extra commit on the lane with `commit-tree` + CAS `update-ref`, run `run_terminus(mission, [...])` with the default strategy; assert the run reached a reconciliation verdict (exit code and output contain the verdict line, NOT "unmaterialized"). Today it exits 0 (the #5046 bug) — assert only "reached the verdict", not the verdict itself, so this test stays valid after WP05.
  2. `test_missing_coord_worktree_dir_is_the_unmaterialized_trigger`: build, `git worktree remove --force <coord worktree>`, run; assert exit ≠ 0 and the whitespace-collapsed output contains `unmaterialized` (observed text: `Coordination branch '<branch>' ... is unmaterialized`; confirm the exact phrase on your run and pin a stable substring).
- Keep it to these two consolidations (runtime).

### Subtask T005 – Correct the recorded limitation

- Update `build_coord_mission_shared_file`'s docstring (it currently repeats "cannot tolerate a lane-branch mutation after construction", conftest ~L565-570) and the mixed-lane builder docstrings: state the observed truth (post-build ref/worktree mutation is fine; the unmaterialized abort needs a missing coord worktree dir; never `git add .` at the fixture root), citing the T004 test.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_fixture_mixed_lane_canceled.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5018.py tests/terminus/test_repro_5022.py -q
# plus every other tests/terminus/test_*.py importing build_coord_mission_shared_file / build_coord_mission, file by file
uv run --frozen ruff check tests/terminus/ && uv run --frozen ruff format --check tests/terminus/
uv run --frozen mypy tests/terminus/conftest.py   # if the repo's mypy config covers tests; otherwise note it
```
In a lane worktree always use `uv run` (or the worktree's own interpreter) so the lane's `src` is imported.

## Risks & Mitigations

- Hidden coupling to the exact init-commit tree (T002's `.gitignore`): grep first; if a test depends on it, keep `.gitignore` out of that builder and note why.
- Slow runs: never run `tests/terminus/` as a directory.

## Review Guidance

- Diff the three rewritten builders' behaviour: reviewer re-runs the baseline terminus tests.
- Confirm `_event` output is byte-identical for existing call sites (no `policy_metadata` key unless passed).
- Confirm the new builder plants before resolve and has no post-build mutation.
- Confirm T004 test 1 asserts "reached a verdict", not PASS.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
