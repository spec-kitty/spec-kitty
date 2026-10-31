# Contract: late-teardown coordination projection

The seam a resumed consolidation uses to carry commits that landed on the coordination branch
*after* the merge verified the landing. Implemented by
`src/specify_cli/consolidation/phase_teardown.py::_land_late_coordination_commits` and
`src/specify_cli/consolidation/bookkeeping_projection.py`.

## Window

`pre_mutation_coord_sha..<coordination-tip>` — every commit in it landed after
`consolidate` verified the landing and recorded its checkpoint. A `` --resume `` that finishes
teardown reads it once, at the live tip.

## Guarantees

| # | Guarantee | Mechanism |
|---|-----------|-----------|
| G1 | Every coordination record changed in the window reaches the target before the coordination branch is deleted. | Status pair: union + rematerialize (`_project_status_bookkeeping_to_target`). Non-status records: `_post_checkpoint_mission_paths`. Gate matrices: `project_late_gate_matrix_commits` (`include_gate_matrices=True`). |
| G2 | The projection cannot lose or overturn a judgement the target already holds. | `_assert_projection_preserves_evidence`: terminal `issue-matrix.json` verdicts (`IssueMatrixVerdict` minus `in-mission`), `pass` acceptance criteria, terminal negative-invariant results (`TERMINAL_INVARIANT_RESULTS`). |
| G3 | The projection is forward-only. | A record deleted on the coordination branch is never resurrected from the target and never deleted on it; the projection refuses. |
| G4 | The resume proves G1 before it deletes anything. | `assert_late_window_landed` runs after the projection commit and before the compare-and-swap branch delete; any unlanded coordination record raises `CoordinationTeardownError`. |
| G5 | Nothing is lost when a guarantee cannot be met. | The refusal keeps the coordination branch, its worktree and the mission's coordination marker together, and does not roll the verified landing back. |
| G6 | A commit landing *during* the projection still refuses rather than being lost. | The delete stays a compare-and-swap at the live tip (`_delete_mission_branch`, `#5570`). |

## Non-goals

- The mid-merge projection (`project_post_checkpoint_commits_to_target`): its path set is
  unchanged, because it feeds the reconciliation squash proof. Gate matrices stay excluded there,
  where the coordination ref can hold only the stale finalize-time placeholder.
- `meta.json` and every other PRIMARY-partition artifact: they are the target's own copy and are
  never projected from the coordination ref.

## Failure surface

`LateProjectionRefused` (seam) → `CoordinationTeardownError` (teardown), never a silent exit 0.
