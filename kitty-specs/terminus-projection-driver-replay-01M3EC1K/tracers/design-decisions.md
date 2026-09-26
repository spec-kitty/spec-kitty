# Tracer: Design Decisions

Seeded at planning; appended during implementation.

- **DD-1**: Proof primitive = replay the registered `merge=<name>` driver on `(%O checkpoint,
  %A pre-merge-target, %B coord)`; PASS iff `landed == expected`. Rejected: (i) symmetry-only fix
  (green-washes P2, fail-open on diverged paths); (ii) stock `git merge-tree` (wrong resolver for
  driver-governed paths; conflicts on the non-driver #5021-r2 path).
- **DD-2**: `%A` MUST be the target blob BEFORE the squash (`target_baseline_sha` / `pre_mutation_*`),
  not the post-squash target — else the replay is tautological. The brownfield scout confirms the
  exact field on the merge run state.
- **DD-3**: Fail-closed is mandatory — no registered driver for a diverged path, a missing input
  blob, or any probe error ⇒ REFUSE (INV-FLOOR-2). Never widen to a silent PASS.
- **DD-4**: `test_5038_p2` re-grounded onto genuine coord-content LOSS (a landed blob the driver
  replay does not reproduce), NOT onto the old same-line union (which is lossless and now legitimately
  PASSes). This is the operator-sanctioned floor re-adjudication (`DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`),
  not a green-wash.
- **DD-5**: #5021-r2 stays `xfail(strict)`; only its reason string is narrowed to name the distinct
  root and the new tracked issue.
