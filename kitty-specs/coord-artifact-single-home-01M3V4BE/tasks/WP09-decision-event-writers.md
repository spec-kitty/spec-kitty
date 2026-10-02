---
work_package_id: WP09
title: Decision event writers move to the accessor
dependencies:
- WP04
- WP07
requirement_refs:
- FR-003
- FR-003a
- FR-016
- SC-002
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
- T052
phase: Phase 3 - Writer migration
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
agent: claude
authoritative_surface: src/specify_cli/decisions/service.py
create_intent:
- tests/specify_cli/decisions/test_service_coord_single_home.py
- tests/runtime/test_decision_git_log_write_dir.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/decisions/emit.py
- src/specify_cli/decisions/service.py
- src/runtime/next/runtime_bridge.py
- src/specify_cli/events/decision_log.py
- tests/specify_cli/decisions/test_service_coord_single_home.py
- tests/runtime/test_decision_git_log_write_dir.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py
- tests/specify_cli/coordination/test_residual_writer_routing.py
- tests/specify_cli/events/test_decision_log_coord.py
- tests/specify_cli/events/test_decision_log.py
- tests/git/test_guard_capability_regression.py
- src/specify_cli/cli/commands/decision.py
- tests/mission_runtime/test_coord_read_seam_callers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP09 – Decision event writers move to the accessor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
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

Close the #5519 clock-restart / fork defect at its live offenders: the **decision event writers**. Both decision-event streams must get their write location from `PlacementSeam.write_dir`. These are the status log (which carries `Decision*` events) and `decisions.events.jsonl` (the `DecisionGitLog` stream).

Done means:

- R4 is green. On a coordination-routed Mission, `decision open` → tracer append → `decision open` leaves exactly **one** status log, on the coordination surface, holding both `DecisionOpened` events, with the logical clock of the second strictly greater than the first (SC-002, US2.1). Read the clock field from the actual event shape (research says `event_lamport`; the lifecycle envelope uses `lamport_clock`, `status/lifecycle_events.py:464`) and assert the field is present so the comparison cannot pass vacuously.
- `decisions/emit.py::_mission_dir` and `decisions/service.py::_mission_dir` use `write_dir(STATUS_STATE)`. These are the two sites the FR-014 gate (WP20) must show red at base and green after: emit.py ≈L88 and service.py ≈L246.
- `service.py`'s direct `materialize_coord_surface_for_write` calls (L499-501, L694-696) are removed. `write_dir` owns materialize, seed and refuse.
- `runtime_bridge._wrap_with_decision_git_log` picks the `DecisionGitLog` worktree via `write_dir(DECISION_LOG)`. `events/decision_log.py` takes the dir from that answer instead of composing `worktree_root / KITTY_SPECS_DIR / <slug>` itself.
- The decision ledger (`decisions/DM-*.md`, `index.json`) is still written on the PRIMARY partition via `_ledger_dir` (FR-009a; untouched here).
- `lanes` / `single_branch` Missions behave as before (C-008).

## Context & Constraints

