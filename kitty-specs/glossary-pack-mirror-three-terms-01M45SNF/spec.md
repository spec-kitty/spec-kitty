# Mission Specification: Mirror three glossary terms into the built-in pack

**Mission Branch**: `issue-5761-glossary-pack-terms`
**Created**: 2026-10-05
**Status**: Draft
**Input**: Issue #5761: "Mirror three new glossary terms into the shipped built-in glossary pack (tool-surface drift, target-owned bookkeeping, integrating worktree)"

## Intent Summary

- **Primary actor**: a Spec Kitty operator in a consumer project, and the agents working there, who meet these terms in `spec-kitty upgrade` output, the upgrade recovery runbook and two ADRs.
- **Trigger**: the operator, or an agent loading glossary context, looks up one of the three terms.
- **Outcome**: the term resolves from the glossary pack that ships with Spec Kitty, with a definition whose meaning matches the canonical entry in `docs/context/`.
- **Invariant**: the `docs/context/` entries are the single source of truth for the wording; the shipped pack and this project's seed carry the same definition as each other and the same meaning as `docs/context/`.
- **Canonical terms**: "tool-surface drift" (never bare "drift"), "integrating worktree", "target-owned bookkeeping" (never "primary-owned").

Confirmation: this run is a scheduled routine with no live user. The operator's stored task brief stands in for the interview; its decisions are recorded as Decision Moments and the pack-tier question is resolved in `research/code-grounding.md` section 3.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Look up an upgrade term in the shipped glossary (Priority: P1)

An operator runs `spec-kitty upgrade`, sees "Not updated, your local edit was kept" or wonders why a lane worktree still holds an older `.kittify/metadata.yaml`, and looks the term up. The glossary that ships with Spec Kitty defines it.

**Why this priority**: it is the whole point of the issue; consumers do not have this repository's `docs/context/`.

**Independent Test**: load the built-in glossary pack through the glossary tooling and find each of the three terms with a non-empty definition.

**Acceptance Scenarios**:

1. **Given** a Spec Kitty install, **When** the built-in `spec-kitty-core` glossary pack is loaded, **Then** it contains "tool-surface drift", "integrating worktree" and "target-owned bookkeeping".
2. **Given** one of those terms, **When** its definition is compared with the `docs/context/` entry, **Then** it states the same meaning, including what the term does not cover.

---

### User Story 2 - The project seed stays in step with the pack (Priority: P2)

A maintainer of this repository relies on the project seed and the shipped pack agreeing term for term.

**Why this priority**: the standing parity invariant fails when either side drifts.

**Independent Test**: the pack/seed parity gate passes and both files carry the three terms with identical fields.

**Acceptance Scenarios**:

1. **Given** the edited pack and seed, **When** the parity gate runs, **Then** every seed term round-trips identically into the pack.

---

### Edge Cases

- The renamed term: "primary-owned" must appear only as the name to avoid, never as the term.
- The shipped pack must not cite issue numbers or `src/` file paths (the shrink-only provenance ratchet on built-in pack files would fail), even though the `docs/context/` entries do.
- A wording error discovered in a `docs/context/` entry is fixed there first, then mirrored, and called out in the PR.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Ship "tool-surface drift" | As an operator, I want "tool-surface drift" in the shipped glossary pack, with its not-drift cases, so that upgrade's "local edit was kept" output is explained. | High | Open | [build] | no |
| FR-002 | Ship "integrating worktree" | As an operator, I want "integrating worktree" in the shipped glossary pack, with its exclusions, so that I know which worktrees upgrade skips. | High | Open | [build] | no |
| FR-003 | Ship "target-owned bookkeeping" | As an operator, I want "target-owned bookkeeping" in the shipped glossary pack, with "primary-owned" named only as the name to avoid, so that I know why a `.kittify/metadata.yaml` conflict is resolved without refusing. | High | Open | [build] | no |
| FR-004 | Mirror into the project seed | As a maintainer, I want the three terms in `.kittify/glossaries/spec_kitty_core.yaml` with fields identical to the pack, so that the pack/seed parity invariant holds. | High | Open | [build] | no |
| FR-005 | Regenerate derived artifacts | As a maintainer, I want every artifact derived from the pack (the pack manifest) regenerated, and the docs index and contextive glossaries confirmed unchanged, so that no freshness gate goes red. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Meaning fidelity | 3 of 3 pack definitions state the same meaning as their `docs/context/` entry, checked by a side-by-side review; 0 `docs/context/` lines change. | Correctness | High | Open |
| NFR-002 | Gate health | 0 failures in the gates named in `research/code-grounding.md` section 2, and the built-in pack's provenance counts stay at or below `repo_paths: 6`, `provenance: 15`. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Source of truth | Do not change the wording or meaning of the three `docs/context/` entries, except to fix an error, which is then mirrored and called out. | Governance | High | Open |
| C-002 | Scope | No other terms, no source code, no recapture of `.github/ci-shard-timings.json`. | Scope | High | Open |
| C-003 | Pack tier | The terms go to `packs/built-in/` only because they name consumer-visible behavior; nothing goes to `packs/internal/`. | Governance | High | Open |
| C-004 | Terminology | Mission, not feature; name the sense of `primary` / `merge`; write "tool surface", never bare "surface"; never "spec-kitty merge" in pack text. | Governance | High | Open |

### Key Entities

- **Glossary term**: surface, definition, confidence, status, and optional `synonyms_to_avoid`.
- **Built-in glossary pack**: the shipped term collection `spec-kitty-core`.
- **Project seed**: this repository's own term list, held in parity with the pack.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 3 of 3 new terms resolve when the built-in glossary pack is loaded. — [build] · no-op passable: no
- **SC-002**: The pack and the seed carry the same 3 new terms with identical definitions, and the parity gate passes. — [build] · no-op passable: no
- **SC-003**: 0 lines of the three `docs/context/` entries change. — [ratchet] · no-op passable: yes — paired with SC-001 on the same files

## Assumptions

- "Do not use" guidance maps to a condensed "not this" sentence in the definition plus `synonyms_to_avoid` (the pack schema has no dedicated field).
- New terms are appended at the end of both files, matching how earlier additions were made.
- Status `draft` mirrors the `docs/context/` status `candidate`; confidence 0.9.
