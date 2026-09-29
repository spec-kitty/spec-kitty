---
work_package_id: WP03
title: WP commit attribution capture
dependencies: []
requirement_refs:
- FR-001
- C-001
- C-002
- NFR-002
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T15:38:16.363341+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Capture (#5046)
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/lane_head.py
- tests/status/test_lane_head.py
- tests/status/test_cutover_eligibility.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/status/lane_head.py
- src/specify_cli/status/transition_pipeline.py
- src/specify_cli/status/emit.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/status/cutover_eligibility.py
- src/specify_cli/status/__init__.py
- tests/status/test_lane_head.py
- tests/status/test_transition_pipeline.py
- tests/status/test_cutover_eligibility.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – WP commit attribution capture

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

Every persisted lifecycle transition of a WP that maps to a non-planning execution lane whose branch exists carries `policy_metadata["lane_head"]` = that lane branch's head SHA at persist time (FR-001, contract C1). Stamping is best-effort: it never blocks, fails, or reorders a transition. No `spec_kitty_events` change (C-001). One authority: the status event log (C-002).

## Context & Constraints

- Plan D-1; research R-2, R-3, R-4, R-10 (B1, B5).
- `StatusEvent.policy_metadata: dict[str, Any] | None` — `src/specify_cli/status/models.py:363` (serialize `:385`, parse `:432`); already carries claim metadata (`status/emit.py:255 build_claim_policy_metadata`).
- The one seam: `prepare_transition` (`src/specify_cli/status/transition_pipeline.py:177`), which builds the event at `:313-331` via `_emit.build_status_event(..., policy_metadata=request.policy_metadata)`. Its four callers: `status/emit.py:944` (flat single), `:1051` (`_prepare_batch`), `coordination/status_transition.py:1528` (transactional single), `:1836` (`_prepare_batch_in_transaction`). The funnel is enforced by `tests/architectural/test_no_legacy_status_emit_callers.py`.
- **Purity (B1, binding):** the pipeline module promises "zero writes, zero locks, zero git" (`transition_pipeline.py:26-28`) and is AST-pinned (`tests/status/test_transition_pipeline.py:369-380`). Therefore: `lane_head_probe: LaneHeadProbe | None = None` where **`None` means no stamp** — the pipeline never imports or defaults to git code. The shells inject the real probe.
- Cold-import boundary: `tests/architectural/test_cold_import_status_boundary.py` — import `lanes`/git helpers function-locally.
- Do not touch `src/specify_cli/consolidation/**` (WP04/WP05) or `tests/terminus/**`.

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace from `spec-kitty agent action implement WP03 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T011 – `status/lane_head.py`

- **API**:
  ```python
  LANE_HEAD_KEY: Final = "lane_head"

  class LaneHeadProbe(Protocol):
      def __call__(self, *, repo_root: Path, mission_slug: str, wp_id: str) -> str | None: ...

  def probe_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str) -> str | None: ...
  ```
- **Algorithm** (mirror `src/specify_cli/lanes/for_review_gate.py:81 _resolve_lane`): resolve lanes.json from the PRIMARY partition via `placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)`, `read_lanes_json` (`lanes/persistence.py:81`; `None` → return `None`; `CorruptLanesError` → `None`), `manifest.lane_for_wp(wp_id)` (`lanes/models.py:155`; unknown → `None`), skip `is_planning_lane(lane)` → `None`, `lane_created_branch(manifest, lane_id)` (`lanes/compute.py:65`), then `git rev-parse --verify --quiet refs/heads/<branch>` from `repo_root` via `specify_cli.core.git_ops.run_command` (the public helper `consolidation/git_probes.py` already uses; there is no public `run_git`). Any exception or non-zero exit → `None` (log at debug).
- **repo_root**: callers pass the canonical root (see T013); never `feature_dir` (coord worktree under coord topology).
- Put `LANE_HEAD_KEY` here **and re-export it from the facade `src/specify_cli/status/__init__.py`** (owned by this WP): SR-2 of `tests/architectural/test_status_module_boundary.py` forbids `specify_cli.status.<submodule>` imports outside the status package, so WP04 must import `from specify_cli.status import LANE_HEAD_KEY`. CLAUDE.md's "changes to `__init__.py` require a version bump" refers to `src/specify_cli/__init__.py` (agent choices); nothing enforces it for the status facade — record this decision in the activity log. Run `tests/architectural/test_no_dead_symbols.py` (the key must have a caller — WP04 provides it; until then the gate may flag it: coordinate by landing WP04 before the mission's final gate run).

### Subtask T012 – Stamp in `prepare_transition`

- Add keyword `lane_head_probe: LaneHeadProbe | None = None` (type-only import of the Protocol under `TYPE_CHECKING`).
- Before `build_status_event`: if `lane_head_probe is not None`, call it with `repo_root=<request.repo_root or the value the caller passed>`, `mission_slug`, `wp_id=request.wp_id`; if it returns a SHA, `policy_metadata = {**(request.policy_metadata or {}), LANE_HEAD_KEY: sha}`. Otherwise leave `request.policy_metadata` untouched (byte-identical events when no probe / no stamp).
- `prepare_transition` has no repo-root keyword today; `TransitionRequest.repo_root` (`status/models.py:872`) may be `None`. Add a `repo_root: Path | None = None` keyword the shells fill — the pipeline must not compute it.
- Keep the function ≤ complexity 15 (extract `_stamped_policy_metadata(...)`).

### Subtask T013 – Inject at the four call sites + pin

- In `status/emit.py` (`:944`, `:1051`) and `coordination/status_transition.py` (`:1528`, `:1836`) pass `lane_head_probe=probe_lane_head` (function-local import) and the canonical repo root: `request.repo_root`, else — in `emit.py` — `workspace.root_resolver.resolve_canonical_root` imported function-locally as `emit.py:349` already does (status must NOT import `coordination`), and in `status_transition.py` its own `_repo_root_for_feature` (`:104`).
- Pin test (in `tests/status/test_lane_head.py`): an **AST** checker (not grep — `emit.py:36` mentions `prepare_transition(` in a docstring) asserting every `prepare_transition(...)` call in `src/specify_cli/` passes `lane_head_probe=` whose value is the **name `probe_lane_head`** (not `None`, not a lambda). Floor: exactly 4 call sites today — assert the count. Self-mutation checks (architectural-gate-non-vacuity): feed synthetic sources (a) lacking the kwarg and (b) with `lane_head_probe=None`, and assert the checker reports both.

### Subtask T014 – Campsite: `cutover_eligibility` [P]

- `src/specify_cli/status/cutover_eligibility.py:133-137,156` treats any non-empty `policy_metadata` as runtime-state evidence; a `lane_head` stamp would make every mission look runtime-bearing. Re-key the check on the claim keys (`shell_pid` / `agent`, see `status/reducer.py:164` and `emit.py:255`) and fix the docstring. Add `tests/status/test_cutover_eligibility.py` covering: claim metadata → detected; `lane_head`-only metadata → not detected; empty → not detected. Check `tests/specify_cli/cli/commands/test_cutover_guard.py` still passes.

### Subtask T015 – Tests and gates

- `tests/status/test_lane_head.py` (git-backed, `tmp_path` repo with a real `lanes.json` written via the lanes persistence API):
  - stamped: WP in a lane with an existing branch → SHA equals `git rev-parse`.
  - no lanes.json / corrupt lanes.json / WP not in manifest / planning lane / branch missing → `None`.
  - end-to-end through `emit_status_transition` (flat shell) and the transactional shell: the persisted event (read back with `read_events`) carries `lane_head`; caller-supplied claim `policy_metadata` keys are preserved alongside it.
  - a transition with no stamp persists byte-identically to today (compare against an event built with the probe injected as `lambda **_: None`).
- `tests/status/test_transition_pipeline.py`: extend for the new kwarg (probe called once with the right args; `None` → no stamp; purity pin still green).

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_lane_head.py tests/status/test_transition_pipeline.py tests/status/test_cutover_eligibility.py tests/status/test_emit.py tests/status/test_emit_backward_transition.py tests/status/test_emit_durability.py tests/status/test_emit_fanout_after_adapter.py -q
uv run --frozen pytest tests/specify_cli/coordination/test_status_transition.py tests/specify_cli/coordination/test_status_transition_adoption.py tests/specify_cli/coordination/test_status_transition_degrade.py tests/specify_cli/cli/commands/test_cutover_guard.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_status_emit_callers.py tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_status_events_writes_gate.py tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_2093_authority_invariant.py tests/architectural/test_execution_context_parity.py tests/architectural/test_no_dead_symbols.py -q
uv run --frozen ruff check src/specify_cli/status src/specify_cli/coordination/status_transition.py tests/status && uv run --frozen ruff format --check src/specify_cli/status src/specify_cli/coordination/status_transition.py tests/status
uv run --frozen mypy src/specify_cli/status/lane_head.py src/specify_cli/status/transition_pipeline.py src/specify_cli/status/cutover_eligibility.py
```

## Risks & Mitigations

- A git call in the status lock on every transition: exactly one `rev-parse`, no `for-each-ref`.
- `test_no_dead_symbols.py`: do not export unused aliases in `__all__`.
- Hosted relay: the Zeitgeist bridge reads only named fields (`status/zeitgeist_bridge.py:161-193`) — confirm no test asserts the full `policy_metadata` dict of a relayed moment.

## Review Guidance

- Confirm `transition_pipeline.py` still imports no git/subprocess (pin green) and `None` = no stamp.
- Confirm the four call sites pass the probe and the pin test has a numeric floor and a self-mutation check.
- Confirm stamping failure paths never raise.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
