# Mission Specification: Action-critical charter sections resolve in the active charter

**Mission Branch**: `kitty/mission-action-critical-sections-resolve-01M6BTST`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6968 — "charter context tells agents to fetch charter sections a consumer charter does not have (code-review-checklist, regression-vigilance, terminology-canon)"

## Context and grounding

`spec-kitty charter context --action implement` currently hard-codes three
action-critical charter headings in core code
(`src/charter/activation/context_renderers/section_bodies.py`,
`ACTION_CRITICAL_SECTIONS`): `Terminology Canon`, `Code Review Checklist` and
`Regression Vigilance`. When the active `charter.md` does not carry a heading,
the renderer still advertises it with a `Run: spec-kitty charter context
--include section:<slug>` stanza, and the follow-up fetch returns the
"has not yet authored" placeholder. Those headings exist in Spec Kitty's own
dogfooding charter, not in a consumer charter, which is why every consumer
project is told to load governance it never authored.

Reproduced on current `main` in a minimal consumer project (charter with only
`Purpose` and `Testing Policy`): three `Run: … --include section:…` lines are
emitted, and each resolves to the placeholder.

The three names come from **core code**, not from `packs/built-in` doctrine;
the built-in `implement`/`review` mission-step prompts also name them in prose
(fetched pack content, source `spec-kitty-open-packs`), which is a separate
upstream follow-up, not fixable in this repository.

Terminology used here: "action-critical section" is a charter heading listed
for an action in `ACTION_CRITICAL_SECTIONS`; "resolves" means the active
`charter.md` carries that heading (a dated/parenthesised variant counts) and a
non-empty body that the existing extractor can slice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A consumer charter is never told to fetch sections it lacks (Priority: P1)

An operator runs `spec-kitty charter context --action implement` (or `review`)
in a project whose charter does not carry `Terminology Canon`,
`Code Review Checklist` or `Regression Vigilance`. The output contains no
`--include section:` instruction that resolves to a placeholder, and the
"Action-Critical Charter Sections" block is omitted entirely rather than
advertising absent governance.

**Why this priority**: This is the reported defect. A governed agent is told
that loading these sections is action-critical, then receives a placeholder
telling it to edit the charter, which pushes it to improvise governance or
stall. doc-kitty compatibility is a 4.0 GA priority.

**Independent Test**: Run the production entry point (`build_charter_context`,
exposed as `charter context`) against a minimal consumer charter fixture and
assert no `--include section:` line is emitted; on the same fixture, assert a
direct `--include section:code-review-checklist` still degrades honestly
(no crash, placeholder), so the absence probe is non-vacuous.

**Acceptance Scenarios**:

1. **Given** a charter with none of the three headings, **When** `charter context --action implement` runs, **Then** the output carries no `Run: spec-kitty charter context --include section:` line and no "Action-Critical Charter Sections" header.
2. **Given** a charter with only `Code Review Checklist`, **When** `charter context --action implement` runs, **Then** only `Code Review Checklist` is advertised, with its verbatim body and its recovery fetch stanza, and the other two headings are absent.
3. **Given** a charter with all three headings (as today's fixtures and Spec Kitty's own charter), **When** `charter context --action implement` or `--action review` runs, **Then** all three bodies and their fetch stanzas render exactly as before.

---

### User Story 2 - The published contract and code docstrings match the fixed behaviour (Priority: P2)

A maintainer reading the resolver contract and the renderer docstrings learns
that action-critical headings are filtered against the active charter, and that
a missing heading is not advertised.

**Why this priority**: The current contract document explicitly pins the
buggy behaviour ("either the verbatim body OR the fetch + when-doing stanza"
for every configured heading), so leaving it unchanged would make the shipped
behaviour contradict its own contract and invite a regression.

**Independent Test**: Grep the contract section and the module docstrings for
the filtered-set rule; they state that missing headings are not advertised.

**Acceptance Scenarios**:

1. **Given** the mission's diff, **When** a reader opens the resolver contract's `Action-Critical Charter Sections` row and the renderer docstrings, **Then** both state that only headings present in the active charter are advertised.

---

### Edge Cases

- **Heading present but empty body**: the section resolves to a heading with no
  rule text; it carries no guidance, so it is treated like a missing section and
  not advertised (a placeholder-shaped non-rule must not be presented as
  action-critical).
- **Heading masked by an unbalanced code fence**: the extractor cannot slice
  it; it is treated as absent for advertising purposes. The direct selector
  fetch keeps its existing honest-degrade behaviour.
