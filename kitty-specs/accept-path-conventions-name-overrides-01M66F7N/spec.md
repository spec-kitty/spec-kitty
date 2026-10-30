# Mission Specification: Name the path-convention override routes in accept's failure text

**Mission Branch**: `issue-6633-accept-path-conventions-name-overrides`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6633 — [bug] accept's path-convention failure never mentions project.path_conventions"
**Tracked issues**: spec-kitty/spec-kitty#6633 (the bug), with #3016, #3730, #3783, #4088, #5298 as referenced history and #2744 as the deferred auto-detection follow-up.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Self-serve a non-`src/` layout from the failure text (Priority: P1)

An operator of a Go + Vue repository (packages under one root, tests colocated as `*_test.go`, no `src/`, `tests/` or `docs/`) runs `spec-kitty accept --mission <m> --diagnose` and is blocked on all three software-dev path conventions. Today the failure text offers only `accept --lenient` (which also skips the per-WP `agent`/`assignee`/`shell_pid` metadata checks) or `mkdir -p src/ tests/ docs/` (fabricating empty directories). The operator should be able to read the failure text and find the honest route #3016 added: `project.path_conventions` in `.kittify/config.yaml`, with the exact remappable key names and a copy-pasteable example.

**Why this priority**: This is the reported defect. The escape hatch exists but is undiscoverable exactly when it is needed — at the moment of blockage.

**Independent Test**: Run `validate_mission_paths` in strict mode against a repo with a Go-style layout and no `path_conventions` config; the raised error text names `project.path_conventions`, `.kittify/config.yaml`, and the missing keys (`workspace`, `tests`, `documentation`) inside a copy-pasteable YAML snippet.

**Acceptance Scenarios**:

