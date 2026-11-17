---
affected_files: []
cycle_number: 1
mission_slug: consolidate-retarget-01M7M5JA
reproduction_command:
reviewed_at: '2026-11-17T10:11:42Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review (claude::reviewer-renata) - changes requested

## Blocking finding: an adopted retarget leaves the persisted landing target on the old branch

`resolve._adopt_retarget` (src/specify_cli/consolidation/resolve.py, about lines 357-366) copies this run's
retarget record onto a LOADED merge record that has no snapshot (zero progress, or re-baselined after a
full restore, #6770). It does not touch `state.target_branch`. Such a record was created by an earlier
plain run on the recorded (old) target, so `state.target_branch` is still the OLD target.

The executor then reseeds the run's landing target from the persisted record
(executor.py:636, `lanes_manifest.target_branch = state.target_branch`). Result:

- the entry preflight judged and admitted a retarget onto the new target (prints `Retargeting ... old -> new`);
- `_phase_retarget_record` commits `target_branch = new` plus a `retarget_history` entry on the Mission branch and on the new target;
- every later phase (merge, bookkeeping, landing, rollback snapshot, cleanup) runs against the OLD target.

The landing goes to the branch the operator moved away from, and `meta.json` on the new target says something else.
That breaks FR-003, FR-004 and NFR-002 ("0 retarget commits on the old target" holds, but the landing lands there).

Reproduction (unit level, reviewer scratch):

```python
save_state(ConsolidationState(mission_id="M", mission_slug="m", target_branch="main", wp_order=["WP01"]), d)  # re-baselined plain run on main
rt = {"from": "main", "to": "develop", "actor": "a", "at": "t", "reason": "r", "committed": False}
state, resumed = _load_or_create_merge_state(main_repo=d, mission_slug="m", canonical_id="M",
    target_branch="develop", wp_order=["WP01"], push_requested=False, retarget=rt)
# -> resumed True, state.target_branch == "main", state.retarget["to"] == "develop"
```

The existing test `test_loaded_record_without_a_retarget_adopts_one_only_without_a_snapshot`
(tests/consolidation/test_retarget_record.py:455) does not catch this. Its loaded record already has
`target_branch="develop"`, the same value as the retarget's `to`.

This scenario is realistic. A plain run on the recorded target that fails at the gate is fully restored and
re-baselined (the record is kept). The operator then decides to retarget. This is close to the motivating
#7692 flow.

### Required fix (pick one and pin it)

1. When `_adopt_retarget` adopts a record (it only does so with no snapshot, so nothing of an earlier attempt
   depends on the old target), also set `state.target_branch = retarget["to"]` and save. Or:
2. Refuse up front with a named code when a loaded record's `target_branch` differs from the retarget's `to`,
   and point the operator at `consolidate --abort`.

Option 1 matches the adoption docstring. Either way, also make sure no other persisted target-scoped field of
a re-baselined record still names the old target (for example `target_baseline` or `restore_targets`, if
the re-baseline keeps any of them).

### Tests to add

- `_load_or_create_merge_state` with a loaded, snapshot-free record whose `target_branch="main"` and
  `retarget={"from": "main", "to": "develop", ...}`. Assert `state.target_branch == "develop"` (option 1)
  or the named refusal (option 2), and assert the persisted record agrees.
- An executor-level test, in the style of the existing `test_retarget_record.py` git-fixture tests: a
  re-baselined record left by a plain run on `main`, then `--target develop --retarget`. Assert that the
  landing and the retarget commit are both on `develop` and that `main` did not move, or the named refusal
  with 0 branch moves (NFR-001).

## Verified and fine (no change needed)

- Plain `--target` path: `target_override_verdict(retarget=False)` is exactly the #6464 then #5783 chain
  (preflight.py:1621-1643). The protected-status probe is unchanged when `is_retarget` is False
  (entry_preflight.py `_refuse_protected_status_target_or_continue`). The only addition before the probe is a
  read-only `load_state` / `resolve_merge_target_branch`.
- `_phase_retarget_record` is the first call inside the rollback `try`, under `reporting_advance_intents`
  (executor.py:735-736). It is decorated `@_record_post_mutation_tips`. Idempotency comes from the
  `(from, to, at)` dedupe. `_persist_retarget_committed` is module-level. No new `restore_branch_ref`; the
  single-rollback-authority AST pin passes.
- Status surface: `_capture_coord_checkpoint` maps the old target to the new one
  (run_state.py `status_surface_tip(..., retarget=...)`), so the old target never enters the snapshot. A
  coordination ref is never equal to `from`, so coordination is untouched.
- Attestation routing (`_retargeted_identity`, status_transition.py) swaps only a destination equal to the
  old recorded target. On a default `single_branch` Mission the status surface before landing is the topic
  branch, so the swap is a no-op there, which is correct. A commit-to-target `single_branch` Mission is
  refused earlier by `RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET`, so no hole there.
- `RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET`: narrow (only `mission_branch == recorded_target` and the targets
  differ), pure, and pinned end to end (test_retarget_record.py:387-409).
- Re-baseline keeps the retarget with `committed=False` (rollback.py). `RETARGET_RESUME_MISMATCH` fires
  before the probe.
- ruff check: clean. `ruff format --check --force-exclude`: clean. C901: clean. mypy: 0 new findings
  (7 pre-existing at base, 7 at head).
