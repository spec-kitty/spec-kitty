---
work_package_id: WP03
title: 'Finalize wiring: evidence, preflight, validate-only and refusal rendering'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-009
- FR-011
- NFR-001
- NFR-003
- C-003
- C-005
- SC-001
- SC-003
- SC-004
planning_base_branch: issue-5573-frozen-started-lanes
merge_target_branch: issue-5573-frozen-started-lanes
branch_strategy: Planning artifacts for this mission were generated on issue-5573-frozen-started-lanes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5573-frozen-started-lanes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-frozen-started-lanes-01M444FM
base_commit: 56c3ef9b8eb7b0f0aaca0ca85fa5ca0451ef57f2
created_at: '2026-10-04T20:43:38.786736+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_finalize_frozen_lane_preflight.py
- tests/integration/test_refinalize_frozen_lane_refusals.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize_lanes.py
- src/specify_cli/cli/commands/agent/mission_finalize_commit.py
- src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py
- tests/specify_cli/cli/commands/agent/test_finalize_frozen_lane_preflight.py
- tests/integration/test_refinalize_frozen_lane_refusals.py
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Finalize wiring: evidence, preflight, validate-only and refusal rendering

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's
`task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP03 --agent claude`

## Post-tasks squad folds (binding — these override any conflicting text below)

- **Preflight placement:** inside the existing `if not refresh_planning_commit:` block (corrected in T011 step 2).
- **The dead-symbol gate is `tests/architectural/test_no_dead_symbols.py`.** After this WP every new public name from
  WP02 must have a `src/` caller and the gate must be **green**. Run it and record the result.
  `test_dead_symbol_allowlist_contract.py` cannot fail, so ignore it.
- **Phase-module seam test** (`tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py`):
  - new phase helpers must be re-exported from `mission_finalize`;
  - calls into another finalize module go through `_mf.`;
  - any name you patch on `mission_finalize` must be in its `_ROUTED_NAMES`.

  Prefer patching on the `mission_finalize_lanes` namespace in your unit tests. If the seam test needs an update to
  list the new routed names, that is an out-of-map edit: allowed with a one-line rationale in the commit (ownership
  leeway). Never weaken the test.
- **Amendments go through `wps.yaml`** when the fixture has one (`mission_finalize_validation.py:~279`). Otherwise
  amend the frontmatter and `tasks.md`.
- **Status seeding:** `claimed → in_progress` needs `workspace_context=`; `in_progress → planned` needs `reason=`.
- **AS6 (absent log) fixture: no lane allocated**, so there is no lane tip; otherwise the tip fallback freezes the
  lane and the run refuses. Separately add an **FR-008 lane-work-tip fallback e2e**:
  - allocate WP02's lane (which records a tip) and emit **no** status events for WP02;
  - apply the US1 amendment;
  - WP02 keeps lane-b.

  This proves `lane_created_branch` matches what `record_tip` writes.
- **Prove the refusal precedes every status writer:** a test (unit or e2e) that, with the preflight raising, spies on
  and asserts that `_emit_tasks_started`, `_emit_local_canonical_events` and `_bootstrap_canonical_state_via_mission`
  are **never called**.
- **More tests:**
  - **FR-009:** the validate-only success preview reports `lane_ids` containing `lane-b` for the US1 scenario.
  - **Skips:** `--refresh-planning-commit` and a `SINGLE_BRANCH` mission do not invoke the preflight (spy).
  - **Remedy round-trip for `started_wp_removed`:** restore the file and cancel the WP. Eligibility reads the retired
    frontmatter `lane` (`mission_finalize_bootstrap.py:~543`), so an event-log cancel keeps the WP lane-eligible and
    present. That means it is **not removed**, and the re-finalize succeeds with the WP staying in its lane.
  - **Remedy hygiene:** every remedy string contains no `reset`, `restore`, `rm `, `--force` or `delete`, and the
    move-task remedy contains `--mission`.
- **Retired reservation e2e:** if you test retirement, use frontmatter `lane: canceled`. That is the only thing the
  projection treats as retired.
- **JSON key set:** owned runs may also carry `stale_repository_root_copy`. Do not assert a closed key set beyond the
  contract's mandatory keys.
- The preflight signature must not carry unused parameters (ruff ARG001). Drop `all_canceled` if unused.

## Objective

Feed real evidence into WP02's pure constraint from the `finalize-tasks` shell:
- the history-based started set from the status log, with fail-closed handling of an unreadable log;
- lane-work-tip fallback evidence.

