# Mission Specification: Anchor the sdist README include to the repository root

**Mission Branch**: `issue-6926-sdist-readme-anchor`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6926 (part of epic #6100, plan step S-2; ADR `2026-10-31-1` D-12). Blocks #6930 and #6939.

## Intent Summary

- **Primary actor:** a Spec Kitty maintainer who publishes the source distribution, and a downstream packager who unpacks it.
- **Trigger:** building the source distribution of the CLI.
- **Desired outcome:** the archive carries the repository's own `README.md` and `CHANGELOG.md` at its root and no stray `README.md` / `CHANGELOG.md` from documentation, Mission, script or test folders; a future `site/` folder (the docsite scaffold, #6930) never ships.
- **Rule that must always hold:** every intended member ships unchanged: the built-in pack tree, the source packages, the service pins and the build hook; the maintainer-only internal pack never ships.
- **Boundary:** the wheel's contents do not change; no `site/` folder is created here; no doc-kitty work.

Discovery was minimised on the operator's instruction: the issue's Done-when and the operator brief answer the interview. The one open shape question (anchor the includes, or exclude the stray trees one by one) is recorded as Decision Moment `01M6BRENGKBHJN1K9CMRE6AKDT`, resolved to "anchor the includes and exclude `site/**`". Grounding: [`research/code-grounding.md`](research/code-grounding.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The source archive carries only what the project means to ship (Priority: P1)

A maintainer builds the source distribution. Today the archive also carries 745 stray `README.md` / `CHANGELOG.md` files from the documentation, Mission, script and test folders, and the docsite migration would add more. After the change, those files are gone and everything that is meant to ship is still there.

**Why this priority**: it is the defect itself, and the docsite scaffold (#6930) and the README rename (#6939) are blocked on it.

**Independent Test**: build the source distribution and list its members.

**Acceptance Scenarios**:

1. **Given** the repository as it is on the base, **When** the archive check runs on the built source distribution, **Then** it fails and names stray members under `docs/` and `kitty-specs/`.
2. **Given** the fix, **When** the source distribution is built, **Then** no member sits under `docs/`, `kitty-specs/` or `site/`, and the root `README.md` and `CHANGELOG.md` are present.
3. **Given** the fix, **When** the archive listing is compared with the base listing, **Then** members were only removed, and every member under `packs/built-in/` is unchanged.

### User Story 2 - A future site folder cannot leak (Priority: P2)

The docsite scaffold will add a `site/` folder with its own `README.md` and build output. It must never ship in the source distribution, whatever the include rules later become.

**Independent Test**: the packaging configuration names `site/**` in the source distribution's exclusions; the archive check asserts no `site/` member.

**Acceptance Scenarios**:

1. **Given** a `site/README.md` in the checkout, **When** the source distribution is built, **Then** no `site/` member ships.

### Edge Cases

- A nested `README.md` that is intended to ship (under `src/`, `packs/built-in/`, or `pins/README.md`) keeps shipping through its own tree rule.
- `packs/README.md` (a core explainer, not built-in pack content) stops shipping; that is intended.
- An empty or broken archive must not pass the absence check: the check carries a same-archive positive control.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Root-only README and CHANGELOG | As a maintainer, I want the source distribution to take `README.md` and `CHANGELOG.md` from the repository root only, so that nested copies in documentation, Mission, script and test folders stop shipping. | High | Open | [build] | no — the archive check fails on the base (745 stray members) |
| FR-002 | Site folder excluded | As a maintainer, I want the source distribution to exclude `site/` whole, so that the docsite scaffold never ships. | High | Open | [build] | no — the configuration check fails while `site/**` is absent from the exclusions |
| FR-003 | Archive check | As a reviewer, I want a packaging-safety test that reads the built source distribution and fails when any member sits under `docs/`, `kitty-specs/` or `site/`, so that the leak cannot come back unnoticed. | High | Open | [build] | no — red on the base, with a same-archive positive control (root `README.md`, `CHANGELOG.md`, a `src/` package) |
| FR-004 | Intended members unchanged | As a consumer, I want the root `README.md` and `CHANGELOG.md`, the built-in pack tree and the service pins to keep shipping byte for byte, so that the fix removes only stray files. | High | Open | [ratchet] | yes — paired with FR-003 on the same archive, and with the before/after listing comparison |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added build cost | The new archive check reuses the existing once-per-run build; it adds no second build and under 1 second of test time. | Performance | Medium | Open |
| NFR-002 | Clean code | New test code passes `ruff check`, `ruff format --check` and `mypy` with zero findings, and no function exceeds complexity 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Wheel untouched | The wheel's contents do not change. | Technical | High | Open |
| C-002 | Internal pack never ships | `packs/internal/` stays out of the wheel and the source distribution, and built-in content stays present (CLAUDE.md "Pack Tiers"). | Technical | High | Open |
| C-003 | No other packaging invariant changes | Only the two include entries and one new exclusion change. The `services/**` and `contracts/**` exclusions and their comment belong to the events-service cut-over (#7004) and are not touched. | Technical | High | Open |
| C-004 | Out of scope | No `site/` folder is created (#6930), and no doc-kitty work. | Business | High | Open |
| C-005 | Red first | The archive check is committed, failing, before the fix. | Process | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The source distribution carries 0 members under `docs/`, `kitty-specs/` and `site/` (745 stray README / CHANGELOG members today). — [build] · no-op passable: no
- **SC-002**: The before/after archive comparison shows 0 added members and 0 changed or removed members under `packs/built-in/`. — [ratchet] · no-op passable: yes (paired with SC-001 on the same archive)

## Assumptions

- Hatchling compiles include and exclude patterns with gitignore semantics, so a leading `/` anchors a pattern to the project root (verified in grounding).
- The events-service cut-over (#7004) lands before or after this change without a textual conflict; whichever lands second rebases.
