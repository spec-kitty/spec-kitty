# Discovery — late teardown verdict projection (#6791)

## Grounding

**Issue state on `main@512567ee` (2026-10-30).** #6791 is OPEN, unassigned and unlabelled before
this mission; not superseded. `git log -S` finds no change to the gate-matrix exclusion since
`f5c15f9f88 feat(consolidate): rename lane-consolidation merge→consolidate (#3080)`, and no commit
on `main` references #6791. The sibling issue #6653 (terminality gate passing while a row is
`in-mission`) is CLOSED and did not touch this projection path.

## Reproduction (real CLI, real git)

Built a coord-topology mission (`wps=WP01,WP02`, `mid8=01M6791A`), seeded an `issue-matrix.json`
with one `in-mission` row on both surfaces, then drove the documented sequence:

1. `agent tasks move-task WP02 --to planned --review-feedback-file …` with `--no-auto-commit`
   leaves `tasks/WP02-work/review-cycle-1.md` untracked in the coordination worktree.
2. `consolidate --mission <slug> --yes` → exit 76 `COORD_TEARDOWN_KEPT_ONLY_COPY`.
3. In the coordination worktree: `git add` the review-cycle file + commit →
   **commit A** (`chore: commit review-cycle artifacts before coordination teardown`).
4. From the primary checkout: `agent issue-verdict --mission <slug> --issue '#6791'
   --verdict fixed --actor tester` → prints `OK #6791 -> fixed (committed,
   surface=kitty/mission-…)` → **commit B** (`chore: update issue-matrix for <slug>`), A's child.
5. `consolidate --mission <slug> --resume --yes` → exit 0, prints
   `Projected the coordination commit(s) that landed during teardown`, then
   `Cleaned up mission/coordination branch + worktree`.

Observed after step 5: `git show main:kitty-specs/<slug>/issue-matrix.json` still reads
`"verdict": "in-mission"`, the coordination branch is gone, and the resume's own gate output had
printed `✓ Gate issue_matrix_verdict_terminality: No unresolved (in-mission/unknown) rows among 1
issue-matrix row(s)` — it validated the verdict from the coordination surface in the same run that
dropped it. Matches the issue's "Actual behavior" exactly.

## Decisions

- **D1 — The exclusion is window-scoped, not a bug in itself.** `_post_checkpoint_mission_paths`
  excludes `IssueMatrix`/`AcceptanceMatrix` because in the *mid-merge* window the coordination ref
  holds only the finalize-time placeholder while `accept` authored the real fill on the primary
  surface (`#2404`, `#2804`). That reasoning is sound for that window and wrong for the
  post-teardown window, where every commit in `pre_mutation_coord_sha..coord-tip` was made *after*
  the merge verified the landing, so it cannot be the stale placeholder. Fix the window, not the
  classifier.
- **D2 — Project, then prove; refuse rather than delete.** The issue accepts either "project every
  attributable commit" or "refuse while unprojected commits exist". This mission does both: it
  projects the gate matrices, then asserts that **every** coordination record changed in the window
  is byte-identical on the target before the branch delete, refusing otherwise. The assertion is
  the generalisation — it also covers kinds this fix does not name.
- **D3 — A projection must not overturn an established judgement.** The exclusion existed to
  protect accepted evidence, so lifting it needs a preservation guard: a gate matrix is projected
  only when the target holds no established judgement (terminal issue verdict, `pass` criterion,
  terminal negative-invariant result) that the coordination copy would lose or downgrade. This
  reuses the documented terminal sets rather than inventing a new one.
- **D4 — Forward-only, as the existing projection already is.** A late *deletion* of a coordination
  record cannot be expressed by a forward projection; it refuses instead of resurrecting or
  silently dropping it (matching `project_post_checkpoint_commits_to_target`'s append-only NFR).
- **D5 — Keep the mid-merge window byte-identical.** `project_post_checkpoint_commits_to_target`'s
  output feeds the reconciliation squash proof (`projected_content_matches_target`), so its path
  set must not change. The new behaviour is a separate seam-stage call in the teardown phase.

## Evidence gathered

- `src/specify_cli/consolidation/phase_teardown.py:_land_late_coordination_commits` — the `#5570`
  resume projection; collects `_post_checkpoint_mission_paths` + the status pair and commits them
  as one bookkeeping commit, then the delete is a compare-and-swap.
- `src/specify_cli/consolidation/bookkeeping_projection.py:_post_checkpoint_mission_paths` — the
  `excluded_kinds = {ISSUE_MATRIX, ACCEPTANCE_MATRIX}` set that drops commit B.
- `src/specify_cli/policy/merge_gates.py:_evaluate_issue_matrix_verdict_terminality_gate` — the gate
  whose PASS the resume printed; it reads the coordination partition.
- `src/specify_cli/tasks/issue_matrix.py` (`build_issue_matrix_document` /
  `parse_issue_matrix_document`, rows keyed by `#NNNN`) and
  `cli/commands/review/_issue_matrix.py:IssueMatrixVerdict` — the document shape and the terminal
  verdict set (`in-mission` and `unknown` are the only non-terminal members, per the gate's own
  pass detail).
- `tests/consolidation/test_teardown_refusal_resume.py` — the existing real-CLI refusal/resume
  fixtures this mission extends (and the `#5965` stranded-path refusal already next door).

## Open questions

- None blocking. Whether `move-task` should commit review-cycle artifacts itself when auto-commit is
  disabled stays out of scope (the issue files it as a separate look).
