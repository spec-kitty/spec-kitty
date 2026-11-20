# Mission Specification: Host-aware mode predicate for tool-surface planners

**Mission Branch**: `kitty/mission-host-aware-mode-predicate-01M7X6B1` (lands on `issue-4927-host-aware-mode-predicate`, PR to `main`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: #4927 (phantom Windows repairs that never converge) with #4810 (close the bug class by construction with a ratchet gate) folded in, per the operator rulings of 2026-11-20 (Decision Moment `01M7X6BEMB6XKJZM2VPV9TDE44`).

## Intent Summary

- **Primary actor:** a Spec Kitty user on Windows (NTFS) who has a converged project and user-global skill and asset roots.
- **Trigger:** any CLI start (the startup sync of global skills and assets), `spec-kitty upgrade --dry-run`, or `spec-kitty upgrade`.
- **Desired outcome:** once a project and the user's global roots are converged, no planner proposes a permission (mode) repair that the host cannot represent. A preview reports zero repairs and agrees with `doctor tool-surfaces`.
- **Rule that always holds:** on POSIX hosts, mode drift is detected and repaired exactly as today, including the execute bit and read-only files.
- **Canonical terms:** *planned mode* (the mode a planner stamps on the state it intends to produce), *observed mode* (the mode the host reports for an existing node), *mode equivalence* (whether the observed mode already satisfies the planned one on this host).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A converged Windows home stops re-planning global repairs (Priority: P1)

A Windows user runs any `spec-kitty` command. The startup sync of global agent skills and runtime assets finds the user's global roots already materialized and plans nothing. A later `spec-kitty upgrade --dry-run` previews no repairs in its global bootstrap phase.

**Why this priority**: this is the reported defect (#4927). Today 252 directory and 1 file permission repairs are re-planned on every start and every preview, and applying them never reduces the count.

**Independent Test**: under an emulated NTFS host (directories report 0o777; files report 0o666 when writable, else 0o444; a permission change only toggles a file's read-only state), assess the global skills and global assets, apply them once, then re-assess. The second assessment has no effects.

**Acceptance Scenarios**:

1. **Given** a converged global home on an emulated Windows host, **When** the global skills are assessed, **Then** the assessment has zero effects.
2. **Given** the same home, **When** the combined global assets (runtime, commands, skills) are assessed, **Then** no permission effect is planned.
3. **Given** a fresh global home on an emulated Windows host, **When** the startup sync runs once, **Then** a second assessment has zero effects.

### User Story 2 - POSIX mode drift is still repaired (Priority: P1)

A Linux or macOS user whose global skill directory was loosened to 0o777, or whose runtime script lost its execute bit, still gets that drift planned and repaired.

**Why this priority**: the fix must not weaken POSIX permission correctness, which other features (executable hook scripts, runtime scripts) depend on.

**Independent Test**: the same fixtures on a POSIX host plan a permission repair for the drifted node, and applying it converges.

**Acceptance Scenarios**:

1. **Given** a POSIX host and a managed skill directory at 0o777, **When** global skills are assessed, **Then** a permission repair to 0o755 is planned and applying it converges.
2. **Given** a POSIX host and a runtime script whose source is executable but whose installed copy is not, **When** assessed, **Then** a permission repair is planned and applying it restores the execute bit.

### User Story 3 - Windows read-only drift is still repaired (Priority: P2)

A Windows user whose managed file became read-only (or writable, where the plan says read-only) still gets that drift repaired, because the read-only state is the one permission Windows can represent.

**Why this priority**: read-only files block overwrites and deletes on Windows (#6228, #3771). Ignoring every file mode on Windows, as the project-skill path does today, hides that drift.

**Independent Test**: on an emulated Windows host, make a planned-writable managed file read-only. A permission repair is planned, applying it makes the file writable, and a re-assessment has no effects. The same holds in the other direction.

**Acceptance Scenarios**:

1. **Given** an emulated Windows host and a managed project skill file planned writable but observed read-only, **When** the project skills are assessed, **Then** a permission repair is planned, and after applying it no repair is planned.
2. **Given** an emulated Windows host and a global asset planned read-only but observed writable, **When** assessed, **Then** a permission repair is planned and converges.

### User Story 4 - Latent Windows refusals do not fire (Priority: P2)

On Windows, staging plugin bundles, projecting agent profiles into a directory a sibling owner just created, and confirming a native-config directory creation all complete instead of refusing, because none of them demands a POSIX mode the host cannot hold.

**Why this priority**: these paths are not reported yet. They are the same defect class, and they would surface as refusals or phantom repairs as soon as they are exercised on Windows.

**Independent Test**: each path is exercised on an emulated Windows host and completes. Its POSIX twin keeps today's behaviour.

**Acceptance Scenarios**:

1. **Given** an emulated Windows host, **When** a staged bundle is assessed against an already-written copy, **Then** no permission repair is planned and finalizing created directories does not refuse.
2. **Given** an emulated Windows host and a sibling owner that created the shared profile directory first, **When** agent profiles are written, **Then** the write proceeds instead of refusing that the destination changed.
3. **Given** an emulated Windows host, **When** a native-config directory creation completes, **Then** its postcondition holds.

### User Story 5 - Maintainers cannot reintroduce the defect (Priority: P1)

A maintainer who adds a new planner in `skills/`, `tool_surface/` or `runtime/` that compares an observed mode with a planned mode directly, instead of through the shared predicate, gets a failing architectural test that names the site.

**Why this priority**: the class has been point-fixed three times (#4776, #4777, 6269777dc) and reappeared each time in a path the fix did not reach (#4810).

**Independent Test**: inject a direct mode comparison into a scanned module (or a synthetic module). The gate fails and names the file and line. Remove it, and the gate passes.

**Acceptance Scenarios**:

1. **Given** the gate, **When** a planner compares `before.mode != after.mode` directly, **Then** the gate fails naming that site.
2. **Given** the gate, **When** an exemption names a site that no longer exists, **Then** the gate fails as stale.
3. **Given** the current tree after this Mission, **Then** the gate passes with an exemption table that lists only adjudicated observed-vs-observed guards and planned-vs-planned conflict checks, each with its rationale.

### Edge Cases

- A symlink's mode on Windows is ignored. On POSIX it keeps today's exact comparison.
- A node whose kind changed (file to directory) is a replacement, never a permission repair, on either host.
- An absent node is never mode-compared.
- Mode comparisons between two observations of the same node (concurrency and precondition guards) stay exact on both hosts, so a genuine change between plan and apply is still detected.
- Comparisons between two planned states (conflicting outputs from two owners) stay exact.
- A Windows file planned executable (0o755) and observed writable (0o666) is equivalent: the execute bit is not representable there.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| planned mode | the mode a planner stamps on the state it intends to produce | "expected mode" for an observed value |
| observed mode | the mode the host reports for an existing node | "actual stamp" |
| mode equivalence | whether an observed mode satisfies a planned mode on the current host | "mode equality" when the host matters |
| guard | a comparison of two observations of the same node, used to detect concurrent change | calling a guard a "planner" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One host-aware mode equivalence | As a maintainer, I want exactly one predicate that decides whether an observed mode satisfies a planned mode, so that every planner agrees. On POSIX it is exact equality. On Windows a directory or symlink compares kind only, and a file compares only its writable/read-only state. | High | Open | [build] | no — the POSIX twin rows (FR-004) run the same fixtures and must still plan repairs |
| FR-002 | Planner actions decided through the predicate | As a Windows user, I want every planner in `skills/`, `tool_surface/` and `runtime/` that decides between "permission repair" and "unchanged" to use FR-001, so that a converged home plans no permission repair (US1). This includes the validator that checks an effect's action against its before/after states. | High | Open | [build] | no — US1 scenario 1 is red today (253 effects) |
| FR-003 | Global skills and assets converge on Windows | As a Windows user, I want the global skill sync and the combined global asset assessment to plan zero effects after one apply, so that every CLI start and upgrade preview is quiet (US1). | High | Open | [build] | no — red today on the emulated host |
| FR-004 | POSIX mode drift still repaired | As a POSIX user, I want directory, file, execute-bit and read-only drift to be planned and to converge exactly as before (US2). | High | Open | [ratchet] | yes — paired on the same fixtures with FR-003, which a do-nothing change fails |
| FR-005 | Windows read-only drift repaired | As a Windows user, I want a managed file whose read-only state differs from the plan to be repaired, in both directions, so that read-only files cannot block later writes (US3). This replaces the project-skill path's "ignore every file mode on Windows" rule. | High | Open | [build] | no — red today for project skills |
| FR-006 | Stamp rechecks use the predicate | As a Windows user, I want every post-apply or pre-apply check that compares an observation against a planned state to use FR-001, so that a permission change the planner skipped never trips a recheck. | High | Open | [build] | no — exercised by the US1 apply and US4 scenarios |
| FR-007 | Latent Windows refusals removed | As a Windows user, I want bundle staging, agent-profile sibling directory acceptance and the native-config directory postcondition to accept host-equivalent modes (US4). | Medium | Open | [build] | no — each US4 scenario is red today on the emulated host |
| FR-008 | Guards stay exact | As a maintainer, I want comparisons of two observations of the same node, and of two planned states, to stay exact on both hosts, so that a genuine concurrent change is still refused. | High | Open | [ratchet] | yes — paired with a mutated-observation control that must still refuse |
| FR-009 | Single authority, no parallel relaxation | As a maintainer, I want the earlier Windows-only relaxation helper retired and its callers moved to FR-001, so that there is one authority. | Medium | Open | [build] | no — the gate (FR-010) fails if the old helper or a raw comparison remains |
| FR-010 | Mutation-proven ratchet gate | As a maintainer, I want an architectural test that fails when a scanned module decides mode equivalence outside FR-001, names the site, rejects stale exemptions, and carries a per-entry rationale for every adjudicated guard (US5). | High | Open | [build] | no — self-mutation and live-mutation controls must turn it red |
| FR-011 | Canonical host check in charter YAML writer | As a maintainer, I want the charter YAML writer's inline operating-system check replaced by the canonical host seam, so that tests can emulate the host there too. | Low | Open | [build] | no — a test that patches the seam must observe the change |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No startup cost | The per-comparison cost of the predicate is a constant number of integer operations plus one host check. Startup global assessment time on a converged home does not regress by more than 5% (median of 9 runs) against the base commit. | Performance | Medium | Open |
| NFR-002 | Quality gates clean | `ruff check`, `ruff format --check --force-exclude` and `mypy` report zero issues on every changed file, with no new suppressions. | Maintainability | High | Open |
| NFR-003 | Coverage | Every new or changed branch is executed by a focused test; diff coverage is at least 90%. | Maintainability | High | Open |
| NFR-004 | Gate cost | The new architectural gate runs in under 5 seconds locally. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Host seam | The host is detected only through `kernel.paths.is_windows`, read at call time, so tests can emulate Windows on Linux. | Technical | High | Open |
| C-002 | Layering | No new import edge breaks the enforced chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`. The predicate lives beside the node-state type it compares. | Technical | High | Open |
| C-003 | Scope exclusions | #5215, #5225, #7761 and #3048 are out of scope and are not folded. | Business | High | Open |
| C-004 | Red first | Each behaviour change lands with a test that is red on the base commit and green after. | Technical | High | Open |
| C-005 | No heavy suites | Mission work runs targeted tests and the specific architectural gate files only (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Process | High | Open |
| C-006 | Semantics change disclosed | The change from "ignore Windows file modes" to "compare the Windows write bit" for project skills is called out in the changelog fragment. | Business | Medium | Open |

### Key Entities

- **Node state**: the kind, content digest, link target, mode and modification time of a file-system node, as observed or as planned.
- **Physical effect**: one planned change to a node, with an action (create, update, permission repair, ...), a before state and an after state.
- **Exemption table**: the gate's list of adjudicated comparisons that are allowed to stay exact, each with a rationale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an emulated Windows host, a converged global home re-plans 0 effects (today: 253) after one sync pass. — [build] · no-op passable: no
- **SC-002**: On a POSIX host, every mode-drift fixture (directory, file, execute bit, read-only) still plans exactly one repair and converges after one apply. — [ratchet] · no-op passable: yes — paired with SC-001 on the same fixtures
- **SC-003**: The ratchet gate fails for 100% of the injected mutation shapes and passes on the final tree. — [build] · no-op passable: no
- **SC-004**: An upgrade preview on an emulated converged Windows project reports zero permission repairs while `doctor tool-surfaces` is clean. — [build] · no-op passable: no

## Assumptions

- The NTFS emulation (synthesized modes; a permission change only toggles a file's read-only state) is faithful enough for planners, which observe nodes through `lstat`/`stat`/`fstat`.
- An effect that plans a permission repair on Windows for host-equivalent modes is a defect. After this Mission the effect validator refuses it, rather than letting it re-plan forever.
