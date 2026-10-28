# Mission Specification: Typed context JSON diagnostics

**Mission Branch**: `issue-6460-typed-context-diagnostics`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Typed context JSON diagnostics: type `charter context --json` diagnostics as {code, message} before schema 1.4.0 ships (#6460); document interview `narrowed` in docs/api and tighten object-typed created_slugs_by_kind/created_slugs (#6461 items 1 and 3)."

## Intent Summary (confirmed 2026-10-27)

- **Primary actor**: a tool or agent that reads `spec-kitty charter context --json` (in-repo: `spec-kitty doctor`; out-of-repo: any integrator).
- **Trigger**: governance resolution reports something worth noting (an unknown selection dropped, a catalog default or fallback applied, selections merged).
- **Desired outcome**: each diagnostic carries a stable code from a closed set plus a readable message, so a consumer classifies it by code, never by matching wording.
- **Invariant**: rewording a message never changes how any consumer classifies it.
- **Boundary**: context schema 1.4.0 has not shipped (rc7 carries 1.3.0), so its `diagnostics` shape is redefined in place, without a new schema version. Release-blocking for 4.0.0rc8 (operator ruling on #6460, 2026-10-19).
- **Also in scope (#6461)**: document the interview JSON `narrowed` field; give the two synthesis helpers that take an untyped `reconciliation` argument a real parameter type, keeping their empty result for missing or foreign input. #6461 item 2 (changelog for `directives_source`) is already done and struck.

Decisions (Decision Moments, all resolved): coarse code set with detailed messages (`01M5ZA7FGHRYPC4FD1F2AVY1W6`, `01M5ZA8A50SYW9VSJHYKESDVNP`); the typed entry is the governance resolution's own type, not a JSON-only mapping (`01M5ZA7MCH04SFCC1ZV25KQCN8`); keep schema 1.4.0 (`01M5ZA7SA40DGDXK3Z223WH23V`); do the helper typing in this mission (`01M5ZA7YYGA9NGXEPTM16A7TZE`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consumers classify context diagnostics by code (Priority: P1)

An integrator or agent reads `charter context --json` and receives `diagnostics` as a list of `{code, message}` objects. It acts on the code; the message is for humans.

**Why this priority**: it is the release-blocking contract change; after rc8 ships, changing the shape needs a breaking schema bump.

**Independent Test**: run `charter context --action <a> --json` in a project with an unknown selected directive and a missing paradigm selection; every entry is an object with exactly `code` and `message`, and the codes are `UNKNOWN_SELECTION_DROPPED` and `CATALOG_DEFAULT_APPLIED`.

**Acceptance Scenarios**:

1. **Given** a clean project with every selection explicit, **When** context JSON is rendered, **Then** `diagnostics` is `[]`.
2. **Given** a charter selecting a directive id no layer knows, **When** context JSON is rendered, **Then** one entry has `code` `UNKNOWN_SELECTION_DROPPED` and a message naming the kind and the id.
3. **Given** no activated paradigm set, **When** context JSON is rendered, **Then** an entry has `code` `CATALOG_DEFAULT_APPLIED` and the message names the default count.
4. **Given** context JSON output, **When** its `context_schema_version` is read, **Then** it is `1.4.0`.

### User Story 2 - Doctor warns by code, not wording (Priority: P1)

`spec-kitty doctor` warns when a selected artifact was dropped. It recognises that case by code, so rewording the message cannot silence the warning.

**Independent Test**: a resolution whose dropped-selection diagnostic carries reworded text still yields the warning; a non-dropped diagnostic whose text starts like the dropped one does not.

**Acceptance Scenarios**:

1. **Given** a resolution with an `UNKNOWN_SELECTION_DROPPED` entry whose message was reworded, **When** doctor checks governance, **Then** it reports the warning and lists the message.
2. **Given** a resolution with only `CATALOG_DEFAULT_APPLIED` / `FALLBACK_APPLIED` / `SELECTION_MERGED` entries, **When** doctor checks governance, **Then** no dropped-selection warning appears.

### User Story 3 - Human-readable surfaces are unchanged (Priority: P2)

Text renderings that list diagnostics (compact charter context, the runtime prompt) show the same message text as before.

**Independent Test**: compact context and the runtime prompt contain the same `Diagnostics:` line content for the same project, before and after.

### User Story 4 - Documented and typed contracts (Priority: P3)

An integrator reading `docs/api` finds the interview JSON `narrowed` field and the `diagnostics` object shape with its code set. A caller of the synthesis slug helpers gets type-checker help.

**Acceptance Scenarios**:

1. **Given** `docs/api/charter-commands.md`, **When** read, **Then** it documents `narrowed` (key → ids that stopped being in force; `{}` when none) and the `{code, message}` shape with all five codes.
2. **Given** the helpers called with a missing or foreign reconciliation value, **When** called, **Then** they still return an empty result.

### Edge Cases

- Governance resolution fails during context JSON rendering: `diagnostics` stays `[]` (today's behaviour), never a partial or prose entry.
- Duck-typed resolution stubs in existing seam tests that omit `diagnostics` keep yielding `[]`.
- The profile-governance path that reports unresolved references uses `UNRESOLVED_REFERENCE`.
- `charter generate --json` has its own `diagnostics` list; it is out of scope and stays a list of strings.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Typed context diagnostics | As a context JSON consumer, I want every `diagnostics` entry to be an object with exactly `code` and `message` so that I never parse prose. | High | Open | [build] | no — today's entries are strings, so a shape assertion fails |
| FR-002 | Closed code set | As a consumer, I want codes drawn only from `UNKNOWN_SELECTION_DROPPED`, `CATALOG_DEFAULT_APPLIED`, `FALLBACK_APPLIED`, `SELECTION_MERGED`, `UNRESOLVED_REFERENCE`, each producer site mapped as in the Intent decision, so that the vocabulary is stable. | High | Open | [build] | no — paired per-code fixtures assert the expected code |
| FR-003 | Doctor classifies by code | As an operator, I want doctor's dropped-selection warning keyed on `UNKNOWN_SELECTION_DROPPED` so that rewording cannot silence it; no prefix matching remains. | High | Open | [build] | no — reworded-message fixture plus a lookalike-prefix negative control |
| FR-004 | Text surfaces unchanged | As a human reader, I want compact context and the runtime prompt to show the same diagnostic text as today. | Medium | Open | [ratchet] | yes — paired with FR-001's shape change on the same project fixture |
| FR-005 | Schema version and docs | As an integrator, I want `context_schema_version` to stay `1.4.0`, and the contract ledger comment, `docs/api` and the rc8 changelog entry to describe the `{code, message}` shape and the code set. | Medium | Open | [build] | no — docs/ledger text asserted by a test or review against the code set |
| FR-006 | Document interview `narrowed` | As an integrator, I want `docs/api` to document the interview JSON `narrowed` field. | Low | Open | [build] | no — absent from docs/api today |
| FR-007 | Typed slug helpers | As a caller, I want the synthesis slug helpers' `reconciliation` parameter typed concretely (no `object`, no suppression) while missing or foreign input still yields an empty result. | Low | Open | [build] | no — mypy reveal plus a foreign-input positive control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Static quality | Touched files pass ruff, `ruff format --check --force-exclude` and mypy (strict) with 0 new findings and 0 new suppressions. | Maintainability | High | Open |
| NFR-002 | Complexity | No touched function exceeds cyclomatic complexity 15. | Maintainability | Medium | Open |
| NFR-003 | Coverage | Diff coverage of changed lines is at least 90%. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Unshipped schema only | The shape change lands before 4.0.0rc8 is tagged; no schema bump. | Business | High | Open |
| C-002 | Charter stays in core | Changes stay inside the in-core charter layer and its seams; no new package, layer rule or gate change (ADR 2026-10-16-1, Amendment 2026-10-19). | Technical | High | Open |
| C-003 | Scope fence | `charter generate --json` diagnostics, the activation ledger and the event writer are untouched. | Technical | Medium | Open |
| C-004 | Sibling coordination | The helper typing touches a file sibling mission M2 also edits; keep the edit to the two signatures and their imports. | Technical | Medium | Open |

### Key Entities

- **Governance diagnostic**: one noteworthy outcome of governance resolution; a code from the closed set and a human message.
- **Diagnostic code**: closed vocabulary of five values; stable across wording changes.
- **Context JSON payload**: the versioned `charter context --json` output (schema 1.4.0), a tracking contract (freezing it is #2787, follow-up).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `diagnostics` entries in context JSON are objects with a code from the five-value set, across the clean, unknown-selection and default/fallback fixtures. — [build] · no-op passable: no
- **SC-002**: Rewording any diagnostic message changes 0 doctor outcomes (proved by a reworded-message fixture). — [build] · no-op passable: no
- **SC-003**: 0 occurrences of prefix-based diagnostic matching remain in the codebase. — [build] · no-op passable: no
- **SC-004**: Text renderings show identical diagnostic messages for the same project before and after. — [ratchet] · no-op passable: yes (paired with SC-001 on the same fixture)

## Assumptions

- The only in-repo consumer of the diagnostics is `doctor`; the spec-kitty-charter service and any external contract fixtures could not be inspected from this session; impact is assumed nil because 1.4.0 never shipped, and the PR will flag it for the operator.
- Follow-up: freezing the context payload is #2787 (context only).
