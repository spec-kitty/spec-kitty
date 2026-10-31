# Tasks: Companion tactic neutrality scope

**Mission**: `companion-tactic-neutrality-scope-01M67JR8` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6724-companion-tactic-neutrality-scope`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first CLI proof: a known-scope project promotes a pytest-naming companion tactic | WP01 | |
| T002 | Unit positive/negative controls on `_is_generic_scoped` from one shared fixture | WP01 | |
| T003 | Move the companion section label to its existing owner (`interview_mapping`) | WP01 | |
| T004 | Narrow the scope rule: a companion tactic's scope is the project's stack | WP01 | |
| T005 | Blast-radius and quality gates on the touched charter test surface | WP01 | |
| T006 | State the rule in the gate's own contract text (module + predicate docstrings) | WP02 | |
| T007 | Amend the harness-handoff ADR with the scope rule | WP02 | |
| T008 | `[Unreleased]` changelog entry, impact-first, under 1,200 characters | WP02 | |
| T009 | Docs freshness check and the terminology guard | WP02 | |

## Phase 1 — Core fix

### WP01 — A companion tactic's scope is the project's stack

- **Prompt**: [tasks/WP01-companion-scope-rule.md](tasks/WP01-companion-scope-rule.md)
- **Goal**: `charter synthesize` promotes a companion tactic `how-we-apply-<directive-id>` that names the project's own test runner when the project's language scope is known (FR-001…FR-006, SC-001). A companion tactic in a project with no observed and no declared language is still refused (FR-004, SC-002), and every non-companion artifact keeps the existing slug-component rule (FR-005).
- **Priority**: P1 (MVP). **Dependencies**: none.
- **Independent test**: the new CLI acceptance case is RED on the planning base and GREEN on this WP's last commit, while the unconfigured-project case is RED-then-GREEN for the opposite reason (it must keep refusing).

T001 Red-first CLI proof (WP01)
T002 Unit positive/negative controls (WP01)
T003 Companion section label to its owner (WP01)
T004 Narrow the scope rule (WP01)
T005 Blast-radius and quality gates (WP01)

**Implementation sketch**: T001 (failing, committed as the red proof) → T002 (failing unit expectations, same commit) → T003 (constant + import; behaviour unchanged, tests still red) → T004 (rule; tests go green) → T005.
**Risks**: the CLI fixture needs a real activation record and a real generated-artifact tree, or synthesis never asks for the companion; a hand-rolled `ProvenanceEntry` in the unit test could pass `source_section` the production path never sets, so T001 drives the production path and T002 only pins the classification.

## Phase 2 — Contract text and release notes

### WP02 — Say what the gate lints, and why

- **Prompt**: [tasks/WP02-docs-and-changelog.md](tasks/WP02-docs-and-changelog.md)
- **Goal**: the gate's module and predicate docstrings state the rule an operator and the next maintainer need (FR-007), the harness-handoff ADR records the amendment (FR-008), and the changelog carries the user-facing before/after.
- **Priority**: P2. **Dependencies**: WP01 (it describes the behaviour WP01 delivers).
- **Independent test**: reading `_is_generic_scoped` alone tells a maintainer why a companion tactic is skipped and why the unconfigured case is not; the ADR amendment names the issue and the two halves; the changelog entry validates against the repo's docs freshness check.

T006 Gate contract text (WP02)
T007 ADR amendment (WP02)
T008 Changelog entry (WP02)
T009 Docs freshness and terminology guard (WP02)

**Risks**: docs regenerate surface is shared with other agents; regenerate only the index the diff touches and verify with `check_docs_freshness --ci`.

## Dependencies

WP01 → WP02. No parallel WPs; WP01 is the MVP.

## Closeout (orchestrator, not a WP)

Issue-matrix row and terminal verdict for #6724; the changelog entry lands inside WP02 but is listed in the PR body; no follow-up issue is expected (the narrowing closes the reported class), unless review finds a second artifact class misclassified.
