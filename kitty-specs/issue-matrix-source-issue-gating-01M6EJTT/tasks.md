# Work Packages: Never auto-demote the issue a Mission exists to fix

**Inputs**: Design documents from `kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/`
**Prerequisites**: plan.md, spec.md, research/code-grounding.md

**Tests**: Required. Both causes are driven red-first through `scaffold_issue_matrix`
(the observable production path) before the classifier is touched.

**Organization**: Three packages, sequenced because the second promotion lands on the
first's corrected classification, and the third asserts that all four consumers agree
on the result.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Scope positional citation labels to their own reference (Priority: P1)

**Goal**: A `parent #` / `epic #` / leading `see #` label demotes only the reference it
leads into, so `**Input**: Issue #6926 (part of epic #6100, …)` keeps `#6926` gating and
`#6100` context-only.
**Independent Test**: `uv run --frozen pytest tests/tasks/test_issue_matrix_citation_label_scope_7011.py -q` is red on the base and green after the change.
**Prompt**: `tasks/WP01-citation-label-scope.md`
**Requirement Refs**: FR-001, FR-005, NFR-001, C-001, C-002, SC-001

### Included Subtasks

T001 Add the red-first repro (scaffold path + direct classifier twin) in `tests/tasks/test_issue_matrix_citation_label_scope_7011.py`; capture the red output on the base (WP01)
T002 Retain the citation offset on `Occurrence` and populate it in `detect_issue_references` (WP01)
T003 Require a positional citation label to end at the citation it describes; keep whole-line semantics when the offset is unknown (WP01)
T004 Run the classification suites, ruff check/format and mypy on the changed files (WP01)

### Implementation Notes

- The pattern stays one definition; only the match *site* changes.
- Do not remove the `epic`/`parent`/`see` arms: #3469's fail-open hole is pinned by an
  existing test.

### Parallel Opportunities

- None: the red test comes first and the fix follows in the same package.

### Dependencies

- None.

### Risks

- Off-by-one when the regex consumes the whitespace before `#`; compute from the capture
  group offset.
- Over-narrowing breaks `Parent context: #200 explains history.` — the pre-existing
  classifier suite is the control.

---

## Work Package WP02: Derive the Mission's source issue and never classify it non-gating (Priority: P1)

**Goal**: The issue the Mission exists to fix is derived from `meta.json`
`source_description`, the spec's `**Input**:` line, or `Closes`/`Fixes`/`Resolves #N`,
and is always `implementation_target` — in the scaffold and in every gate, through one
shared promotion helper.
**Independent Test**: `uv run --frozen pytest tests/tasks/test_issue_matrix_source_issue_7011.py -q` is red on the base and green after.
**Prompt**: `tasks/WP02-source-issue-promotion.md`
**Requirement Refs**: FR-002, FR-003, FR-004, NFR-002, NFR-003, C-003, SC-002

### Included Subtasks

T005 Add the red-first source-issue repros: three derivation sources, the uncited-source negative control, and the malformed-metadata fail-open control (WP02)
T006 Add `mission_primary_issue_numbers` (guarded meta + spec readers) and the `issue_numbers_in_text` helper that reuses the one `#NNNN` pattern (WP02)
T007 Add `promote_source_issue_references` and call it from both `discover_issue_references` and the scaffold, without inventing rows (WP02)
T008 Run the tasks/specify_cli-tasks/status/zero-reference suites, ruff and mypy (WP02)

### Implementation Notes

- Promotion only rewrites `classification` on an existing reference.
- `_scaffold_issue_matrix_locked` derives the source issue from `spec_md_path.parent`.

### Parallel Opportunities

- None: depends on WP01's corrected classification.

### Dependencies

- WP01.

### Risks

- Over-promotion from prose: only the leading `Issue #N:` / `#N:` form qualifies.
- Unguarded metadata read would raise inside the approval blocker, which must only fail
  closed on its own rule.

---

## Work Package WP03: Pin cross-consumer agreement and document the narrowed rule (Priority: P2)

**Goal**: The scaffold, the approval blocker, `status doctor` and the merge gate return
the same gating set for the promoted issue; the reference doc and a per-PR changelog
fragment describe the narrowed rule.
**Independent Test**: `uv run --frozen pytest tests/policy/test_issue_matrix_cross_site_consistency.py -q`.
**Prompt**: `tasks/WP03-consumer-agreement-docs.md`
**Requirement Refs**: FR-004, FR-005, SC-003, SC-004

### Included Subtasks

T009 Extend `tests/policy/test_issue_matrix_cross_site_consistency.py` with the shared fixture: four views agree, `#6100` gates nowhere, an omitted source row is reported missing (WP03)
T010 Update `docs/development/reference/issue-matrix-verdicts.md`: positional vs line-scoped demotion signals, plus the source-issue guarantee (WP03)
T011 Add the per-PR changelog fragment in `docs/changelog/unreleased/` (WP03)
T012 Run the cross-site/tasks suites, `check_changelog_style`, `check_docs_freshness --ci` and the legacy-terminology test (WP03)

### Implementation Notes

- Extend the existing cross-site module rather than adding a second one.
- Verify docs freshness with the checker, never with a full shared-cache rebuild.

### Parallel Opportunities

- T010/T011 are independent of T009 and may run alongside it.

### Dependencies

- WP01, WP02.

### Risks

- Documenting the old flat signal list would contradict the code.
- Regenerating the whole docs index on a shared host is unsafe.
