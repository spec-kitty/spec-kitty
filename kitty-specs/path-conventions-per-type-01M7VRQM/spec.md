# Mission Specification: Per-mission-type path conventions and a narrow path waiver

**Mission Branch**: `kitty/mission-path-conventions-per-type-01M7VRQM` (lands on `issue-7566-path-conventions-per-type`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: Operator brief for #7566 and #7748 (references #2330 item 1 only), plus operator rulings Q1–Q3 (Decision Moments `01M7VRR00QYQ5DRXSRYV6TJQG7`, `01M7VRR2HQZZ6DNR5FQNA52CCJ`, `01M7VRR4Z91FGFD07XY9XM42D0`).

## Intent Summary

- **Primary actor:** the operator of a repository whose real layout differs from a mission type's conventions. The typical case is a content repository such as spec-kitty-open-packs, which has `packs/` and no `src/`.
- **Trigger:** `spec-kitty accept` on a Mission whose type declares a directory (software-dev `workspace: src/`) that the repository does not have.
- **Desired outcome:** the operator can remap the path for **one mission type** without moving the same key for the others. Where a layout mismatch is genuine and one-off, the operator can waive **path conventions only** while metadata validation stays strict.
- **Rule that must always hold:** a remap changes *which* directory is checked, never *whether* a missing directory blocks. The #3783 blocking policy is unchanged, and a malformed configuration fails closed.
- **Canonical terms:** *path convention* (a mission type's declared `paths:` key); *flat override* (a string value under `project.path_conventions`); *per-type section* (a mapping value under `project.path_conventions` keyed by a mission-type id); *path-convention waiver* (the narrow escape). `--lenient` stays as the broad escape.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remap one mission type's path (Priority: P1)

The operator of a repository with no `src/` declares:

```yaml
project:
  path_conventions:
    software-dev:
      workspace: packs/
```

A software-dev Mission then accepts against `packs/`. Documentation, plan and research Missions keep their own defaults (`docs/`, `docs/`, `research/`).

**Why this priority**: it is the durable fix for #7748 and the default route #7566 asks for.

**Independent Test**: use a fixture shaped like open-packs (`packs/` and `docs/` present, no `src/`) holding one Mission of each built-in type, and run the path-convention evaluation for each.

**Acceptance Scenarios**:

1. **Given** the per-type section above and no `src/`, **When** a software-dev Mission is evaluated, **Then** `workspace` resolves to `packs/` and no path violation is reported.
2. **Given** the same configuration, **When** a research Mission is evaluated, **Then** `workspace` still resolves to `research/` (under the Mission's deliverables prefix), not `packs/`.
3. **Given** a flat `workspace: apps/` plus a per-type `software-dev.workspace: packs/`, **When** a software-dev Mission is evaluated, **Then** `packs/` wins. **When** a documentation Mission is evaluated, **Then** `apps/` wins.
4. **Given** a per-type `workspace: packs/` with `packs/` absent, **When** a software-dev Mission is evaluated strictly, **Then** it still blocks, naming `packs/` (non-fakeable).

### User Story 2 - Fail closed on a malformed per-type section (Priority: P1)

**Why this priority**: the configuration is user-facing. A typo must be loud, never silently ignored.

**Acceptance Scenarios**:

1. **Given** a mapping value keyed by an id that is not in the project's layered mission-type roster, **When** the configuration is read, **Then** a typed configuration error names the id and the known ids.
2. **Given** a per-type section with an unknown path key, a non-string value, a blank value, an absolute path or a `..` segment, **When** the configuration is read, **Then** a typed configuration error names the type and the key.
3. **Given** a per-type section that is not a mapping of strings (e.g. a list), **Then** the read fails closed.
4. **Given** `deliverables` inside a per-type section, **Then** it is warned about and ignored, exactly as in the flat form.

### User Story 3 - The remedy names the per-type remap first (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a missing remappable path on a software-dev Mission, **When** accept fails, **Then** the first remedy shown is a copy-pasteable `project.path_conventions.software-dev.<key>` snippet for the failing type.
2. **Then** no `mkdir -p` is offered for a remappable path.
3. **Then** the full `mission.yaml` override copy is not presented as the default route. It appears, if at all, only as a last resort that freezes the mission definition.
4. **Given** a missing `contracts/` Mission artifact, **Then** `mkdir -p` is offered, and the `contracts: none` waiver is named as the alternative.
5. **Then** the text names the narrow path-convention waiver before `--lenient`.

### User Story 4 - Waive path conventions without weakening metadata checks (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a missing path, **When** the operator runs `accept --waive-path-conventions --waive-reason "<why>"`, **Then** the path violation becomes a non-blocking warning, **and** strict metadata validation still blocks on a metadata problem.
2. **Given** that per-run waiver on a successful accept, **Then** the acceptance history entry records the waiver and its reason.
3. **Given** `meta.json` with `"path_conventions": "waived"` and a non-blank `path_conventions_rationale`, **When** accept runs without any flag, **Then** path conventions are advisory and the rationale is surfaced in the accept output. Metadata stays strict.
4. **Given** a malformed per-Mission waiver (a wrong value or a missing or blank rationale), **Then** nothing is waived, and the blocking text carries a warning naming the problem.
5. **Given** `--waive-path-conventions` without `--waive-reason` (or with a blank one), **Then** accept refuses with a usage error before doing anything.
6. **Given** the orchestrator-api accept or consolidate path, **Then** it offers no per-run waiver; it honours a well-formed `meta.json` waiver exactly as the CLI does (operator ruling Q4), and metadata stays strict.

### Edge Cases

- A per-type section for a type whose Mission does not declare that key: ignored (remap-only).
- A per-type value colliding with a Mission artifact token: dropped with a warning, as for flat.
- A Mission whose type cannot be determined: only the flat form applies.
- A mission-type roster that cannot be read: the configuration read fails closed, since a per-type key cannot be validated.
- No per-type sections in the config: the roster is not read (no cost for the flat-only or empty case).
- Both waivers present: the effect is the same (advisory). Both are recorded or surfaced.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | Under `project.path_conventions`, a mapping value keyed by a mission-type id is a per-type section; a string value keeps the existing flat meaning. | Draft | [build] | no |
| FR-002 | Per key, the resolved directory is the per-type value for the Mission's type, else the flat value, else the mission-type default. A per-type value applies to its own type only. | Draft | [build] | no |
| FR-003 | A per-type section keyed by an id outside the project's layered mission-type roster (built-in, org, project) raises the configuration error, naming the id. | Draft | [build] | no |
| FR-004 | Inside a per-type section, an unknown path key, a non-string, blank, absolute or `..` value, or a non-mapping section raises the configuration error. `deliverables` is warned about and ignored (C-010). | Draft | [build] | no |
| FR-005 | Flat-form behaviour (keys, validation, warnings, errors) is unchanged. | Draft | [ratchet] | yes — positive control: the existing reader tests stay green unmodified |
| FR-006 | For a missing remappable path, the failure and warning texts name the per-type remap for the failing type as the first remedy, with a copy-pasteable snippet. | Draft | [build] | no |
| FR-007 | No `mkdir -p` is offered for a remappable path. `mkdir -p` is offered only for Mission artifact paths and research deliverable paths, and a missing `contracts/` also names the `contracts: none` waiver. | Draft | [build] | no |
| FR-008 | The full `mission.yaml` override copy is no longer the default route. If shown, it is marked as a last resort that freezes the mission definition. | Draft | [build] | no |
| FR-009 | `accept --waive-path-conventions --waive-reason "<why>"` makes path-convention misses non-blocking for that run, keeps metadata validation strict, and records `path_conventions_waived` with the reason on the acceptance history entry. | Draft | [build] | no |
| FR-010 | A `meta.json` declaration `"path_conventions": "waived"` with a non-blank string `path_conventions_rationale` makes path-convention misses non-blocking for that Mission. The rationale is surfaced in the accept output. A malformed declaration waives nothing and warns. | Draft | [build] | no |
| FR-011 | `--waive-path-conventions` without a non-blank `--waive-reason` is refused before any write. | Draft | [build] | no |
| FR-012 | The failure text names the narrow waiver before `--lenient`. `--lenient` keeps its current meaning. | Draft | [build] | no |
| FR-013 | The orchestrator-api accept and consolidate paths offer no per-run waiver (path misses block there unless the Mission's `meta.json` carries a well-formed waiver, which every accept path honours, operator ruling Q4), and metadata stays strict there. | Draft | [build] | no — the same Mission data gives the same path verdict on the CLI and orchestrator-api paths |

### Non-Functional Requirements

| ID | Requirement | Threshold | Status |
|----|-------------|-----------|--------|
| NFR-001 | The configuration is read at most once per accept run, and the mission-type roster is read only when at least one per-type section exists. | 1 config read; 0 roster reads for a flat-only or empty config | Draft |
| NFR-002 | Existing configurations keep working without edits. | 0 changes needed to any currently valid `.kittify/config.yaml` | Draft |
| NFR-003 | Touched code passes ruff, ruff format and mypy, with C901 ≤ 15. | 0 findings | Draft |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | `validate_mission_paths` keeps exactly one production caller (`evaluate_path_conventions`). | Draft |
| C-002 | No change to built-in pack `mission.yaml` schemas; packs stay pinned at a79c3631. | Draft |
| C-003 | Remap-only: a per-type section never adds a required path. | Draft |
| C-004 | The #3783 policy is unchanged: a remap changes the checked directory, never whether absence blocks. Wording pins from #3783 and #7512 are updated deliberately, never loosened. | Draft |
| C-005 | Only `project.path_conventions` is read, never the rest of the `project:` block (identity fields). | Draft |
| C-006 | Waivers cover path conventions only. Neither waiver changes metadata validation. | Draft |

## Success Criteria *(mandatory)*

- **SC-001**: In an open-packs-shaped fixture, a software-dev Mission accepts through a per-type override, while research and documentation Missions in the same fixture resolve to their own defaults. — [build] · no-op passable: no
- **SC-002**: Every fail-closed case in FR-003/FR-004 produces a typed error. — [build] · no-op passable: no
- **SC-003**: The first remedy line for a missing software-dev `workspace` names `software-dev:` under `project.path_conventions`. — [build] · no-op passable: no
- **SC-004**: With either waiver, a path miss no longer blocks while a metadata issue still does. — [build] · no-op passable: no

## Key Entities

- **Project path conventions:** the flat override mapping plus the per-type sections, read from `.kittify/config.yaml`.
- **Path-convention waiver:** a per-run flag with a reason, or a per-Mission `meta.json` declaration with a rationale.

## Assumptions

- The Mission's type comes from its resolved mission definition (the same slug the remedy text already uses). Where that slug is unavailable, only the flat form applies.
- The precedence contract of the original override Mission is no longer under `kitty-specs/`. ADR `2026-08-28-1` is its durable record and is amended by this Mission.
- `spec-kitty agent mission accept` forwards the new flag, matching how it forwards `--lenient`.

## Out of Scope

- `mission.yaml` schema changes in packs, and layout auto-detection (#2744).
- #2330's other items.
- Moving the check earlier to specify or plan (#7566 expectation 4).
