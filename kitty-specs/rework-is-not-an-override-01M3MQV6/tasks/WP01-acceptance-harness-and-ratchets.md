---
work_package_id: WP01
title: Acceptance harness and ratchet controls
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-008
planning_base_branch: issue-5196-rework-is-not-an-override
merge_target_branch: issue-5196-rework-is-not-an-override
branch_strategy: Planning artifacts for this mission were generated on issue-5196-rework-is-not-an-override. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5196-rework-is-not-an-override unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rework-is-not-an-override-01M3MQV6
base_commit: 59502db6825305687ecd04cc4262a05cdca0c52c
created_at: '2026-09-28T20:15:55.297910+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation (acceptance harness)
history:
- at: '2026-09-28T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/_rework_loop_harness.py
- tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/agent/_rework_loop_harness.py
- tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Acceptance harness and ratchet controls

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE — no heavy full suites during the mission

During implement and **every WP review** (by you AND every implementer/reviewer subagent you dispatch), NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave the broad sweeps to the END of the mission (closeout, and only the targeted set listed below) or to CI. This is the internal-pack directive NO_FULL_HEAVY_SUITES_IN_MISSION.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

This mission (#5196, epic #3044) makes the ordinary review loop (reject → rework → resubmit → approve) work without `--force`, and stops it from recording fake arbiter overrides. WP01 builds the **shared test harness** that WP02 and WP03 import, plus **ratchet tests**. Ratchets pin behaviour that is already correct on the base and must stay correct.

Done when:
- `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py` exists. It drives a real LANES (non-coord) mission through the real `move-task` Typer app, one hop at a time, with three identities on **distinct tools**.
- `tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py` passes **on the planning base (no product change in this WP)** and covers:
  - T003: a genuine for_review-source arbiter override lights all five probes (positive control);
  - T004: an unrelated agent is refused on an occupied slot and on an `in_review` verdict, with 0 events appended;
  - T005: `agent action implement` rework is unforced, with no override;
  - T006: an intervening annotation does not hide a genuine override.
- WP01 changes no `src/` file.

## Context & Constraints

- Read first: `kitty-specs/rework-is-not-an-override-01M3MQV6/spec.md`, `plan.md`, `research.md` (R-06, R-07), `contracts/*.md`.
- Charter `.kittify/charter/charter.md`: ATDD-first, realistic test data, non-vacuity (`spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity`).
- **Constraints**:
  - C-001: do not edit `tests/integration/**`. You may *read* it for patterns (e.g. `tests/integration/test_review_durability_matrix.py::_run_cell`).
  - Do not edit golden/snapshot files under `tests/specify_cli/**`.
  - C-007: identities must differ by **tool**. The ownership guard compares tool keys via `_actor_key` (`src/specify_cli/status/work_package_lifecycle.py:103`).
- **Base pattern to adapt**: `tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py` (`_build_mission`, `_move`). Copy the patterns you need; do **not** import from it and do not edit it. **Do not reproduce its flaw**: it seeds rework hops with `at_day="2026-01-02"`, which orders them *before* the real rejection. Only seed `GENESIS → PLANNED`, and drive every other hop through the CLI.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: `issue-5196-rework-is-not-an-override`
- **Merge target branch**: `issue-5196-rework-is-not-an-override`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP01 --agent <you>`. Inside a lane worktree, run tests with `uv run --frozen` or the worktree's own interpreter; a bare `python` imports the primary checkout's `src`.

## Subtasks & Detailed Guidance

### Subtask T001 – Real-CLI rework-loop harness

- **Purpose**: one reusable fixture that makes the review loop testable through the production entry point.
- **File**: `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py` (new, ~200 lines). This is a helper module, not a test module; the leading underscore keeps pytest from collecting it.
- **Contents**:
  - Identity constants, production-shaped and tool-distinct:
    - `IMPLEMENTER = "claude:opus:implementer-ivan:implementer"`
    - `REVIEWER = "codex:gpt-5:reviewer-renata:reviewer"`
    - `THIRD = "gemini:2.5-pro:python-pedro:implementer"`
  - A realistic mission slug, e.g. `rework-loop-fixture-01M3MQZZ` (a mid8-suffixed shape).
  - `build_mission(tmp_path, monkeypatch) -> ReworkMission`, a small dataclass with `repo`, `feature_dir`, `mission_slug` and `wp_dir`:
    - Build a git repo with `.kittify/config.yaml` (`auto_commit: false`, `protection: protected_branches: []`), `write_single_lane_manifest(feature_dir, wp_ids=("WP01",))`, `meta.json` with `status_phase: "1"`, `tasks.md`, and `tasks/WP01-core.md` with frontmatter (`agent:` unset or the implementer).
    - Seed only `GENESIS → PLANNED` via `append_event`.
    - Apply the same monkeypatches as the base pattern (`locate_project_root`, `_validate_ready_for_review`, `get_mission_type`).
  - `move(m, wp, to, agent, *extra) -> Result`: a `CliRunner().invoke(tasks_app, ["move-task", wp, "--to", to, "--mission", slug, "--agent", agent, *extra])`.
  - `drive_to_for_review(m, agent=IMPLEMENTER)`: `planned → claimed → in_progress → for_review` as separate CLI moves. Assert `exit_code == 0` on each and **never** pass `--force`.
  - `reject(m, route, reviewer=REVIEWER, cycle=1)`, where `route ∈ {"for_review_to_planned", "in_review_to_planned", "in_review_to_in_progress"}`:
    - Write a feedback file and use `--review-feedback-file`.
    - For the `in_review_*` routes, first move `for_review → in_review` as the reviewer.
    - **On the base**, some routes need `--force` to get the rejection or review claim through, so accept an `allow_force: bool` parameter. The rejection step itself is setup, not the thing under test.
    - Return the index of the rejection event in the log.
  - `events(m) -> list[dict]`: parse `status.events.jsonl` (raw JSON lines, all event types).
  - `lane_events_after(m, idx)`: the lane-transition events strictly after index `idx`.
  - `forced_after(m, idx) -> int`: the count of lane events after `idx` with `force: true`. This is SC-001's measure. The `→ planned` rejection edges are auto-forced (the #3307 wire contract), so the count starts strictly after the rejection. `in_review → in_progress` is `force: false`. Define `idx` over **raw** log lines (annotations included), and use the same indexing in `lane_events_after`.
- **Parallel?**: no (T002–T006 import it).
- **Notes**: keep mypy-clean type hints. Keep helper functions small (cc ≤ 15).

### Subtask T002 – Five override probes + artifact lister

- **Purpose**: "no override" must be proven by **every** surface that can show one. A blind probe proves nothing.
- **File**: `_rework_loop_harness.py`.
- **Implement** `override_probes(m, wp="WP01", move_output: str = "") -> dict[str, bool]`, with each value True iff that surface shows an arbiter override:
  1. `raw_log_review_override`: any raw event (`InnerStateChanged`-type, however the store encodes it) whose review delta carries a complete `ReviewOverride` (`at`, `actor`, `wp_id`, `reason` all non-empty). Written by `persist_arbiter_decision` (`src/specify_cli/review/arbiter.py:378+`) via `_persist_review_artifact_override` (`src/specify_cli/cli/commands/agent/tasks_materialization.py:50-108`). Read the code to get the exact event shape.
  2. `reduced_overrides`: `get_arbiter_overrides_for_wp(...)` (`arbiter.py:~498`) returns a non-empty result.
  3. `forward_review_ref`: any lane event with `from_lane == "planned"` and a non-null `review_ref`. An arbiter-forward move copies the rejection's ref (`tasks_transition_core.py:~322`, `tasks_move_task.py:~3688`).
  4. `cli_marker`: `"Arbiter override recorded"` appears in `move_output` (`tasks_verdict_persistence.py:~1028`).
  5. `status_history`: the human output of `agent tasks status --mission <slug>` (invoke via the same Typer app, `["status", ...]`) contains the arbiter override history section or `rejected → overridden` (`tasks_status_cmd.py:622-642`).
- Also add `review_cycle_files(m) -> list[str]`, the sorted names of `review-cycle-*.md` under `tasks/WP01-*/`.
- **Notes**: if a probe needs `st.json_output` vs human output, pick the human output for (5). Document in a docstring which production function each probe mirrors.

### Subtask T003 – Ratchet: genuine for_review-source override lights all five probes

- **Purpose**: the positive control that makes every "no override" assertion in WP02/WP03 non-vacuous (FR-005 [ratchet] half, SC-003).
- **File**: `tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py` (new).
- **Test**:
  1. `drive_to_for_review`.
  2. `reject(route="for_review_to_planned", allow_force=True)`.
  3. As the arbiter, run `move(m, "WP01", "approved", REVIEWER, "--force", "--note", "arbiter: rejection superseded by design decision")`.
  4. Assert exit 0 and that **all five** probes are True.
- **Marker**: match the base pattern (`pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`). The fast-tier marker gate does not govern this directory.

### Subtask T004 – Ratchet: unrelated agent refused

- **Purpose**: FR-006 / SC-004. Relaxing the guard (WP02) must not open it to unrelated agents.
- **Tests** (same file), all run without `--force`. Record the event count before each attempt, assert exit code ≠ 0 and `"Agent mismatch"` in the output, and assert the event count is unchanged:
  - (a) Implementer owns the WP in `in_progress` (after `planned → claimed → in_progress`). `THIRD` moves it `→ for_review`: refused.
  - (b) After a `for_review_to_planned` rejection that was forced on the base (slot = REVIEWER), `THIRD` moves `planned → claimed`: refused.
  - (c) REVIEWER holds `in_review` (claimed via the CLI). `THIRD` moves `in_review → approved`: refused. Then `THIRD` moves `in_review → planned` with feedback: refused.
- **Document by-design behaviour in a docstring, not a test**: after an `in_review → planned` rejection the slot is released (#4673), so an unclaimed WP is claimable by anyone.

### Subtask T005 – Ratchet: `agent action implement` rework stays unforced

- **Purpose**: FR-008. The canonical rework path already works unforced from `planned`, and it must stay that way. `start_implementation_status` (`src/specify_cli/status/work_package_lifecycle.py:~147`) leaves only its PLANNED branch unchecked; its CLAIMED and IN_PROGRESS branches call `_actors_compatible` against the latest transition actor. Test the `in_review_to_planned` route only. The `in_review → in_progress` route is a known residual (research R-07).
- **How**: reuse the in-process harness pattern of `tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py` (`workflow_repo` fixture, `_write_current_analysis_report`, `_mint_fake_worktree`, `workflow.app ["implement", ...]`). Copy the helpers you need into the harness; do not edit that file. Invoke the **production entry point** (the Typer app for `agent action implement WP01 --agent IMPLEMENTER`) on a WP rejected via `in_review_to_planned`. Assert success, no `force: true` event emitted by that invocation beyond what the production path documents, and all five probes False.
- **If the in-process `action implement` path needs worktrees/workspace plumbing that cannot be built in a unit-sized fixture**: call the production core `workflow_executor`'s implement entry, not `start_implementation_status` directly, and record the rationale in the test docstring and the Activity Log. Do not call a lower-level helper alone (the non-vacuity tactic's production-path rule).

### Subtask T006 – Ratchet: intervening annotation does not hide a genuine override

- **Purpose**: US3 scenario 3 [ratchet]. `read_events` returns lane transitions only, so a non-lane annotation between the rejection and the arbiter move must not matter.
- **Test**:
  1. Drive to `for_review`.
  2. Reject via `for_review_to_planned` (forced on the base).
  3. Append an annotation event with `specify_cli.status.emit_inner_state_changed(feature_dir, 'WP01', WPInnerStateDelta(note=...), actor=..., mission_slug=...)`. Use a note-only delta, never a `review` delta. No CLI writes annotation events (`add-history` writes the WP file).
  4. Force `planned → approved` with `--note`.
  5. Assert all five probes are True.

## Test Strategy

Commands (from the lane worktree):

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py -q   # neighbour sanity
uv run --frozen ruff check tests/specify_cli/cli/commands/agent/_rework_loop_harness.py tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py
uv run --frozen ruff format --check <same files>
uv run --frozen mypy tests/specify_cli/cli/commands/agent/_rework_loop_harness.py
```

All ratchets must be **GREEN on the base**. That is the point of a ratchet. If one is red on the base, stop: either the ratchet is mis-specified or you found a real defect. Report it in the Activity Log and to the orchestrator.

## Risks & Mitigations

- **Blind probe**: T003 must light all five probes. If a probe cannot see a real override, fix the probe before proceeding.
- **Timestamps**: never seed hops after `GENESIS → PLANNED`.
- **Same-tool identities** silently bypass the guard (C-007). Keep the three constants distinct by tool.

## Review Guidance

- Verify every hop after `planned` goes through `move-task` via the CLI; grep the harness for `append_event`.
- Verify T003 asserts all five probes True, and that probe (1) reads the raw log rather than the reduced snapshot.
- Verify no `src/` change, and that the ratchets pass on the planning base.
- Reviewer ≠ implementer. Respect the HARD RULE above.

## Hardening (post-tasks squad — binding)

- **Monkeypatch signature**: patch `locate_project_root` with `lambda *_a, **_k: repo`. The base pattern's zero-arg lambda crashes `agent tasks status`, and probe 5 then reads False silently.
- **`--agent` is mandatory**: `move()` must `assert agent`. Omitting `--agent` switches the ownership guard off (the actor is recorded as `user`, and a red test goes green for the wrong reason). Record every argv the harness sends, and expose `argv_log(m)` so tests can assert that `"--force"` never appears after the rejection. Wire `force` cannot tell you this, because `→ planned` is auto-forced.
- **Probe 5 liveness**: inside `override_probes`, assert `status.exit_code == 0 and "WP01" in status.output`.
- **Probe 1 strictness**: count only a `ReviewOverride` with **all four** fields non-empty. Every rejection writes an empty-field `review` clear delta.
- **Probe independence**: probes 2 and 5 share one source (`get_arbiter_overrides_for_wp`). Say so in the docstring; they do not count as independent evidence.
- **T004**: do NOT add a ratchet that a THIRD agent is refused on a `for_review` review act. After WP02 that is allowed by design. For "0 appended", count **raw** log lines, not lane events.

## Activity Log

- 2026-09-28T20:30:00Z – system – Prompt created.
