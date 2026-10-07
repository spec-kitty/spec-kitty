---
work_package_id: WP04
title: consolidate refuses on stale evidence and lanes (#5780)
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-002
- FR-008
- FR-015
- SC-001
- SC-004
- NFR-004
- C-002
- C-007
- FR-009
- FR-010
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:44:22.248420+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: Phase 3 - Gates
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/origin_gate.py
- tests/terminus/test_consolidate_sees_teammate_rejection.py
- tests/consolidation/test_origin_gate.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/origin_gate.py
- src/specify_cli/cli/commands/consolidate.py
- tests/terminus/test_consolidate_sees_teammate_rejection.py
- tests/consolidation/test_origin_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – consolidate refuses on stale evidence and lanes (#5780)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

`spec-kitty consolidate` runs the origin freshness check before any branch moves:
1. **Status evidence** (FR-001): when the remote's status evidence branch carries commits that change this Mission's `status.events.jsonl` and local lacks them → refuse `ORIGIN_STATUS_STALE`, exit 1, nothing moved, nothing pushed (also with `--push`).
2. **Approved lanes** (FR-002): when an approved code lane's remote tip is ahead of / diverged from local, or local is missing → refuse `ORIGIN_LANE_STALE` before the approval-stamp check.
3. **Unreachable** (FR-008) → refuse `ORIGIN_UNREACHABLE` naming the opt-out.
4. `--origin-check warn` / `SPEC_KITTY_ORIGIN_CHECK=warn` (FR-009) → warnings, run continues.
5. Unchanged (FR-015, FR-007): target behind only for unrelated commits → proceeds; no remote / remote lacks branches → as today.

Closes #5780 (P0). SC-001: 0 of the plain and `--push` arms land the rejected WP, for both coordination and lanes topologies.

## Context & Constraints

- Read `spec.md` US1 + FR-001/002/008/009/010/015, `plan.md` "Where each gate calls the check" (post-plan squad folded — the ordering there is mandatory), `contracts/origin-freshness.md`, `traces/design-decisions.md`.
- `origin_freshness` (WP03) gives `check_status_evidence`, `check_branches`, `enforce_merge_gate`, `resolve_origin_check_mode`, `OriginFreshnessRefused`.
- Placement in `src/specify_cli/consolidation/executor.py::_run_lane_based_consolidation` (~:613):
  - status evidence: right after `seam = placement_seam(main_repo, mission_slug)` (~:670) and BEFORE `feature_dir = _resolve_run_status_dir(seam)` (~:671; it can seed/commit the coordination surface);
  - lanes: after `lanes_manifest` is read (~:697-705), before the protected-status-target / push preflight steps. Lane selection: `origin_freshness.approved_lane_branches(...)` (WP03) — pass `completed_wps` from the persisted `ConsolidationState` on resume (`consolidation.state.load_state`). If its canceled-lane predicate needs the status read surface, run the lane check right after `_resolve_run_status_dir` instead, still before any branch move — record your choice.
- Coordination topology with the coordination branch only on the remote: do NOT add a refusal — the existing `COORDINATION_WORKTREE_UNMATERIALIZED` path handles it (ADR 2026-09-24-2). The fetch WP03 performs makes its remedy actually work.
- Rendering: reuse `consolidation.entry_preflight._merge_record_may_exist(seam)` for `merge_record_exists` and the `_protected_refusal_footer` wording; put the executor-side wrapper in a NEW small module `consolidation/origin_gate.py` (keeps `executor.py` within C901 ≤ 15 — it is 12 today; add at most two calls).
- C-007: do NOT edit `consolidation/rollback.py`, `git/ref_advance.py`, `coordination/status_surface_guard.py`.
- `--dry-run` returns before the executor (`cli/commands/consolidate.py` ~:1298) — exempt, unchanged.

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP04`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T019 — Red-first regression (#5780) — FIRST commit

`tests/terminus/test_consolidate_sees_teammate_rejection.py`, `pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]`, docstring names #5780 and ADR 2026-07-17-1. Drive the REAL CLI (`run_terminus`), no subprocess mocking.
- Fixture: `build_coord_mission(tmp_path, wps=("WP01","WP02"))` (both approved, coordination topology). Use `two_clone_support` (WP01): bare remote, push target + coordination + lane branches; `clone_from` → clone B. In B, append a WP02 `approved → planned` rejection event to the coordination branch's `status.events.jsonl` (reuse the conftest `_event` builders; fixture surgery in B is fine — the gate under test is A's consolidate) and push.
- Arm 1 (plain): A runs `consolidate --mission <m>` → exit != 0, output contains `ORIGIN_STATUS_STALE`, target tip unchanged, WP02 not done on target.
- Arm 2 (`--push`): same, AND the remote's target tip is unchanged.
- Arm 3 (lanes topology): use `tests/terminus/lanes_fixture.py` (or extend `build_coord_mission` usage) so status lives on the target; B pushes the rejection on the target → refusal.
- Arm 4 (FR-015 positive control, same lanes fixture): B pushes a commit to the target that touches only `src/unrelated.py` → A's consolidate proceeds past the freshness check (exit 0 or at least no `ORIGIN_*` code).
- Arm 5 (control after remedy): A pulls the coordination worktree (the remedy command printed) → consolidate refuses with the ordinary "missing review approval: WP02".
Prove red on the planning base (arms 1-3 exit 0 today), commit.

### T020 — Campsite (behaviour-preserving, separate commit)

Extract from `_run_lane_based_consolidation` the block that computes `lanes_manifest` / `planning_artifact_only` into a helper if needed to keep complexity ≤ 15 after T021; no behaviour change; run `tests/consolidation/test_executor_coverage.py` before/after.

### T021 — Wire the checks

- `consolidation/origin_gate.py`:
  - `check_evidence_before_status_dir(main_repo, mission_slug, seam, setting) -> None`
  - `check_approved_lanes(main_repo, mission_slug, lanes_manifest, setting, *, resume_completed: frozenset[str]) -> None`
  Both call `origin_freshness`, print warnings via `console.print(..., markup=False)`, and on `OriginFreshnessRefused` print the message (+ the protected-refusal footer wording when a record exists) and `raise typer.Exit(1)`.
- In the executor call them at the two points above; thread `origin_check: str | None` into `_run_lane_based_consolidation` (new keyword, default `None`).

### T022 — `consolidate --origin-check`

`--origin-check` option (`typer.Option(None, "--origin-check", click_type=click.Choice(["enforce","warn"]))`, help names `SPEC_KITTY_ORIGIN_CHECK`), threaded to the executor; `--resume` honours it too. Help text in `--mission` terms (terminology canon).

### T023 — Affected test sweep

```bash
.venv/bin/python -m pytest -q tests/terminus/test_consolidate_sees_teammate_rejection.py tests/consolidation/test_origin_gate.py
.venv/bin/python -m pytest -q tests/terminus/ -k "not slow"          # terminus neighbourhood (targeted directory of the touched gate)
.venv/bin/python -m pytest -q tests/consolidation/test_executor_coverage.py tests/consolidation/test_target_branch_preflight.py tests/cli/commands/test_merge_strategy.py tests/cli/commands/test_merge_status_commit.py tests/integration/test_merge_resume.py
.venv/bin/python -m pytest -q $(ls tests/consolidation/test_ordering_bake_seam.py tests/consolidation/test_mission_number_truthful_4900.py 2>/dev/null)
make test-fast
```
Fixtures built on `tests/_support/git_template` have an `origin` holding only `main`: lane/coord branches read `remote_missing` and pass. If a subprocess-sequence mock breaks, patch `origin_gate` at its boundary rather than reorder assertions. Record counts.

## Definition of Done

- [ ] Regression test committed first and red on the base; green after.
- [ ] Refusal happens before `_resolve_run_status_dir` for evidence; no branch, worktree or remote moved on refusal.
- [ ] FR-015 positive control green on the same lanes fixture.
- [ ] `_run_lane_based_consolidation` C901 ≤ 15; mypy/ruff clean on touched files.

## Risks

- Lane-check placement vs the canceled-lane predicate (see Context); resume.
- A teammate's bookkeeping-only lane push now refuses (accepted: remedy is "update the lane, re-run").

## Reviewer Guidance

Run the regression file on the planning base (stash `src/`) to see red. Verify no new destructive or ref-moving call. Verify the opt-out warning names the source.

## Post-tasks squad folds (binding — supersede conflicting text above)

- ONE check, before `_resolve_run_status_dir`: compute the lane list read-only (`approved_lane_branches`, `completed_wps` from the persisted state when a record exists) and call `check_mission_branches` once (NFR-001). The "run the lane check after `_resolve_run_status_dir`" fallback is removed.
- Coordination topology + evidence `local_missing` → pass through (no ORIGIN refusal); test it.
- T019 extra arms on the SAME two-clone fixture, each with an up-to-date control: (6) `ORIGIN_LANE_STALE` — B pushes a commit on WP02's lane after approval (A's approval stamp == A's local lane tip): red-first, today lands v1 at exit 0; (7) `ORIGIN_UNREACHABLE` — A's remote URL dead; (8) `--origin-check warn` → warning names `flag`, run continues past the check; (9) `SPEC_KITTY_ORIGIN_CHECK=warn` → warning names `environment`; (10) merge record present (create one by an interrupted/refused earlier run, or seed `state.json` via the state API) → remedy text starts with `spec-kitty consolidate --abort`.
- SC-001 lanes + `--push` arm: on the base it already refuses via the push preflight (target behind), so assert the CODE `ORIGIN_STATUS_STALE` (red-first by code, not by exit status) and that it fires before the push preflight.
- `tests/consolidation/test_origin_gate.py` covers `origin_gate` rendering units (warning lines, refusal + footer, `typer.Exit(1)`).

## Activity Log

- 2026-10-06 — prompt generated.
