# REASONS Canvas — honest-feedback-file-drop-01M66FMD

## Requirements

One sentence: a supplied `--review-feedback-file` must never be validated and
then silently dropped by `move-task` (#6699).

- **Problem**: `move-task` resolves the file on every edge, but only the
  rejection writer and the approval writer consume it. On edges that write no
  review cycle the file was validated and dropped in silence.
- **Acceptance criteria**: see `spec.md` FR-001..FR-004 and SC-001..SC-005.
  Must (Safeguards): non-review edges refuse the flag (exit 1) with no durable
  write; rejection/approval edge behaviour is unchanged. Should (Norms): the
  refusal names the actual edge and the recording edges; the arbiter-override
  warning is pinned end-to-end. May (Approach options): recording the file in
  the arbiter decision artifact — deferred (contract change, follow-up issue).
- **Definition of done**: the red-first tests per edge are green, the
  `--help` text and its golden fixture are narrowed, `#6652`'s tests pass
  unmodified, changelog entry under `[Unreleased]`.

## Entities

One sentence: the domain concepts are the flag, the edge families that consume
it, and the two writers.

- **`--review-feedback-file`**: operator-supplied reviewer feedback; required
  on review-rejection edges, recorded-or-warned on approval edges (#6652),
  refused everywhere else after this mission.
- **Review-rejection edge**: any `* → planned`, plus `in_review → in_progress`
  (frozen #4899 contract, `is_review_rejection_edge`).
- **Approval edge**: target `approved` or `done` (`_APPROVAL_LANES`); consumes
  the file via `_persist_approved_review_cycle`.
- **Non-review edge**: every other FSM edge; writes no review cycle and no
  on-wire `review_ref` — the complement of the two families above.
- **Arbiter override**: `--force` from `planned` to `approved`/`done` over a
  standing rejection; recorded as a `ReviewOverride` (frozen four-field
  shape), never as an approval (I-4).
- **`_guard_feedback_file`**: the pure guard validating the supplied file; the
  refusal arm lands here.

## Approach

One sentence: refuse the flag inside the existing pure guard rather than
adding a guard slot or a second decision path.

- **Chosen**: a leading arm in `_guard_feedback_file`
  (`tasks_transition_core.py`) — edge check before the exists/is-file checks;
  exit 1 with an edge-naming message; nothing durable written before it.
- **Rejected**: warn-and-continue (weaker than the issue's first-listed
  remedy; the flag's validation is already strict); a new guard slot (changes
  the `_GUARDS` tuple and risks the OLD-timing signal slices for no gain);
  recording the file in the arbiter artifact (frozen `ReviewOverride` shape —
  maintainer decision, deferred).
- **Rationale and per-edge detail**: `research.md` D-2/D-3.

## Structure

One sentence: the change is confined to the guard module, the CLI help
registration and its golden fixture, one new e2e test file, and docs.

- Code: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`
  (guard arm + message helper), `tasks.py` (help text).
- Tests: `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py`
  (rework-loop harness, red-first) + `fixtures/tasks_cli/help/move-task.help`.
- Ownership boundary: `tasks_verdict_persistence.py`, `tasks_move_task.py`
  and `review/arbiter.py` are read-only context; no new writer, no new field.
- Concern map: `plan.md` IC-01..IC-03.

## Deviations

- None yet.

<!-- Retained below: the earlier Requirements/Entities capture from the specify step. -->
