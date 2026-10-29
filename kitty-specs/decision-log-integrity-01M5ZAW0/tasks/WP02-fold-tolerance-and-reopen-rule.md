---
work_package_id: WP02
title: Duplicated logs fold; reopen rule from the events package
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- C-003
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-4848-decision-open-lock
merge_target_branch: issue-4848-decision-open-lock
branch_strategy: Planning artifacts for this mission were generated on issue-4848-decision-open-lock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4848-decision-open-lock unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Reader side
history:
- at: '2026-10-27T19:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/specify_cli/decisions/test_index_fold_duplicate_open.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/index_fold.py
- tests/specify_cli/decisions/test_index_fold_duplicate_open.py
- tests/decisions/test_decisions_reconciler.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Duplicated logs fold; reopen rule from the events package

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- FR-003: `index_fold.fold_events` folds a decision with several `DecisionPointOpened` rows whose
  payloads are equal after removing `recorded_at`; result equals the fold of the earliest alone,
  in any row order. Rows whose payloads differ in any other field still raise `FoldError`.
- `doctor decisions` reports no malformed fold for such a log; `--repair` rebuilds the entry.
- FR-004: `is_allowed_terminal_reopen` is derived from
  `spec_kitty_events.decisionpoint.DECISION_POINT_TERMINAL_REOPEN`; `ALLOWED_TERMINAL_REOPEN`
  no longer exists in `src/`. Verdicts unchanged (deferred→resolved allowed; all else refused).
- C-003: every other doctor behaviour unchanged.

## Context & Constraints

- Operator rulings 1 and 2 (spec.md Intent Summary); research.md R-3, R-4.
- Do NOT adopt `reduce_decision_point_records` (needs full envelopes; #92/#6194).
- `_fold_opened` ignores `recorded_at`, so any identical row yields the same entry; still choose
  deterministically: `min(opened, key=lambda e: (str(e["payload"].get("recorded_at", "")), str(e.get("event_id", ""))))`.
- Callers of `is_allowed_terminal_reopen`: `service._is_allowed_terminal_reopen`,
  `consolidation/drivers.py` (merge driver) — keep the signature.
- Keep the module docstring accurate (it documents the fold's rules).

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: issue-4848-decision-open-lock
- **Merge target branch**: issue-4848-decision-open-lock

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement with: `spec-kitty agent action implement WP02 --agent claude --mission decision-log-integrity-01M5ZAW0`

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first tests

- Create `tests/specify_cli/decisions/test_index_fold_duplicate_open.py` (`pytest.mark.unit`):
  - build one opened row from a real `open_decision` (or a hand-built payload validated by
    `DecisionPointOpenedInterviewPayload`); copy it with a new `event_id`, later `at` and later
    `payload.recorded_at`;
  - `test_identical_duplicate_openings_fold_like_one` (both orders, parametrized) — equals
    `fold_events([original])`;
  - `test_identical_duplicate_openings_with_terminal_row_fold` (dup opens + one resolved row);
  - `test_three_identical_openings_fold`;
  - `test_duplicate_openings_differing_payload_refuse` (question changed) → `FoldError`
    (positive control on the same fixture);
  - `test_reopen_rule_comes_from_events_package`: `not hasattr(index_fold, "ALLOWED_TERMINAL_REOPEN")`,
    and for every `(a, b)` in `DECISION_POINT_TERMINAL_REOPEN` the mapped statuses are allowed,
    and no other status pair is (exhaustive over `DecisionStatus` terminal states).
- Commit alone; record red output.

### Subtask T007 – Re-pin stale tests

- `tests/decisions/test_decisions_reconciler.py::test_fold_events_rejects_duplicate_opened_events`
  and `::test_repair_reports_malformed_fold_instead_of_crashing` duplicate an IDENTICAL opened row
  to fake a malformed group. Under ruling 1 that group is now valid; the tests still mean to
  pin "malformed groups refuse / are reported". Re-pin them: make the duplicate's payload
  differ (e.g. `question` changed). Judge-the-test (charter SO#4): stale fixture, valid intent.

### Subtask T008 – Fold tolerance

- In `_fold_events`: when `len(opened) > 1`, compare `{k: v for k, v in payload.items() if k != "recorded_at"}`
  across rows; all equal → keep the earliest (key above); otherwise raise
  `FoldError("more than one DecisionPointOpened event for one decision_point_id with differing payloads")`
  (keep the `"more than one DecisionPointOpened"` prefix: doctor output and tests match on it).
  Extract a small helper (`_select_opened_event`) to keep complexity low and testable.

### Subtask T009 – Reopen rule from the package

- `from spec_kitty_events.decisionpoint import DECISION_POINT_TERMINAL_REOPEN`; define the
  status-level view via `_OUTCOME_TO_STATUS` (private module constant) and make
  `is_allowed_terminal_reopen` read it. Delete `ALLOWED_TERMINAL_REOPEN`; fix comments in
  `index_fold.py` that name it (`_select_terminal_event`). `__all__` unchanged.
- Grep `src/` and `tests/` for `ALLOWED_TERMINAL_REOPEN`; there must be no reference left.

### Subtask T010 – Doctor acceptance + CHANGELOG

- Add `test_doctor_and_repair_accept_identical_duplicate_openings` to
  `tests/decisions/test_decisions_reconciler.py`: seed a decision, append an identical-but-for-
  `recorded_at` copy of its opened row, drop the index entry; `doctor decisions --json` (helper
  `_invoke_doctor_decisions_json`) reports no malformed folds; `--repair` restores the entry
  equal to the original; the log bytes are unchanged (no rewrite).
- `docs/changelog/CHANGELOG.md` `[Unreleased]` → `### Fixed`: one entry covering #4848 (open
  half: concurrent identical opens / concurrent retries write one opening; existing duplicated
  logs read again, nothing rewritten) and the #6412 reopen-rule part (refs #6412; envelope half
  stays with spec-kitty-events #92 / #6194). Plain language, no model ids.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/decisions/test_index_fold_duplicate_open.py tests/decisions/test_decisions_reconciler.py \
  tests/decisions/test_defer_resolve_repair_4919.py tests/specify_cli/decisions tests/consolidation -k "decision or reopen"
uv run --frozen ruff check src/specify_cli/decisions/index_fold.py <tests>
uv run --frozen ruff format --check --force-exclude src/specify_cli/decisions/index_fold.py <tests>
uv run --frozen mypy src/specify_cli/decisions/index_fold.py <new test file>
```

## Risks & Mitigations

- Over-tolerance hides a real conflict → differing-payload control; only `recorded_at` is ignored.
- Merge-driver order → both orders tested.

## Review Guidance

- Red→green for T006; T007 re-pins keep their intent (still prove malformed handling).
- No `ALLOWED_TERMINAL_REOPEN` left; reopen verdicts unchanged.
- Log never rewritten by doctor/--repair.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks mark-status T006 --status done`
- `spec-kitty agent tasks status`
