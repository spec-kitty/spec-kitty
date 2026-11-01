# Work Packages: Charter synthesize JSON reports POSIX paths on every OS

**Inputs**: Design documents from `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/`
**Prerequisites**: plan.md, spec.md, research.md
**Issue**: #6277

**Organization**: Two work packages. WP01 is the code change that fixes the spelling and
proves it red-first; WP02 is the reporting surface (acceptance scenario + changelog) that
must not land until the code is green.

## Work Package WP01: One POSIX spelling for reported charter paths (Priority: P0)

**Goal**: Every repository-relative path `charter synthesize` reports or records is a POSIX
string on every operating system, proven by a Windows-simulated regression test that is red
before the change.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py -q` passes, and reverting the source change makes it fail.
**Prompt**: `tasks/WP01-posix-reported-paths.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

T001 Add a repo-relative POSIX helper to `src/kernel/charter_pack_paths.py`
T002 Route the fresh-seed reported paths through the helper in `src/specify_cli/cli/commands/charter/_fresh_project_layer.py`
T003 Record `ManifestArtifactEntry.path` POSIX in `src/charter/activation/synthesizer/write_pipeline.py` and normalise the manifest projection in `src/specify_cli/cli/commands/charter/_synthesis.py`
T004 Write the Windows-simulated regression test (red before T001–T003) with a non-vacuity control in `tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py`
T005 Run the targeted charter-synthesis test selection and the type/lint checks on the changed files

### Implementation Notes

- Red first: land T004 and show it failing against the unfixed source before applying
  T001–T003. The failing run is the evidence for SC-004.
- The simulation patches `Path.relative_to` to return a Windows-flavoured path so `str()`
  renders `\` while `.as_posix()` renders `/`. Do not fake `os.name` (it flips `pathlib`
  mid-run and crashes pytest — see `tests/kernel/test_is_windows_seam.py`).
- Preserve POSIX-host output byte for byte: `str(p)` and `p.as_posix()` agree there, so no
  committed fixture may change.

### Parallel Opportunities

- T001 and T004 were written independently of T002/T003 and only meet at the assertions.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Changing a manifest byte on POSIX would churn committed fixtures → assert equality on the
  existing synthesis pipeline tests, not just the new module.
- Helper misuse on an already-relative string → take `Path` arguments, not `str`, and
  document the contract in its docstring.

---

## Work Package WP02: Reporting surface — acceptance scenario and changelog (Priority: P1)

**Goal**: The end-to-end acceptance scenario asserts the full forward-slash paths again
(dropping #6266's interim file-name-only relaxation) and the change is recorded in the
`[Unreleased]` changelog.
**Independent Test**: the `charter.feature` scenarios that assert reported paths pass, and
`docs/changelog/CHANGELOG.md` carries the `(#6277)` entry.
**Prompt**: `tasks/WP02-reporting-surface.md`
**Requirement Refs**: FR-005, SC-001, SC-002, SC-005

### Included Subtasks

T006 Restore the full `.kittify/...` path assertions in `tests/scenarios/charter/charter.feature` and update the ledger note in `tests/scenarios/absorption-ledger.json`
T007 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md`

### Implementation Notes

- The scenario comment that explains the file-name-only relaxation is replaced by a
  comment naming the contract: reported paths are POSIX on every platform.
- Changelog entry: bold impact-first lead with `(#6277)`, before/after, under 1,200
  characters.

### Parallel Opportunities

- T006 and T007 touch disjoint files and may proceed in parallel.

### Dependencies

- Depends on WP01 (the scenario's full-path assertion is only true after the code fix).

### Risks & Mitigations

- The BDD scenario requires the built CLI to be current → run it after WP01 against the
  working tree, not the stale global install.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: WP01's subtasks are file-disjoint except the test/fix pairing, which
  is sequential by design (red then green).
- **MVP Scope**: WP01 alone fixes the defect; WP02 makes it observable and lands the
  user-facing record.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP02 |
| FR-006 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01, WP02 |
| SC-002 | WP01, WP02 |
| SC-003 | WP01 |
| SC-004 | WP01 |
| SC-005 | WP01, WP02 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Repo-relative POSIX helper | WP01 | P0 | No |
| T002 | Fresh-seed reported paths POSIX | WP01 | P0 | No |
| T003 | Manifest record + projection POSIX | WP01 | P0 | No |
| T004 | Windows-simulated regression test | WP01 | P0 | No |
| T005 | Targeted tests, lint and types | WP01 | P0 | No |
| T006 | Restore acceptance full-path assertions | WP02 | P1 | Yes |
| T007 | Changelog entry | WP02 | P1 | Yes |
