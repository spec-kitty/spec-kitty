---
affected_files: []
cycle_number: 1
mission_slug: coord-closeout-leftovers-01M78FRR
reproduction_command:
reviewed_at: '2026-11-12T20:26:39Z'
reviewer_agent: claude-reviewer
wp_id: WP02
---

# WP02 review (claude-reviewer, reviewer-renata) -- changes requested

The #7491 fix itself is sound and I found no soundness hole in the narrowed resume base or in the
landed-coordination ref (details at the end). One blocking issue: an architectural gate this WP
was asked to run is green on the base and red on the lane.

## Issue 1 (BLOCKING): `tests/architectural/test_no_dead_symbols.py` goes red

Reproduce (lane `kitty/mission-coord-closeout-leftovers-01M78FRR-lane-b` @ 7db19fbd):

    cd .worktrees/coord-closeout-leftovers-01M78FRR-lane-b
    PYTHONPATH=$PWD/src /home/user/spec-kitty/.venv/bin/python -m pytest -q \
      tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported

    E   Symbol-level dead-code gate FAILED ...
    E       - specify_cli.consolidation.landed_coordination::LANDED_COORDINATION_REF_PREFIX
    E       - specify_cli.consolidation.landed_coordination::landed_coordination_ref
    E       - specify_cli.consolidation.landed_coordination::landed_coordination_tip

The same test passes at 983a9c7c (base + red test): 1 passed. So this is introduced by
16faef12. The reader side (`landed_coordination_tip`, the ref name helper and the prefix) has no
src/ caller yet; its consumer is WP04 (#4041 reclaim).

Fix (pick one, in the gate's own order of preference):
- keep the three names out of `__all__` (they stay in the module) until WP04 wires them, and have
  the unit tests import them by module attribute; or
- add `(module, name)` entries to `tests/architectural/dead_symbol_allowlist.yaml` with category
  and rationale naming WP04 / #4041 as the consumer, so WP04 removes them when it wires the reader.

Re-run the gate and record the command and count in history.

## Non-blocking notes (no change required; fix if cheap)

- N1: `_branch_kept_after_teardown_message`'s no-holder arm says "(see the warning above)". The
  warning is a `logger.warning` in `_delete_mission_branch`; whether an operator sees it depends on
  the CLI's logging setup. Consider folding the `RefDeleteError` text into the message instead of
  pointing at a log line.
- N2: the prompt pointed at the registered-worktree authority in
  `coordination/surface_resolver.py`; the code uses `git.ref_advance.worktrees_with_branch_checked_out`.
  That is also a `git worktree list` reader (not name-guessing), so it meets the intent; just say so
  in history.
- N3: `rollback._clear_landed_coordination_ref` passes `state.pre_mutation_coord_ref or ""`;
  `landed_coordination_ref` raises `ValueError` for an empty or `refs/heads/`-only name, which would
  escape `rollback_to_snapshot` before its `save_state`. `_coord_anchor_is_the_target` filters
  `None`, and no writer stores `""`, so this is theoretical; catching `ValueError` there (like
  `record_landed_coordination_ref` does) would make the best-effort contract literal.

## What I checked and found sound

- Base selection: `_verified_resume_base` returns the persisted tip only with a tip, a
  `landing_verified_for_resume` true and `is_ancestor_strict(tip, refs/heads/<coord>)`; any
  `GitProbeError` (gc'd tip, missing branch) falls back to `pre_mutation_coord_sha`.
- The tip is written only in `_record_reconciliation_pass` (same `save_state` as the anchor, after the
  F3 projection proof) and in `_persist_proven_coordination_tip`, which runs only after
  `_assert_window_landed_in_every_mission_dir` passed and only while an anchor is set. A verified
  resume returns early in `_phase_reconcile_before_teardown` before `_record_reconciliation_pass`,
  so it never overwrites the tip with the unset in-memory value.
- Every anchor clear/restore goes through the pair (`clear_reconciliation_pass` in
  `_clear_bookkeeping`, `rebaseline_after_full_restore`, F4; `restore_reconciliation_pass(anchor, tip)`
  in the executor door). The only direct anchor write outside the pair is the pre-existing
  `_carry_pass_anchor_over_own_commit` (cleanup commit on the landing), where the coordination tip
  correctly stays.
- Landed ref: written only after PASS / proven advance; forward-only with a real 3-arg
  `update-ref` CAS (`expected_old`), `create_only` for creation, the two flags mutually exclusive,
  the old 2-arg form unchanged when neither is given; deleted at F4 whenever the target is RESTORED,
  independent of the anchor (so the executor door resetting the anchor first does not skip it);
  write failure is caught and logged at warning. `--abort` over a verified landing keeps the ref,
  which matches "exists only while its landing stands".
- C-002: exception type, exit codes and refusal codes unchanged; `rollback.py` still the only
  restore authority (`test_single_rollback_authority.py` green).
- Red->green: at 983a9c7c the #7491 e2e fails (resume exits 1, `COORD_LATE_PROJECTION_REFUSED`)
  and the negative control passes; on the lane both pass.
- ruff check / ruff format --check --force-exclude / C901: clean. mypy: no new errors (the three
  remaining no-any-return errors exist on the base). `__all__` present. Trailers present. Leeway
  edits recorded in history.