Evaluate it in a read-only **preflight before the first status write** (so `--validate-only` refuses identically).
Thread it into the real write, and render `LANE_MEMBERSHIP_FROZEN` with its remedy. This WP turns WP01's red tests
green without editing them.

## Context

- **Spec:** US1/US2, FR-005–FR-009, SC-001/SC-003/SC-004.
- **Plan:** "Design → Evidence", "Preflight and threading", IC-03.
- **Contract:** `contracts/lane-membership-frozen.md` (exact JSON keys, reasons, remedies).
- **From WP01:** `_resolve_status_read_dir(repo_root, mission_slug, *, owned)` in `mission_finalize_planning_pin.py`
  (raises on an unresolvable surface; the caller owns the policy), and the red e2e tests in
  `tests/integration/test_refinalize_keeps_started_lanes.py`.
- **From WP02** (`specify_cli.lanes.frozen_membership` / `specify_cli.lanes.compute`): `started_wp_ids`,
  `build_frozen_membership`, `FrozenLaneMembership`, `MembershipConflict`, `remedy_for`; `compute_lanes(...,
  frozen=)`, `compute_and_write_lanes(..., frozen=)`, `LaneMembershipFrozenError`; and
  `specify_cli.lanes.lane_tip.recorded_tip_branches`.
- **Ordering facts (base commit):**
  - `finalize_tasks` (`mission_finalize.py` ~L1170-1330) runs `_run_finalize_ownership_gates`, then
    `_read_meta_for_emission`, then `_emit_tasks_started`, which is the **first status write**.
  - Then either the validate-only branch (`_emit_validate_only_report`) or `_run_commit_pipeline`
    (`mission_finalize_commit.py:608`). The pipeline writes status (`_emit_local_canonical_events`,
    `_bootstrap_canonical_state_via_mission`) **before** `_compute_and_write_lanes`.
  - Any exception inside the `finalize_tasks` try is rendered by `_emit_finalize_error_with_revert_note`
    (`mission_finalize_commit.py` ~L922-972), and the except path restores the mission write scope
    (`mission_finalize.py` ~L1398-1416). That is why a preflight raise leaves frontmatter, `tasks.md` and `meta.json`
    byte-identical.
- **Seam idiom:** `mission_finalize.py` re-exports every phase-module name, and phase modules call patched names via a
  lazy `from specify_cli.cli.commands.agent import mission_finalize as _mf`. Follow it, and add re-exports for the new
  helpers.
- **Sibling missions:** do **not** modify `src/specify_cli/cli/commands/implement.py` or
  `src/specify_cli/core/mission_creation.py` (C-005).

### Subtask T010: `_gather_frozen_lane_membership` (evidence, fail-closed)

**Steps**:
1. In `mission_finalize_lanes.py` add
   `_gather_frozen_lane_membership(planning_dir, repo_root, mission_slug, *, wp_frontmatters, eligible_wp_ids, owned=None) -> FrozenLaneMembership`:
   - `previous = read_lanes_json(planning_dir)`. If it is `None` → `FrozenLaneMembership.empty()`. This is a first
     finalize; nothing else is read.
   - Resolve the read dir with `_mf._resolve_status_read_dir(...)`. On its resolver exceptions, raise
     `LaneMembershipFrozenError((MembershipConflict(reason="status_unreadable", wp_ids=(), recorded_lanes=(), remedy=remedy_for("status_unreadable", ())),))`
     and chain the cause.
   - `has_event_log(read_dir)` is false → `started = frozenset()` (absent log: nothing history-started, FR-007).
     Otherwise `started_wp_ids(read_events(read_dir))`. A `StoreError` (malformed JSON line), `UnicodeDecodeError` or
     `OSError` → the same `status_unreadable` refusal.
     **Read-only: never call `materialize()`.**
   - `tipped = recorded_tip_branches(owned.repository_root if owned else repo_root)`, but only when `previous` has at
     least one code lane with no history-started member. Skip the git call otherwise.
   - Return `build_frozen_membership(previous, started=..., tipped_branches=..., present_wp_ids=frozenset(wp_frontmatters), eligible_wp_ids=eligible_wp_ids)`.
