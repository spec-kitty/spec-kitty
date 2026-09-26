---
work_package_id: WP04
title: Lifecycle probe removal, acceptance roots, recovery Mission-branch refusal
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-011
- FR-012
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Lane consumers (wave 1)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/lifecycle_sync.py
- src/specify_cli/lanes/recovery.py
- src/specify_cli/acceptance/__init__.py
- tests/integration/test_lane_lifecycle_sync.py
- tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py
- tests/lanes/test_lane_consumers_divergent.py
authoritative_surface: src/specify_cli/lanes/lifecycle_sync.py
create_intent:
- tests/lanes/test_lane_consumers_divergent.py
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

# Work Package Prompt: WP04 – Lifecycle probe removal, acceptance roots, recovery Mission-branch refusal

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

This WP clears the lanes-subsystem consumers that diverge today, or that carry a third naming strategy.

1. **FR-007: retire the dual-name probe.** `lanes/lifecycle_sync.py::_resolve_lane_branch` tests an identity-form candidate and then a slug-form candidate for existence, and finally falls back to the worktree's `HEAD`. That is forbidden probing (C-004) and a third naming strategy. Delete it, together with `_git_ref_exists`, which only the probe uses. `sync_lane_after_coordination_commit` obtains the path and branch from `predict_lane_worktree(repo_root, mission_slug, lane.lane_id)`.
2. **FR-006 / PD-8: acceptance source roots.** `acceptance/__init__.py::_approved_lane_source_roots` passes `mission_id=manifest.mission_id`, so for divergent shapes acceptance silently finds no lane source root. It must look at the **created** worktree.
3. **FR-006: route recovery worktree lookups through the authority.** `lanes/recovery.py` has three `_worktree_path(..., mission_id=None, lane_id=...)` sites. Route them through `predict_lane_worktree`, with byte-identical behaviour, so the file carries no `mission_id` naming keyword when WP07 removes the parameter.
4. **FR-011 / PD-13: recovery Mission-branch fallback.** `lanes/recovery.py::_resolve_mission_branch` already prefers the recorded `lanes.json` `mission_branch`. When that value is absent and it recomposes from `meta.json`, an identity shorter than 8 characters raises a raw `ValueError` from `_mid8`. Convert that into the typed `BranchIdentityUnresolved`, with the Mission-directory hint the function already adds for its own refusal.

## Context & Constraints

- **Spec**:
  - FR-006 (consumer list) and FR-007.
  - FR-011, the clause "refusing with a typed error rather than crashing when it must recompose from an invalid identity".
  - FR-012 and C-004.
  - Edge case "Manifest identity not a valid ULID … neither may raise" (lane naming).
- **Plan**: PD-1 (`predict_lane_worktree` is the placement decision), PD-8, PD-13, and the Parallel Work Analysis for WP04.
- **tasks.md deviation 2**: `worktree_dir_name` and `worktree_path` take `mission_id` as a **required** keyword at HEAD. You cannot drop the keyword before WP07's cutover. That is why this WP routes through `predict_lane_worktree`, which has no identity parameter, instead. The pure-drop files (`lanes/merge.py`, `lanes/implement_support.py`, `workspace/context.py`, …) belong to WP07.
- **tasks.md deviation 6**: the recovery Mission-branch fallback moved here from WP03, so `lanes/recovery.py` has one owner.
- **Research**:
  - Part A §3 "FR-007" and the "FR-006 — consumer re-routes" table.
  - Part A §4, the "Independent composers" bullet for `recovery.py:268`.
  - Complexity: `sync_lane_after_coordination_commit` is CC7 and `_approved_lane_source_roots` is CC7. Keep both ≤ 15, and preferably at or below their current scores.

**Implementation command**: `spec-kitty agent action implement WP04 --agent <name>`. The dependency list is empty.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first lifecycle-sync test on a divergent shape

