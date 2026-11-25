# Code grounding: #7755 / #7754 (re-verified on origin/main cfa68136, 2026-11-20)

Author: claude::python-pedro. Read-only pass done before planning.

## Root-cause citations (issue lines re-verified; current line numbers)

| Issue citation | Current location | Verified behaviour |
|---|---|---|
| `lanes/consolidation.py:227-246` `_try_auto_rebase_if_stale` | `src/specify_cli/lanes/consolidation.py:228-247` | Runs `attempt_auto_rebase` against the *in-run* Mission branch. On `report.succeeded` it re-checks; otherwise `return stale` (`:247`) — `report.halt_reason` is discarded. No-worktree path returns early (`:238-241`) with no attempt. |
| (caller) | `src/specify_cli/lanes/consolidation.py:328-344` | Stale result rendered as `Lane <id> is stale: overlapping files [...]. <remediation>`; `LaneConsolidationResult.stale_check` carries the `StaleCheckResult`. |
| `consolidation/phase_advance.py:260-274` | `src/specify_cli/consolidation/phase_advance.py:419-432` (`_phase_merge_lanes`) | Prints each error and raises `typer.Exit(1)`. |
| `consolidation/executor.py:698-703`, `_report_rollback :774-810` | `src/specify_cli/consolidation/executor.py:743-760` (door), `:865` `_report_rollback` → `rollback.rollback_to_snapshot` (`:894`) | The single rollback door restores the Mission branch to its pre-run tip; lane branches are report-only (never restored). So the sibling lane's *branch* survives; its merge into the Mission branch does not. |
| `stale_check.py:190-197` remedy | `src/specify_cli/lanes/stale_check.py:150-198` (`_stale_remediation`), `:144-147` (`_reentry_command`) | Names the Mission branch and `agent action implement <WP>`; never consults the WP state. |
| #7754 `work_package_lifecycle.py:244-249` | `src/specify_cli/status/work_package_lifecycle.py:244` | `implement` raises `WorkPackageStartRejected` for `Lane.APPROVED`, naming `move-task <WP> --to planned --review-feedback-file <file>` as the rework route. |

`check_lane_staleness` has exactly one production caller chain: `consolidate_lane_into_mission` (`lanes/consolidation.py:246,328`). Consolidate gates on review approval first (`Gate evidence`), so every WP of a stale lane is approved when the remedy prints.

## Live reproduction (exploratory, real CLI)

A coordination Mission (two independent approved lanes, adjacent hunks of `src/components/Popup.vue`, real worktrees, production status shell): `spec-kitty consolidate` prints the #7755 refusal verbatim and `restored kitty/mission-…  <in-run> -> <pre-run>`. Following the candidate remedy — reopen WP02 (approved → planned), merge `lane-a`'s branch in lane-b's checkout, resolve, commit, review + approve again — the next `consolidate` passes lane-b, lands, and reconciliation verifies (`squash content attribution verified`). The reviewed merge of another approved lane's approval stamp authors its content (#7626, `reconciliation_authorship.py` `_authoring_merges`), so the route is sound under today's gate.

## Invariants that must survive

- One rollback authority (`consolidation/rollback.py`), AST-pinned by `tests/consolidation/test_single_rollback_authority.py`; no new restore path; lane branches stay report-only.
- CAS ref discipline (`git/ref_advance.py`), approved-bound refusals (`approved_bound.py`), the reconciliation axes — untouched.
- `AutoRebaseReport` invariant: `halt_reason` is set iff an attempted rebase did not succeed (`lanes/auto_rebase.py:140-150`).
- Lane branch names come from `lanes/branch_naming.lane_branch_name` (gate `tests/architectural/test_no_worktree_name_guess.py` flags hand-composed `kitty/mission-…` strings).
- Subprocess discipline in `lanes/consolidation.py` (`tests/architectural/test_merge_pipeline_ratchets.py` AC-F1: every `subprocess.run` carries `env=`; no bare `os.environ`). New git probes go through `kernel.git` helpers instead.
- Planning-lane remedy (repository-root checkout) unchanged.

## Gates that reference these files

- `tests/consolidation/test_single_rollback_authority.py` (rollback door)
- `tests/architectural/test_merge_pipeline_ratchets.py` (`lanes/consolidation.py` subprocess/env)
- `tests/architectural/test_no_worktree_name_guess.py` (branch-name composition; mentions `_stale_remediation`)
- `tests/architectural/test_commit_scope_owner.py`, `test_exemption_registry_ratchet.py`, `test_no_legacy_terminology.py` (list `lanes/consolidation.py`)
- `tests/architectural/test_marker_job_completeness.py`, `test_issue_named_test_census.py` (p0_repro marker bookkeeping)

## Existing test seams

- `tests/consolidation/test_p0_repro_7755_auto_rebase_halt_reason.py` (red-first, `p0_repro(issue=7755)`; drives `consolidate_lane_into_mission`).
- `tests/lanes/test_stale_remediation_cli_command.py`, `tests/lanes/test_stale_check.py` (remedy text; single non-approved-WP fixture — the #7754 gap).
- `tests/integration/test_consolidate_upgraded_mission_recovery.py::test_lanes_that_change_gitattributes_differently_are_still_refused_as_stale` pins the old remedy text and asserts `git merge kitty/mission-` is absent (from #7311, where the remedy merged the Mission branch).
- `tests/terminus/` harness (`run_terminus`, `CoordMission`, `mixed_lane_support.transition`) for a real-CLI coordination Mission.

## 90-day churn

The checkout is a shallow clone (51 commits), so `git log --since=90.days` shows one commit per file (`81dd4989`, 2026-11-18) and understates churn. Not used for prioritisation.
