# Implementation Plan: Issue-matrix reference over-matching

**Branch**: `kitty/mission-issue-matrix-over-matching-01M81KK0` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/issue-matrix-over-matching-01M81KK0/spec.md`

## Summary

Narrow the issue-matrix detector and its one classifier so that colour values, commit-SHA
citations and out-of-scope prose stop forcing verdict rows. All number recognition goes
through `_GH_ISSUE_PATTERN` plus `_matched_issue_number` (`src/specify_cli/tasks/issue_matrix.py`);
all gating decisions go through `classify_occurrence`
(`src/specify_cli/tasks/issue_reference_discovery.py`).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: standard library `re` only (no new dependency)
**Storage**: N/A (pure text parsing over Mission artefacts on disk)
**Testing**: pytest, red-first through the existing entry points (`discover_issue_references`,
`detect_issue_references`, `classify_occurrence`, `mission_source_issue_numbers`)
**Target Platform**: the spec-kitty CLI (approval blocker, merge gate, `doctor`)
**Project Type**: single
**Performance Goals**: no extra file reads; per-line regex work stays linear
**Constraints**: no new `GatingClass` value; default-gating fail-safe inside the gating scope;
ruff/format/mypy clean without suppressions
**Scale/Scope**: two source modules, one ADR amendment, focused tests

## Charter Check

- Single canonical authority: one number detector, one filter, one classifier. The two
  duplicated `\d{2,6}` arms are removed, not mirrored. PASS.
- ATDD / red-first: the four acceptance cases from the brief are written first as failing tests
  through the public entry points. PASS (planned).
- Architectural gate discipline: no new allowlist. PASS.
- Terminology canon: Mission, not Feature. PASS.

## Design

### D1 - Number filter (#7808)

- `_GH_ISSUE_PATTERN` hash arm and URL arm require a first digit `1-9`. A leading-zero run
  then cannot match at that `#`, and it does not partially match either, because the `#` must
  sit directly before the digits.
- `_matched_issue_number` also returns `None` for an all-digit value in CSS declaration form.
  The declaration form is matched against the text that directly precedes the `#`:
  `(?:--[\w-]+|[\w-]*(?:color|colour|background|border|fill|stroke|outline|shadow)[\w-]*)\s*:\s*$`
  (case-insensitive). The match is only on the property name directly before the value, never a
  keyword elsewhere on the line, so a real reference on a line that mentions CSS is kept.

### D2 - Converge the three number patterns (FR-006)

- `_CLOSING_KEYWORD_PATTERN` becomes a label-only pattern that must end at the citation's `#`
  (like the positional context labels). `_source_issues_from_spec` walks the canonical
  detector's occurrences and asks the classifier helper whether a non-negated closing keyword
  leads into each one.
- `_SOURCE_DESCRIPTION_LEAD_PATTERN` keeps only the lead label
  (`issue`/`ticket`/`github issue`, optional `#`). The number after it is read through
  `issue_numbers_in_text`, and it must be the canonical match at that position. The hashless
  `Issue 123` form is normalised by prefixing `#` before delegation, so it gets the same filter.

### D3 - Commit citation rule (#5297)

- New positional rule in `classify_occurrence`: a backticked token of 7-40 hex characters with at
  least one `a-f` letter, ending within 16 characters before the citation's `#` or starting within
  16 characters after the citation's digits, gives `PR_OR_COMMIT_REF`. With no `ref_offset`, the
  whole line is searched (C-002 parity with the other positional rules).

### D4 - Scope rule (#5516)

- `Occurrence` gains `in_gating_scope: bool = True` (a trailing defaulted field, so positional
  construction is unchanged).
- `discover_issue_references` marks occurrences from `plan.md`, `research.md`,
  `analysis-report.md` and `contracts/*.md` as out of scope before classification, through one
  helper `_gating_scope_for(path, feature_dir)`.
- `classify_occurrence` order: a closing keyword leads in, giving `IMPLEMENTATION_TARGET`; then
  PR/commit, then out-of-scope (`CONTEXT_ONLY`), then the line markers, then the positional
  labels, then the default `IMPLEMENTATION_TARGET`.
- The source-issue promotion (#7011) still runs after classification, so the Mission's own issue
  gates wherever it is cited.

### D5 - ADR amendment (FR-007)

`docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md` gets an
"Amendment 2026-11-22" section. It records the scope rule, the closing-keyword precedence, the
commit-citation rule and the number filter, and states that the FR-011 fail-safe default now
holds inside the gating scope only.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-matrix-over-matching-01M81KK0/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/tasks/issue_matrix.py              # detector + filter (D1)
src/specify_cli/tasks/issue_reference_discovery.py # classifier, scope, convergence (D2-D4)
docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md  # amendment (D5)
tests/specify_cli/tasks/test_issue_reference_discovery.py
tests/specify_cli/tasks/test_issue_reference_terminators.py
tests/tasks/test_issue_reference_classification.py
tests/tasks/test_issue_matrix_source_issue_7011.py
```

**Structure Decision**: single project; changes stay inside the two owned modules.

## Implementation Concern Map

### IC-01 - Detector, classifier and ADR

- **Purpose**: deliver D1-D5 together. They share two small modules and one test family, so
  splitting them would only create merge overlap.
- **Relevant requirements**: FR-001..FR-007, NFR-001..NFR-003, C-001..C-003
- **Affected surfaces**: the two modules and the ADR above, plus their tests
- **Sequencing/depends-on**: none
- **Risks**: tests that pinned research/plan references as gating must be re-pinned with the
  scope ruling as the stated reason (SC-004); the out-of-matrix review tests are disclosed as
  nightly-only.