- **Purpose**: Prove, through the pre-existing entry point `sync_lane_after_coordination_commit(*, repo_root, mission_slug, wp_id, coordination_branch)`, that the probe diverges. Take a lane created by the allocator whose worktree has been removed. Record an identity in `lanes.json` whose identity-form branch **also exists**; this reproduces the probe's first-candidate win. The sync then attaches the wrong branch.
- **File**: `tests/lanes/test_lane_consumers_divergent.py` (new).
- **Fixture**: a real tmp git repo.
  - Create the lane via `allocate_lane_worktree(...)`, which records the created `(path, branch)`.
  - Use a mismatched-mid8 or backfilled-legacy shape. Build it locally, following WP01's `tests/merge/_divergent_shapes.py` pattern. You cannot import WP01's module because WP04 runs in parallel. If you factor shared bits, keep them private to this test file.
  - To trigger the probe's wrong pick, create a decoy branch at the identity-form name with `git branch <decoy> <some commit>`. Take the decoy string from a **literal in the test**, never from calling the naming code with an identity. Then remove the lane worktree (`git worktree remove`).
- **Assertions**:
  - After sync, `git -C <lane worktree> rev-parse --abbrev-ref HEAD` equals the allocator-created branch (red on HEAD: the decoy is attached).
  - A second test: a worktree whose `HEAD` is detached or on another branch, with the created branch absent. Sync raises `LaneAutoRebaseSyncError` naming the created branch; it never falls back to `HEAD` (red on HEAD).
  - A third test, **invalid identity < 8 characters, no decoy**: `lanes.json` records `mission_id="abc"` (a literal), the lane is created by the allocator, and no decoy branch exists. On HEAD the probe's identity-form candidate calls the naming code with that identity and **crashes** (`ValueError` from `_mid8`: "mission_id must be at least 8 characters…"). After T008, sync attaches the allocator-created branch and never raises `ValueError`. Record the HEAD traceback as the red evidence.
- Mark with the markers used by `tests/integration/test_lane_lifecycle_sync.py` (for example `git_repo`).
- **Validation**: red run recorded in the Activity Log.

### Subtask T008 – Delete the probe; route through `predict_lane_worktree`

- **File**: `src/specify_cli/lanes/lifecycle_sync.py`.
- **Steps**:
  1. Delete `_resolve_lane_branch` and `_git_ref_exists`. Confirm no other references with `grep -rn "_resolve_lane_branch\|_git_ref_exists" src tests`. `tests/architectural/test_no_dead_symbols.py` may list them; if so, the removal shrinks that list.
  2. In `sync_lane_after_coordination_commit`, replace the `_worktree_path(..., mission_id=None, ...)` plus `_resolve_lane_branch(...)` pair with one call:
     ```python
     from specify_cli.lanes.worktree_allocator import predict_lane_worktree  # noqa: PLC0415 — function-local: worktree_allocator imports lanes.merge at module import; keep lifecycle_sync import-light
     worktree_path, lane_branch = predict_lane_worktree(repo_root, lanes_manifest.mission_slug, lane.lane_id)
     ```
     Use `lanes_manifest.mission_slug` (PD-2). It equals `mission_slug` for every real caller; assert that in a comment only if it is true.
     Before adding the `noqa`, check whether a module-level import is cycle-free. If it is, prefer it and drop the `noqa`; suppressions need justification.
  3. Remove the now-unused `lane_branch_name` / `_worktree_path` imports if nothing else uses them.
  4. Error path — **do NOT change it in this WP.** The `CorruptLanesError` branch builds `lane_worktree_path=repo_root / WORKTREES_DIRNAME / f"{mission_slug}-unknown"`. That line is a content-pinned carve-out in the existing gate `tests/architectural/test_no_worktree_name_guess.py` (`_ALLOWED_SITES_FILES` + `_NAME_COMPOSE_BASELINE_RAW_MATCHES = 5`). Changing it here would turn that gate's staleness guard RED in this lane, and the gate file is owned by WP11. WP11 removes the placeholder and shrinks the allow-list in one commit (tasks.md ownership table). Keep the line byte-identical, and make sure your edits above it do not change its enclosing function's qualname.
  5. If the worktree is missing and the created branch does not exist, `git worktree add` fails, and the existing `LaneAutoRebaseSyncError` path already reports it. Keep that path and make sure the message names `lane_branch`.
