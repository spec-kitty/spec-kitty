# Research — honest-feedback-file-drop-01M66FMD (#6699)

## Decisions

### D-1: The defect still reproduces on `main@512567ee` (grounded 2026-10-30)

Live reproduction through the production `move-task` Typer app (rework-loop
harness, `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py`):

| Edge | Result on main |
| --- | --- |
| `in_progress → for_review` + `--review-feedback-file` (existing file) | exit 0, `✓ Moved`, **no** warning, no review cycle — silent drop (reproduces) |
| `for_review → in_review` + `--review-feedback-file` | exit 0, **no** warning — silent drop (reproduces) |
| arbiter override `planned --force → approved` + `--review-feedback-file` | exit 0; the #6652 stderr warning **fires** ("was not recorded … an arbiter override is recorded as a review override, not an approval"); the event-sourced `ReviewOverride` records only the `--note` |

Supersession check: `git log -S` on `resolved_feedback_source` /
`_warn_feedback_file_not_recorded` shows the #6652 mission (commits
`74b5162393`, `24c4b63497`, `22ccd4c464`) landed approval-edge recording and the
skip-warning **after** issue #6699 was filed (issue 22:01Z; commits ~22:48Z
commit-date). It never touched the non-review edges or the `--help`
over-claim. Not superseded.

### D-2: Per-edge remedy — refuse on non-review edges, keep+pin the warning on the arbiter edge

Rationale from the issue text ("Pick one per edge") and the surrounding
contract:

- **Non-review edges** (neither review-rejection nor approval target): nothing
  consumes the file — no review cycle is written, no on-wire `review_ref`
  exists. The honest remedy is **refusal (exit 1)** with an edge-naming
  message. This matches the flag's already-strict validation
  (`_guard_feedback_file` refuses a missing path on *every* edge today) and the
  issue's own ordering ("refuse it (exit 1), or at least warn"). Refusal is
  safe here: the override/arbiter OLD-timing persists only arm on approval
  edges (`override_persist_signal` / `arbiter_persist_signal` both require an
  approval-lane target or `--skip-review-artifact-check`), and the new guard
  arm sits inside `_guard_feedback_file`, which pass-1 `decide_transition`
  runs before any lane hop — so a refused move writes nothing (NFR-001).
- **Arbiter override into `approved`/`done`**: already meets the issue's
  "at least warn on stderr" floor (D-1, row 3). The stronger remedy — recording
  the file in the arbiter decision artifact — needs either a fifth field on the
  frozen four-field `ReviewOverride` shape (`specify_cli.status.models`.
  `ReviewOverride`'s docstring forbids it; `persist_arbiter_decision`'s
  docstring records the folding rule) or polluting the `--note`-derived reason
  that `parse_category_from_note` parses back for the kanban display. That is
  a contract change → maintainer decision → **deferred** with a follow-up
  issue (named in the PR's `## Deferred`). This mission pins the existing
  warning **end-to-end** through the real CLI (FR-003), because today it is
  only pinned at writer level (`test_tasks_move_task_seam.py`).
- **Help text**: currently claims the file is "Recorded as the transition's
  on-wire review_ref rationale" unconditionally; narrowed to name the refusal
  (FR-004).

### D-3: Where the refusal lives

In `_guard_feedback_file` (`tasks_transition_core.py`), as a new leading arm:
when `feedback_provided` and the edge is neither a review-rejection edge
(`is_review_rejection_edge`) nor an approval edge (target in
`_APPROVAL_LANES`), refuse. The edge check precedes the exists/is-file checks
so the message explains the flag is useless on that edge regardless of the
path's validity. Guard-order constraints (C-002): the arm is inert on approval
edges, so `override_persist_signal` (guards before `_guard_rejected_verdict`)
and `arbiter_persist_signal` (guards before `_guard_issue_matrix`, which
includes `_guard_feedback_file`) are unchanged — on every edge where those
signals arm, the new arm cannot fire.

## Evidence

- Issue text: spec-kitty/spec-kitty#6699 (findings C1/C2 of mission
  `truthful-verdicts-and-gates-01M5WZCP`, #6652).
- `src/specify_cli/cli/commands/agent/tasks_transition_core.py`:
  `_guard_feedback_file` (validates on every edge), `is_review_rejection_edge`
  (frozen #4899 contract), `_APPROVAL_LANES`, `_GUARDS` order and the two
  OLD-timing persist signals.
- `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py`:
  `_warn_feedback_file_not_recorded`, `_approval_write_skip_reason`,
  `_persist_approved_review_cycle` (skip arms warn).
- `src/specify_cli/review/arbiter.py`: `persist_arbiter_decision` (frozen
  `ReviewOverride` four-field shape; reason folding), `get_arbiter_overrides_
  for_wp` (parses the reason back).
- No internal runtime caller passes `--review-feedback-file` on a non-review
  edge (grep over `src/`: every caller passes it on `--to planned` rejection
  edges or renders help text).

## Open questions (resolved by deferral, not blocking)

- Whether the arbiter decision artifact should one day carry the feedback
  file (content or pointer) — maintainer decision, follow-up issue filed at
  wrap-up; see D-2.
