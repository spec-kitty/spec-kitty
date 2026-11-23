---
work_package_id: WP01
title: setup-plan commits its lifecycle events on the coordination branch
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: issue-3933-lifecycle-event-placement
merge_target_branch: issue-3933-lifecycle-event-placement
branch_strategy: Planning artifacts for this mission were generated on issue-3933-lifecycle-event-placement. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3933-lifecycle-event-placement unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Behaviour
history:
- at: '2026-11-23T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/mission_setup_plan.py
create_intent:
- tests/coordination/test_setup_plan_coord_lifecycle_3933.py
- docs/changelog/unreleased/3933-setup-plan-coord-lifecycle.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- tests/coordination/test_setup_plan_coord_lifecycle_3933.py
- docs/changelog/unreleased/3933-setup-plan-coord-lifecycle.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3933'
---

# Work Package Prompt: WP01 – setup-plan commits its lifecycle events on the coordination branch

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission setup-plan-coord-lifecycle-commit-01M84SXJ`). Address all feedback before completion and record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

On a Mission whose coordination branch exists when setup-plan runs (created with an explicit `--topology coord` or `--topology lanes_with_coord`):

- **SC-001 / FR-002**: after `spec-kitty agent mission setup-plan --mission <h> --json`, the coordination branch holds a commit with `SpecifyCompleted`, `PlanStarted` and `PlanCompleted` for this Mission, and `git status --porcelain` is empty for the Mission's `status.events.jsonl` in BOTH the repository root checkout and the coordination worktree (`.worktrees/<slug>-coord`).
- **FR-001 (ratchet)**: the events are written through `placement_seam(...).write_dir(MissionArtifactKind.STATUS_STATE).path`, never through a read-resolver path; behaviour unchanged (today they already land in the coordination worktree).
- **NFR-001**: at most one coordination commit per run; a re-run whose events are all present makes no commit (router `unchanged`).
- **FR-004 / SC-003**: a refused or failed coordination commit exits 1 with `error_code: SETUP_PLAN_LIFECYCLE_UNCOMMITTED`, naming the unrecorded event types and the router diagnostic; a plan commit that already landed is kept and reported (`commit_hash`).
- **FR-003 / NFR-002 / SC-002**: `single_branch`, `lanes`, and a default Mission before settlement are byte-identical in written files, commits and JSON keys (no `lifecycle_commit` key there).
- **FR-005 (folded)**: no doctor change. The existing `COORDINATION_WORKTREE_DIRTY` warning already reports leftover uncommitted events (operator ruling `01M853E34H1MN0CQGQ9209P8MR`).

## Context & Constraints

- Spec: `kitty-specs/setup-plan-coord-lifecycle-commit-01M84SXJ/spec.md` (read the "Premise correction" section first). Plan, research D1-D4.
- **Reproduction (main @ 1890a6c)**: explicit `lanes_with_coord` Mission → create → commit substantive spec → setup-plan (scaffold) → write substantive plan → setup-plan. Root checkout clean; coordination worktree ` M kitty-specs/<slug>/status.events.jsonl` holding the three events. That is the red state T001 must reproduce.
- Why it happens: `setup_plan`'s `feature_dir` comes from the coordination-aware read resolver (`_resolve_setup_plan_scope` → `_find_feature_directory`), so `emit_artifact_phase(feature_dir, ...)` already appends to the coordination log; `_lifecycle_log_for_plan_commit` then (correctly) keeps that log out of the PRIMARY plan commit, and nothing else commits it.
- C-001: a default Mission before settlement (no `--topology`) is out of scope (#7827): its topology is `single_branch` at setup-plan time, so it already takes the unchanged path. C-002: never migrate, commit-by-hand or delete pre-existing uncommitted events beyond what this run commits — note the run's commit of `status.events.jsonl` will include any lines already present in the file; that is the existing behaviour of a whole-file commit and is acceptable (the file is append-only and finalize already commits it whole).
- C-003: no new seam, no new commit path, no ADR. Use `placement_seam(...).write_dir(...)` and `specify_cli.coordination.commit_router.commit_for_mission`. Precedents: `mission_finalize_commit._emit_tasks_started` (write_dir resolved outside the try, WP15 B3) and `core/mission_creation_events._commit_coord_create_events` (STATUS_STATE commit + result check).
- Complexity ≤ 15 per function (ruff C901 / Sonar S3776). `setup_plan` is already long: put the new leg in a small helper with direct tests.
- Keep the `mission._commit_to_branch` / `mission.<name>` patch seams working; do not move existing functions.
- Coordinate: Slice 6 (another runner) touches `mission_finalize.py`, not this module. The #7809 WP04 Mission touches finalize bootstrap. No expected overlap.

## Branch Strategy

- **Planning base branch**: `issue-3933-lifecycle-event-placement` (planning artifacts generated on `kitty/mission-setup-plan-coord-lifecycle-commit-01M84SXJ`).
- **Merge target branch**: `issue-3933-lifecycle-event-placement`; a PR from there to `main` follows consolidation.
- Execution workspaces are allocated per computed lane from `lanes.json`; with one WP the Mission settles to `single_branch` and the WP runs in the write checkout. Use `spec-kitty agent action implement WP01 --agent claude --mission setup-plan-coord-lifecycle-commit-01M84SXJ` and the workspace it prints; never reconstruct paths.

## Subtasks

### Subtask T001: Red-first real-CLI tests (new `tests/coordination/test_setup_plan_coord_lifecycle_3933.py`)

**Purpose**: pin the defect through the pre-existing entry point before changing code (Standing Order 4).

**Steps**:
1. Reuse the subprocess harness `tests.integration.cli_mission_fixture_7545` (`init_repo`, `run_sk`, `json_of`, `git`, `dirty`, `flat`), as `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py` does. Module markers: `integration`, `git_repo`, `timeout(900)`.
2. A fixture helper `_coord_mission(tmp_path, topology="lanes_with_coord")` that runs `agent mission create ... --topology <t> --target-branch dev --json`, writes a substantive `spec.md` (one FR row), commits it, and returns `(repo, env, slug, mission_dir, coord_root)` where `coord_root = repo / ".worktrees" / f"{slug}-coord"`.
3. `test_coord_setup_plan_commits_lifecycle_events_on_the_coordination_branch` (parametrize `lanes_with_coord` and `coord`): scaffold run, write the substantive plan (`_PLAN` text from the existing test), second run. Assert exit 0; `dirty(repo) == []`; `git status --porcelain` in `coord_root` is empty; the coordination branch's `kitty-specs/<slug>/status.events.jsonl` (read with `git show <coord-branch>:...`, branch name from `meta.json` `coordination_branch`) contains `SpecifyCompleted`, `PlanStarted`, `PlanCompleted`; the payload has `lifecycle_commit.status == "committed"` and its hash equals the coordination branch tip.
4. `test_coord_scaffold_only_run_commits_the_events_recorded_so_far`: only the scaffold run; assert the coordination worktree is clean and `SpecifyCompleted` + `PlanStarted` are on the coordination branch.
5. `test_coord_rerun_makes_no_new_commit` (NFR-001): after the full flow, record the coordination tip, run setup-plan again, assert the tip is unchanged and `lifecycle_commit.status == "unchanged"`.
6. `test_single_branch_setup_plan_is_unchanged` (FR-003/NFR-002): `--topology single_branch` flow; assert the plan commit contains `plan.md` and `status.events.jsonl` (as today), `dirty(repo) == []`, and `"lifecycle_commit" not in payload`.
6b. Parametrize that test over `--topology single_branch` and a default Mission (no `--topology`, C-001): both take the unchanged path. `lanes` shares the same non-coordination branch of `routes_through_coordination` and is already pinned by the partition test in `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py`.
7. Run them: the coordination cases must FAIL today (worktree dirty / no `lifecycle_commit`); the single_branch case passes (ratchet). Record the red output in the WP history.

**Files**: `tests/coordination/test_setup_plan_coord_lifecycle_3933.py` (new, ~200 lines).

**Edge cases**: the coordination branch name is `kitty/mission-<slug>` style; read it from `meta.json`, never hard-code. Each `run_sk` is a real subprocess; keep the number of runs low (the suite is slow).

### Subtask T002: Write through `write_dir(STATUS_STATE)` (FR-001 ratchet, D1/D2)

**Purpose**: one write authority for status records; a write-location refusal fails setup-plan closed.

**Steps**:
1. Add a helper `_lifecycle_status_dir(repo_root, mission_slug, owned) -> Path` returning `placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE).path`. Mirror `_emit_tasks_started`: an owned run passes `owned` (owned checkouts are single_branch, so this is the owned mission dir).
2. In `_emit_spec_plan_phase_events` and the `PlanCompleted` emission in `_commit_plan_if_substantive`, resolve the directory with the helper **before** the `try:` and pass it to `emit_artifact_phase` instead of `feature_dir`. Keep the `try/except` around the emission itself only.
3. Resolve once per run if practical (pass the path down) to avoid repeated seam calls; do not change function signatures that tests patch without checking `grep -rn "_emit_spec_plan_phase_events\|_commit_plan_if_substantive" tests src`.
4. `_lifecycle_log_for_plan_commit` keeps its partition decision unchanged, but should read the log from the same status dir (on non-coordination topologies it equals `feature_dir`).
5. Confirm with the T001 single_branch test plus `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py` that nothing changed.

**Validation**: `test_no_write_side_rederivation.py` and `test_layer_rules.py` stay green.

### Subtask T003: One coordination commit at the end of the run (FR-002, NFR-001, D3)

**Purpose**: commit the events where they live.

**Steps**:
1. New helper `_commit_lifecycle_events_on_coordination(repo_root, mission_slug, status_dir, owned) -> CommitRouterResult | None`:
   - Resolve the topology the same way `_lifecycle_log_for_plan_commit` does (`owned.topology` or `resolve_topology`); return `None` when `not routes_through_coordination(topology)` (non-coordination topologies: no call, no JSON key).
   - `log = mission_event_log_path(status_dir)`; return `None` if it does not exist.
   - `policy = ProtectionPolicy.resolve_for_mission(repo_root, mission_slug)`; call `commit_for_mission(repo_root, mission_slug, files=(log,), message=f"chore({mission_slug}): record setup-plan lifecycle events", policy=policy, kind=MissionArtifactKind.STATUS_STATE)` (create's `_commit_coord_create_events` is the model; no seed trailer here).
2. Call it in `setup_plan` after `_commit_plan_if_substantive` (all three outcomes: committed, scaffold-only, blocked) and before `_emit_setup_plan_result`.
3. The router answers `unchanged` when the file matches the branch: that is the NFR-001 no-op.

**Edge cases**: unmaterialized coordination worktree — the router/write authority establishes or refuses; a refusal is handled by T004. A coordination status lock held by another writer surfaces as the router's error (T004).

### Subtask T004: Fail loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED` (FR-004, D4)