- **Validation**:
  - [ ] T007 is green.
  - [ ] `tests/integration/test_lane_lifecycle_sync.py` is green. Adjust only assertions that pinned the probe or HEAD fallback, and record why.
  - [ ] C901 for `sync_lane_after_coordination_commit` is ≤ 7.

### Subtask T009 – Acceptance lane source roots use the created worktree

- **Purpose**: US1 extends to acceptance: a divergent Mission's approved lane tree must count as candidate source (#4254 behaviour).
- **File**: `src/specify_cli/acceptance/__init__.py`, function `_approved_lane_source_roots(repo_root, feature_dir, lanes)`.
- **Red-first**:
  - In `tests/lanes/test_lane_consumers_divergent.py`, or in `tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py` if the pre-existing entry point is exercised there, build a divergent shape with an approved lane via the allocator.
  - Assert that `_approved_lane_source_roots(...)`, or the public acceptance entry point that consumes it, returns the created worktree.
  - Red on HEAD: it returns `()` because the identity-form path does not exist.
- **Fix**: replace `worktree_path(repo_root, manifest.mission_slug, mission_id=manifest.mission_id, lane_id=lane.lane_id)` with `predict_lane_worktree(repo_root, manifest.mission_slug, lane.lane_id)[0]`. Use a function-local import with a rationale if needed, and check `acceptance/__init__.py`'s import surface first. If `predict_lane_worktree` cannot be imported without a cycle, use `worktree_path(..., mission_id=None, ...)` and note the site in the Activity Log for WP07.
- **Migrate** `tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py`. Its fixture builds the lane root with `worktree_path(repo_root, _SLUG, mission_id=_MISSION_ID, lane_id="lane-a")` (≈L91). Move it to `predict_lane_worktree`, or to the allocator if the test needs a real worktree. The test's intent (build paths only in the approved lane satisfy acceptance) must still hold.
- **Validation**:
  - [ ] The divergent-shape acceptance test is red on HEAD and green after.
  - [ ] The #4254 tests are green.

### Subtask T010 – Route `lanes/recovery.py` worktree lookups through the authority

- **Purpose**: behaviour-preserving (FR-006). The three `_worktree_path(repo_root, mission_slug, mission_id=None, lane_id=…)` calls (HEAD ≈L398, ≈L696, ≈L718; anchors are the enclosing functions, including the one calling `_recover_lane_worktree`) must stop carrying the naming keyword that WP07 removes.
- **Steps**:
  1. Replace each with `predict_lane_worktree(repo_root, mission_slug, lane_id)[0]`. `recovery.py` already imports `_recover_lane_worktree` function-locally from `worktree_allocator`; follow that pattern.
  2. Where the site also needs the branch, take it from the same call instead of re-deriving it. Keep the existing `state.branch_name` where recovery deliberately uses the **parsed** branch of an existing ref (C-005 creation-site table: `_recover_lane_worktree` attach uses the parsed branch). Do not change which branch is attached.
  3. **Do not touch** the recovery enumeration `kitty/mission-{slug}*` (≈L136). It is spec-excluded, allow-listed, and a follow-up (prefix over-match).
- **Validation**:
  - [ ] `tests/lanes/test_implementation_recovery.py`, `tests/lanes/test_recovery_post_merge.py` and every test that greps `recovery` are green, unedited.
  - [ ] Alias-aware AST scan: 0 `mission_id` keywords in lane-naming calls in `recovery.py`.

### Subtask T011 – `_resolve_mission_branch` typed refusal on an invalid identity (PD-13)

- **File**: `src/specify_cli/lanes/recovery.py`, `_resolve_mission_branch(feature_dir, mission_slug)`.
- **Steps**:
  1. Keep the recorded-first behaviour: `_find_mission_branch(feature_dir)` wins.
  2. Around `mission_branch_name_required(mission_slug, _mission_id_from_meta(feature_dir))`, also catch `ValueError`. It is raised by `_mid8` for an identity shorter than 8 characters. Raise `BranchIdentityUnresolved(mission_slug, next_step=...)` `from exc`, with a next_step that names the invalid identity and the `meta.json` path, and suggests `spec-kitty doctor identity --json` / `spec-kitty migrate backfill-identity`. Keep the message style of the existing re-raise.
  3. Hoist the next_step suffix into a module constant if it appears ≥ 3 times (S1192).
