# Mission Specification: Custom-type action-sequence + analysis-currency generalization

**Mission Branch**: `kitty/mission-custom-type-sequence-analysis-currency-01M535FV`
**Created**: 2026-10-16
**Status**: Draft
**Input**: GitHub issue #4983 (first slice). An activated custom mission type cannot resolve a complete canonical lifecycle; analysis-currency enforcement is hard-keyed to `software-dev`.

## Summary

A project- or org-pack author can ship a reusable custom mission type (org-pack
runtime shape: `missions/<type>/mission-runtime.yaml` + `command-templates/`, as
the `cave-kitty` and `qa` packs do). When such a type is *activated*, it is
discovered at the custom-type layer but **fails to resolve a usable lifecycle**:
`spec-kitty mission-type list` reports `mission type '<id>' resolved from layer
'project' has an empty action sequence`, because the type file carries no
`action_sequence` (neither does built-in `software-dev.yaml`) and the org-pack
runtime steps are not linked into the `project_action_sequence` projection at
that layer. Separately, the stale-analysis → re-`analyze` currency gate is keyed
to the literal `software-dev` family at three runtime sites, so an
`analyze`-declaring custom type never gets it.

This slice makes an activated custom type resolve its full, ordered action
sequence from its own runtime steps, and generalizes the analysis-currency gate
to any mission family whose resolved runtime declares an `analyze` step. It
reuses the charter `ResolvedMissionType` authority as the single type authority
and introduces no competing resolver. It is the first slice of #4983; the
remaining lifecycle contract (accept / merge / dossier / retrospective) is out
of scope here and tracked under the same issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An activated custom type resolves its lifecycle (Priority: P1)

A pack author activates a custom mission type whose runtime declares ordered
steps. The CLI resolves the type's `action_sequence` from those steps so the
type is listable, creatable, and runnable through the canonical loop.

**Why this priority**: Without a resolved sequence the type is inert — every
downstream command fails closed on the empty sequence. This is the blocker that
makes a custom type a second-class citizen.

**Independent Test**: Activate a custom type with a known step list; assert
`mission-type list` / the resolver returns its steps in declared order, with no
"empty action sequence" error — and a built-in type's resolved sequence is
unchanged on the same run.

**Acceptance Scenarios**:

1. **Given** an activated custom type whose resolved runtime declares steps
   `[discovery, specify, plan, tasks, analyze, implement, review, accept]`,
   **When** its mission type is resolved, **Then** `action_sequence` equals that
   list in order and no empty-sequence error is raised.
2. **Given** a custom type whose runtime declares no steps, **When** it is
   resolved, **Then** the existing empty-action-sequence failure still fires
   (fail-closed is preserved, not weakened).

---

### User Story 2 - An analyze-declaring custom type gets the analysis-currency gate (Priority: P1)

For any mission family whose resolved runtime declares an `analyze` step, the
runtime recomputes analysis currency at the analyze step and refuses to advance
to `implement` on a stale or missing analysis report, re-issuing `analyze` —
exactly as `software-dev` does today.

**Why this priority**: Equal rigour is the whole point of a custom type (e.g.
`cave-dev` re-voices software-dev without weakening a gate). A missing currency
gate lets `implement` run against a stale analysis silently.

**Independent Test**: Drive an analyze-declaring non-`software-dev` family to the
`implement` boundary with a stale analysis report; assert the decision re-issues
`analyze` with the stale-analysis failure — and a family with no analyze step is
never sent to `analyze`.

**Acceptance Scenarios**:

1. **Given** an analyze-declaring custom family with a stale `analysis-report.md`,
   **When** the runtime decides the next action at the `implement` boundary,
   **Then** it re-issues `analyze` carrying the stale-analysis failure (decide
   path and preview/query path alike).
2. **Given** a family whose resolved runtime declares no `analyze` step,
   **When** it reaches `implement`, **Then** no analysis-currency check runs and
   no `analyze` re-issue occurs.

### Edge Cases

- A custom type whose runtime is unreadable/malformed resolves to the existing
  fail-closed error, never a silent empty sequence.
- `software-dev` and the other built-in families (`research`, `documentation`,
  `plan`) produce byte-identical decisions and sequences after this change.
- A custom family that declares `analyze` but has never recorded an analysis
  report refuses `implement` with the "analysis report missing" failure, not a
  pass.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Custom-type action_sequence resolves from runtime steps | As a pack author, I want an activated custom type to resolve its full ordered action_sequence from its own runtime steps so that it is usable through the canonical loop. | High | Open | [build] | no — paired with the empty-runtime control (FR-002) on the same fixture |
| FR-002 | Empty/malformed runtime still fails closed | As a maintainer, I want a custom type with no resolvable steps to keep raising the empty-action-sequence error so that an unusable type is never silently accepted. | High | Open | [ratchet] | no — paired with the populated-runtime positive control (FR-001) |
| FR-003 | Analysis-currency fact computed for any analyze-declaring family | As a custom-type consumer, I want the analyze step to recompute analysis currency for any family whose resolved runtime declares an analyze step so that the stale-analysis gate is not software-dev-only. | High | Open | [build] | no — paired with the no-analyze-step control (FR-005) |
| FR-004 | Implement reissues analyze on stale analysis for analyze-declaring families | As a custom-type consumer, I want the decide path and the preview/query path to re-issue analyze before implement on a stale/missing analysis report for any analyze-declaring family so that implement never runs against stale analysis. | High | Open | [build] | no — paired with the fresh-analysis control (passes implement) |
| FR-005 | Families without an analyze step are unaffected | As a maintainer, I want a family whose resolved runtime declares no analyze step to never trigger an analysis-currency check or analyze re-issue so that research/documentation/plan behaviour is unchanged. | High | Open | [ratchet] | no — paired with the analyze-declaring positive control (FR-003/FR-004) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Built-in decision parity | `software-dev`, `research`, `documentation` and `plan` resolve byte-identical action sequences and emit byte-identical `decide_next` decisions before and after this change (0 diffs across the existing runtime decision tests). | Reliability | High | Open |
| NFR-002 | Single type authority | The generalization reads the mission's resolved runtime/`ResolvedMissionType`; it adds no new mission-type resolver and no second source of the step list. | Maintainability | High | Open |
| NFR-003 | Quality gates clean | New/changed code passes `ruff check`, `ruff format --check`, and `mypy` with zero new issues; complexity stays ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse #3831 ResolvedMissionType | Resolution reuses the charter `ResolvedMissionType` authority landed in #3831; no competing resolver is introduced. | Technical | High | Open |
| C-002 | Key on resolved-runtime analyze presence, not a family list | The analysis-currency gate is keyed on the resolved runtime declaring an `analyze` step, never on a hardcoded enumeration of family names. | Technical | High | Open |
| C-003 | No packaging/gate changes | Packaging invariants, wheel include, and architectural gates are untouched; the runtime stays stdlib-pure where it already is. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An activated custom type whose runtime declares N ordered steps resolves an `action_sequence` of exactly those N steps in order, with zero "empty action sequence" errors. — [build] · no-op passable: no
- **SC-002**: An analyze-declaring non-`software-dev` family refuses `implement` and re-issues `analyze` on a stale/missing analysis report, on both the decide and preview paths. — [build] · no-op passable: no
- **SC-003**: The existing runtime decision + mission-type resolution test suites show 0 behavioural diffs for `software-dev`, `research`, `documentation`, and `plan`. — [ratchet] · no-op passable: no
