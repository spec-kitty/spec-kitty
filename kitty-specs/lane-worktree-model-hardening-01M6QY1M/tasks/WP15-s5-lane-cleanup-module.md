---
work_package_id: WP15
title: S5 - one lane-cleanup module behind a remover port; keep and report
dependencies:
- WP03
requirement_refs:
- FR-030
- FR-031
- FR-032
- FR-033
- FR-034
- FR-035
- FR-039a
- SC-005
- SC-012
- NFR-002
- NFR-004
- C-012
- C-017
- NFR-009
- NFR-008
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-worktree-model-hardening-01M6QY1M
base_commit: a4e342649cfe4936e89b4da0e8599dffc658ace2
created_at: '2026-11-06T10:13:58.589077+00:00'
subtasks:
- T091
- T092
- T093
- T094
- T095
- T096
- T097
- T098
- T099
phase: Phase 6 - S5 cleanup as the last consolidation step
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/lane_cleanup.py
- tests/consolidation/test_lane_cleanup_module.py
- tests/consolidation/test_lane_cleanup_kept_report.py
- tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/lane_cleanup.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/orchestrator_api/envelope.py
- docs/api/orchestrator-api.md
- src/specify_cli/cli/commands/mission_type.py
- tests/consolidation/test_lane_cleanup_module.py
- tests/consolidation/test_lane_cleanup_kept_report.py
- tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 - S5: one lane-cleanup module behind a remover port; keep and report

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP15 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP15 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S5 (#7280), the seam (does NOT wait for #7275):

- FR-030: one `consolidation/lane_cleanup.py` (pure `plan_lane_cleanup`, `apply(items, remover: LaneRemover) -> LaneCleanupReport`) shared by the consolidate executor, `orchestrator-api consolidate-mission` and `mission close --discard`; the three teardown copies and their branch-name drift become one.
- FR-031: order = coordination teardown first (S10 codes/exits unchanged), then lane legs, then the consolidation record cleared; nothing mutates afterwards.
- FR-032 / NFR-004 / SC-005: a lane the remover cannot remove after a verified landing is reported (lane, code, remedy, command), the record is cleared, exit 0.
- FR-033 / C-017: retention precedence unchanged; retained lanes reported "retained by policy", distinct from "kept".
- FR-034: a lane-tip ref is cleared only after a confirmed branch delete; a missing branch keeps its lane-tip ref.
- FR-035: `--resume` after a kill following cleanup's own commits completes without re-running the gate against deleted lane branches - proven by a red-first test written BEFORE any fix; if that test is green on the base, do not add the fix (record it).
- FR-039a / SC-012: `consolidate-mission` returns per-lane outcomes in `data.lane_cleanup` under the Mission's one contract bump: `CONTRACT_VERSION` 1.23.0 -> 1.24.0 (`orchestrator_api/envelope.py:~192`), which also carries WP13/WP14's topology fields (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).

## Context & Constraints

- Read: spec User Story 6, FR-030 to FR-039a, Edge Cases (`--abort` after partial cleanup, PR closed, coordination teardown refusal); `research.md` R-9; `data-model.md` §6 (exact types); `contracts/consolidate-cleanup-report.md`; `quickstart.md` §3; WP03's `upstream/adr-2026-11-06-1-amendment-draft.md` (vocabulary); CLAUDE.md "Consolidation & Preflight Patterns" (retention, rollback authority, `CoordMovedAfterLanding`).
- Sources to extract from: `phase_teardown.py:~868-1031` and `orchestrator_api/consolidation.py:~391-447`. The main-today remover calls the current guarded primitives exactly as now (no new raw `git worktree remove`, `branch -D` or `--force`; C-004 and its recorded interim exception, DM `01M6QY4B7P4T68TE7JE30FRJV6` s5-seam, until WP16 binds the port).
- **#7274 (NOT merged, S10)** shares `phase_teardown.py` and `run_state.py`: rebase onto it when it lands; keep coordination teardown codes intact (exit 1 / 75).
- **#7275 (NOT merged, S4)**: not needed here. The `LaneRemover` Protocol lets WP16 bind `guarded_landed_removal` later.
- Contract version tests to update: `tests/specify_cli/orchestrator_api/test_contract_version.py`, `tests/contract/test_orchestrator_api.py` (out-of-map edits; record them).
- `ConsolidationState.cleanup_started: bool = False` is additive and read with a default; ADR `2026-09-19-1` is NOT amended (not persisted across `--abort`).
- Rollback authority AST pin (`tests/consolidation/test_single_rollback_authority.py`) stays green.
- C-011 red-first. This WP is at the 9-subtask limit; keep each subtask tight.
- **Later recorded out-of-map hunks by WP20** (analysis G3/G4/G5/G8): WP20 (after you) edits `consolidation/phase_teardown.py` (land-before-coordination-teardown check), `consolidation/run_state.py` (`_is_coord_topology_mission` for a default Mission), `consolidation/executor.py` (the `target_feature_dir` PRIMARY anchor at `:446`; not the `lands_mission_branch` calls at `:456` / `:953`) and, only if its parity test needs it, `orchestrator_api/consolidation.py`. Keep your teardown order and S10 exit codes stable so WP20 rebases cleanly.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T091 - Red-first: drift pin and resume crash window

- `tests/consolidation/test_lane_cleanup_module.py::test_branch_name_drift_pinned`: `_created_lane_branch` vs `code_lane_branch_name` disagree on a fixture today; the module must use one answer.
- `test_resume_after_kill_in_cleanup_skips_regate` (FR-035): kill the process after cleanup's own commits (inject an exception after the first lane leg), then `consolidate --resume`; expected: completes, no gate re-run against deleted branches. Write it first; run it on the base; record red/green.

### Subtask T092 - Red-first behaviour tests

`tests/consolidation/test_lane_cleanup_kept_report.py` (through `spec-kitty consolidate`):

- `test_dirtied_lane_after_preflight_kept_exit_0_record_cleared` (SC-005, NFR-004)
- `test_retained_by_policy_distinct_from_kept` (paired with the no-retention fixture where lanes are removed, FR-033 ratchet)
- `test_missing_branch_keeps_lane_tip_ref` (FR-034)
- `test_abort_after_partial_cleanup_never_restores_lane_branches`
- `test_coord_teardown_refusal_exit_codes_unchanged`

`tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py::test_orchestrator_and_executor_same_lane_outcome` (per-lane outcome parity; `contract_version == "1.24.0"`).

### Subtask T093 - Extract the module

- `LaneCleanupOutcome`, `LaneCleanupItem`, `LaneCleanupResult`, `LaneCleanupReport`, `LandingProof` (`LocalTargetAtPass`, `RemoteRef`), `LaneRemover(Protocol)` per data-model §6.
- `plan_lane_cleanup(state, manifest, retention) -> tuple[LaneCleanupItem, ...]` pure; `apply(items, remover, *, landing, retention)` never raises after a verified landing: a guard refusal becomes `KEPT` with its code, remedy and command (`spec-kitty doctor workspaces --prune`), and recreate hint (`git branch <b> refs/spec-kitty/discarded/<b>`).
- `MainTodayRemover` wraps the current guarded primitives exactly.

### Subtask T094 - Teardown order and `clear_tip`

- `phase_teardown.py`: coordination triple -> lane legs (module) -> record clear. `clear_tip` only after the branch delete is confirmed (`git show-ref --verify` fails afterwards).

### Subtask T095 - `cleanup_started` marker (only if T091 was red)

- `state.py`: `cleanup_started: bool = False`; `run_state.py`: set before the first lane leg; on `--resume` with it set, skip the gate and go to cleanup; carry the PASS anchor over cleanup's own commits.

### Subtask T096 - Rendering and executor wiring

- `cli/commands/consolidate.py`: a "Lane cleanup" block (`Removed` / `Kept <code> <remedy>` / `Retained ... retained by policy`) per `quickstart.md` §3; `--json` per `contracts/consolidate-cleanup-report.md`. `executor.py`: call the module; exit 0 after a verified landing regardless of kept lanes.

### Subtask T097 - Orchestrator envelope and contract bump

- `orchestrator_api/consolidation.py` on the module; `data.lane_cleanup` list. `envelope.py`: `CONTRACT_VERSION = "1.24.0"`. `docs/api/orchestrator-api.md`: document `lane_cleanup` and the topology fields (`topology_source`, `topology_provisional` on `specify`; `topology_decision` on `tasks`) per `contracts/`.

### Subtask T098 - `mission close --discard` [P]

- `cli/commands/mission_type.py`: the discard path uses the module (landing proof: none; a discard keeps unabsorbed lanes per existing semantics - preserve them).

### Subtask T099 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/consolidation/test_lane_cleanup_module.py tests/consolidation/test_lane_cleanup_kept_report.py tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py -q
uv run --frozen pytest tests/consolidation tests/orchestrator_api tests/specify_cli/orchestrator_api tests/specify_cli/consolidation -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands -q -n auto --dist loadfile -k "consolidate or mission_type or close"   # out-of-matrix dir
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py tests/contract/test_orchestrator_api.py tests/specify_cli/orchestrator_api/test_contract_version.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

**NFR-008 (Linux and Windows).** The kept-report path must pass on the Linux and Windows CI lanes: a lane that cannot be removed (for example a file held open on Windows) is kept and reported with exit 0, never retried with `--force`; remedies print `spec-kitty` commands with platform-neutral paths. NFR-008's "off Linux, never removed without a process proof" is delivered by the WP16 guard binding; the interim remover adds no new removal path (C-004 recorded interim exception). `test_dirtied_lane_after_preflight_kept_exit_0_record_cleared` must not rely on POSIX-only behaviour; reviewers check the Windows lane result on the PR (`ci-windows.yml`).

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP15] ...**`, naming the trace file); the orchestrator appends them. Record whether FR-035's crash window was real.

## Risks & Mitigations

- Exit-code regressions for coordination teardown: dedicated test.
- One bump only: WP15 is the single owner of `CONTRACT_VERSION` 1.23.0 -> 1.24.0 and of the `docs/api/orchestrator-api.md` rows for every 1.24.0 field (its own `lane_cleanup` plus WP13's `topology_source` / `topology_provisional` and WP14's `topology_decision`, per `contracts/`). WP13 and WP14 depend on WP15 and only emit their fields; they do not edit `envelope.py` or the doc page (analysis F2). No release ships 1.24.0 without all three.

## Review Guidance

- One module, three callers; order coord -> lanes -> record; kept = exit 0; retained distinct; `clear_tip` after confirmed delete; red-first FR-035 evidence; 1.24.0 documented.

## Definition of Done

- T091-T099 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T091 T092 T093 T094 T095 T096 T097 T098 T099 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP15 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
