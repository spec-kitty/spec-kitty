---
work_package_id: WP01
title: Derive the wire pointer and gate the edge
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-009
- SC-001
- SC-002
- SC-003
- SC-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-006
planning_base_branch: issue-7080-gated-in-review-rewind
merge_target_branch: issue-7080-gated-in-review-rewind
branch_strategy: Planning artifacts for this mission were generated on issue-7080-gated-in-review-rewind. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7080-gated-in-review-rewind unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - The fix
history:
- at: '2026-11-03T09:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/transition_pipeline.py
create_intent:
- tests/status/test_forced_rewind_requires_review_ref.py
- tests/status/test_transition_pipeline.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/transition_pipeline.py
- src/specify_cli/status/wp_state.py
- src/specify_cli/status/validate.py
- tests/status/test_forced_rewind_requires_review_ref.py
- tests/status/test_transition_pipeline.py
- tests/status/test_transitions.py
- tests/status/fsm_parity_baseline.jsonl
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7080'
---
# Work Package Prompt: WP01 – Derive the wire pointer and gate the edge

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Context

Issue #7080. The pinned `spec_kitty_events` contract gates three rewinds to `in_progress`
(`for_review`, `in_review`, `approved`) on a non-empty `review_ref`, forced or not. This base
gates only `for_review` (`approved` is #6955 / PR #7102). The `in_review` edge is the reported
gap. Its evidence is a **structured** `review_result` that `prepare_transition` never turns
into a `review_ref`, which is why #6955 deferred the edge: gating it alone would refuse
legitimate writes.

Read first: `src/specify_cli/status/transition_pipeline.py` (`prepare_transition`),
`src/specify_cli/status/wp_state.py` (`REVIEW_REF_REQUIRED_EDGES`, `check_transition`),
`src/specify_cli/cli/commands/agent/tasks_transition_core.py::build_transition_plan` (the
existing `move-task` derivation this mirrors), and
`tests/status/test_forced_rewind_requires_review_ref.py` (the door fixture and the #6955 pin).

## Subtasks

**T001 (red first).** Through the real `agent status emit` door on a WP in `in_review`, emit
`--to in_progress --review-result-json '{"reviewer": ..., "verdict":
"changes_requested", "reference": "review-cycle://WP01/1"}'` and assert the last
`status.events.jsonl` row carries `review_ref == "review-cycle://WP01/1"`, and that rebuilding
that row as a `spec_kitty_events.status.StatusTransitionPayload` and calling
`validate_transition` yields `valid is True`. Fails before the fix (`review_ref: null`,
invalid). A unit-level twin on `prepare_transition` is welcome.

**T002 (red first).** On the same fixture, the pointerless forced rewind through
`agent status emit` must exit non-zero naming `review_ref`, with `status.events.jsonl` and
`status.json` SHA-256 unchanged; the structured-review-request twin appends exactly one row and
`status validate` exits 0. Before the fix the pointerless request exits 0 and appends.

**T003.** Add `(Lane.IN_REVIEW, Lane.IN_PROGRESS)` to `REVIEW_REF_REQUIRED_EDGES` — the one
owning definition — and update the module comment and the `status/validate.py` docstring so
they name the widened set and why the derivation had to land first.

**T004.** Flip the #6955 deferral pins deliberately: in
`tests/status/test_forced_rewind_requires_review_ref.py`, `("in_review", "in_progress")` moves
out of `test_requires_review_ref_excludes_every_other_edge` and out of
`test_force_elsewhere_is_unchanged` into the positive pin, with a comment stating that the
deferral from #6955 is now closed. Do not add or remove any assertion about the `approved`
edge: it is #6955/PR #7102's.

**T005.** Ratchet, merge-order independent: every member of the local set is proven to be a
real requirement of the installed `spec-kitty-events` (pointerless forced payload invalid,
`force-override`-carrying payload valid, same fixture), the local set is a subset of the
contract's `_REVIEW_REF_GATED_REWINDS`, and the derivation performs no I/O (no `Path.read_text`
/ `open` / `subprocess.run` while `prepare_transition` derives).

**T006.** Amend `tests/status/fsm_parity_baseline.jsonl` by exactly the four
`in_review -> in_progress` / `in_review -> doing` rows for the `force_full` and `review_result`
contexts, and extend the amendment note in `tests/status/test_transitions.py` with the date,
the issue and the reason. No other row may move (`NFR-003`).

**T007.** Writer/auditor pins: the requirement is force-insurmountable on the added edge; a
`migration:` actor stays exempt; an explicit `--review-ref` wins over the structured reference;
a blank explicit pointer is still refused; a pointerless stored row is reported by
`validate_event_schema` while its pointer-carrying twin is clean.

## Definition of Done

- `pytest -q tests/status/test_forced_rewind_requires_review_ref.py tests/status/test_transition_pipeline.py tests/status/test_transitions.py` green.
- No change to `spec-kitty-events`, no new sentinel, no other edge's verdict moved.
- Red-first evidence kept in the commit history (the two red commits precede the fix).