- **Test** (new, in `tests/lanes/test_lane_consumers_divergent.py`): `meta.json` has `mission_id="abc"` and `lanes.json` is absent. `_resolve_mission_branch` raises `BranchIdentityUnresolved`, not `ValueError` (red on HEAD). Also check that a recorded `mission_branch` wins even when the identity is invalid.
- **Validation**: C901 ≤ 15 (the function is small).

### Subtask T012 – Tests, quality gates and blast radius

- Run the Test Strategy commands and record exact commands plus pass/fail counts in the Activity Log.
- Alias-aware AST scan over the owned files: 0 identity keywords on lane-naming calls.

## Test Strategy

- **Red-first**: T007, T009 and T011 fail on HEAD through their entry points (`sync_lane_after_coordination_commit`, `_approved_lane_source_roots` or its public caller, `_resolve_mission_branch`).
- **Real git**: tmp repos and real `git worktree`. Lanes come from `allocate_lane_worktree`. Decoy branches use test literals, never identity-composed calls.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/lanes/test_lane_consumers_divergent.py tests/integration/test_lane_lifecycle_sync.py tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py -q
.venv/bin/python -m pytest tests/lanes/ tests/specify_cli/lanes/ tests/specify_cli/acceptance/ -q
.venv/bin/python -m pytest $(grep -rl "lifecycle_sync\|lanes.recovery\|_approved_lane_source_roots" tests --include=*.py | tr '\n' ' ') -q
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_worktree_name_guess.py -q
make test-fast
```

- **NFR gates** (touched files):

```bash
.venv/bin/ruff check src/specify_cli/lanes/lifecycle_sync.py src/specify_cli/lanes/recovery.py src/specify_cli/acceptance/__init__.py tests/lanes/test_lane_consumers_divergent.py
.venv/bin/ruff check --select C901 src/specify_cli/lanes/lifecycle_sync.py src/specify_cli/lanes/recovery.py src/specify_cli/acceptance/__init__.py
.venv/bin/ruff format --check src/specify_cli/lanes/ src/specify_cli/acceptance/__init__.py tests/lanes/test_lane_consumers_divergent.py
.venv/bin/mypy src/specify_cli/lanes/lifecycle_sync.py src/specify_cli/lanes/recovery.py src/specify_cli/acceptance/__init__.py
```

- Diff coverage ≥ 90% (NFR-004). The deleted probe removes branches; the new typed-refusal branch needs its test (T011).

## Definition of Done

- [ ] `_resolve_lane_branch` and `_git_ref_exists` are deleted and there is no HEAD fallback. The `-unknown` error-path placeholder is intentionally left for WP11.
- [ ] Acceptance finds divergent-shape lane roots.
- [ ] `recovery.py` worktree lookups go through `predict_lane_worktree`. The enumeration is untouched.
- [ ] An invalid identity raises `BranchIdentityUnresolved` in `_resolve_mission_branch`.
- [ ] Red-first evidence is recorded, all gates are clean, and `make test-fast` is green (baseline reds classified).

## Risks & Mitigations

- **Import cycles** from `predict_lane_worktree`: use a function-local import with a rationale. As a last resort, pass `mission_id=None` and log the site for WP07.
- **Existing gate interaction**: `tests/architectural/test_no_worktree_name_guess.py` pins the `-unknown` placeholder by content. Leave it untouched, and run the gate to confirm it stays green.
- **Tests that pinned the probe's HEAD fallback**: that behaviour is the defect. Re-express those tests as the named failure.

## Review Guidance

- Verify no candidate-list or existence probing remains in `lifecycle_sync.py` (C-004).
- Verify the decoy branch in T007 is a test literal, not produced by naming code with an identity.
- Verify the recovery enumeration (`kitty/mission-{slug}*`) is unchanged.
- Verify the implementer ran mypy as well as pytest.

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
