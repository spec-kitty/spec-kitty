---
work_package_id: WP02
title: Derive the Mission's source issue and never classify it non-gating
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- NFR-002
- NFR-003
- C-003
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Cause 2
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/tasks/test_issue_matrix_source_issue_7011.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tasks/issue_reference_discovery.py
- src/specify_cli/tasks/issue_matrix.py
- tests/tasks/test_issue_matrix_source_issue_7011.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7011'
---

# Work Package Prompt: WP02 – Derive the Mission's source issue and never classify it non-gating

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

## Objectives & Success Criteria

- The Mission's source issue is derived from, in order: `meta.json`
  `source_description` (leading `Issue #N:` / `#N:` form), the spec's `**Input**:` line
  (first same-repo reference on it), and `Closes|Fixes|Resolves #N` lines (FR-002, SC-002).
- A source issue that is cited in any scanned artifact is always
  `implementation_target`, whatever its line reads (FR-003, US2).
- An uncited source issue gains no row — the zero-reference rule (#6653) is unchanged
  (US2 scenario 4).
- Scaffold and discovery agree because they share one promotion helper (FR-004).
- A missing, unreadable or malformed `meta.json` raises nothing and changes nothing
  (NFR-002); at most one `meta.json` + one `spec.md` read per call (NFR-003).
- `not-applicable` stays a legitimate explicit verdict (C-003).

## Context & Constraints

- Consumer map: `../research/code-grounding.md` §4. Four consumers, one predicate
  (`is_gating` / `gating_issue_numbers`) — attach the promotion there, never in a
  fourth predicate.
- `_scaffold_issue_matrix_locked` calls `detect_issue_references(spec_md_path)` (single
  file) and has no `feature_dir`; it must apply the same promotion with
  `spec_md_path.parent` as the mission directory.
- Free-form `source_description` values in this repository are mostly prose without
  issue numbers ("Refactor mission system to address architectural concerns…") — the
  leading-form rule must leave those alone.
- Do not add a second `#NNNN` regex (C-002): reuse the pattern in `issue_matrix.py`
  through a small public text helper there.

## Branch Strategy

Populated by `finalize-tasks`; depends on WP01.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first source-issue tests

- `tests/tasks/test_issue_matrix_source_issue_7011.py` (`fast` + `regression`):
  1. `meta.json` `source_description` = `Issue #6926: anchor the sdist README include…`
     plus a `spec.md` that mentions `#6926` only under `Parent epic: #6926` → the
     scaffolded row for `#6926` is `unknown`. (Red on the base: `not-applicable`.)
  2. No `meta.json`, spec header `**Input**: Issue #7011 — …`, and the spec cites
     `#7011` under a context marker → `unknown`.
  3. No `meta.json`, no `**Input**:` line, spec line `Closes #7011` plus a
     context-marked mention → `unknown`.
  4. A mission whose `source_description` names `#7011` but whose artifacts never
     mention it → no row for `#7011` and `discover_issue_references` returns nothing.
  5. Malformed / unreadable / absent `meta.json` → classification equals the
     metadata-free baseline (NFR-002).
- Record the red output before implementing.

### Subtask T006 – Derive the source issues

- Add `mission_primary_issue_numbers(feature_dir: Path) -> frozenset[int]` to
  `issue_reference_discovery.py`, plus its two private readers (meta and spec). All
  reads are guarded: `FileNotFoundError`, `OSError`, `json.JSONDecodeError`,
  `UnicodeDecodeError`, non-dict JSON and non-str fields degrade to "no contribution".
- Add `issue_numbers_in_text(text: str) -> list[int]` to `issue_matrix.py` (reuses
  `_GH_ISSUE_PATTERN` + `_matched_issue_number`, so cross-repo URLs stay excluded) and
  consume it from the derivation rather than writing a new pattern.
- `**Input**:` line = the first stripped line starting with `**Input**`; take its first
  reference. `Closes|Fixes|Resolves #N` = case-insensitive scan of the whole spec, all
  matches (a mission may close more than one issue).

### Subtask T007 – Promote in the one gating seam

- Add `promote_source_issue_references(refs, source_issues) -> list[IssueReference]`
  returning refs whose `classification` is forced to `implementation_target` when the
  number is in `source_issues` (`IssueReference._replace`), leaving every other field
  untouched.
- Call it at the end of `discover_issue_references` (so the approval blocker, doctor
  and merge gate inherit it through `is_gating`) and in
  `_scaffold_issue_matrix_locked` after `detect_issue_references` (so the scaffolded
  row is `unknown`), deriving the source issues from `spec_md_path.parent`.
- Do not create rows: promotion filters the references that already exist.

### Subtask T008 – Verify

- `uv run --frozen pytest tests/tasks/test_issue_matrix_source_issue_7011.py tests/tasks/ -q`
- `uv run --frozen pytest tests/specify_cli/tasks/ tests/specify_cli/cli/commands/review/test_zero_reference_not_applicable.py -q`
- `uv run --frozen pytest tests/status/ -q -k issue_matrix`
- ruff check/format + mypy on the changed files.

## Test Strategy

Each derivation source gets its own fixture (SC-002 = 3 of 3), with a negative control
proving an uncited source issue invents nothing and a malformed-metadata control proving
fail-open (NFR-002). The scaffold path is used for the assertions, not the helper.

## Risks & Mitigations

- Over-promotion from `source_description` prose → only the leading `Issue #N:` / `#N:`
  form qualifies; the fleet convention is exercised by the fixtures.
- A second read of `spec.md` in discovery → acceptable (NFR-003 bounds it at one extra
  read); prefer reading the already-scanned `spec.md` text once inside the derivation.
- Import cycles: `issue_reference_discovery` must keep its deferred import of
  `issue_matrix` (the module already defers it for the patch seam).

## Review Guidance

- Confirm every new read is guarded and that no `except Exception` swallows a
  programming error silently (log at debug where the module already does).
- Confirm promotion cannot add a row and cannot demote one.
- Confirm the scaffold and the discovery path call the SAME promotion helper.
