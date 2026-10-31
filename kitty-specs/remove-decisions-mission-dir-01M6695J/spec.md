# Mission Specification: Remove the read-side decisions service._mission_dir

**Mission Branch**: `issue-6766-remove-decisions-mission-dir`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6766. PR #6762 (#4848) moved the
opened-row check in `src/specify_cli/decisions/service.py` to the pre-resolved
write-side `events_path` and removed the read-side `_events_path` helper. Since
then the read-side `_mission_dir` (`service.py:335`) has no caller in `src/`;
its only users are two tests in `tests/specify_cli/test_read_seam_leniency.py`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No dead read-side helper in the decisions service (Priority: P1)

As a Spec Kitty maintainer, I want the read-side
`decisions/service.py::_mission_dir` helper deleted (together with the tests
that only exercise it and the docstrings that still name it) so that the
decisions module carries exactly one STATUS_STATE access path — the
write-side pre-resolved `_write_events_path` — and no reader can mistake the
dead read helper for a live seam.

**Why this priority**: This is the whole issue; everything else is guard-rail
work around it.

**Independent Test**: After the change, `specify_cli.decisions.service`
defines no `_mission_dir`, holds no `read_dir(STATUS_STATE)` call, and every
existing decisions test plus the read-seam / dead-symbol / write-side
rederivation gates are green.

**Acceptance Scenarios**:

