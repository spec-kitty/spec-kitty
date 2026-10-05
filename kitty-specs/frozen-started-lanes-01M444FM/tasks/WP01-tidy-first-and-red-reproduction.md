---
work_package_id: WP01
title: 'Tidy-first enablers and the red #5573 reproduction'
dependencies: []
requirement_refs:
- C-001
- C-007
- FR-001
- FR-002
- FR-005
- FR-006
- FR-011
- SC-001
planning_base_branch: issue-5573-frozen-started-lanes
merge_target_branch: issue-5573-frozen-started-lanes
branch_strategy: Planning artifacts for this mission were generated on issue-5573-frozen-started-lanes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5573-frozen-started-lanes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-frozen-started-lanes-01M444FM
base_commit: 56c3ef9b8eb7b0f0aaca0ca85fa5ca0451ef57f2
created_at: '2026-10-04T19:40:10.549996+00:00'
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/specify_cli/cli/commands/agent/finalize_runner.py
- tests/specify_cli/cli/commands/agent/test_resolve_status_read_dir.py
- tests/integration/test_refinalize_keeps_started_lanes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
- tests/specify_cli/cli/commands/agent/finalize_runner.py
- tests/specify_cli/cli/commands/agent/test_resolve_status_read_dir.py
- tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py
- tests/specify_cli/cli/commands/agent/test_issue_3311_finalize_rewrites_active_lanes.py
- tests/integration/test_refinalize_keeps_started_lanes.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Tidy-first enablers and the red #5573 reproduction

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's
`task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP01 --agent claude`

## Post-tasks squad folds (binding — these override any conflicting text below)

- **Entry point:** use the `mission_app` idiom (corrected in T004 step 2), not the root app.
- **Status seeding:** `claimed → in_progress` needs `workspace_context=`; a reset to planned needs `reason=`
  (`src/specify_cli/status/wp_state.py:~341,~396`).
- **Amendments go through `wps.yaml`.** When the mission dir has `wps.yaml`, it is the source of dependencies and
  `owned_files`, and `tasks.md` is regenerated from it (`mission_finalize_validation.py:~279`). If your fixture
  creates `wps.yaml`, amend there. Otherwise amend the WP frontmatter and the `tasks.md` `**Dependencies**` line, and
  assert that the re-finalize actually saw the amendment: the collapse report contains `write_scope_overlap`.
- **Make "refuse before any write" non-fakeable** (T004 refusal test): the amendment also adds a new WP03, so a late
  refusal would leave a seed event (byte-identity fails). Include the non-colliding positive control.
- **Determinism note:** sort anything you compare.

## Objective

Land the behaviour-preserving enablers that make the #5573 fix testable (tidy-first, DIRECTIVE_025). Then commit a
**failing** end-to-end reproduction of #5573 through the real `agent mission finalize-tasks` entry point (charter
Standing Order 4, C-001), before any fix commit exists.

## Context

- **Spec:** `kitty-specs/frozen-started-lanes-01M444FM/spec.md`, US1 and US2.
- **Plan:** `plan.md`, IC-01.
- **Grounding:** `research/code-grounding.md` §1 (live repro) and §5 (why the suite missed it).
- **The defect.** WP02 is `in_progress` with commits on lane-b. Planned WP01 is amended to also own WP02's file and
  depend on it. `finalize-tasks` then exits 0 and writes `lanes.json` with a single lane **lane-a** holding [WP02, WP01].
  The next allocation of WP02 raises `LaneWorkTipUnknownError`.
- **Why it escaped.** `test_finalize_provenance_guard.py::test_execution_begun_path_does_not_write_status_json`
  (~L300-354) already drives this exact scenario but asserts nothing about lanes. Both `_run_finalize` helpers swallow
  `typer.Exit`, so a refusal and a success look the same.
- **Dependents.** WP03 (finalize wiring) depends on this WP. It turns the red tests green without editing them, and
  reuses `_resolve_status_read_dir` from T001.
- **Commit order (strict):**
  1. T001 commit (pure move);
  2. T002 commit (test helper, behaviour-preserving);
  3. **one red commit** with T003 + T004 (the failing assertions and the failing e2e test).

  Do not fix product code in this WP.

### Subtask T001: Extract `_resolve_status_read_dir` from `_execution_has_begun` (pure move)

**Purpose**: WP03 needs the coordination-aware status read-dir recipe without `_execution_has_begun`'s fail-open
policy. Extract it so there is one recipe (single canonical authority) rather than a copy.

**Steps**:
1. In `src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py`, add
   `_resolve_status_read_dir(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Path`.
   Its body is exactly today's surface-resolution block from `_execution_has_begun` (~L76-94): the
   `placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)` branch when `owned`, otherwise
   `resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir`.
   - It **raises** the underlying errors (`FileNotFoundError`, `ValueError`, `StatusReadPathNotFound`,
     `CoordinationBranchDeleted`); it does not swallow them.
   - Document that callers own the failure policy.
2. Rewrite `_execution_has_begun` to call it inside the existing `try/except` and return `False` on those same
   exceptions. The behaviour is byte-identical.
