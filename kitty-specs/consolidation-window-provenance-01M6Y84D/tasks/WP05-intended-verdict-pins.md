---
work_package_id: WP05
title: Intended-verdict strict-xfail pins
dependencies:
- WP02
- WP04
requirement_refs:
- FR-016
- NFR-002
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/test_reconciliation_intended_verdicts.py
create_intent:
- tests/consolidation/test_reconciliation_intended_verdicts.py
execution_mode: code_change
model: ''
owned_files:
- tests/consolidation/test_reconciliation_intended_verdicts.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Intended-verdict strict-xfail pins

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

The golden file (WP02) records what the gate does **today**, known-wrong verdicts included. This work package records what the gate **should** do in each case Phase 4 fixes, as separate strict `xfail(raises=AssertionError)` tests (FR-016, renata F-04). Each Phase 4 fix removes exactly one or two of these markers in its fix commit (NFR-002), which makes "the golden diff is a subset of the named cells" checkable.

Done means `tests/consolidation/test_reconciliation_intended_verdicts.py` contains these tests, every one reporting `xfailed` today:

| Test name | NFR-002 cell | Flipped by |
|---|---|---|
| `test_commit_between_two_approvals_is_refused` | (a) | WP19 |
| `test_gap_then_recorded_stray_commit_is_refused` | (a) mixed | WP19 |
| `test_window_refusal_names_commit_and_preceding_wp` | (b) | WP19 |
| `test_rewound_wp_window_opens_after_rewind[lanes]`, `[single_branch]` | (c) | WP19 / WP20 |
| `test_history_read_error_refuses_instead_of_deleting` | (d) | WP16 |
| `test_resume_closed_world_reads_frozen_anchors` | (e) | WP18 |
| `test_resume_approved_bound_reads_frozen_anchors` | (f) | WP18 |
| `test_resume_fully_canceled_lane_reads_frozen_anchors` | (g) | WP18 |
| `test_forecast_uses_fresh_run_excluded_canceled_set` | (h) | WP17 |
| `test_forecast_resolves_coordination_base_to_fresh_run_sha` | (h) | WP17 |
| `test_parallel_claims_window_is_not_over_wide` | named residual WW-6 | stays `xfail` |

