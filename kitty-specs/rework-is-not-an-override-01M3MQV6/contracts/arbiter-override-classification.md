# Contract: arbiter override classification

`is_arbiter_override_history(events, wp_id, old_lane, target_lane, force) -> bool` is pure.

It returns True iff all four hold:

- `force`;
- `old_lane` resolves to `planned`;
- `target_lane` resolves to `approved` or `done`;
- the WP's latest event with `to_lane == planned` has `from_lane ∈ {for_review, in_review}` and a non-`None` `review_ref`.

`review/arbiter.py::_is_arbiter_override(feature_dir, wp_id, old_lane, target_lane, force)` keeps its signature (it is pinned through the `_detect_arbiter_override` compat re-export) and delegates to this predicate. `read_events` returns lane transitions only, so with the WP in `planned` "the latest transition into planned" is the latest event. The rejection lookup is a private helper in `arbiter.py`. `_run_arbiter_override` (`tasks_move_task.py:~3681`) independently copies `wp_events[-1].review_ref` via `read_events_transactional`. For a WP in `planned` that is the same rejection event, so the two agree for LANES/flat missions, and the runner is left unchanged to keep file ownership disjoint. The read-path divergence under a coordination topology (post-plan D4) is recorded as a residual in research R-07.

`approved → planned` (a reopen) is **deliberately excluded** from the rejection sources, as on the base. It is not a review rejection of submitted rework.

Consumers are unchanged:

- `tasks_transition_core.arbiter_persist_signal`
- `Emit.arbiter_forward`
- `tasks_verdict_persistence.py:~842`

Truth-table deltas versus the base:

| Case | Base | New |
|---|---|---|
| Forced `planned → for_review` after a `for_review` rejection | True | **False** |
| Forced `planned → claimed` after a `for_review` rejection | True | **False** |
| Forced `planned → approved` after a `for_review` rejection | True | True |
| Forced `planned → approved` after an `in_review` rejection | False | **True** |
| Forced `planned → done` after a rejection (with `--done-override-reason`, clearing `_guard_done_ancestry`) | False | **True** |
| Any unforced move | False | False |
| Forced move after a rollback with no `review_ref` | False | False |