3. Keep the lazy imports inside functions (the module's existing idiom). Do not change `__all__` or re-exports unless
   the module already lists private helpers; if `mission_finalize.py` re-exports planning-pin names, note that WP03
   adds the re-export (it owns that file).
4. Add `tests/specify_cli/cli/commands/agent/test_resolve_status_read_dir.py`, marked `unit` and `fast`. Use
   monkeypatched resolvers to cover:
   - the `owned` branch calls `placement_seam`;
   - the non-owned branch returns `resolve_status_surface_with_anchor(...).read_dir`;
   - resolver errors propagate;
   - `_execution_has_begun` still returns `False` when the resolver raises.

**Files**: `mission_finalize_planning_pin.py` (~+25/−15 lines); the new test file (~60 lines).

**Validation**:
- `pytest tests/specify_cli/cli/commands/agent/test_resolve_status_read_dir.py tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py tests/architectural/test_finalize_refresh_pin_authority.py -q`
  is green;
- `mypy` and `ruff` are clean on the touched files.

### Subtask T002: Shared finalize runner that records the exit code (boy-scout, behaviour-preserving)

**Purpose**: the two `_run_finalize` helpers (`test_finalize_provenance_guard.py:~72`,
`test_issue_3311_finalize_rewrites_active_lanes.py:~71`) are verbatim duplicates that swallow the exit code. Extract one
helper that records it, so later assertions can tell a refusal from a success.

**Steps**:
1. Create `tests/specify_cli/cli/commands/agent/finalize_runner.py` (a plain module, not a test file) exposing
   `run_finalize(mission_slug: str, patches: Mapping[str, object], *, validate_only: bool = False) -> int | None`.
   - It starts and stops the `unittest.mock.patch` objects exactly as today and calls
     `finalize_tasks(feature=..., json_output=True, validate_only=...)`.
   - It returns `0` on normal return, `exc.exit_code` for `typer.Exit`, and `int(exc.code or 0)` for `SystemExit`.
   - Mirror the `_run_real_finalize` idiom in `test_finalize_tasks_commit_surface.py:~237-282`.
2. Replace both local `_run_finalize` definitions with imports of `run_finalize`. Existing call sites ignore the return
   value, so behaviour is unchanged.
3. Run both test files before and after; the pass counts must be identical.

**Files**: the new helper (~40 lines); two test files (−~30 lines total).

**Validation**: both test files pass, with the same counts as before the change.

### Subtask T003: Make the vacuous lane assertions real (red, boy-scout)

**Purpose**: turn the existing harness that already reproduces #5573 into a real guard (grounding §5, test-suite
lens). This is part of the red commit.

**Steps**:
1. `test_finalize_provenance_guard.py::test_execution_begun_path_does_not_write_status_json`:
   - capture `read_lanes_json(feature_dir)` **before** the execution-begun finalize call;
   - after the call, assert that WP02's lane id is unchanged
     (`after.lane_for_wp("WP02").lane_id == before.lane_for_wp("WP02").lane_id`);
   - assert that `run_finalize` returned `0`.

   Keep the status-hash assertions. This assertion is expected to **fail** on the base (WP02 moves to lane-a).
2. `test_issue_3311_finalize_rewrites_active_lanes.py::test_ownership_only_amendment_preserves_established_lanes_and_provenance`:
   - the test name promises lane preservation, so add a lane-identity assertion for the started WP;
   - seed the WP that **loses** the overlap tie (the one on the higher-sorting lane, i.e. WP02) as started, so the
     assertion cannot pass by luck;
   - if the fixture cannot express this without a large rewrite, rename the test to what it asserts and record the
     choice in the commit message;
   - correct the module docstring's scope note (~L17-20) that says "topology collapse / lane renumber does NOT
     reproduce": #5573 disproves it. Cite #5573.
3. Do not touch other tests in these files beyond the T002 helper swap.

**Validation**: both modified tests fail on the base for the lane reason (paste the failure excerpt into the commit
message body); everything else in the files still passes.

### Subtask T004: Red end-to-end reproduction through `agent mission finalize-tasks`

**Purpose**: pin #5573 exactly as a user hits it (US1 AS1–AS3, US2 AS1) through the pre-existing CLI entry point, with
real git, real status events and a real allocated lane worktree.

**Steps**:
1. Create `tests/integration/test_refinalize_keeps_started_lanes.py`, marked `pytest.mark.integration` and
   `pytest.mark.git_repo`.