Each `xfail` carries `strict=True`, `raises=AssertionError` and a `reason=` naming the NFR-002 cell, the FR and the work package that flips it (residual: the ADR slug `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition` and "named residual").

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US2 (acceptance 1, 5, 7), US1-6, US4 (1, 3, 5), US5-3, NFR-002, NFR-010, Edge Cases (rewind, parallel claims).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` sections 3-4 (window opener, WW-2, WW-2a, WW-6, WW-7) and section 6 (`ClaimInputs` sources).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-02 (list of intended verdicts), IC-13..IC-16 (what each fix changes).
- Precedent: `tests/consolidation/test_approved_bound_residuals.py` (strict `xfail(raises=AssertionError)` driving the real CLI).
- Reuse from WP02's `tests/consolidation/characterization_support.py`: `build_shape`, `set_window_state`, `run_in_process`, `interrupt_after_claim`. Reuse from WP04: `tests/consolidation/reconciliation_family.py` (`setattr_reconciliation_family`) for the probe patch in (d).
- Every test drives the entry point (`consolidate`, `consolidate --dry-run`, `consolidate --resume`) in process and asserts on refusal code, named commit/work package and "no branch moved" (NFR-010), except (h), which compares `ClaimInputs`-relevant forecast output with the fresh run.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP05 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## The precondition rule (read before writing any test)

A strict `xfail(raises=AssertionError)` turns **any** `AssertionError` into an expected failure, including a broken fixture. So:

- Fixture preconditions must **not** raise `AssertionError`. Add a helper `require(condition: bool, message: str) -> None` that raises `FixturePrecondition(RuntimeError)`. A broken fixture then errors the test (red), instead of hiding behind the `xfail`.
- Only the final verdict assertions use `assert`.
- Each test asserts its preconditions first (e.g. "the stray commit exists on lane A", "`state.json` holds `pre_interrupt_lane_tips` for the dependency lane", "the event log carries `wp_window.open_sha` for WP02").

## Subtasks & Detailed Guidance

### Subtask T024 – Commit between two approvals (a, b) [P]

- **Fixture**: `build_shape(tmp_path, "two_wp_lane")` on a lanes topology: WP01 approved (stamp S1); a stray commit X on the lane; WP02 opens (recorded `open_sha` = lane head incl. X, set with `set_window_state(..., "recorded")`), commits its work, is approved. No other lane's approval stamp reaches X.
- **`test_commit_between_two_approvals_is_refused`**: run `consolidate --mission <slug> --yes` in process. Assert: exit code != 0, `LANE_MOVED_AFTER_APPROVAL` in output, target branch SHA unchanged (compare with the SHA read before the run).
- **`test_window_refusal_names_commit_and_preceding_wp`**: same fixture; assert the refusal names X (short SHA as rendered) and `WP01` (the work package approved before it), per FR-007 and `write_branch_bound._preceding_wp`.
- **`test_gap_then_recorded_stray_commit_is_refused`**: WP01 with window state `not_recorded` (gap), stray commit X after WP01's approval, WP02 recorded and approved after X. Today it passes; intended: refused (NFR-002 (a) mixed case, data-model WW-7 second sentence).
- **Notes**: Also add, as a plain **passing** precondition test outside the xfail, that the same fixture without X passes today (`test_two_approvals_without_stray_commit_pass`), so the xfail cannot be explained by an unrelated refusal.

### Subtask T025 – Rewound work package (c) [P]

- **Fixture**: WP01 claimed (recorded `open_sha` = S0); commit C1 on the lane; WP01 moved `in_progress -> planned` (a rewind, not a review rejection); claimed again (recorded `open_sha` = S1, the lane head including C1); commit C2; approved.
- **Intended verdict** (FR-021, data-model section 3 cycle rule, section 4 WW-1): the window is `(S1, stamp]`; C1 lies in the abandoned cycle, outside every window and every exemption anchor, so it is refused (`LANE_MOVED_AFTER_APPROVAL` on lanes; the `single_branch` window refusal on `single_branch`). C2 is inside the window.
- Parametrize over `lanes` and `single_branch` (`ids=["lanes", "single_branch"]`).
- **Before pinning**, confirm this reading against FR-021, contract rule R-1 and data-model section 3. If you read the intended verdict differently, stop and ask the orchestrator; record the question in the WP history.

### Subtask T026 – History-read error is never a deletion (d) [P]

- **Fixture**: a lane whose spine **modifies** (not deletes) path P. Find `touch_sha`, the newest commit on the lane's first-parent spine that touches P (the one commit `_final_authored_walk` reads P at; `git rev-list --first-parent <coord base>..<lane branch> -- P | head -1`). Patch the history probe used by `_final_authored_walk` (today `blob_id_at`, looked up in `specify_cli.consolidation.reconciliation`) through `setattr_reconciliation_family(monkeypatch, "blob_id_at", fake)`, where `fake` raises `GitProbeError` (from `specify_cli.consolidation.git_probes`) **only for `(touch_sha, P)`** and delegates for every other `(ref, path)`.
  - **Why so narrow** (post-tasks squad pedro #3): the verifier also calls `blob_id_at(self._repo, target_ref, path)` at gate time (`reconciliation.py` ~1370 and ~1596, "raises -> REFUSE"). A fake that raises for P on **any** ref makes today's run refuse at the **gate** and roll back: exit != 0, P named, target unchanged. That satisfies loose assertions, the strict xfail XPASSes, and the WP is red on delivery. Never raise for `target_ref` or any ref other than `touch_sha`.
- **`test_history_read_error_refuses_instead_of_deleting`**: run `consolidate` in process. Intended: refused **at claim time, before any mutation**:
  - exit code 1 and the output contains `a git probe failed while building the approved-WP claim` (`phase_claim._exit_on_claim_probe_error`) and names P;
  - no branch moved **and nothing was moved and rolled back**: record `rollback_harness.ref_shas(mission)` and the reflog of the target and coordination branches before the run; assert both unchanged after (a gate FAIL/REFUSE moves the target and restores it, which leaves a reflog entry; a claim-time refusal leaves none);
  - no pre-mutation snapshot remains (`rollback_harness.state_path(mission)` absent, or its `pre_mutation_refs` empty: a claim-time exit clears the fresh record).
  Today the error is recorded as a deletion of P, the claim builds, and the run continues past claim time, so these assertions fail with `AssertionError`.
- **Notes**: WP16 will change the probe to `path_state_at`; the fix work package rewrites the patch target when it flips this test. Write the fake so it is easy to retarget (one helper `_failing_probe_for(path, touch_sha)`, scoped to that one pair).

### Subtask T027 – Resume reads frozen anchors (e, f, g) [P]

- **Topology**: all three tests build their shapes on the **coordination** topology. `pre_interrupt_lane_tips` is persisted only when the coordination checkpoint resolves (`phase_claim._resolve_pre_mutation_coord_sha`); on LANES or `single_branch` there are no frozen tips to read (post-tasks squad pedro #4).
- **Fixture**: `interrupt_after_claim(mission)` from WP02 (SIGKILL after the claim anchors were saved, before lanes are consolidated). Precondition via `require`: `state.json` holds `pre_interrupt_lane_tips` with the dependency lane's tip. Then add a commit D to the dependency lane (after the kill), then run `consolidate --resume` in process.
- **(e) `test_resume_closed_world_reads_frozen_anchors`**: mixed lane (approved WP + canceled WP) whose closed-world anchors include the dependency lane. Intended: D does not widen the exempt set; the resume reaches the verdict the closed world reaches with the frozen tip (spec US4-3).
- **(f) `test_resume_approved_bound_reads_frozen_anchors`**: a non-mixed lane whose dependency lane gained D after the interruption, and the dependent lane then merged D. Intended: `LANE_MOVED_AFTER_APPROVAL` instead of exempting D (spec US4-5).
- **(g) `test_resume_fully_canceled_lane_reads_frozen_anchors`**: a fully canceled dependency lane; a dependency-lane advance after the interruption. Intended: the fully-canceled-lane content check judges against the frozen tip. If you find the flip unreachable, keep a test that records the reason in its docstring and `reason=` and asserts the reachable consequence, and tell the orchestrator (NFR-002 (g) allows "a cell recording that the flip is unreachable, with the reason").
- **Notes**: Coordinate the fixture with WP18 (it reuses this). Never hand-write `state.json`.

### Subtask T028 – Forecast inputs (h) [P]

- **`test_forecast_uses_fresh_run_excluded_canceled_set`**: a Mission with an excluded canceled work package (`mixed_lane_canceled_wp` shape). Run `consolidate --dry-run --json` and a fresh `consolidate` on copies of the same unmutated repo. Intended: the forecast reports the same claim-time refusal or pass as the fresh run (spec US5-3).
- **`test_forecast_resolves_coordination_base_to_fresh_run_sha`**: intended: the forecast's coordination base equals the SHA the fresh run resolves. If the forecast payload does not expose the base, assert on the claim-time verdict of a fixture where the live `mission_branch` name and the fresh-run base differ (move the mission branch after the fresh run's base would be captured is not possible pre-run; instead build a fixture where the coordination tip differs from the mission branch name's resolution, cf. `forecast.py` `_forecast_claim_status_dir` and the `coord_base` row of data-model section 6). If you cannot construct a visible difference, record why in the docstring and tell the orchestrator; WP09's parity test pins the field-level divergence.

### Subtask T029 – Parallel-claims named residual

- **`test_parallel_claims_window_is_not_over_wide`**: WP01 and WP02 on one lane, both claimed before either commits (or WP02 claimed early and parked without returning to `planned`); a stray commit between their work. Intended (ideal): the stray commit is refused. Under the window model it stays covered (WW-6). `reason=` names the ADR slug and "named residual"; this marker is **not** removed by this Mission.

## Test Strategy

Tests are the deliverable. Mark the module `pytest.mark.integration` and `pytest.mark.git_repo`.

## Definition of Done

```bash
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen mypy tests/consolidation/test_reconciliation_intended_verdicts.py
make test-fast
```

- [ ] The `-rxX` summary lists exactly the tests of the table as `XFAIL`, zero `XPASS`, zero errors; `test_two_approvals_without_stray_commit_pass` passes.
- [ ] Every precondition uses `require(...)` (raises `FixturePrecondition`), never `assert`.
- [ ] Every `xfail` has `strict=True`, `raises=AssertionError` and a `reason=` naming cell, FR and flipping work package.
- [ ] Temporarily break one fixture precondition locally and confirm the test **errors** (not xfails); discard the change.
- [ ] No production code changed.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP05" --entry "<summary>. <detail>"` for your reading of (c) and (g), any unreachable flip, the `touch_sha` scoping of the (d) fake; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Vacuous xfail**: the precondition rule plus the passing sibling test.
- **Intended verdict misread**: (c) and (g) carry an explicit stop-and-ask instruction.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid to top** (soundness of the pins decides whether Phase 4 can be judged).
- For each test, check that the assertion would hold under the intended rule as written in the spec and data model, and fail under today's rule for the stated reason.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP05 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP05 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