2. Import status helpers through the `specify_cli.status` facade (`has_event_log`, `read_events`, `StoreError`).
3. Unit tests in `tests/specify_cli/cli/commands/agent/test_finalize_frozen_lane_preflight.py`, monkeypatching the
   seams:
   - no previous manifest → empty, with no status read;
   - absent log → no history-started;
   - `StoreError` → `status_unreadable`;
   - resolver error → `status_unreadable`;
   - the tip call is skipped when every code lane has a started member;
   - retired = present − eligible.

### Subtask T011: Preflight before the first status write

**Steps**:
1. Add `_preflight_frozen_lane_membership(planning_dir, repo_root, mission_slug, meta, target_branch, *, lane_wp_manifests, lane_wp_dependencies, lane_wp_bodies, wp_frontmatters, eligible_wp_ids, all_canceled, owned=None) -> FrozenLaneMembership`
   in `mission_finalize_lanes.py`:
   - resolve topology via `topology_from_meta(meta or {}, planning_dir)`. For `SINGLE_BRANCH` → return `empty()`;
   - gather the evidence (T010). If it is empty → return it;
   - otherwise dry-run `compute_lanes(dependency_graph=lane_wp_dependencies, ownership_manifests=lane_wp_manifests,
     mission_slug=..., target_branch=..., wp_bodies=lane_wp_bodies, mission_id=<from meta>,
     previous_lanes=read_lanes_json(planning_dir), topology=topology, mission_branch=<from meta>, frozen=frozen)`;
   - **no write**; `LaneMembershipFrozenError` propagates. Skip the dry run when there are no lane inputs
     (`not (lane_wp_manifests and lane_wp_dependencies)`): the existing empty-input guard owns that case. Return the
     frozen membership.
2. In `finalize_tasks` (`mission_finalize.py`):
   - set `frozen: FrozenLaneMembership | None = None` before the existing `if not refresh_planning_commit:` block
     (~L1298);
   - **inside** that block, before `_emit_tasks_started`, assign `frozen = _preflight_frozen_lane_membership(...)`.

   That adds no branch (`finalize_tasks` is at complexity 14), skips refresh runs, and covers `--validate-only`. Use
   `frozenset(own_gates.eligibility.eligible_wp_ids)` (it is a tuple) and `own_gates.wp_frontmatters`.

   The function is near the complexity limit. If adding the call pushes `finalize_tasks` over 15, move the
   call into an existing helper phase rather than inlining more branches. Check with `ruff check --select C901`.
3. Re-export `_preflight_frozen_lane_membership` and `_gather_frozen_lane_membership` from `mission_finalize.py`, in
   the existing re-export block style.

### Subtask T012: Thread `frozen` into the write path and the validate-only preview

**Steps**:
1. Add `frozen: FrozenLaneMembership | None = None` as a keyword:
   - on `_run_commit_pipeline` (`mission_finalize_commit.py`);
   - on `_compute_and_write_lanes` (`mission_finalize_lanes.py`), passing it to `compute_and_write_lanes(..., frozen=frozen)`.

   Pass it from `finalize_tasks`. The defaults keep historical monkeypatch seams in `test_mission_finalize_phases.py`
   working.
2. Add `LaneMembershipFrozenError` handling in `_compute_and_write_lanes`: let it propagate (do **not** add a local
   except arm). The terminal renderer handles it (T013). This is defence in depth: the preflight already raised for
   any conflict.
3. Validate-only preview (`_emit_validate_only_report` in `mission_finalize_bootstrap.py` ~L736-746): pass
   `previous_lanes=read_lanes_json(planning_dir)` and `frozen=frozen`, so preview lane ids match a real run. Thread
   `frozen` in as a keyword (default `None`). This intentionally changes the preview's `lane_ids` for missions that
   already have lanes (squad finding 13); note it in the commit message.

### Subtask T013: Render `LANE_MEMBERSHIP_FROZEN`

**Steps**:
1. In `_emit_finalize_error_with_revert_note` (`mission_finalize_commit.py`), mirror the `LaneDependencyCycleError`
   branch:
   - JSON: `error_payload.update({"error_code": error.error_code, "reason": error.reason, "conflicts": [c.to_dict() for c in error.conflicts], "next_step": error.next_step})`;
   - console: for each conflict print `  {reason}: {WP (lane), …}`, then `  Remedy: {remedy}`.

   Keep the existing keys and order for every other error byte-identical (C-003).
2. Verify the `--validate-only` path renders through the same handler (it is inside the same try).

### Subtask T014: End-to-end refusal-path tests (+ WP01's red tests go green)