- **Spec**: FR-003 (writer families "decision events in the status log, and the decision event stream"), FR-003a, FR-016 (#5519 "the logical clock restarting" reproduction), SC-002, US2.1, US2.3, US2.6, US2.8; Domain Language "Decision ledger" vs decision events.
- **Plan**: IC-04 (rows "Decision events (status log)" and "Decision event stream").
- **Research**: D1, D2, R4 (red-first list), grounding correction "runtime_bridge builds the DecisionGitLog target…" (`CommitTarget(ref=coordination_branch)` is built in `runtime_bridge_io.py:1552`, and the worktree is picked at `runtime_bridge.py:359-363`).
- **Contracts**: `contracts/write-location-accessor.md` (relationship rows "`materialize_coord_surface_for_write`: its two writer callers (`decisions/service.py:501,696`) switch to `write_dir`"), `contracts/seed.md`.
- **Plan IC-04 risk**: "`DecisionGitLog` composes `<slug>` while the transaction composes `<slug>-<mid8>` (`_transaction_dir_name`); both must agree with `write_dir`."
- **Upstream**: WP03/WP04 (accessor), WP02 (fixtures). The tracer append in R4 still uses the pre-migration tracer path (WP10 migrates it). That is fine: at that point the coordination surface is already MATERIALIZED by the first decision's seed.
- **Cold-import boundary**: `decisions.*` sits on the charter cold-import path (`tests/architectural/test_cold_import_status_boundary.py`, cited in service.py ≈L497). Keep `mission_runtime` / `coordination` imports function-local, as today.
- **Layer rules**: `src/runtime/` → `specify_cli` is a shrink-only outbound ledger (`tests/architectural/test_layer_rules.py` ≈L147-170). `runtime_bridge.py` already imports `mission_runtime.placement_seam` (L261) and `specify_cli.coordination.workspace` (L311). Reach `write_dir` through `mission_runtime.placement_seam` (an existing edge) and do not add a new `runtime → specify_cli` import.
- Load the charter and `spec-kitty charter context --action implement --json`.
- **Model discipline**: implement with sonnet (`claude-sonnet-5`); review with opus.
- **Terminology**: "Mission", never "feature". Name each sense of "primary".
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Dependency added (P-M1)**: WP07. It owns and re-pins `tests/mission_runtime/test_coord_read_seam_callers.py` first.
- **Brownfield scout (binding read)**: before coding, read `## WP09` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP09 --agent claude`, and use the printed workspace path.
- **Lane notes (updated by the post-tasks squad)**: this WP's ownership is disjoint, so it gets its own lane. It depends on WP04 (lane A) and WP07 (P-M1: WP07 re-pins `tests/mission_runtime/test_coord_read_seam_callers.py` first), so its base stacks both. WP17 depends on this WP for the decision-stream dir-name ruling (P-M4). `runtime_bridge_io.py` is not owned. Do not edit it.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T048 – Red-first R4: one log, monotonic clock across decision → tracer → decision

- **Purpose**: The #5519 P0 reproduction through the pre-existing CLI entry points (FR-016, C-005). Commit separately, first.
- **Steps**:
  1. Create `tests/specify_cli/decisions/test_service_coord_single_home.py` with `test_decision_tracer_decision_keeps_one_log_and_monotonic_clock`, parametrized over `coord` and `lanes_with_coord`.
  2. Fixture: a coordination-routed Mission in the state today's create leaves behind. Use WP02's `make_prefix_coord_mission(worktree="absent")` so the test stays meaningful after WP06 changes create. Optionally add a second parametrization through `make_coord_mission` (post-fix create).
  3. Drive through the CLI:
     - `spec-kitty agent decision open --mission <slug> --flow specify --slot-key s.a --input-key a --question "A?" --json`
     - `spec-kitty agent tracer-append ...` (the command registered at `cli/commands/agent/__init__.py:33`; check its options in `cli/commands/agent/tracer_append.py`), or the library `append_tracer_finding` (`retrospective/tracer_writer.py:227`) if the CLI needs extra fixture state
     - `spec-kitty agent decision open ... --slot-key s.b --input-key b --question "B?" --json`
  4. Assertions:
     - exactly one `status.events.jsonl` among {root checkout, coordination worktree} contains `DecisionOpened` events, and it is the coordination one (`<coord wt>/kitty-specs/<dir>/status.events.jsonl`);
     - it holds both `DecisionOpened` (match by decision id / input key);
     - `lamport(second) > lamport(first)`, and lamports strictly increase across the whole log;
     - no event id appears twice;
     - the root checkout's log gained no decision event (compare its event ids to the pre-test snapshot).
  5. Run on the lane base. Expected RED: the first `DecisionOpened` lands in the root checkout (read resolver substitutes root on EMPTY/UNMATERIALIZED). The tracer append then creates the coordination Mission dir, and the second decision lands there with a restarted clock. Record the output in the Activity Log.
- **Files**: `tests/specify_cli/decisions/test_service_coord_single_home.py` (new).
- **Edge cases**: `decision open` at base calls `materialize_coord_surface_for_write` first (service.py:501). So the base failure may be "first event lands in the coordination worktree's freshly created, un-seeded dir, orphaning the root creation events" rather than "lands in root". Either way, assert the invariant (one log, all events, monotonic), not a specific broken shape.

### Subtask T049 – `decisions/emit.py::_mission_dir` → `write_dir(STATUS_STATE)`

- **Purpose**: `_mission_dir` (emit.py:75; `read_dir(STATUS_STATE)` at L88) is a read resolver used as the write location for decision events in the status log. It is one of WP20's red-at-base offenders.
- **Steps**:
  1. Read emit.py:60-100 and the docstring at L75-90. Replace L88 with `placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.STATUS_STATE).path`. Keep the function-local import style.
  2. Update the docstring: decision events are COORD-partition records. The write location comes from the one accessor, which may materialize or seed and refuses loudly otherwise. The read resolver is never the write location.
  3. If any read-only caller uses `_mission_dir` / `_events_path` (L94) purely to read, split it: give the reader its own helper calling `read_dir`, so the write helper is used only by writers. Grep `_mission_dir\|_events_path` in emit.py.
  4. Owned checkouts: if emit.py receives an `owned` fact anywhere, thread `owned=` into `placement_seam(...)`. Otherwise leave it as is.
- **Files**: `src/specify_cli/decisions/emit.py`.
- **Validation**: `tests/specify_cli/decisions/test_emit.py`, `test_emit_locking.py` stay green; T048 progresses.
- **Edge cases**: `write_dir` takes the status lock during a seed, and emit has its own locking (`test_emit_locking.py`). Confirm it uses the same reentrant `feature_status_lock` key. If emit already holds that lock when it calls `_mission_dir`, reentrancy covers it. If it holds a different lock first, check I-SEED-2 (never take the status lock while holding the workspace lock).

### Subtask T050 – `decisions/service.py`: `_mission_dir` → `write_dir`; drop direct materialize calls

- **Purpose**: `service.py::_mission_dir` (L231; `read_dir(STATUS_STATE)` at L246) is the second offender. The direct `materialize_coord_surface_for_write` calls (L499-501 in `open_decision`, L694-696 in the terminal path) materialize but never seed, so a pre-fix Mission forks at the first decision.
- **Steps**:
  1. Replace L246 with `write_dir(MissionArtifactKind.STATUS_STATE).path`.
  2. Remove both `materialize_coord_surface_for_write(...)` calls and their imports. The `_events_path(repo_root, mission_slug)` "pre-resolve: any placement failure fails before write" calls (L502, L697) now trigger `write_dir`, which materializes, seeds or refuses before any ledger write. Keep that ordering: resolve the event write location BEFORE `_ledger_dir` writes, so a refusal leaves the ledger untouched (zero record loss, NFR-002). Rewrite the #5113 / FR-013 comments to say this.
  3. Leave `_ledger_dir` (L255-279, `read_dir(PRIMARY_METADATA)`) and the L163-171 helper untouched. The ledger is a PRIMARY-partition record (FR-009a; WP12 adds the ratchet test).
  4. Check the T010 (D4/FR-004) dedup-under-one-lock section after L502. The lock it takes must be compatible with a seed that already ran (the seed releases the status lock before returning, or re-enters it reentrantly).
- **Files**: `src/specify_cli/decisions/service.py`.
- **Validation**: `test_service_idempotency.py`, `test_service_terminal.py`, `test_ownership_3111.py` green; T048 green once T051 is done too (if the DecisionGitLog leg also participates).
- **Edge cases**:
  - Remote-only coordination branch: `decision open` must exit non-zero with the `COORDINATION_WORKTREE_UNMATERIALIZED` hint, and must write NO ledger file. Add this to T052.
  - DELETED: same, with `COORDINATION_BRANCH_DELETED`.

### Subtask T051 – `runtime_bridge._wrap_with_decision_git_log` and `events/decision_log.py`

- **Purpose**: `_wrap_with_decision_git_log` (runtime_bridge.py:283-385) picks the `DecisionGitLog` worktree with its own ladder: `worktree_root_candidate.exists()` → use it; else `CoordinationWorkspace.resolve` (L361), or `_resolve_owned_coordination_workspace` for owned callers (≈L363-368). `DecisionGitLog.__init__` (decision_log.py ≈L118-120) composes `worktree_root / KITTY_SPECS_DIR / _safe_slug / "decisions.events.jsonl"`, with `<slug>` and not `<slug>-<mid8>`. Neither path seeds, so the stream can fork, and the dir name may disagree with the transaction's `<slug>-<mid8>`.
- **Steps**:
  1. In the `coord_routing_topology` arm, replace the materialization ladder with `placement_seam(repo_root, mission_slug, owned=<owned fact>).write_dir(MissionArtifactKind.DECISION_LOG)`. Derive `worktree_root` from it (the coordination worktree containing `.path`). Keep the stored-topology SHAPE decision (`coord_routing_topology`) and the coord-less arm byte-identical (C-008).
  2. Owned callers: `write_dir`'s owned arm (WP04) must give the same answer `_resolve_owned_coordination_workspace` gives today, and preserve the #4867 (T062) typed refusal propagation (`CoordinationWorkspaceUnavailable` → typed refusal for owned callers). Keep that `except` arm behaviour identical for owned callers. Add a test.
  3. `events/decision_log.py`: make `mission_dir: Path` a **required** keyword argument of `DecisionGitLog` (post-tasks squad R-m5 / P-m4, preferred over an optional kwarg), set `self._decisions_file = mission_dir / "decisions.events.jsonl"`, and pass `location.path` from the bridge. Delete the legacy `worktree_root / KITTY_SPECS_DIR / <slug>` composer, so no second composer remains. Migrate every test caller (now owned by this WP): `tests/runtime/test_bridge_decision_log_flush.py`, `tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py`, `tests/specify_cli/coordination/test_residual_writer_routing.py`, `tests/specify_cli/events/test_decision_log_coord.py`, `tests/specify_cli/events/test_decision_log.py`, `tests/git/test_guard_capability_regression.py`. Keep `assert_safe_path_segment(mission_slug)` validation first.
  4. Dir-name agreement: add a test asserting that for a slug that embeds its mid8 and one that doesn't, `DecisionGitLog`'s file dir == `write_dir(DECISION_LOG).path` == the transaction's `_transaction_dir_name` dir (`coordination/status_transition.py`). If today's `<slug>` composition differs for some slug shape, the `mission_dir` injection fixes it. Record which shapes differed.
  5. Do not edit `runtime_bridge_io.py:1552` (`CommitTarget(ref=coordination_branch)`); it is not owned and it stays correct.
  6. Keep `_wrap_with_decision_git_log` C901 (11 today) ≤ 15. Removing the ladder should lower it.
- **Files**: `src/runtime/next/runtime_bridge.py`, `src/specify_cli/events/decision_log.py`.
- **Validation**: `tests/runtime/test_bridge_decision_log_flush.py`, `test_bridge_composition.py`, `test_bridge_io.py` green; new `tests/runtime/test_decision_git_log_write_dir.py` green.
- **Edge cases**: the bridge catches `CoordinationWorkspaceUnavailable` (≈L385). `write_dir` raises `CoordinationWorktreeUnmaterialized` / `CoordinationBranchDeleted` / `CoordSeedForkRefused`. Decide per error whether the bridge degrades (today's behaviour for unavailable workspaces in non-owned flows) or propagates. Never silently write to the repository root checkout: degrading means "no DecisionGitLog wrapper", not "wrapper on root".
- **Dir-name compatibility (post-tasks squad P-M4)**: `DecisionGitLog` composed `kitty-specs/<slug>/`, while the status path uses `coord_mission_dir_name(slug, mid8)` (`lanes.branch_naming`). Do one of the following:
  - (a) prove, with a pinned test over the reachable creation paths, that no coordination-routed Mission has differing shapes; or
  - (b) carry and fold a legacy `kitty-specs/<slug>/decisions.events.jsonl` stream once into the canonical dir. Do it under the seed's status lock, reusing WP03's `event_prefix` classifier and refusing a true fork.
  Record the choice in the activity log. WP17 depends on this WP and composes dir names only via `lanes.branch_naming`.
- **`WriteLocation.checkout_root` (post-tasks squad P-M3):** take the checkout root from `write_dir(kind).checkout_root` (WP03/WP04). Never derive it as `.path.parent.parent` or by guessing a worktree name. `test_no_worktree_name_guess.py` does not police `.parent.parent` (#2007); WP20 extends `test_no_write_side_rederivation.py` to enforce this, so until then review checks it.

### Subtask T052 – State matrix, ledger control, C-008

- **Purpose**: One test per writer family and per reachable state (FR-003: "one test per writer family; each fails if that family still uses a read resolver").
- **Steps**:
  1. In `tests/specify_cli/decisions/test_service_coord_single_home.py`, parametrize `decision open` over the states:
     - UNMATERIALIZED + local branch → materialized, event on coord;
     - pre-fix EMPTY → seeded once (one seed commit), event appended after the carried events;
     - MATERIALIZED-forked (#5519 shape, WP02 fork builder (a)) → writes proceed on coord with no lockout (US2.6);
     - remote-only → refused, no ledger and no event written;
     - DELETED → refused with hint.
  2. In `tests/runtime/test_decision_git_log_write_dir.py`: the DecisionGitLog stream lands at `write_dir(DECISION_LOG).path / "decisions.events.jsonl"` in the coordination worktree for a pre-fix EMPTY Mission (seeded), and for the owned variant (if WP02 provides an owned builder; otherwise a unit test with a fake seam).
  3. Ledger control: after `decision open` on a coordination Mission, `decisions/DM-*.md` and `decisions/index.json` exist in the repository root checkout's Mission dir (PRIMARY partition), never in the coordination Mission dir (US1.3 / FR-009a).
  4. C-008: `lanes` and `single_branch` decision open → events at the same path as before (compute the expected path the old way in the test).
  5. Make sure each test would fail if its writer reverted to `read_dir` (mutation sanity: temporarily revert locally, confirm red, restore; note it in the log).
- **Files**: the two new test files.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Decision rows have no Lamport field.** Their keys are `event_id`, `at`, `event_type` (`"DecisionPointOpened"`, not `"DecisionOpened"`) and `payload` (`decisions/emit.py:241-245`). The clock is the line-count proxy returned by `_append_raw_event` (`emit.py:140`), surfaced as `event_lamport` in `decision open --json` (`decision.py:162`). R4 asserts on that value or on log position. This supersedes the earlier `lamport_clock` note for decision rows.
- **Keep fail-closed**: a coordination-routed non-owned failure raises `DecisionGitLogUnavailable` (`runtime_bridge.py:403-408`). Only the coordination-less arm falls back to the plain emitter.
- **Read/write split in `service.py` too**: `_events_path` also serves reads (`_opened_event_exists` L303-312, via `_repair_missing_opened_event` L336/L529). Reads keep the read resolver; writes use `write_dir`. Otherwise the idempotency probe would seed or materialize.
- **Other `open_decision` callers**: `charter/_widen.py`, `charter/interview.py`, `missions/plan/{plan,specify}_interview.py`, `orchestrator_api/commands.py:144`. Run their tests by name.
- **`decision.py:217` (now owned; shared with WP17, which depends on this WP)**: `_handle_status_read_path_error` catches only `StatusReadPathNotFound`. Add arms rendering `COORD_SEED_FORK_REFUSED` (`.code` on the `ActionContextError`) and `STATUS_LOCK_HELD` with recovery hints, plus tests.
- **`DecisionGitLog.worktree_root`** stays; it is the commit `cwd` (L252). Take it from `WriteLocation.checkout_root`.
  - The coordination-less arm passes `mission_dir = anchor_root/kitty-specs/<slug>`, using the owned root for owned coordination-less Missions (C-008).
  - In `runtime_bridge.py`, take the coordination worktree root from `checkout_root`, not from `resolve_commit_target`'s naming-convention candidate (`runtime_bridge_io.py:1505`). Do not edit `runtime_bridge_io.py`.
- `materialize_coord_surface_for_write` stays live (`_coordination_doctor.py:1424`); do not delete it.
- **L198 re-pin**: re-pin `tests/mission_runtime/test_coord_read_seam_callers.py::test_decisions_emit_mission_dir_fails_loud_sanely` here; it expected a raise on UNMATERIALIZED with a local branch, and `write_dir` now materializes. The file is co-owned with WP07; this WP depends on WP07, so they share a lane.
- **Valid guards**:
  - `test_read_seam_leniency.py::test_decisions_mission_dir_fails_loud_when_coord_deleted` and `::test_decisions_mission_dir_preserves_healthy_status_home`;
  - `test_coord_read_seam_callers.py::test_decisions_emit_mission_dir_no_raise_on_single_branch`;
  - in `test_decision_fresh_coord_5113.py`: `test_materialization_failure_is_byte_identical`, `test_list_and_verify_never_materialize` and `test_dry_run_never_materializes` (list, verify and dry-run never reach `write_dir`), plus the remote-only refusals;
  - `test_decision_log.py:493` (an unsafe slug raises `ValueError` before placement).
- **Lock key**: `emit.py:138` uses `feature_dir.name`, which must equal the seed lock key (`coord_mission_dir_name`).
- **Cold import**: keep the `mission_runtime` import function-local in `decisions/*`. Add no new `specify_cli` subpackage edges from `runtime`.
- **P-M3 gap**: `decisions/*`, `events/decision_log.py` and `runtime_bridge*.py` are not yet scanned for `.parent.parent`. WP20 extends the gate; until then review checks it. `test_no_worktree_name_guess.py` is **not** the P-M3 guard (it excludes `.parent.parent`, #2007).
- C901: `_wrap_with_decision_git_log` 11, `open_decision` 8.

## Targeted test surface

- New: `tests/specify_cli/decisions/test_service_coord_single_home.py`, `tests/runtime/test_decision_git_log_write_dir.py`.
- Owning-module tests: `tests/specify_cli/decisions/` (whole dir; fast), `tests/decisions/` (by file: `grep -rl "decisions.service\|decisions.emit\|DecisionGitLog" tests/decisions tests/runtime tests/next | head`), `tests/runtime/test_bridge_decision_log_flush.py`, `test_bridge_composition.py`, `test_bridge_io.py`, plus any `tests/events/` decision-log tests.
- Baseline: `make test-fast`.
- Named architectural gates only: `tests/architectural/test_layer_rules.py` (runtime outbound ledger), `tests/architectural/test_cold_import_status_boundary.py`, `tests/architectural/test_no_write_side_rederivation.py`, `tests/architectural/test_status_events_writes_gate.py`.
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). Record commands and counts in the Activity Log. Classify unexplained reds with CLAUDE.md's baseline-red gotcha.
- Post-tasks squad additions, by name: `tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py`, `tests/mission_runtime/test_coord_read_seam_callers.py` (re-pinned by WP07, which this WP now depends on), the six migrated `DecisionGitLog` caller test files, and `tests/architectural/test_status_events_writes_gate.py`.

## Quality gates

- Keep C901 ≤ 15 for every touched function (NFR-004): `_wrap_with_decision_git_log` (11), `open_decision` and the terminal decision path in service.py. Extract if any approaches 15.
- Run `ruff check`, `ruff format --check` and `mypy --strict` on the changed files, with no new suppressions (NFR-005). `src/runtime/` and `src/specify_cli/` both run under strict mypy.
- Reach ≥ 90% coverage of new and changed lines, with focused tests per new branch (NFR-003). If you add public symbols, run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #2533

## Definition of Done

- R4 was committed first and RED on the lane base (output recorded), and is GREEN at the end.
- `emit.py::_mission_dir` and `service.py::_mission_dir` derive their location from `write_dir`. There are no direct `materialize_coord_surface_for_write` calls in service.py.
- `DecisionGitLog` writes at `write_dir(DECISION_LOG)`, the dir names agree, and owned refusals are preserved.
- The ledger is still PRIMARY, the C-008 controls are green, and the quality gates are green, with commands and counts logged.

## Risks & Mitigations

- **Ordering regression (ledger written, event refused)**: keep "resolve write location before any ledger write", and test the remote-only case writes no ledger file.
- **Owned-checkout behaviour drift in the bridge**: dedicated owned test; keep the #4867 typed refusal.
- **Cold-import regression**: keep imports function-local and run `test_cold_import_status_boundary.py`.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: R4 (and the T052 state tests that were red) are RED on the WP's base and GREEN on the final commit.
- Confirm `grep -n "read_dir(MissionArtifactKind.STATUS_STATE)\|materialize_coord_surface_for_write" src/specify_cli/decisions/` returns no write-location use.
- Confirm the `DecisionGitLog` API change is additive and the dir-name agreement test covers both slug shapes.
- Confirm no new `runtime → specify_cli` import edge (`test_layer_rules.py` green, ledger unchanged).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
