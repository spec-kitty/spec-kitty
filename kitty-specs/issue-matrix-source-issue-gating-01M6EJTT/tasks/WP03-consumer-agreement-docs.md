---
work_package_id: WP03
title: Pin cross-consumer agreement and document the narrowed rule
dependencies:
- WP01
- WP02
requirement_refs:
- FR-004
- FR-005
- SC-003
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - Agreement, docs, changelog
history: []
agent_profile: python-pedro
authoritative_surface: docs/development/reference/
create_intent:
- docs/changelog/unreleased/7011-issue-matrix-source-issue-gating.fixed.md
execution_mode: code_change
model: ''
owned_files:
- tests/policy/test_issue_matrix_cross_site_consistency.py
- docs/development/reference/issue-matrix-verdicts.md
- docs/changelog/unreleased/7011-issue-matrix-source-issue-gating.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7011'
---

# Work Package Prompt: WP03 – Pin cross-consumer agreement and document the narrowed rule

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

## Objectives & Success Criteria

- One shared fixture proves the scaffold, the approval blocker, `status doctor` and the
  merge gate return the same gating set for the promoted issue (SC-003, FR-004).
- The reference doc states which demotion signals are positional (they bind to the
  reference they precede) and that the Mission's source issue always gates.
- A per-PR changelog fragment exists in the documented shape; the root
  `docs/changelog/CHANGELOG.md` is untouched.

## Context & Constraints

- Cross-consumer module: `tests/policy/test_issue_matrix_cross_site_consistency.py`
  already owns this agreement contract — extend it, do not start a second file.
- Changelog shape: `docs/changelog/unreleased/README.md`; `check_changelog_style`
  rejects the old `[Unreleased]`-entry shape. Rename the fragment to `<pr>.fixed.md`
  once the PR number exists.
- Do not edit `docs/api/*` generated reference unless the diff actually changes the CLI
  surface (it does not).

## Branch Strategy

Populated by `finalize-tasks`; depends on WP01 and WP02.

## Subtasks & Detailed Guidance

### Subtask T009 – Cross-consumer agreement test

- Add a case to `tests/policy/test_issue_matrix_cross_site_consistency.py` built on the
  reported header line (`**Input**: Issue #6926 (part of epic #6100, …)` plus a
  `meta.json` naming `#6926`): assert the gating set from `gating_issue_numbers`, from
  the scaffolded rows with `verdict == "unknown"`, and from the approval blocker's own
  evaluation are equal, and that `#6100` is in none of them.
- Assert the blocker reports the source issue as **missing** when a matrix omits its
  row (US3 scenario 2).

### Subtask T010 – Document the rule

- In `docs/development/reference/issue-matrix-verdicts.md`, under "Default-gating
  fail-safe": split the demoting signals into line-scoped ones (`Follow-up:`,
  `baseline-red`) and positional ones (`see #`, `parent`/`epic`), and state that a
  positional label only demotes the reference it leads into.
- Add a short subsection: the Mission's source issue (from `meta.json`
  `source_description`, the `**Input**:` line, or `Closes`/`Fixes`/`Resolves #N`) is
  never auto-classified non-gating; cite #7011 and
  [ADR 2026-09-20-1](../../adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md)
  as the verdict design it preserves.

### Subtask T011 – Changelog fragment

- `docs/changelog/unreleased/7011-issue-matrix-source-issue-gating.fixed.md` in the
  documented shape: impact-first bold lead with `(#7011)`, then before/after, under
  1,200 characters.
- `uv run --frozen python -m scripts.docs.check_changelog_style`.

### Subtask T012 – Verify

- `uv run --frozen pytest tests/policy/test_issue_matrix_cross_site_consistency.py -q`
- `uv run --frozen pytest tests/tasks/ tests/specify_cli/tasks/ -q`
- `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (expect errors=0;
  this WP adds no ADR or page, so no index regeneration should be needed)
- `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`

## Test Strategy

Agreement is asserted from four independently-computed views of the same fixture, so a
fix wired into only one consumer fails. The missing-row assertion is the refusal/
absence probe, paired on the same fixture with the positive case (the promoted row
present and gating).

## Risks & Mitigations

- The docs page lists the signals flatly; leaving it unchanged would document the old
  behaviour — the doc edit is part of the deliverable, not a courtesy.
- Regenerating the whole docs index on a shared host is unsafe (brief, shared machine
  state) — verify with `check_docs_freshness --ci` instead of a full rebuild.

## Review Guidance

- Confirm the doc wording matches the code exactly (which arms are positional).
- Confirm the changelog fragment is a fragment, not a `CHANGELOG.md` edit.
