---
work_package_id: WP05
title: Explicit placement seam for artifact presence; bootstrap reads the door
dependencies:
- WP04
requirement_refs:
- C-002
- FR-001
- FR-006
- FR-010
- FR-011
- NFR-003
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
phase: Phase 2 - Reads move onto the door
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/next/test_artifact_presence_seam_param.py
- tests/runtime/next/test_bootstrap_read_door.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_composition.py
- src/specify_cli/acceptance/non_wp_runtime.py
- tests/runtime/next/test_artifact_presence_seam_param.py
- tests/runtime/next/test_bootstrap_read_door.py
- tests/next/test_runtime_bridge_blocked_paths.py
- tests/runtime/test_bridge_decide_next.py
- tests/integration/test_owned_next_runtime.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Explicit placement seam for artifact presence; bootstrap reads the door

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Two sites use the status directory only as a **key**:
- `decision._with_guard_failure_paths` (owned arm) passes it to `guard_failure_artifact_paths`;
- `runtime_bridge_io._artifact_presence_seam` maps it back to a placement seam by comparing it with `read_dir(STATUS_STATE)`.

`_dn_bootstrap`'s owned arm picks `feature_dir = status_dir if is_dir() else primary`, which feeds `ctx.feature_dir` into progress and guards. This WP passes the seam explicitly (DM-3, Decision Moment `01M73HKTCYP1WB4VEQF39VEC74`) and makes bootstrap read status through the door.

Done when:
- `gather_artifact_presence` / `guard_failure_artifact_paths` / `artifact_search_paths` take `seam: PlacementSeam | None`. With `None`, they resolve every artifact to the supplied directory, today's fallback when no seam was recognised. `_artifact_presence_seam` is deleted.
- Every caller passes its seam: `runtime_bridge.py:275`, `runtime_bridge_composition.py:495`, `acceptance/non_wp_runtime.py:89`, `decision.py:452`. The last is an **out-of-map edit** in WP03's file; record it with one line in `add-history`.
- Reported guard-failure paths and artifact-presence answers are unchanged on every existing fixture (characterisation first, T023).
- `_dn_bootstrap`:
  - takes its Mission directory identity from `PRIMARY_METADATA`;
  - its board/progress comes from the door, read **after** the decision-log wrap, so advancing `next` on an empty or unmaterialized coordination worktree reports the real progress (FR-001; red-first);
  - the owned O8 refusals are unchanged (`OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` blocked decision; `test_owned_next_runtime.py:301-374`, `test_owned_lifecycle_acceptance_next.py:276`) (FR-006).
- Gate: 3 entries removed (`_with_guard_failure_paths`, `_artifact_presence_seam`, `_dn_bootstrap`); floor 38 → 34 (`_artifact_presence_seam` has 2 hits); baseline 37 → 34. The gate files are an out-of-map edit (owned by WP04).

## Context & Constraints