- **Nested heading** (`### Code Review Checklist` under `## Code Quality`):
  already supported by the extractor and still advertised.
- **Dated heading variant** (`## Regression Vigilance (2026-04-06)`): counts as
  the same logical section and stays advertised.
- **Action with no configured section set** (`specify`, `plan`, `tasks`,
  unknown): still yields no block, unchanged.
- **Token-budget substitution**: the per-heading split-out cannot invent a
  selector for a heading that is no longer in the rendered block.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Advertise only resolving sections | As a governed agent in a consumer project, I want the charter context to name only charter sections my charter actually has, so that I am never sent to fetch a placeholder. | High | Open | [build] | no — a no-op still emits the three stanzas |
| FR-002 | Keep verbatim body plus recovery stanza for present sections | As an implementer whose charter carries an action-critical heading, I want its verbatim body and its fetch stanza, so that the existing governance contract is preserved. | High | Open | [ratchet] | no — paired with FR-001 on the same fixtures |
| FR-003 | Omit the block when nothing resolves | As a consumer, I want no empty "Action-Critical Charter Sections" header, so that absent governance is not advertised as present. | Medium | Open | [build] | no — the header is emitted today |
| FR-004 | Direct selector fetch still degrades honestly | As an operator who fetches `section:<slug>` explicitly for a heading my charter lacks, I want the existing honest placeholder rather than a crash, so that the direct surface stays usable. | Medium | Open | [ratchet] | no — guarded by a same-fixture positive control |
| FR-005 | Regression test on a minimal consumer charter | As a maintainer, I want a regression test that runs the production entry point on a charter with none of the three headings, so that this defect cannot silently return. | High | Open | [build] | no — the assertion fails on current main |
| FR-006 | Contract and docstrings updated | As a maintainer, I want the resolver contract and renderer docstrings to state the filtered-set rule, so that the shipped behaviour and its contract agree. | Medium | Open | [build] | no — the contract currently pins the old rule |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No crash on hostile or absent input | The renderer and resolver never raise on an empty charter, a charter without the headings, or a masked/unbalanced heading; each path returns the empty block or the honest placeholder. | Reliability | High | Open |
| NFR-002 | Rendering cost stays linear | The filter adds at most one extra bounded scan of `charter.md` per render; no new full-canon resolution and no measurable regression against the <2s CLI budget. | Performance | Medium | Open |
| NFR-003 | Targeted validation only | Mission validation runs the affected charter/specify test packages, not the full suite, per `NO_FULL_HEAVY_SUITES_IN_MISSION`. | Process | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority | The action-critical heading list stays owned by `section_bodies.py`; the fix filters it against the charter rather than adding a second list or a project-config override. | Technical | High | Open |
| C-002 | No pack edits in this repository | `packs/built-in` is fetched from `spec-kitty-open-packs` and gitignored; the pack prose that names the three headings is fixed upstream and pinned, not edited here. | Technical | High | Open |
| C-003 | Preserve the ATDD anchors | The WP-prompt governance contract tests for present sections must keep passing unchanged in intent; only tests that pinned the defective missing-section behaviour may be updated. | Technical | High | Open |

### Key Entities

- **Action-critical section set**: the per-action ordered heading list in `ACTION_CRITICAL_SECTIONS`; the configured maximum, not the advertised set.
- **Advertised section set**: the subset of the configured set whose heading resolves in the active `charter.md`; what the rendered block names.
- **Selector**: `section:<kebab-cased-heading>`, the `--include` handle for a heading; advertised only for headings in the advertised set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a minimal consumer charter with none of the three headings, `charter context --action implement` and `--action review` emit zero `--include section:` lines (currently three each) — [build] · no-op passable: no
- **SC-002**: In a charter carrying all three headings, all three bodies and all three fetch stanzas still render for `implement` and `review`, byte-identical to today's output — [ratchet] · no-op passable: no
- **SC-003**: A regression test exercises the production entry point on a minimal consumer charter and fails on unpatched `main` — [build] · no-op passable: no
- **SC-004**: The targeted charter/specify test packages pass, and the resolver contract states the filtered-set rule — [build] · no-op passable: no

## Out of Scope

- Serving built-in doctrine content in place of a missing charter section. The
  issue's expected behaviour is to stop advertising; inventing substitute
  governance is a larger design change and is not required for the reported
  defect.
- Editing `packs/built-in` mission-step prompt prose (fetched, pinned; upstream
  follow-up in `spec-kitty-open-packs`).