1. **Given** a software-dev mission whose `src/`, `tests/` and `docs/` are all missing at the repo root, **When** strict path validation fails, **Then** `format_errors()` names `project.path_conventions` and `.kittify/config.yaml`, and the YAML example it prints lists exactly the missing remappable keys (`workspace`, `tests`, `documentation`), not a hardcoded list.
2. **Given** only some conventions are missing (e.g. `docs/` exists), **Then** the example lists only the keys that are actually missing.
3. **Given** the only missing key is artifact-routed (`deliverables`), **Then** the failure text does NOT suggest `project.path_conventions` for it (that key cannot be overridden; the #5298 waiver route governs it), while the #3783 contract still holds (`--lenient` named, before `mkdir -p`).

### User Story 2 - Drop a convention with no directory, honestly (Priority: P2)

An operator whose project genuinely has no `docs/` directory (and does not want one) needs to drop the `documentation` convention. The remap-only project override cannot do this (it refuses empty values and never drops a key); the honest route is a project mission-type override at `.kittify/overrides/missions/<type>/mission.yaml` (#4088). The failure text and the accept how-to should name this route.

**Why this priority**: The issue explicitly asks for it; without it the text points every project at remapping, including projects with no directory to remap to.

**Independent Test**: The strict failure text names `.kittify/overrides/missions/` and `mission.yaml` as the route for a key the project has no directory for; the accept how-to names both routes where it currently says other conventions "stay in force".

**Acceptance Scenarios**:

1. **Given** strict path validation fails for a mission, **When** the failure text is rendered, **Then** it names the mission-override route (`.kittify/overrides/missions/<type>/mission.yaml`) as the way to drop a key the project has no directory for.
2. **Given** a reader of `docs/guides/how-to/missions/accept-and-merge.md`, **When** they reach the `contracts: none` waiver bullet that says other conventions "stay in force", **Then** the surrounding text names `project.path_conventions` (remap) and the mission-override route (drop) as the project-level levers for those conventions.

### Edge Cases

- A hand-built `PathValidationResult` (as existing unit tests construct) with no override metadata must still render valid failure text — the new guidance degrades gracefully rather than crashing or printing empty key lists.
- The `--diagnose` wrapper (`summary_core.evaluate_path_conventions`) wraps `format_errors()` output verbatim; the new lines must survive that wrapping and the waiver-notice prefix unchanged.
- An org-registered or neutral mission type (no `mission.yaml` at any tier): the mission-type slug must not be guessed from a path that does not describe a tier; when it cannot be derived, the override-route line stays generic (`<mission-type>` placeholder) rather than naming a wrong directory.
- The #3783/#3730 contract tests (`--lenient` present, before `mkdir -p`, no unconditional "are required" claim) must stay green byte-for-byte in their assertions.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Name `project.path_conventions` in the strict failure text | As an operator blocked on path conventions, I want the failure text to name the config override with its exact keys and a copy-pasteable example, so I can self-serve a non-`src/` layout without `--lenient` or fabricated directories. | High | Open | [build] | no — pinned by a red-first regression test asserting the key names on the pre-fix entry point |
| FR-002 | Name the mission-override drop route | As an operator whose project has no directory for a convention, I want the failure text to name `.kittify/overrides/missions/<type>/mission.yaml`, so I know the honest way to drop the key. | High | Open | [build] | no — asserted in the same regression test |
| FR-003 | Keep the #3783 remediation contract | As a maintainer, I want `--lenient` still named and still ordered before `mkdir -p`, and no unconditional "required" claim, so the #3730/#3783 regression tests stay green unmodified. | High | Open | [ratchet] | yes — paired with FR-001's positive control on the same fixture |
| FR-004 | Document both routes in the accept how-to | As a reader of the accept how-to, I want the section on path conventions to name the remap and drop routes, so the docs stop implying only `--lenient` and `mkdir` exist. | Medium | Open | [build] | no — the docs section currently names neither route |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Failure text stays bounded | The added guidance adds no more than ~10 lines to `format_errors()` output; no per-key repetition beyond the key list. | Usability | Medium | Open |
| NFR-002 | No behaviour change to validation | Path validation semantics (blocking, remap application, waiver handling, artifact routing) are unchanged; only the rendered text and the docs change. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | #3783 contract | `--lenient` remains named and appears before any `mkdir -p` suggestion; the "are required by the active mission" phrase stays absent. | Technical | High | Open |
| C-002 | Remap-only override vocabulary | The text must not suggest overriding `deliverables` (artifact-routed, excluded from `project.path_conventions`); the #5298 waiver governs `contracts` and its own guidance already prints. | Technical | High | Open |
| C-003 | Single seam | The guidance is built in `PathValidationResult.format_errors()` (the sole strict-failure text source, consumed by `summary_core` and `PathValidationError`); no second copy of the remediation text. | Technical | High | Open |
| C-004 | Not a layout-inference change | Auto-detection of layouts stays out of scope (#2744, the ADR's deferred next step). | Business | Medium | Open |

### Key Entities

- **PathValidationResult**: the validation outcome; gains the data needed to render project-level guidance (the missing keys that a `path_conventions` override could remap, and the mission-type slug for the override path).
- **project.path_conventions**: the remap-only project config section (`.kittify/config.yaml`) added by #3016; applies ahead of mission-type doctrine defaults.
- **Mission-type override**: a project copy of a packaged `mission.yaml` under `.kittify/overrides/missions/<type>/` (#4088); the only sanctioned way to drop a path-convention key.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The strict path-convention failure text for a Go-style repo missing `src/`, `tests/` and `docs/` names `project.path_conventions`, `.kittify/config.yaml`, and each missing remappable key (`workspace`, `tests`, `documentation`) in a copy-pasteable example — [build] · no-op passable: no
- **SC-002**: The same text names the `.kittify/overrides/missions/<type>/mission.yaml` route for dropping a key — [build] · no-op passable: no
- **SC-003**: The existing #3730 contract test (`test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim`) passes unmodified, and a new assertion keeps `--lenient` ordered before `mkdir -p` on the new fixture — [ratchet] · no-op passable: yes — positive control is SC-001's fixture
- **SC-004**: `docs/guides/how-to/missions/accept-and-merge.md` names both routes where it says the other conventions "stay in force" — [build] · no-op passable: no
- **SC-005**: A `[Unreleased]` changelog entry (bold impact-first lead, `(#6633)`, before/after) documents the improved failure text — [build] · no-op passable: no