**Steps**:
1. Create `tests/integration/test_refinalize_frozen_lane_refusals.py` (`integration`, `git_repo`). Reuse WP01's fixture
   helpers by importing them from `tests/integration/test_refinalize_keeps_started_lanes.py`. If they are private,
   copy the minimal fixture and record the duplication for a follow-up; do not edit WP01's file. Drive the real CLI
   entry point in each test:
   - **US2 AS2:** `--validate-only` refuses with the same code and reason, and nothing is written.
   - **US2 AS3:** a removed started WP. Delete WP02's task file and its `tasks.md` section, commit, re-finalize →
     `started_wp_removed`; the remedy mentions `move-task` and "without clearing".
   - **US2 AS4:** a kind change. Set the started WP02's `execution_mode: planning_artifact` and its owned files under
     `kitty-specs/` → `started_wp_kind_changed`.
   - **US2 AS5:** a malformed status log. Append a corrupt line to `status.events.jsonl` and commit →
     `status_unreadable`.
   - **US2 AS6:** an absent status log with an existing `lanes.json` (delete `status.events.jsonl` and commit) → the
     run proceeds (exit 0). This is the positive control for AS5.
   - **US2 AS7:** after a `started_lanes_collapsed` refusal, apply the remedy (move the shared path into a new WP03
     that depends on both), and the next re-finalize succeeds. Both started WPs keep their lanes.
   - **Edge:** a started WP rejected back to `planned` (`in_progress → planned` via `emit_status_transition`) still
     keeps its lane under the collapsing amendment.
   - **SC-003:** for every refusal test, `lanes.json`, `status.events.jsonl`, `tasks.md`, `meta.json` and the WP files
     are byte-identical, and HEAD is unchanged.
2. Run WP01's `tests/integration/test_refinalize_keeps_started_lanes.py` and the two boy-scouted tests: they must
   now pass, **unchanged**.
3. **Performance spot-check (NFR-001):** time `finalize-tasks` on a 30-WP fixture before and after (median of 5). Record
   the numbers in the WP review notes; no committed perf test is required.

## Definition of Done

- WP01's red tests pass unchanged, and every new test passes.
- **Blast radius green:**
  - `tests/specify_cli/cli/commands/agent` (finalize/mission files);
  - `tests/lanes`, `tests/status`, `tests/specify_cli/lanes`;
  - `tests/cli -k "finalize or lanes"`, `tests/integration -k finalize`;
  - `tests/tasks/test_finalize_tasks_lanes_disjoint_fan_in.py`, `tests/unit/migration/test_mission_state_lanes_rebuild.py`.
- **Gates green:**
  - `tests/architectural/test_status_module_boundary.py`
  - `test_cold_import_status_boundary.py`
  - `test_finalize_refresh_pin_authority.py`
  - `test_json_contract_enumeration.py`
  - `test_no_write_side_rederivation.py`
  - `test_status_events_writes_gate.py`
  - `test_cli_error_surface_seam.py`
  - `test_no_worktree_name_guess.py`
  - `test_layer_rules.py`
  - `test_dead_symbol_allowlist_contract.py`

  If `test_json_contract_enumeration.py` enumerates finalize JSON keys, add the new refusal keys the way that gate
  expects; never by an allowlist entry (C-004).
- Existing finalize refusal texts and codes are unchanged (C-003). `implement.py` and `mission_creation.py` are
  untouched (C-005).
- `ruff check` / `ruff format --check --force-exclude` / `mypy` are clean on the changed files. Every touched function
  has complexity ≤ 15.
- Each subtask is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.

## Risks

- **Preflight after a status write:** if anything writes status before the preflight, the refusal is no longer
  write-free. Assert byte-identity of `status.events.jsonl` in the tests.
- **`finalize_tasks` complexity:** keep the new call in a helper.
- **Monkeypatch seams:** add new parameters as keywords with defaults; keep re-exports.
- **`--refresh-planning-commit`:** it must skip the preflight. Run `test_issue_4141_refresh_planning_commit.py`.

## Reviewer Guidance

- Confirm the preflight sits before `_emit_tasks_started`, and that the validate-only path hits it.
- Confirm absent-log vs malformed-log handling matches FR-007 exactly, with a test for each.
- Confirm the JSON envelope matches `contracts/lane-membership-frozen.md` and the remedies are non-destructive.
- Confirm no `materialize()` call is added on the read path.
