# Mission Specification: Never auto-demote the issue a Mission exists to fix

**Mission Branch**: `issue-7011-issue-matrix-source-issue-gating`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #7011 — "[bug] issue-matrix auto-classifies the issue a Mission fixes as context-only / not-applicable" (type:bug).

## Intent Summary

- **Primary actor:** an agent or maintainer running a governed Mission who relies on the issue matrix as the audit trail of every referenced issue's verdict.
- **Trigger:** `spec-kitty agent mission finalize-tasks` scaffolds `issue-matrix.json` from the references discovered in the Mission's planning artifacts.
- **Desired outcome:** the issue the Mission exists to fix always carries a gating placeholder verdict (`unknown`), so the approval gate forces an explicit verdict instead of silently recording `not-applicable` for the Mission's own target.
- **Rule that must always hold:** fail-safe default-gating — a reference stays gating unless a positive, explicit signal demotes *that* reference; a citation label attached to one number never demotes another number on the same line.
- **Boundary:** the closed verdict vocabulary and the `<auto-classified: …>` scaffold shape are unchanged; no new CLI surface; the fast-suite classification tests keep their existing expectations.

Grounding: [`research/code-grounding.md`](research/code-grounding.md) reproduces the defect on the current base, names the two independent causes, and maps each to the file and line that carries it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A label on the line cannot silence the Mission's own issue (Priority: P1)

A Mission's `spec.md` header reads `**Input**: Issue #6926 (part of epic #6100, …)`. The scaffolded matrix classifies `#6926` as `context_only` — the target issue the Mission was created to fix — and pre-resolves its row to `not-applicable`. After the change, `#6926` scaffolds `unknown` (gating) while `#6100` — which the `epic` label really does describe — stays context-only.

**Why this priority**: it is the reported defect; a silent `not-applicable` on the target issue defeats the purpose of the matrix.

**Independent Test**: run the scaffold against a `spec.md` carrying that header line and read the verdicts in `issue-matrix.json`.

**Acceptance Scenarios**:

1. **Given** a `spec.md` whose `**Input**:` line is `Issue #6926 (part of epic #6100, sdist packaging cleanup)` and no mission metadata, **When** the issue matrix is scaffolded, **Then** `#6926` has verdict `unknown` and `#6100` has verdict `not-applicable`.
2. **Given** the same fixture, **When** the classifier is asked for the Mission's gating refs, **Then** `#6926` is in the set and `#6100` is not.
3. **Given** a line where the citation label precedes the number the same way (`Tracked by the epic #6100`), **When** it is classified, **Then** it stays context-only — the positive control proving the label is not simply disabled.

### User Story 2 - The source issue stays gating even when its own prose looks like context (Priority: P1)

A maintainer opens a Mission for an issue, and the spec records that issue on a line that also — or even exclusively — reads like a citation, for example `**Input**: Issue #6926, follow-up: patched in #7004`, or with the only mention of the target under a `Parent epic: #6926` heading. The Mission's own source issue is never auto-classified non-gating, so the approval gate still forces an explicit verdict.

**Why this priority**: the classifier reads prose; prose can always misfire. The guarantee cannot rest on the heuristic alone.

**Independent Test**: build a fixture whose `meta.json` `source_description` names the source issue, add a spec line that carries a context marker for that same number, and assert the scaffolded row is gating.

**Acceptance Scenarios**:

1. **Given** a `meta.json` whose `source_description` is `Issue #6926: anchor the sdist README include…`, **When** the matrix is scaffolded for a spec that mentions `#6926` only on a context-marked line, **Then** `#6926`'s row is `unknown`, not `not-applicable`.
2. **Given** a spec with no `meta.json` whose first line is `**Input**: Issue #7011 — …`, **When** the matrix is scaffolded for a spec that also cites `#7011` under a context marker, **Then** `#7011`'s row is `unknown`.
3. **Given** a spec with no `meta.json` and no `**Input**:` line but a `Closes #7011` line, **When** the matrix is scaffolded, **Then** `#7011`'s row is `unknown`.
4. **Given** a mission whose source issue is never mentioned in any scanned artifact, **When** the matrix is scaffolded, **Then** no row is invented for it — promotion applies only to references that actually exist.

### User Story 3 - Every gate agrees with the scaffold (Priority: P2)

The scaffold, the approval blocker, `status doctor` and the merge gate all derive "referenced-but-missing" from one predicate. After the change they agree: a promoted source issue is required by all of them, so a Mission cannot satisfy the matrix with a `not-applicable` row for its own target.

**Independent Test**: compute the gating set from the same fixture through the shared helper and through the blocker's own path; both include the source issue.

**Acceptance Scenarios**:

1. **Given** the User Story 2 fixture, **When** the shared gating helper and the scaffold-derived rows are compared, **Then** every ref the scaffold marks gating is in the helper's set and vice versa.
2. **Given** the same fixture, **When** the approval blocker evaluates a matrix that omits the source issue's row, **Then** it reports that row as missing.

### Edge Cases

- The same number appears twice on one line, once under a citation label and once bare: any gating occurrence still wins (existing aggregate rule).
- A reference carried as a same-repo GitHub issue URL rather than a bare `#NNNN`: unchanged — URL references are never demoted by a bare `#`-positioned label, which is the fail-safe direction.
- A citation label that appears *after* the reference it would otherwise describe: it does not demote that reference.
- `meta.json` absent, unreadable or not valid JSON: discovery degrades to spec-derived sources only and never raises; classification equals the pre-change behaviour.
- `meta.json` `source_description` is free-form prose that names several issues: only the leading `Issue #N` / `#N` form is treated as the source issue, so a passing mention is not promoted.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Positional labels bind to their own reference | As an operator, I want a citation label (`parent #N` / `epic #N` / leading `see #N`) to demote only the reference it actually leads into, so that a label for one number cannot silence another on the same line. | High | Open | [build] | no |
| FR-002 | Source issue is discovered from the Mission's own record | As an operator, I want the Mission's source issue read from `meta.json` `source_description`, the spec's `**Input**:` line, or a `Closes`/`Fixes`/`Resolves #N` line, so that the guarantee does not depend on one authoring convention. | High | Open | [build] | no |
| FR-003 | The source issue is never classified non-gating | As an operator, I want the source issue forced to `implementation_target` however its line reads, so that the approval gate always forces an explicit verdict for it. | High | Open | [build] | no |
| FR-004 | Scaffold and gates share the promoted classification | As an operator, I want the scaffold, the approval blocker, `status doctor` and the merge gate to agree on which references gate, so that a `not-applicable` row can never satisfy the matrix for a promoted issue. | Medium | Open | [build] | no |
| FR-005 | Existing classification outcomes are preserved | As a maintainer, I want every pre-existing classification test to keep its expected outcome, so that the fix does not quietly widen or narrow gating elsewhere. | Medium | Open | [ratchet] | yes — guarded by the untouched pre-existing classification suite as the paired control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Classifier stays pure and deterministic | `classify_occurrence` / `classify_occurrences` remain side-effect free: no filesystem, environment, network or git access, and two runs over the same occurrences return the same class. | Reliability | High | Open |
| NFR-002 | Discovery fails open, never closed, on unreadable metadata | An absent, unreadable or malformed `meta.json` (and an absent spec) adds no source issue and raises nothing; measured by a test that shards the metadata file in three ways and asserts classification equals the metadata-free baseline. | Reliability | High | Open |
| NFR-003 | Discovery cost stays bounded | Source-issue derivation reads at most one `meta.json` and one `spec.md` per call, and adds no scan of the artifacts already scanned for references. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | `Occurrence` construction stays backward compatible | The new position field is optional with a default, so existing keyword construction (`Occurrence(source_file=…, line_text=…)`) is unchanged and keeps today's whole-line semantics for callers that cannot supply a position. | Technical | High | Open |
| C-002 | One issue-reference pattern definition | The `#NNNN` / issue-URL regex remains defined exactly once (`_GH_ISSUE_PATTERN`); source-issue derivation reuses it rather than adding a second pattern. | Technical | High | Open |
| C-003 | No verdict-vocabulary change | `not-applicable` stays a legitimate explicit verdict for genuinely-context issues; the closed set of verdicts and the `<auto-classified: …>` scaffold shape are unchanged. | Technical | High | Open |

### Key Entities

- **Occurrence**: one site where a number was cited — the file, the stripped line, and now the character offset at which the citation begins (optional, for whole-line-only callers).
- **Issue reference**: a deduplicated number with its first-seen context, provenance, every occurrence, and its aggregate gating class.
- **Source issue**: the issue number(s) the Mission exists to fix, derived from the Mission's own metadata and spec header, always gating.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Scaffolding the reported header line yields `verdict: unknown` for `#6926` and `verdict: not-applicable` for `#6100` — 2 of 2 rows as specified. — [build] · no-op passable: no
- **SC-002**: A context-marked line naming only the source issue yields a gating row, for all three derivation sources (`meta.json`, `**Input**:`, `Closes #N`) — 3 of 3 cases. — [build] · no-op passable: no
- **SC-003**: The four consumers (scaffold, approval blocker, `status doctor`, merge gate) return the same gating set for the shared fixture — 0 disagreements. — [build] · no-op passable: no
- **SC-004**: The pre-existing issue-classification and issue-matrix suites pass unchanged — 0 modified pre-existing assertions. — [ratchet] · no-op passable: yes — the untouched suites are the paired control for the fix's own new tests