**Purpose**: never report success while the events are uncommitted.

**Steps**:
1. Red first: in the T001 module, an in-process test (Typer `CliRunner` on `specify_cli.cli.commands.agent.mission.app`, with the harness's patches for `locate_project_root`, as `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py::run_finalize` does) that monkeypatches `specify_cli.coordination.commit_router.commit_for_mission` to return a `CommitRouterResult` with `status="refused"` and a diagnostic **only for `kind=STATUS_STATE`** (delegate other kinds to the real function so the plan commit still lands). Assert exit 1, `error_code == "SETUP_PLAN_LIFECYCLE_UNCOMMITTED"`, the payload lists the event types and the diagnostic, and `commit_hash` (the plan commit) is present.
2. Add a module constant `SETUP_PLAN_LIFECYCLE_UNCOMMITTED: Final = "SETUP_PLAN_LIFECYCLE_UNCOMMITTED"`.
3. When the helper's result status is not `committed`/`unchanged`: build the normal result payload (so the plan commit is reported), set `result: "error"`, `error_code`, `uncommitted_lifecycle_events` (the three type names present in the log for this run) and `lifecycle_diagnostic`, emit it (JSON or a red text line with `markup=False` for untrusted diagnostics), and `raise typer.Exit(1)`.
4. Message: name the coordination worktree and say the events stay uncommitted there; the operator can commit them in that worktree or re-run setup-plan once the refusal is fixed.

### Subtask T005: Surface `lifecycle_commit` in the JSON result (data-model)

**Steps**:
1. Pass the router result into `_build_setup_plan_result`/`_emit_setup_plan_result` as an optional keyword (default `None`) and, when not `None`, add `"lifecycle_commit": {"status": ..., "commit_hash": ..., "branch": <coord ref if available>}`.
2. Non-coordination topologies: key absent (FR-003). Check `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py` and any JSON golden for setup-plan (`grep -rn "setup_plan\|setup-plan" tests/**/golden* tests/architectural/test_json_contract_enumeration.py`) and update a golden only if it enumerates keys — disclose it if out of matrix.

### Subtask T006: Changelog fragment, gates, blast radius

**Steps**:
1. `docs/changelog/unreleased/3933-setup-plan-coord-lifecycle.fixed.md`, one entry in the house style (Before/After), e.g. "**`setup-plan` commits its lifecycle events on a coordination Mission** (#3933). **Before:** ... left uncommitted in the coordination worktree. **After:** committed on the coordination branch in the same run; a refused commit exits 1 with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`." Check with `uv run --frozen python -m scripts.docs.check_changelog_style` and `... check_spelling --pass unreleased`.
2. `ruff check`, `ruff format --check --force-exclude`, `mypy` on changed files: zero issues, no suppressions.
3. Tests: `make test-fast`; `tests/coordination/`; `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py test_mission_setup_plan_phases.py test_setup_plan_branch_match.py test_setup_plan_read_surface.py` (out of matrix: nightly-only, disclose with the local run); gates `tests/architectural/test_no_write_side_rederivation.py test_layer_rules.py test_commit_scope_owner.py test_guard_capability_call_sites.py test_no_legacy_terminology.py`.
4. Record exact commands and counts in the WP history for the PR's *Tests run*.

## Test Strategy

Red-first through the real CLI (T001, T004) on explicit coordination Missions; ratchet the single_branch path in the same module; targeted out-of-matrix regressions disclosed.

## Definition of Done

- T001-T006 done; the coordination tests were red before the fix and are green after.
- Non-coordination topologies unchanged (T001 single_branch case + the existing #3933 tests).
- Gates clean; changelog fragment present; `tracer-*` files updated with any friction.

## Risks

- Whole-file commit of `status.events.jsonl` picks up any earlier uncommitted lines (acceptable, see C-002 note).
- A lock or protection refusal on the coordination branch: must become the named refusal, not a crash.
- Long test runtime: each `run_sk` is a subprocess; keep scenarios lean.

## Reviewer Guidance

- Verify the red state: run the new coordination tests against the base commit.
- Verify no new seam/commit path (grep for `git commit`/`safe_commit` additions: there must be none).
- Verify single_branch JSON has no `lifecycle_commit` key and the plan commit still includes the log.
- Verify the refusal payload keeps `commit_hash` and exits 1.