2. **Fixture** (adapt the issue's reproducer; see the `<details>` block in #5573 and
   `research/code-grounding.md` §1):
   - `git init -b main` in `tmp_path`, user config, `.gitignore` with `.worktrees/` and `.kittify/runtime/`, files
     `a.py` and `b.py`, first commit.
   - `make_mission(repo, "lane-preservation", target_branch="main", topology=MissionTopology.LANES)` from
     `tests._factories`.
   - Write `spec.md` (FR-001, FR-002), `plan.md`, a `tasks.md` with two WP sections, and WP01/WP02 frontmatter via
     `specify_cli.frontmatter.write_frontmatter`:
     `owned_files` [a.py] / [b.py], `authoritative_surface`, `execution_mode: code_change`, `requirement_refs`,
     `subtasks`, `dependencies: []`. Commit.
   - Drive finalize through the **`agent mission finalize-tasks` Typer command in-process**, using the per-command
     `mission_app` idiom in `tests/integration/test_owned_lifecycle_acceptance_e2e.py:~349`:
     `CliRunner().invoke(mission_app, ["finalize-tasks", "--mission", slug, "--json"])`.
     - Do not use the root app. `[project.scripts]` points to `specify_cli:main` (a function), and the root callback
       runs a schema gate that can block in a tmp repo.
     - `chdir` to the repo (monkeypatch).
   - Assert the first finalize gives lane-a=[WP01], lane-b=[WP02].
3. **Start a WP**:
   - `wt, branch = allocate_lane_worktree(repo, slug, "WP02", manifest)` from `specify_cli.lanes.worktree_allocator`
     (it returns `(path, branch)`);
   - commit `b = 42` in that worktree;
   - `emit_status_transition(feature_dir, slug, "WP02", "claimed", "test")`, then `"in_progress"` **with
     `workspace_context=...`** (see `src/specify_cli/status/wp_state.py:~341` for what it requires; without it the
     transition refuses and the test goes red on the harness, not on the defect);
   - **assert** that the seeded `in_progress` event exists in `status.events.jsonl` before amending.
4. **Amend** WP01: `owned_files: [a.py, b.py]`, `dependencies: [WP02]`, and `**Dependencies**: WP02` under its
   `tasks.md` heading. Commit. Re-run finalize-tasks via the CLI.
5. **Tests** (each its own function; share the fixture via helpers, keeping each test's behaviour explicit):
   - `test_started_wp_keeps_its_lane_when_a_planned_wp_joins` (US1 AS1, SC-001):
     - exit 0;
     - exactly one code lane, `lane-b`, with `wp_ids == ("WP02", "WP01")`;
     - `allocate_lane_worktree(...)` for WP02 returns the original lane-b worktree path, and `b.py` contains `b = 42`.
   - `test_claimed_only_wp_keeps_its_lane` (US1 AS2): same as above, with WP02 only `claimed` and no commit.
   - `test_lane_follows_the_started_wp_not_lane_id_order` (US1 AS3, positive control): WP01 started on lane-a, WP02
     amended to overlap. The merged lane is lane-a. This passes on the base too; keep it as the same-fixture control.
   - `test_two_started_lanes_forced_together_refuse_before_writing` (US2 AS1, FR-005/FR-006, SC-003):
     - both WPs started (WP01 on lane-a, WP02 on lane-b, each allocated), then an overlap amendment;
     - assert exit code 1 and a JSON payload with `error_code == "LANE_MEMBERSHIP_FROZEN"` and
       `reason == "started_lanes_collapsed"`;
     - assert a conflict naming both WPs and `["lane-a", "lane-b"]`, and a non-empty `next_step`;
     - assert `lanes.json`, `status.events.jsonl`, `tasks.md`, `meta.json`, `wps.yaml` (if present) and every WP file
       are byte-identical to before the run (snapshot bytes), and that no new commit was made (`git rev-parse HEAD`
       unchanged);
     - the amendment **also adds a new planned WP03** (its own file `c.py`), so that a late refusal (one raised after
       finalize's status seeding) would write a seed event for WP03 and fail the byte-identity check. Add a
       same-fixture positive control: the same WP03 addition **without** the collision succeeds and seeds WP03.
6. Parse the JSON robustly: the CLI may print one JSON object; reuse an existing helper if one exists (grep
   `json.loads(result.stdout` under tests/integration).
7. Expected on the base: the first, second and fourth tests **fail** (lane moved / exit 0); the third passes. Record
   the failure excerpts in the red commit message.

**Files**: the new test file (~250-300 lines).

**Validation**: red on the base for the right reasons (not harness errors); the whole file runs in < 30 s warm
(NFR-004).

## Definition of Done

- T001 and T002 are behaviour-preserving, each in its own commit; the touched test files pass with unchanged counts.
- One red commit contains T003 + T004, whose failures are the #5573 lane move or the missing refusal, with the
  excerpts in the commit message.
- `ruff check`, `ruff format --check --force-exclude <files>` and `mypy` are clean on the changed files; no new
  suppressions.
- Each subtask is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.

## Risks

- **Harness drift:** `make_mission` defaults to `SINGLE_BRANCH`; pass `topology=MissionTopology.LANES` explicitly.
- **In-process CLI state:** the conftest isolates HOME/XDG; make sure `chdir` and the env are restored (monkeypatch).
- **False red:** confirm the red failures are lane assertions, not import or fixture errors.

## Reviewer Guidance

- Verify T001/T002 are pure (a diff read plus unchanged test counts).
- Verify the red tests go through the real `finalize-tasks` entry point, not `compute_lanes`.
- Verify the refusal test checks byte-identity of every listed file and that HEAD is unchanged.
- Verify the positive control (US1 AS3) exists, so the suite is not satisfiable by "always refuse".