- Spec FR-001 (advancing progress), FR-006, FR-010, FR-011; plan IC-04; research R-5; data model § placement seam handed to artifact presence.
- Evidence: `research/code-grounding.md` §0 (sites), §1 (`ctx.feature_dir` consumers), §3 (owned refusals and the **hazard**: the door raises `WorktreeRegistryUnavailable` / `StatusSurfaceRefUnreadable`, which `_is_owned_coordination_unavailable` does not map, so read the door **after** the wrap, or map those codes); `research/architecture-options.md` §2 (why a naive `PRIMARY_METADATA` swap is a regression: coordination-kind artifacts would resolve in the primary dir).
- End-to-end probe: `research/repro/advancing_cells.py <spec-kitty> MATERIALIZED EMPTY UNMATERIALIZED`. Today advancing empty and unmaterialized show weighted 0.0.
- Out of scope: `_resolve_runtime_feature_dir` (non-owned identity, not an allowlist key); `committed_authority` (`has_event_log` on `ctx.feature_dir`), unless it reads a wrong source after this change. If it does, report it rather than widen scope.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP05 --agent <name> --mission runtime-status-read-door-01M73HHB` (it depends on WP04).

## Subtasks & Detailed Guidance

### Subtask T023 – Characterisation of guard paths and presence

- **Steps**: new `tests/runtime/next/test_artifact_presence_seam_param.py`. For non-owned single_branch, non-owned coord (materialized), owned single_branch and owned coord (materialized), record today's `guard_failure_artifact_paths(...)` and `gather_artifact_presence(...)` output for a fixed set of guard failures and artifact names: spec.md, plan.md, tasks.md, a coord-kind artifact, and a custom filename. Commit it green on the base, before any move.

### Subtask T024 – `seam=` on the presence API; delete the reverse map

- **Steps** in `runtime_bridge_io.py`:
  1. Add keyword `seam: PlacementSeam | None = None` to `artifact_search_paths`, `gather_artifact_presence`, `guard_failure_artifact_paths`; thread it to `_ArtifactPresenceHomes(feature_dir, seam)`.
  2. Delete `_artifact_presence_seam` and `_PRESENCE_SEAM_DEGRADES` if they become unused.
  3. A degraded seam read (the exceptions `_PRESENCE_SEAM_DEGRADES` lists) still falls back to the supplied directory **per artifact**, as today.
- **Notes**: keep complexity ≤ 15; T023 must stay green.

### Subtask T025 – Callers pass the seam

- **Steps**: each caller builds or already holds the right seam:
  - non-owned: `placement_seam(repo_root, mission_slug)`;
  - owned: `placement_seam(repo_root, mission_slug, owned=owned)`.

  Pass it. Edit `decision._with_guard_failure_paths` (out-of-map): it no longer reads `artifact(STATUS_STATE)`. Its `feature_dir` for mission-type lookup becomes `PRIMARY_METADATA`'s read dir, and the seam goes to `guard_failure_artifact_paths`. T023 stays green.

### Subtask T026 – Bootstrap reads the door after the wrap (red-first)

- **Steps**:
  1. Red test in `tests/runtime/next/test_bootstrap_read_door.py`: for a non-owned coordination Mission (WP01 planned, WP02 for_review, committed), an advancing decision through `decide_next_via_runtime` on **empty** and **unmaterialized** worktrees reports weighted progress 30.0 and the same counts as the materialized control. Commit it red.
  2. `_dn_bootstrap` owned arm: the Mission directory comes from `mission_context.artifact(PRIMARY_METADATA).read_dir`, and the `artifact(STATUS_STATE)` read is removed. Keep the `ActionContextError` → `_owned_coordination_unavailable_decision` mapping exactly.
  3. Progress (`runtime_bridge.py:539`): compute from `board_status_from_surface(resolve_status_read(repo_root, slug, owned=owned))`, called **after** the decision-log wrap (`:505-507`), so the worktree it may materialize is already there. Map `WorktreeRegistryUnavailable` / `StatusSurfaceRefUnreadable` for owned calls to the same typed blocked decision as the wrap's failures (hazard above), and pin it with a test that injects a `git worktree list` failure (pattern: `test_owned_lifecycle_acceptance_next.py:276`).
  4. Re-pin stale mechanism pins: `tests/next/test_runtime_bridge_blocked_paths.py` (4× `patch.object(rb, "_compute_wp_progress")`; keep working if the name is still called), `tests/runtime/test_bridge_decide_next.py` (`_dn_bootstrap` direct calls and monkeypatch), `tests/integration/test_owned_next_runtime.py:376` (monkeypatches `mission_context_for` for any owned call; re-pin to the new owned read). List each in `add-history`.

### Subtask T027 – Gate

- **Steps** (out-of-map edit of WP04's gate files): delete
  - `src/runtime/next/decision.py::_with_guard_failure_paths::artifact(STATUS_STATE)`
  - `src/runtime/next/runtime_bridge_io.py::_artifact_presence_seam::read_dir(STATUS_STATE)`
  - `src/runtime/next/runtime_bridge.py::_dn_bootstrap::artifact(STATUS_STATE)`

  Then set `_LIVE_HIT_FLOOR = 34`, change `_baselines.yaml` `legacy_read_allowlist` from 37 to 34, and extend the justification with `Shrunk 37 -> 34 by runtime-status-read-door WP05`. Use the same commit as the move.

### Subtask T028 – Run suites

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/runtime/next/test_artifact_presence_seam_param.py tests/runtime/next/test_bootstrap_read_door.py tests/next/test_guard_failure_paths_3883.py tests/runtime/test_analyze_step.py tests/runtime/test_artifact_presence_placement.py tests/next/test_runtime_bridge_blocked_paths.py tests/runtime/test_bridge_decide_next.py tests/next/test_next_concurrency.py tests/integration/test_owned_next_runtime.py tests/integration/test_owned_lifecycle_acceptance_next.py tests/next/test_next_command_integration.py tests/runtime/next/test_board_query_read_door_7507.py`
- Plus the acceptance non-WP runtime tests: `grep -rl non_wp_runtime tests/ --include=*.py`, run those.
- Gates: `tests/architectural/test_status_read_single_door.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py`
- `ruff check`, `ruff format --check --force-exclude`, `mypy` on every changed source file.

## Risks & Mitigations

- **Guard paths drift** (coordination-kind artifacts resolving in the primary dir). T023 is the guard.
- **O8 typed refusal lost** if the door read moves before the wrap. Order matters; T026 step 3 pins it.
- **`ctx.feature_dir` consumers** (`committed_authority`, `_should_advance_wp_step`) see a different directory. Run their suites; any change in output is a stop-and-report.

## Review Guidance

- T023 committed green before the refactor; T026's test committed red before its fix.
- The out-of-map edits (`decision.py`, the gate files) are each recorded with a rationale.
- O8 pins unchanged and green.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP05 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP05 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
