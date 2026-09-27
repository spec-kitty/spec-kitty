# Decision Moment `01M3GNE8NKNQ9214VCEP4GD5DW`

- **Mission:** `review-feedback-to-implementer-01M3GKZ8`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.rejection-edge-seam`
- **Input key:** `rejection_edge_seam`
- **Status:** `resolved`
- **Created:** `2026-09-27T05:29:39.251578+00:00`
- **Resolved:** `2026-09-27T05:30:32.642117+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should the four scattered Lane.PLANNED-keyed write-side gates be coupled so the re-implement (in_review->in_progress) edge cannot be half-fixed (C-003)?

## Options

- Single is_review_rejection_edge(old,target) predicate as SSOT replacing all four == PLANNED checks
- Add an == IN_PROGRESS clause at each of the four sites independently
- Introduce a new Emit.is_review_rejection flag only

## Final answer

Single is_review_rejection_edge(old_lane, target_lane) predicate as SSOT. Defined pure in tasks_transition_core.py as: resolve_lane_alias(old)==IN_REVIEW and resolve_lane_alias(target) in (PLANNED, IN_PROGRESS), unioned with target==PLANNED (preserving the existing any-source ->planned rollback guard). It replaces the four scattered == Lane.PLANNED checks: (1) content read in _mt_resolve_feedback (tasks_move_task.py:615), (2) Emit.planned_rollback construction (tasks_transition_core.py:829, generalized to the predicate and renamed is_review_rejection so the persist-call gate at tasks_move_task.py:2334 and rebuild trigger at :2371 flip together), (3) emit_review_ref selection (tasks_transition_core.py:296), (4) _guard_planned_rollback refusal (tasks_transition_core.py:596). Coupling enforced by construction, not discipline. NFR-003: arbiter-forward edges are in_review->{approved,done}, outside the predicate, so the arbiter emit is untouched.

## Rationale

_(none)_

## Change log

- `2026-09-27T05:29:39.251578+00:00` — opened
- `2026-09-27T05:30:32.642117+00:00` — resolved (final_answer="Single is_review_rejection_edge(old_lane, target_lane) predicate as SSOT. Defined pure in tasks_transition_core.py as: resolve_lane_alias(old)==IN_REVIEW and resolve_lane_alias(target) in (PLANNED, IN_PROGRESS), unioned with target==PLANNED (preserving the existing any-source ->planned rollback guard). It replaces the four scattered == Lane.PLANNED checks: (1) content read in _mt_resolve_feedback (tasks_move_task.py:615), (2) Emit.planned_rollback construction (tasks_transition_core.py:829, generalized to the predicate and renamed is_review_rejection so the persist-call gate at tasks_move_task.py:2334 and rebuild trigger at :2371 flip together), (3) emit_review_ref selection (tasks_transition_core.py:296), (4) _guard_planned_rollback refusal (tasks_transition_core.py:596). Coupling enforced by construction, not discipline. NFR-003: arbiter-forward edges are in_review->{approved,done}, outside the predicate, so the arbiter emit is untouched.")
