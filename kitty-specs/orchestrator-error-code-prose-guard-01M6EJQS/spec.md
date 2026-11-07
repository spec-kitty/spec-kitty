# Mission Specification: Orchestrator error-code prose guard

**Mission Branch**: `kitty/mission-orchestrator-error-code-prose-guard-01M6EJQS`
**Created**: 2026-11-02
**Status**: Draft
**Input**: GitHub issue [#7035](https://github.com/spec-kitty/spec-kitty/issues/7035) — "The orchestrator error-code prose enumerations are unchecked and already 22 codes behind the contract". Operator guidance: *"The goal is a check that keeps prose enumerations honest, not a one-off re-sync."*

## Problem

`src/specify_cli/core/upstream_contract.json` → `orchestrator_api.allowed_error_codes` is the
machine-readable authority for the codes an orchestrator-api caller may see (80 codes on
`main` at `9aed3a8012`). Two prose surfaces enumerate the same set by hand:

1. `docs/api/orchestrator-api.md`, the bullet list under `## Error Codes`.
2. `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`,
   the `## Error Code Summary` table (the shipped skill an integrator's agent reads).

Neither enumeration is checked against the authority, and both have drifted: the docs list is
missing 22 codes (the whole `DESIGN_*` family except `DESIGN_STATUS_EVENT_LOG_UNREADABLE`, plus
`INVALID_MISSION`, `RUNTIME_NEXT_FAILED`, `RUNTIME_BLOCKED`, `SAFE_COMMIT_STAGED_TREE_UNCHANGED`,
`UNSUPPORTED_CAPABILITY`), and the table is missing the same 22 plus `WORKFLOW_EVIDENCE_REQUIRED`.
Only the machine-readable side has a guard (`tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes`
walks emitted literals and the `SafeCommitError` family against `allowed_error_codes`); nothing
reads the prose. A newly registered code can therefore go missing from the documentation a
caller actually reads, which is the inverse of the #6997 failure.

The issue leaves the docs shape open: restate the families as enumeration items, or record an
explicit "documented in prose at X" mapping. Either way the durable deliverable is the same —
**a check**, not a re-sync.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A newly registered code cannot go missing silently (Priority: P1)

A developer registers a new code in `allowed_error_codes` (the way #6997 added
`SAFE_COMMIT_DIRECTORY_ARGUMENT`) and runs the contract tests. The suite fails, naming the code
and each prose surface that does not enumerate it, so the documentation is fixed in the same PR
that registers the code.

**Why this priority**: This is the defect. Without it a re-sync is just today's snapshot of a
surface that will drift again on the next registration.

**Independent Test**: Add a synthetic code to an in-memory copy of the contract and assert the
check reports it as missing from both surfaces, naming it; on the unmodified tree the same check
is green. This is the same-fixture positive control the negative assertion needs.

**Acceptance Scenarios**:

1. **Given** the contract lists a code that a surface's enumeration omits, **When** the guard
   runs, **Then** it fails and its message names the surface *and* the missing code.
2. **Given** both surfaces enumerate exactly the contract set, **When** the guard runs, **Then**
   it passes.

---

### User Story 2 - An integrator sees the complete set on both surfaces (Priority: P1)

Someone integrating against `spec-kitty orchestrator-api` reads `docs/api/orchestrator-api.md`,
or the shipped operator skill's reference, and finds every code the CLI can return — including
the `DESIGN_*`, `RUNTIME_*` and `UNSUPPORTED_CAPABILITY` families — as an enumerable item rather
than having to reconstruct them from contract-version history prose.

**Why this priority**: The guard is only worth having if the surfaces it guards are correct now;
the 22/23 missing codes are the concrete user-visible harm.

**Independent Test**: Read each surface and compare its enumerated set with
`allowed_error_codes`; the two are equal in both directions, with no duplicates.

**Acceptance Scenarios**:

1. **Given** the two documented surfaces on current `main`, **When** their enumerations are
   compared with the contract, **Then** the set difference is empty in both directions.
2. **Given** the same surfaces, **When** a reader looks for `DESIGN_ARTIFACT_UNSUPPORTED`,
   `RUNTIME_BLOCKED` or `UNSUPPORTED_CAPABILITY`, **Then** each appears as its own enumerable
   entry (list item / table row) with a short meaning, not only inside a version-history bullet.

---

### User Story 3 - The guard cannot be silently disarmed (Priority: P2)

A future editor reformats the docs and deletes or renames the region the guard parses. The guard
fails closed instead of quietly checking nothing.

**Why this priority**: An enumeration check that skips when its anchor disappears is the same
class of hole as no check at all, and is invisible in review.

**Independent Test**: Remove or rename the anchor markers in an in-memory copy of a surface's
text and assert the check fails with a message naming the missing anchor, rather than passing
with an empty set.

**Acceptance Scenarios**:

1. **Given** a surface whose machine-readable anchor is absent, **When** the guard runs, **Then**
   it fails and names the surface and the anchor it expected.
2. **Given** a surface whose enumerated region parses to zero codes, **When** the guard runs,
   **Then** it fails rather than treating "found nothing" as agreement.

---

### Edge Cases

- **Sub-code namespaces inside the same section.** `docs/api/orchestrator-api.md` documents
  `data.preflight_error_code`, `data.teardown_error_code` and the origin-freshness codes
  (`LANE_MOVED_AFTER_APPROVAL`, `ORIGIN_LANE_STALE`, …) in the same `## Error Codes` section.
  Those names are *not* `allowed_error_codes` entries; the check must neither demand them in the
  contract nor complain that they are absent from it, and it must not start failing when that
  table gains a row. Hence the checked region is bounded explicitly, not "everything under the
  heading".
- **Annotations after the code.** Several list items carry an explanation in parentheses that
  itself backticks other codes (e.g. `SAFE_COMMIT_INDEX_RESIDUE` mentions
  `SAFE_COMMIT_RECOVERY_FAILED`). The parser takes each item's leading code only, so an
  annotation can never invent an enumeration entry.
- **Descriptions in the table.** The table's description cell mentions codes; only the first
  cell is an enumeration entry.
- **Duplicates.** A code listed twice in one enumeration is a defect the guard reports, not a
  set-equality no-op.
- **A code in the contract but in neither surface** must be reported per surface, not as one
  merged "docs are stale" message, so the fix is mechanical.
- **Prose outside the checked region** (contract-version history, per-verb "Error codes: …"
  lines, usage notes) stays free-form and unguarded: it is narrative, not an enumeration.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Contract test compares both prose surfaces to the authority | As a maintainer, I want one test that compares each prose enumeration with `allowed_error_codes` so drift is caught in CI rather than in a reader's head. | High | Open | [build] | no |
| FR-002 | Both directions are asserted | As a code author, I want the check to fail both when a contract code is missing from a surface and when a surface lists a code the contract does not allow, so neither side can drift silently. | High | Open | [build] | no |
| FR-003 | Failure names the surface and the codes | As the author of a registration PR, I want the failure message to name the surface path and every offending code so the fix is mechanical. | High | Open | [build] | no |
| FR-004 | Each surface has one explicit machine-readable enumeration region | As a docs editor, I want the checked region delimited by explicit anchors in the document itself, so the guard reads a declared enumeration rather than heuristically scanning prose. | High | Open | [build] | no |
| FR-005 | The guard fails closed on a missing or empty region | As a reviewer, I want a surface whose anchor is absent, or whose region yields no codes, to fail the test, so deleting the anchor cannot silently disable the check. | High | Open | [build] | no |
| FR-006 | `docs/api/orchestrator-api.md` enumerates all 80 codes | As an integrator reading the API reference, I want every contract code to appear as its own list item with a short meaning, so I can enumerate the failure surface without reading version history. | High | Open | [build] | no |
| FR-007 | The shipped operator-skill reference table enumerates all 80 codes | As an integrator whose agent loads the operator skill, I want its `Error Code Summary` table to list every contract code, so the skill's claim to be a complete reference is true. | High | Open | [build] | no |
| FR-008 | Duplicates within an enumeration are rejected | As a maintainer, I want a code listed twice in one enumeration reported as a defect, so a copy-paste cannot pass as set equality. | Medium | Open | [build] | no |
| FR-009 | Non-contract sub-code namespaces are out of scope | As a docs editor, I want the `preflight_error_code` / `teardown_error_code` / origin-freshness codes to stay outside the checked region, so the guard neither demands them in the contract nor breaks when that table changes. | Medium | Open | [build] | no |
| FR-010 | The guard is anchored to the real authority, not a copy | As a maintainer, I want the test to read `allowed_error_codes` from `specify_cli.core.upstream_contract.json` at test time, so the docs can never be validated against a second hand-maintained list. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast and offline | The guard runs in the `contract` + `fast` test selection, completes in under 2 s, and makes no network call (the contract is read from the installed package resource). | Performance | High | Open |
| NFR-002 | Deterministic failure output | For a given drift, the failure message is stable and lists offending codes sorted, so CI logs diff cleanly between runs. | Reliability | Medium | Open |
| NFR-003 | Docs stay lint-clean | Both edited surfaces remain valid Markdown for the repository's markdownlint config, and the docs-freshness gate stays at errors=0. | Maintainability | High | Open |
| NFR-004 | No new single-source violation | The checked region adds no second copy of the contract: it is the human enumeration, and the test is the only comparison point. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Contract file unchanged | `src/specify_cli/core/upstream_contract.json` is the vendored upstream authority; this Mission reads it and must not edit it. | Technical | High | Open |
| C-002 | No gate weakened | No existing test, marker, or CI gate is skipped, xfailed, deselected or relaxed to make this pass; the new guard is additive. | Technical | High | Open |
| C-003 | Existing guards untouched | `TestAllowedErrorCodes`'s emitted-literal and `SafeCommitError` family assertions keep working as they are; the prose check is a sibling, not a replacement. | Technical | High | Open |
| C-004 | Both surfaces stay human-readable | The enumeration must remain prose a person reads (list items and a table), not a generated block or a link to the JSON. | Business | High | Open |
| C-005 | Scope excludes history prose | Contract-version bullets and per-verb narrative are not enumeration surfaces and are not re-synced by this Mission. | Business | Medium | Open |

### Key Entities

- **Contract authority**: `orchestrator_api.allowed_error_codes` in the vendored
  `upstream_contract.json` — the set the guard compares against.
- **Prose enumeration surface**: a documented region of a Markdown file that claims to list the
  codes, bounded by explicit anchors; two instances (API reference list, skill reference table).
- **Enumeration anchor**: the machine-readable marker that delimits a surface's enumeration, and
  whose absence is itself a failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the fix applied, both prose surfaces enumerate exactly the 80 contract codes — set difference empty in both directions and zero duplicates. — [build] · no-op passable: no
- **SC-002**: A contract code injected only into an in-memory copy of the authority makes the guard fail, and the message names that code and both surface paths. — [build] · no-op passable: no
- **SC-003**: Deleting a surface's anchor from an in-memory copy makes the guard fail naming the anchor; the unmodified text passes. — [build] · no-op passable: no
- **SC-004**: The check runs green on the delivered tree in under 2 s and needs no network access. — [build] · no-op passable: no
- **SC-005**: Reverting the docs enumeration fix alone (leaving the test in place) turns the guard red on both surfaces, naming the 22 and 23 missing codes respectively — the half-by-half proof that the guard, not the docs edit, is what closes the issue. — [build] · no-op passable: no
