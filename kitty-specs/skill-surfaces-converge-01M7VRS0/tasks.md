# Work Packages: Skill surfaces converge

**Inputs**: `kitty-specs/skill-surfaces-converge-01M7VRS0/` (spec.md, plan.md, research.md, data-model.md, quickstart.md, occurrence_map.yaml)
**Tests**: required. Every WP is red-first (C-005): its failing test lands in its own commit before the fix.

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red tests: reader contract + current renders present | WP01 | |
| T002 | Generator script (git history, union-only) | WP01 | |
| T003 | Generate and commit the frozen JSON | WP01 | |
| T004 | Reader module `historical_renders.py` | WP01 | |
| T005 | RELEASE_CHECKLIST step | WP01 | [P] |
| T006 | Red tests: moved-root inventory, schema-1 migration | WP02 | |
| T007 | Schema-2 inventory (absolute keys) load/store | WP02 | |
| T008 | One-time schema-1 migration | WP02 | |
| T009 | `retire()` byte proof hook | WP02 | |
| T010 | Changelog fragment #7722 | WP02 | [P] |
| T011 | Red tests: global sync refresh/keep/stamp/retire | WP03 | |
| T012 | Global sync uses historical proof | WP03 | |
| T013 | Stamp withheld while canonical preserved | WP03 | |
| T014 | Retired dirs retire on byte proof | WP03 | |
| T015 | Project installer: historical render refreshes (#2527) | WP03 | |
| T016 | Kept-file classifier | WP03 | |
| T017 | Changelog fragments #7700, #2527 | WP03 | [P] |
| T018 | Red tests: tool-surfaces kept findings | WP04 | |
| T019 | Finding codes | WP04 | |
| T020 | Append global kept findings in `run_tool_surfaces` | WP04 | |
| T021 | Skipped surfaces name their reason (#2527) | WP04 | |
| T022 | Changelog fragment #5983 | WP04 | [P] |
| T023 | Red: flip #5281 xfail; red tests for old-root leftovers | WP05 | |
| T024 | `VerifyReport.outdated` + repair trigger | WP05 | |
| T025 | Old-root leftover discovery | WP05 | |
| T026 | `doctor command-files` / `doctor skills` report leftovers | WP05 | |
| T027 | Changelog fragments #5281, #7723 | WP05 | [P] |
| T028 | Red test: hash-clean retired orphan drained | WP06 | |
| T029 | `VerifyResult.retired` | WP06 | |
| T030 | `_delegate_repair` runs on retired entries | WP06 | |
| T031 | Changelog fragment #2460 | WP06 | [P] |
| T032 | Red test: retired-name guards + grep contract | WP07 | |
| T033 | Move skill dir, frontmatter name | WP07 | |
| T034 | Retire old id; update shipped-name lists | WP07 | |
| T035 | Repoint references (README, start-here, skill map, docs/api) | WP07 | |
| T036 | Regenerate historical JSON; changelog #7725 | WP07 | |

---

## Work Package WP01: Historical-render proof source (Priority: P1)

**Goal**: frozen, reviewed list of every shipped skill render + its reader.
**Independent Test**: reader proves a known historical blob for its path, refuses it for another path, and every current render is present.
**Prompt**: `tasks/WP01-historical-render-proof-source.md`
**Requirement Refs**: FR-001, C-001, NFR-001

### Included Subtasks

T001 Red tests: reader contract + current renders present (WP01)
T002 Generator script (git history, union-only) (WP01)
T003 Generate and commit the frozen JSON (WP01)
T004 Reader module `historical_renders.py` (WP01)
T005 RELEASE_CHECKLIST step (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Shallow CI clones: tests never read git; only the generator does.

---

## Work Package WP02: Global asset preparation primitives (Priority: P1)

**Goal**: inventory survives a moved root (#7722); `retire()` can accept a byte proof.
**Independent Test**: a recorded file under `~/.agents/skills` stays proven after `CLAUDE_CONFIG_DIR` moves outside home.
**Prompt**: `tasks/WP02-global-asset-preparation-primitives.md`
**Requirement Refs**: FR-007, FR-008

### Included Subtasks

T006 Red tests: moved-root inventory, schema-1 migration (WP02)
T007 Schema-2 inventory (absolute keys) load/store (WP02)
T008 One-time schema-1 migration (WP02)
T009 `retire()` byte proof hook (WP02)
T010 Changelog fragment #7722 (WP02)

### Dependencies

- None.

---

## Work Package WP03: Install surfaces use the proof (Priority: P1)

**Goal**: global sync and project installer refresh/retire byte-proven files; no current stamp while a canonical destination is kept (#7700, #2527, #5983 retire half).
**Prompt**: `tasks/WP03-install-surfaces-use-the-proof.md`
**Requirement Refs**: FR-001, FR-002, FR-004, FR-011, FR-012

### Included Subtasks

T011 Red tests: global sync refresh/keep/stamp/retire (WP03)
T012 Global sync uses historical proof (WP03)
T013 Stamp withheld while canonical preserved (WP03)
T014 Retired dirs retire on byte proof (WP03)
T015 Project installer: historical render refreshes (#2527) (WP03)
T016 Kept-file classifier (WP03)
T017 Changelog fragments #7700, #2527 (WP03)

### Dependencies

- Depends on WP01, WP02.

---

## Work Package WP04: doctor tool-surfaces reports kept files (Priority: P1)

**Goal**: kept stale canonical global skills and kept edited retired copies appear as findings; skipped repairs name their reason.
**Prompt**: `tasks/WP04-doctor-reports-kept-files.md`
**Requirement Refs**: FR-003, FR-004, FR-012

### Included Subtasks

T018 Red tests: tool-surfaces kept findings (WP04)
T019 Finding codes (WP04)
T020 Append global kept findings in `run_tool_surfaces` (WP04)
T021 Skipped surfaces name their reason (#2527) (WP04)
T022 Changelog fragment #5983 (WP04)

### Dependencies

- Depends on WP03.

---

## Work Package WP05: doctor skills/command-files converge and report leftovers (Priority: P2)

**Goal**: `doctor skills --fix` repairs a self-consistent corrupted command skill (#5281); both doctors list proven old-root leftovers (#7723).
**Prompt**: `tasks/WP05-doctor-skills-converge-and-leftovers.md`
**Requirement Refs**: FR-005, FR-009, FR-011

### Included Subtasks

T023 Red: flip #5281 xfail; red tests for old-root leftovers (WP05)
T024 `VerifyReport.outdated` + repair trigger (WP05)
T025 Old-root leftover discovery (WP05)
T026 `doctor command-files` / `doctor skills` report leftovers (WP05)
T027 Changelog fragments #5281, #7723 (WP05)

### Dependencies

- Depends on WP01, WP02.

---

## Work Package WP06: Verify-side retired-orphan detection (Priority: P2)

**Goal**: a hash-clean retired managed entry is reported by verification so the drain runs (#2460).
**Prompt**: `tasks/WP06-verify-retired-orphan.md`
**Requirement Refs**: FR-006

### Included Subtasks

T028 Red test: hash-clean retired orphan drained (WP06)
T029 `VerifyResult.retired` (WP06)
T030 `_delegate_repair` runs on retired entries (WP06)
T031 Changelog fragment #2460 (WP06)

### Dependencies

- None.

---

## Work Package WP07: Rename spk-start-first-feature → spk-start-first-mission (Priority: P3)

**Goal**: #7725 rename under the bulk-edit gate.
**Prompt**: `tasks/WP07-rename-first-mission-skill.md`
**Requirement Refs**: FR-010

### Included Subtasks

T032 Red test: retired-name guards + grep contract (WP07)
T033 Move skill dir, frontmatter name (WP07)
T034 Retire old id; update shipped-name lists (WP07)
T035 Repoint references (README, start-here, skill map, docs/api) (WP07)
T036 Regenerate historical JSON; changelog #7725 (WP07)

### Dependencies

- Depends on WP01 (the generator and JSON must exist to regenerate).
