# Tasks: Issue-matrix reference over-matching

**Mission**: `issue-matrix-over-matching-01M81KK0` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first acceptance tests (colours, commit citation, scope, closing keyword) | WP01 | |
| T002 | Number filter: leading zero and CSS-declaration colour (D1) | WP01 | |
| T003 | Converge closing-keyword and source-description patterns onto the canonical detector (D2) | WP01 | |
| T004 | Commit-citation positional rule in the classifier (D3) | WP01 | |
| T005 | Scope rule: `in_gating_scope` on Occurrence, set by discovery, read by the classifier (D4) | WP01 | |
| T006 | Re-pin tests that pinned the old over-matching; ADR 2026-09-20-1 amendment (D5) | WP01 | |

## WP01 - Narrow the issue-matrix detector and classifier

- **Goal**: only real, in-scope issue statements gate approval (FR-001..FR-007).
- **Priority**: P1
- **Independent test**: the four acceptance cases in T001 go red before the change and green after it.
- **Prompt**: [tasks/WP01-narrow-detector-and-classifier.md](tasks/WP01-narrow-detector-and-classifier.md)
- **Dependencies**: none

T001 Red-first acceptance tests (WP01)
T002 Number filter: leading zero and CSS-declaration colour (WP01)
T003 Converge the closing-keyword and source-description patterns (WP01)
T004 Commit-citation positional rule (WP01)
T005 Scope rule on Occurrence (WP01)
T006 Re-pins and ADR amendment (WP01)

Implementation sketch: tests first, then D1, D2, D3, D4, then the re-pins and the ADR.
Risks: re-pinned tests must name the scope ruling; out-of-matrix review tests are nightly-only and disclosed.
