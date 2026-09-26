# Tasks: Merge resume primary-site staged-deletion integrity

**Mission**: resume-primary-staged-deletion-integrity-01M3CCH9 · **Issue**: #4997 (P0, milestone #11)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Two work packages, one lane (both touch `merge/executor.py` → collapse by write-scope;
WP02 depends on WP01). Red-first (ADR 2026-07-17-1): each defect lands an issue-pinned
`@pytest.mark.regression` repro that is RED through the real `spec-kitty merge` entry point
before the fix; transitional repros become focused units after the fix.

## Work Package WP01: Phantom-only resume recovery + faithful repro (Defect A, P0)

**Dependencies**: None
**Requirement refs**: FR-001, FR-002, FR-004, NFR-001, NFR-002, C-001
**Authoritative surface**: `src/specify_cli/merge/`

- **T001** — Correct `tests/terminus/test_repro_4997.py::_interrupt_with_staged_deletion` to
  model the REAL behind-own-HEAD window: advance the target so the mission branch is an
  ancestor of the primary HEAD; persist `pre_mutation_target_sha` = pre-advance target tip;
  leave the primary tree/index at that base with phantom staged deletions of the mission's
  OWN files. Keep the test name, assertion, and `regression`-shape. Confirm it is RED
  (still `xfail`/failing) BEFORE the product fix.
- **T002** — Add `is_pure_behind_head_lag(repo_root, *, base_sha, env)` (in
  `merge/preflight.py`): True iff HEAD is a descendant of `base_sha` AND the primary's
  working tree AND index are byte-identical to `base_sha` (`git diff --quiet <base>` and
  `git diff --cached --quiet <base>` both clean). Focused unit tests for each branch.
- **T003** — At `merge/executor.py` `except DestructiveOpRefused` handler (the resume path),
  on `MERGE_UNSAFE_PRIMARY_DIRTY` + a resume + `classify_resume_dirty_remedy ==
  BEHIND_OWN_HEAD` + `is_pure_behind_head_lag(..., base_sha=state.pre_mutation_target_sha)`:
  run `git -C main_repo reset --hard HEAD`, re-run the pre-mutation preflight once, and
  continue into the locked flow. Otherwise abort unchanged (advisory). Keep complexity ≤15
  (extract a helper).
- **T004** — New safety test `tests/terminus/test_resume_phantom_only.py`: a behind-own-HEAD
  window where the primary ALSO carries a genuine tracked edit (tree differs from
  `pre_mutation_target_sha`) → `merge --resume` REFUSES (`rc != 0`) and the genuine edit
  survives (no `reset --hard`). Guards Renata's data-loss hole.
- **T005** — Remove the `xfail` from `test_repro_4997.py`; prove it PASSES. Prove
  `test_repro_4982.py` still PASSES (no regression).

## Work Package WP02: Merge-strategy no-op adjudication (Defect B)

**Dependencies**: WP01
**Requirement refs**: FR-003, NFR-003, C-002
**Authoritative surface**: `src/specify_cli/lanes/`

- **T006** — New red-first test `tests/terminus/test_merge_noop_adjudication.py`: merge
  strategy, mission branch already an ancestor of the target but the target tree diverges
  from the mission tree (mission content removed on top) → `merge --resume --strategy merge`
  must REFUSE (`rc != 0`), NOT stamp WPs `done` / delete lanes / exit 0. Confirm RED first.
- **T007** — In `lanes/merge.py::_merge_branch_into` MERGE branch: detect the "Already up to
  date" no-op (capture the target tip before `git merge`; if unchanged after, it is a no-op)
  and `return False` when `allow_noop_squash` (resume tolerance) is set, else raise — mirroring
  the squash zero-staged path. So `already_applied=True` propagates for the merge no-op.
- **T008** — Rename `_reject_zero_diff_noop_squash` → strategy-neutral
  (`_reject_zero_diff_noop_integration`) in `merge/executor.py` (honest naming; the guard is
  already strategy-agnostic). Update its one call site + any test references.
- **T009** — Prove T006 now PASSES; record the C-002 residual (merge-axis reconciliation
  blind spot) in the PR body, not a ticket.