1. **Given** current `main` (post-#6762), **When** the mission's guard test
   runs, **Then** it fails, because `service.py` still contains a read-side
   `placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)`
   resolution inside the caller-less `_mission_dir` (red-first proof).
2. **Given** the mission's change, **When** the same guard test runs,
   **Then** it passes: the decisions service resolves STATUS_STATE only
   through the write-side seam (`_write_mission_dir` /
   `_write_events_path`).
3. **Given** the mission's change, **When** the decisions test surface
   (`tests/decisions/`, `tests/specify_cli/decisions/`,
   `tests/specify_cli/test_read_seam_leniency.py`) runs, **Then** it is
   green.
4. **Given** the mission's change, **When**
   `tests/architectural/test_no_dead_symbols.py`,
   `tests/architectural/test_no_read_side_bypass.py` and
   `tests/architectural/test_no_write_side_rederivation.py` run, **Then**
   they are green.

### User Story 2 - Stale prose does not outlive the symbol (Priority: P2)

As a Spec Kitty maintainer reading `decisions/service.py`, I want the
docstrings and comments that reference `_mission_dir`
(`_resolve_mission_id`, `_write_mission_dir`, `_ledger_dir`, the
`open_decision` / terminal-write call sites, and the
`test_read_seam_leniency.py` module docstring) re-pointed to the surviving
seams so the module's documentation names only live code.

**Why this priority**: Dangling references to a deleted symbol are the next
best thing to a lie; cheap to fix in the same diff.

**Independent Test**: `grep -rn "_mission_dir" src/specify_cli/decisions/service.py`
returns no hits after the change, no test asserts on the deleted helper, and
the WP06 ledger row for `decisions/service.py` in
`docs/development/reference/read-side-seam-classification.md` records the
removal (spec-squad finding).

**Acceptance Scenarios**:

1. **Given** the mission's change, **When** the module and its tests are
   grepped for `_mission_dir`, **Then** `decisions/service.py` and
   `tests/specify_cli/test_read_seam_leniency.py` no longer reference the
   service.py helper (the separate, live `decisions/emit.py::_mission_dir`
   is out of scope and untouched).

### Edge Cases

- The two leniency tests
  (`test_decisions_mission_dir_fails_loud_when_coord_deleted`,
  `test_decisions_mission_dir_preserves_healthy_status_home`) guard the
  read-seam behaviour of the deleted helper only; the fail-loud
  coordination contract they probed is now exercised through the write-side
  pre-resolution in `_write_events_path` (covered by the existing
  `tests/specify_cli/decisions/` and `tests/decisions/` suites), so they are
  deleted, not re-pointed.
- `decisions/emit.py` has its own live `_mission_dir` (census-named in
  `test_no_write_side_rederivation.py`); it must not be touched.
- `_PRE_SPLIT_QUALNAMES` in `test_no_write_side_rederivation.py` maps the
  service pair back to `_mission_dir` for the red-at-base proof only; it
  keys off the census pair, not the live source, and must stay as-is.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Delete the read-side `_mission_dir` | As a maintainer, I want `specify_cli.decisions.service::_mission_dir` deleted so that no dead read-side STATUS_STATE resolution remains in the module. | High | Open | [build] | no |
| FR-002 | Remove the orphaned leniency tests | As a maintainer, I want the two `tests/specify_cli/test_read_seam_leniency.py` tests that call the deleted helper removed (and the module docstring's site ledger mention corrected, including its wrong ledger path `docs/development/read-side-seam-classification.md` → `docs/development/reference/read-side-seam-classification.md`) so the file pins only live read-seam behaviour. | High | Open | [build] | no |
| FR-003 | Re-point stale docstrings | As a maintainer, I want every docstring/comment in `decisions/service.py` that names `_mission_dir` re-pointed at the surviving seams, and the WP06 ledger row for `decisions/service.py` in `docs/development/reference/read-side-seam-classification.md` updated to record the site's removal (#6766, following the ledger's own "(removed, #NNNN)" convention), so module and reference documentation name only live code. | Medium | Open | [build] | no |
| FR-004 | Guard the single STATUS_STATE access path | As a maintainer, I want a regression test that fails while `decisions/service.py` still resolves STATUS_STATE through a read-side `read_dir` call and passes once all STATUS_STATE access is write-side, so the read/write split #4848 established cannot silently regress. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate parity | The architectural gates named in the issue (`test_no_dead_symbols.py`, the read-seam gates incl. `test_no_read_side_bypass.py` and `test_no_write_side_rederivation.py`) pass on the mission branch with zero allowlist additions. | Quality | High | Open |
| NFR-002 | Smallest viable diff | The change touches only `src/specify_cli/decisions/service.py`, its test file(s), and the changelog; no behaviour, exit-code, or artifact change for any decisions CLI verb. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | emit.py is out of scope | `src/specify_cli/decisions/emit.py` and its live `_mission_dir` (the COORD writer census entry) must not change. | Technical | High | Open |
| C-002 | No gate suppression | No `# noqa`, allowlist entry, skip, or xfail may be added to make a gate green. | Governance | High | Open |
| C-003 | PR-only delivery | Branch `issue-6766-remove-decisions-mission-dir`; PR targets `main`; the operator merges. | Governance | High | Open |

### Key Entities

- **Decisions service (STATUS_STATE access)**: `open_decision` /
  `resolve_decision` read and write decision events at
  `kitty-specs/<mission>/status.events.jsonl`. Since #4848/#6762 every
  STATUS_STATE access in `service.py` is a write-side pre-resolution
  (`_write_mission_dir` / `_write_events_path`); the read-side
  `_mission_dir` was left behind caller-less.
- **Read-seam leniency pins**: `tests/specify_cli/test_read_seam_leniency.py`
  pins migrated (fail-loud) and stay-lenient read-seam sites; two of its
  pins exercise only the dead helper.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -c "_mission_dir" src/specify_cli/decisions/service.py`
  returns 0 — [build] · no-op passable: no
- **SC-002**: the new STATUS_STATE-access guard test is red on the mission's
  planning base and green on the mission head — [build] · no-op passable: no
- **SC-003**: `tests/decisions/`, `tests/specify_cli/decisions/` and
  `tests/specify_cli/test_read_seam_leniency.py` pass in full on the mission
  head — [build] · no-op passable: no
- **SC-004**: `tests/architectural/test_no_dead_symbols.py`,
  `test_no_read_side_bypass.py` and `test_no_write_side_rederivation.py`
  pass on the mission head with zero new allowlist entries — [build] ·
  no-op passable: no
