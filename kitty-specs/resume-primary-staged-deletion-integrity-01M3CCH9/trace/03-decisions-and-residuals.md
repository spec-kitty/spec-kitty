# Tracer 03 — Decisions & residuals (append during implement)

## Decisions
- D1: **Recover, don't just advise.** On `--resume`, a pure behind-own-HEAD primary is
  recovered with `git reset --hard HEAD` and the merge continues. (FR-001)
- D2: **Phantom-only proof gates the reset** (Renata's hole). Recover iff the primary's
  working tree AND index are byte-identical to persisted `pre_mutation_target_sha` AND HEAD
  is its descendant. Else REFUSE — never reset. (FR-002, C-001)
- D3: **Fixture corrected, not rewritten.** `test_repro_4997.py` keeps its name, structure,
  and assertion; `_interrupt_with_staged_deletion` is corrected to model the REAL window
  (advance target so mission branch is an ancestor of HEAD; persist `pre_mutation_target_sha`
  = pre-advance tip; leave primary lagging with phantom staged deletions of the mission's
  own files). (FR-004)
- D4: **Defect B via `changed=False` on merge no-op** + strategy-neutral rename of the
  zero-diff guard. (FR-003)
- D5: New safety test (US1 AC2) + new red-first merge-no-op test (US2) added alongside the
  corrected repro.

## Pre-PR second-opinion squad (opus, profile-loaded) + folds
- **reviewer-renata (correctness/fail-closed) — 1 CONFIRMED finding, folded.** Empirically
  proved (throwaway repo) an **untracked-file collision** hole: `git diff --quiet <base>` is
  blind to untracked files, so `is_pure_behind_head_lag` returned True while `git reset
  --hard HEAD` silently CLOBBERED an untracked operator file sitting at a to-be-restored
  mission path. Narrow trigger, but silent + irreversible on a P0 integrity mission. **Fold:**
  added `_untracked_obstructs_head` to `preflight.py` (reuses the single obstruction
  authority `ref_advance._path_obstructs_target_tree`/`_target_tree_paths` vs HEAD — INV-3),
  gating the recovery; new covering test `test_resume_phantom_only.py::...untracked_file...`;
  red-first confirmed (neutralizing the check reds the test). Findings 2–6 all sound.
- **paula-patterns (boundary/overlap) — boundary-clean, releasable.** 2 LOW fold-worthy
  notes, both folded: F1 (the NFR-001 pre-lock-immutability comment now names the sanctioned
  resume-recovery mutation exception) and F2 (the `is_pure_behind_head_lag` docstring now
  documents the untracked-obstruction screen). Confirmed: single dirty-classifier authority
  reused (no parallel predicate), rename complete, new param reaches only mission→target,
  seam placement + resume-key correct, import direction clean.
- **Campsite fix:** reverted an accidental whole-file `ruff format` of the format-`exclude`d
  `merge/executor.py` (explicit-path ruff bypasses the gate's exclude — memory
  `ruff-format-explicit-path-bypasses-exclude`); executor.py diff is now logical-only.

## Residuals / follow-ups (note in PR, do NOT ticket while pushing for release)
- R1 (C-002): the reconciliation gate's merge/rebase axis is pure ancestry and blind to a
  *merged-then-content-reverted* lane; extending the #5013 blob-attribution content axis to
  the merge strategy is a defense-in-depth follow-up, out of scope here (FR-003's
  tree-equality adjudication is the primary guard for this mission's window).

- D6: **Execution path.** The lane/`implement`/`merge`/status-bookkeeping machinery is the
  very subsystem under repair, and with `meta.target_branch=main` (protected) a LANES
  mission mints no coord worktree so `finalize-tasks` status bookkeeping is refused
  (`PROTECTED_BRANCH_REFUSED`). To avoid dogfooding the merge-integrity subsystem to land
  its own fix (a real correctness risk) and the protected-branch friction, WP01/WP02 are
  implemented **red-first directly on the topic branch `fix/4997-...`** via sonnet
  subagent dispatch (python-pedro, profile-loaded) + opus review, with the full
  `tests/terminus/` + merge subsystem run by the orchestrator before push. Governance is
  preserved by the committed spec/plan/tasks/tracers, the issue claim/assignment/matrix,
  the profile-loaded squad, and a non-draft PR the operator merges. Publication is via the
  topic branch + PR to skupstream, never `spec-kitty merge`.

## Implement log
- **WP01 (Defect A) — DONE.** Corrected `test_repro_4997.py` to the real behind-own-HEAD
  window (`_interrupt_behind_own_head`: consolidate all lanes onto coord, `update-ref` the
  target, leave primary lagging; persist `pre_mutation_target_sha`). RED proof: with the
  product fix stashed the corrected test FAILS rc=1 (advisory-only "reset --hard HEAD",
  classification confirmed BEHIND_OWN_HEAD). Fix: `is_pure_behind_head_lag` phantom-only
  proof (`preflight.py`) + `_recover_behind_head_primary_on_resume` +
  `_pre_mutation_safety_preflight_with_recovery` (`executor.py`). GREEN: `test_repro_4997`
  ✓, `test_repro_4982` ✓ (no regression), `test_resume_phantom_only` ✓ (genuine edit
  preserved, resume refuses). ruff+format clean; mypy clean (4 pre-existing executor
  `no-any-return` are baseline, not new). Complexity held ≤15 by extracting the recovery
  helper.
- **WP02 (Defect B) — DONE.** `_merge_branch_into` MERGE branch now detects the
  "Already up to date" no-op (pre/post HEAD unchanged) and reports `changed=False`
  (→ `already_applied=True`), gated by a new `raise_on_unexpected_noop` param so ONLY the
  mission→target caller raises on an unpermitted no-op (lane→mission consolidation keeps its
  benign no-ops — caught a regression in `test_planning_lane_uses_target_branch_not_main`
  and fixed it with the param gate). Renamed `_reject_zero_diff_noop_squash` →
  `_reject_zero_diff_noop_integration` (strategy-neutral). RED proof (unit): with the fix
  stashed the two new `tests/lanes/test_merge.py::test_merge_strategy_noop_*` FAIL
  (`success=True, already_applied=False` — the silent-success bug). GREEN: all 25
  `tests/lanes/test_merge.py` pass. Integration regression
  `tests/terminus/test_merge_noop_adjudication.py` green.
- **Empirical scope note:** on current main the catastrophic exit-0 outcome for the
  deleting-commit path is ALSO backstopped by the reconciliation gate's closed-world /
  un-attributable-content axis (proven: it fires for the merge strategy, rc=1, no teardown)
  — contra the squad's "merge axis is blind" note (that was reachability-only; the
  closed-world axis is strategy-agnostic and caught it). So Defect B's fix is close-by-
  construction defense-in-depth (honest `already_applied`, earlier adjudication) rather than
  the sole guard. R1 (C-002) merge-axis reachability blind spot for a NON-committing content
  divergence remains a documented follow-up.
