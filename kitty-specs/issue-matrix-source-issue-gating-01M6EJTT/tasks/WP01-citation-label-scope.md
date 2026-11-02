---
work_package_id: WP01
title: Scope positional citation labels to their own reference
dependencies: []
requirement_refs:
- FR-001
- FR-005
- NFR-001
- C-001
- C-002
- SC-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Cause 1
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/tasks/test_issue_matrix_citation_label_scope_7011.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tasks/issue_reference_discovery.py
- src/specify_cli/tasks/issue_matrix.py
- tests/tasks/test_issue_matrix_citation_label_scope_7011.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7011'
---

# Work Package Prompt: WP01 – Scope positional citation labels to their own reference

## ⚡ Do This First: Load Agent Profile

Load the agent profile in the frontmatter (`python-pedro`, role `implementer`) and behave
according to its guidance before parsing the rest of this prompt.

## Objectives & Success Criteria

- `**Input**: Issue #6926 (part of epic #6100, …)` classifies `#6926` as
  `implementation_target` and `#6100` as `context_only` (SC-001, FR-001).
- The label arms that already demote keep demoting: `Tracked by the epic #6100`,
  `Parent context: #200`, a leading `see #200` (FR-005 ratchet, US1 scenario 3).
- `classify_occurrence`/`classify_occurrences` stay pure and deterministic (NFR-001).
- Existing `Occurrence(source_file=…, line_text=…)` construction keeps today's result
  (C-001); the `#NNNN` pattern stays defined once (C-002).

## Context & Constraints

- Evidence and exact line numbers: `../research/code-grounding.md` §2.
- `_CONTEXT_MARKER_PATTERN`'s own comment states the intended rule — "`parent`/`epic`
  sitting immediately … before the `#` ref". The match site, not the pattern, is wrong.
- Do **not** delete the `epic`/`parent`/`see` arms: #3469's fail-open hole (ordinary
  English words) is pinned by
  `tests/tasks/test_issue_reference_classification.py::test_ambiguous_english_word_on_implementation_line_still_gates`.
- Do not touch `issue_matrix_approval.py`, `status/doctor.py` or `merge_gates.py`.

## Branch Strategy

Populated by `finalize-tasks`. Single-branch mission: work in the repository root
checkout on the mission's write branch.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reproduction through the scaffold

- Add `tests/tasks/test_issue_matrix_citation_label_scope_7011.py` with a module
  `pytest.mark.fast` marker and a `pytest.mark.regression` repro marked to #7011.
- Drive the OBSERVABLE path (`scaffold_issue_matrix`, stubbing `mission_runtime.coord_read_dir_for`
  and `write_seam.write_artifact` exactly as `tests/tasks/test_issue_reference_classification.py`
  does): a `spec.md` whose only line is
  `**Input**: Issue #6926 (part of epic #6100, sdist packaging cleanup)`.
- Assert the pre-fix failure: `#6926` must be `unknown` (gating) and `#6100`
  `not-applicable`. On the base the first assertion fails — record that output in the
  WP history before fixing.
- Add the direct-classifier twin in the same file: two `Occurrence`s for the same line,
  one at each citation offset (via the position field added in T002), asserting
  `implementation_target` and `context_only` respectively.

### Subtask T002 – Retain the citation position

- In `issue_reference_discovery.py`, add an optional `ref_offset: int | None = None` to
  `Occurrence`, documented as "index in `line_text` at which the citation begins (the
  `#` of a bare reference, the `h` of an issue URL); `None` = unknown, whole-line
  semantics".
- In `issue_matrix.py::detect_issue_references`, compute the offset from the match and
  the stripped line: leading whitespace of the raw line plus the index of the `#`
  (`match.start(1) - 1` for the hash arm) or `match.start()` for the URL arm; pass it
  to `Occurrence`. Include it in the occurrence dedupe key so two different citations
  of the same number on one line are both kept.

### Subtask T003 – Require a positional label to end at its reference

- Split the marker definition into the non-positional arms (`follow-up:`,
  `baseline-red` — matched over the whole line, unchanged) and the positional arms
  (`^\s*see\s*#`, `(?:parent|epic)\b[^#\n]{0,12}#`).
- In `classify_occurrence`, when `ref_offset` is known, search the positional pattern
  over `line_text[: ref_offset + 1]` and demote only when a match **ends** at that
  boundary; when it is `None`, keep today's whole-line search (C-001).
- Keep the both-kinds-single-definition property: the patterns stay module constants in
  this module, and the docstrings/comments explain why the positional pair is separate.

### Subtask T004 – Verify

- `uv run --frozen pytest tests/tasks/test_issue_matrix_citation_label_scope_7011.py tests/tasks/test_issue_reference_classification.py -q`
- `uv run --frozen pytest tests/specify_cli/tasks/test_issue_matrix_structured.py -q`
- `uv run --frozen ruff check` and `ruff format --check` on the two source files and the
  new test; `uv run --frozen mypy` on the same.

## Test Strategy

Red first through `scaffold_issue_matrix` (the production path), then a direct
classifier twin that pins which number each label belongs to. Positive control on the
same fixture: the `epic`-labelled `#6100` still demotes, so a fix that simply disabled
the arm would fail.

## Risks & Mitigations

- Over-narrowing the window breaks `Parent context: #200 explains history.` → the
  existing classifier suite is the control; run it before declaring done.
- Off-by-one when a match consumes the whitespace before `#` → compute the offset from
  the capture group, not `match.start()`.

## Review Guidance

- Confirm the red output was captured on the base.
- Confirm `ref_offset=None` reproduces the pre-change classification exactly.
- Confirm no second `#NNNN` regex was introduced.
