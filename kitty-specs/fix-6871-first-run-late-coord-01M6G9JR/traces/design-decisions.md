# Design decisions — #6871

- **D1: reuse, do not fork.** The first run calls the same seams (`_project_status_bookkeeping_to_target`,
  `_post_checkpoint_mission_paths`, `project_late_gate_matrix_commits`, `assert_late_window_landed`)
  and the same refusal builder. No second record selector, no second refusal text.
  Rejected: a first-run-only "compare tips and refuse" guard — cheapest, but it leaves the loss to
  a resume instead of landing what the operator committed, and the issue names reporting-only as
  the weakest option.
- **D2: base selection, not a mode flag.** `_late_window_base` returns the resume base for a resume
  and the merge's verified tip for a first run. The rest of the function is unchanged, so the
  resume path cannot drift.
- **D3: the approved tip advances only under proof.** The projection teardown gate and the branch
  delete stay compare-and-swap anchored. After a successful projection + assertion the run sets
  `coord_tip_after_projection` to the tip the assertion was made over, and only while the ref is
  still there; otherwise the older anchor stands and the gate refuses. Precedent:
  `_carry_pass_anchor_over_own_commit`.
- **D4: no anchor means no window, not a refusal.** A first run with neither
  `coord_tip_after_projection` nor a checkpoint cannot prove what the tip held when the merge
  verified it. Refusing there would strand a Mission whose coordination placement does not resolve
  and no `--resume` could clear. Behaviour unchanged; recorded as a residual in `## Deferred`.
- **D5: the commit message stays #5570's.** "project coordination commits that landed during
  teardown" remains the single shape, so history reads the same and existing tests that count
  projection commits keep their meaning. Only the console line distinguishes the two windows.
