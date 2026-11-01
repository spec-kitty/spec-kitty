# Contract: `move-task --review-feedback-file` edge applicability

**CLI surface**: `spec-kitty agent tasks move-task <task_id> --to <lane> [--review-feedback-file <path>]`
**Introduced in**: WP01 (guard arm in `_guard_feedback_file`, `tasks_transition_core.py`), WP02 (help text)
**Issue**: spec-kitty/spec-kitty#6699
**Companion**: [spec.md](../spec.md), [plan.md](../plan.md)

---

## Behaviour by edge family

The flag's applicability is the union of two edge families — everywhere else it
is **refused (exit 1)** before any lane hop or durable write:

| Edge family | Definition | Flag behaviour |
| --- | --- | --- |
| Review-rejection edges | any `* → planned` (incl. `--force`), plus `in_review → in_progress` (`is_review_rejection_edge`, #4899 frozen contract) | **Required.** Omitting it makes the status event contract-invalid; the file is recorded as the transition's on-wire `review_ref` rationale. |
| Approval edges | `→ approved`, `→ done` (`_APPROVAL_LANES`) | **Recorded-or-warned (#6652).** Content is recorded when the move writes a new approval review-cycle record; otherwise a warning on stderr says it was not recorded (JSON stdout unchanged). An arbiter override records only the `--note` in the `ReviewOverride` decision. |
| Every other edge | e.g. `planned → claimed`, `claimed → in_progress`, `in_progress → for_review`, `for_review → in_review`, `→ blocked`, forced rework exits | **Refused (exit 1).** No review cycle is written on these edges, so the file would be validated and then dropped. |

## Refusal shape

- Fires in pass-1 `decide_transition`, before the exists/is-file path checks and
  before any lane hop or durable write (nothing is written before the refusal).
- Exit code 1 via the standard `RefuseExit1` error envelope (`--json` included).
- Message names the task and the alias-resolved `old -> new` edge, states that
  the edge writes no review cycle, names the two recording edge families, and
  suggests removing the flag or using `--note`.
- On recordable edges the pre-existing path-check messages are unchanged:
  `Review feedback file not found: <path>` / `Review feedback path is not a
  file: <path>`.

## Invariants

- No guard slot was added to or reordered in `_GUARDS`; the arm is a leading arm
  inside `_guard_feedback_file` and is inert on approval lanes by construction
  (so the `arbiter_persist_signal` prefix slice is unchanged).
- The frozen surfaces are untouched: `is_review_rejection_edge`, the
  `_planned_rollback_message` texts, the four-field `ReviewOverride` shape, and
  `_mt_resolve_feedback`.

## Deferred

Recording the file (path or content) in the arbiter-override decision artifact
would need a fifth `ReviewOverride` field or folding it into the note-derived
reason — a contract change requiring a maintainer decision. Deferred; follow-up
issue to be filed at mission wrap-up and named in the PR description.

## Regression pins

`tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py`
(e2e refusals, positive controls, arbiter-override ratchet, unit matrix) and the
unmodified #6652 suite in `test_tasks_move_task_seam.py`.
