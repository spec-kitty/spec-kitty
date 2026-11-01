# Mission Specification: Charter synthesize JSON reports POSIX paths on every OS

**Mission Branch**: `kitty/mission-charter-synthesize-json-posix-paths-01M6BTVM`
**Created**: 2026-11-01
**Status**: Ready for planning
**Input**: GitHub issue #6277 — "charter synthesize --json reports backslash paths on Windows"

## Problem

`spec-kitty charter synthesize --json` is a machine-readable envelope: agents and CI
scenarios read `files_written`, `files_planned`, `planned_deletes` and
`written_artifacts[].path` to learn which repository-relative files synthesis touched.
On Windows the same fields are spelled with `\` (`.kittify\charter-packs\PROVENANCE.md`)
because the strings are produced with `str(Path.relative_to(...))`, whose separator
follows the host OS. On Linux and macOS they read `.kittify/charter-packs/PROVENANCE.md`.

Two consequences follow:

1. A consumer of the envelope gets a different path spelling per operating system, so
   "the same run" is not byte-comparable across platforms. The acceptance scenario
   `tests/scenarios/charter/charter.feature` was relaxed in #6266 to assert file *names*
   only, with an explicit note that this stays relaxed "until this is decided".
2. The real-run envelope's `written_artifacts[].path` is not built from the synthesizer's
   own `.as_posix()` computation: the write pipeline records
   `ManifestArtifactEntry.path` with the same OS-separator spelling into the committed
   `.kittify/charter/synthesis-manifest.yaml`, and the envelope projects that recorded
   string verbatim. So the manifest itself — a file committed to a project repository —
   is OS-dependent, not just the JSON.

## Goals

- Every repository-relative path string this command emits (JSON and human output) is
  POSIX on every operating system.
- The recorded `synthesis-manifest.yaml` entry paths are POSIX too, so the file is
  portable and identical across platforms.
- The fix is raised at the point the repo-relative string is produced (one spelling rule,
  not per-field normalisation), so a future field cannot reintroduce the divergence.
- The acceptance scenario returns to asserting the full forward-slash paths.

## Non-goals

- No change to the JSON envelope shape, field names, schema
  (`contracts/synthesis-envelope.schema.json`) or exit codes.
- No change to how paths are used for filesystem access; only the reported spelling.
- No normalisation of arbitrary user-supplied paths, or of path strings in unrelated
  commands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Windows consumer reads the same paths as a Linux consumer (Priority: P1)

An agent or CI scenario runs `spec-kitty charter synthesize --json` on Windows and parses
`written_artifacts[].path` to locate the artifacts that were written. It must receive
`.kittify/charter-packs/PROVENANCE.md`, exactly as a Linux or macOS consumer would.

**Why this priority**: this is the reported defect and the whole point of the mission; a
consumer that compares or records envelope paths is wrong on Windows today.

**Independent Test**: run the fresh-project `charter synthesize --json` path with the
Windows path-rendering semantics simulated on POSIX, and assert that every reported path
equals the `as_posix()` spelling of its on-disk file.

**Acceptance Scenarios**:

1. **Given** a fresh project on any OS, **when** `charter synthesize --json` runs, **then**
   `files_written` and `written_artifacts[].path` contain
   `.kittify/charter-packs/PROVENANCE.md` and `.kittify/charter/synthesis-manifest.yaml`
   with `/` separators.
2. **Given** a fresh project on any OS, **when** `charter synthesize --dry-run --json`
   runs, **then** `files_planned` and `written_artifacts[].path` use the same forward-slash
   spelling, and the dry-run paths equal the real-run paths byte for byte.
3. **Given** a stale project-local `.kittify/charter-packs/graph.yaml` on any OS, **when**
   a fresh-seed synthesize runs, **then** `planned_deletes` reports
   `.kittify/charter-packs/graph.yaml` with `/` separators.

### User Story 2 - A synthesized project's manifest is portable (Priority: P2)

A team synthesizes a charter on Windows and commits
`.kittify/charter/synthesis-manifest.yaml`. A teammate on Linux re-runs synthesis and gets
no diff, and the real-run envelope they read carries the same path strings.

**Why this priority**: the manifest is committed, so an OS-dependent spelling is a
cross-platform diff and a second, divergent source of the same path.

**Independent Test**: with Windows path rendering simulated, promote an artifact and assert
the recorded `ManifestArtifactEntry.path` is the POSIX spelling; then assert the real-run
envelope's `written_artifacts[].path` is that same POSIX spelling.

**Acceptance Scenarios**:

1. **Given** a project with authored doctrine on any OS, **when** `charter synthesize` runs
   for real, **then** each `synthesis-manifest.yaml` artifact entry records a
   `/`-separated repo-relative path.
2. **Given** that manifest, **when** the same command emits `--json`, **then**
   `written_artifacts[].path` matches the manifest path and contains no `\`.
3. **Given** the same project and authored doctrine on two platforms, **when** synthesis
   runs, **then** the manifest bytes (ignoring the documented volatile provenance fields)
   are identical.

### Edge Cases

- A path with no separator at all (a repo-root file) renders identically before and after;
  the change must not add or drop a leading `./`.
- `planned_deletes` is empty when no stale graph exists; an empty list stays empty.
- A path recorded by an older, already-committed Windows manifest still carries `\`. The
  envelope must not re-emit it verbatim as the only spelling: the reader normalises what
  it projects, so an existing manifest cannot re-break the envelope.
- Non-Windows hosts must be byte-for-byte unchanged (`str()` and `as_posix()` agree when
  the separator is `/`), so no committed fixture on Linux changes.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fresh-seed report paths are POSIX | As an agent consuming `--json`, I want `files_written` / `files_planned` / `planned_deletes` / `written_artifacts[].path` to use `/` on every OS so that one parser works everywhere. | High | Open | [build] | no |
| FR-002 | Recorded manifest paths are POSIX | As a maintainer, I want `ManifestArtifactEntry.path` written with `/` so the committed `synthesis-manifest.yaml` is identical on every platform. | High | Open | [build] | no |
| FR-003 | Real-run envelope normalises what it reads | As a consumer, I want `written_artifacts[].path` from a manifest projection to be POSIX even when the manifest on disk was written by an older Windows run, so the envelope never leaks a backslash. | Medium | Open | [build] | no |
| FR-004 | One spelling rule, not per-field patches | As a maintainer, I want repo-relative path rendering to go through one helper used by every emitting site so that a new field cannot reintroduce OS-dependent spelling. | Medium | Open | [build] | no |
| FR-005 | Acceptance scenario asserts full paths again | As a maintainer, I want `tests/scenarios/charter/charter.feature` to assert the full `.kittify/...` paths so the cross-platform contract is guarded end to end. | Medium | Open | [ratchet] | no |
| FR-006 | Regression test proves the Windows behaviour | As a maintainer, I want a test that simulates Windows path rendering and fails on the pre-fix code, so the defect cannot silently return on a POSIX-only CI. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | POSIX behaviour unchanged | On POSIX hosts the reported strings are byte-identical to today's output (no committed fixture or expected value changes). | Compatibility | High | Open |
| NFR-002 | Envelope cost | The change adds no filesystem I/O to the JSON path: normalisation is pure string/`Path` work on values already in hand. | Performance | Medium | Open |
| NFR-003 | Test cost | The regression test runs in the fast unit tier (no subprocess, no real Windows host), so it gates every PR run in well under a second. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Envelope contract frozen | `contracts/synthesis-envelope.schema.json` field names, types and required set do not change; only the string spelling of repo-relative paths does. | Technical | High | Open |
| C-002 | No host detection seam change | The fix is separator-agnostic (`Path.as_posix()`), not a new `is_windows()` branch; no new OS-detection seam is introduced. | Technical | High | Open |
| C-003 | Scope | Changes stay inside the charter synthesis reporting path plus its tests, the acceptance scenario and the changelog. | Business | Medium | Open |

### Key Entities

- **Envelope path field**: a repo-relative, `/`-separated string in `files_written`,
  `files_planned`, `planned_deletes` or `written_artifacts[].path`.
- **Manifest artifact entry**: one `ManifestArtifactEntry` in
  `.kittify/charter/synthesis-manifest.yaml`; its `path` is the same contract, persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With Windows path rendering simulated, 0 of the reported envelope paths in a fresh-seed synthesize (real and dry run) contain a backslash. — [build] · no-op passable: no
- **SC-002**: For the same fresh project, the `--dry-run` `files_planned` values equal the real-run `files_written` values byte for byte (2 of 2 entries compared) under Windows-simulated rendering. — [build] · no-op passable: no
- **SC-003**: A manifest produced under simulated Windows rendering contains 0 backslashes, and the real-run envelope projects those same POSIX strings. — [build] · no-op passable: no
- **SC-004**: The pre-fix code fails the new regression test and the post-fix code passes it (1 red → 1 green on the same fixtures). — [build] · no-op passable: no
- **SC-005**: POSIX host output is unchanged: the full existing charter synthesis test selection stays green with 0 expected-value edits. — [ratchet] · no-op passable: no
