---
description: "Work package task list for mission quick-win-remediation-01M72855"
---

# Work Packages: Quick-win remediation

**Inputs**: Design documents from `kitty-specs/quick-win-remediation-01M72855/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/`: `meta.json` records `contracts: none`)

**Tests**: Required. The charter's ATDD-first rule (C-011) and NFR-003 make every WP start with a failing test committed before its fix.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into five work packages with non-overlapping owned files. WP01–WP04 are independent; WP05 (the Mission 058 data repair) depends on WP02.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`. Keep deep implementation detail in the prompt files.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`; changelog fragments in `docs/changelog/unreleased/`.

---

## Work Package WP01: Status event log — line framing, writer bytes, session sanitising (Priority: P1)

**Goal**: Every `status/store.py` reader ends rows only at real line breaks and reports JSON-limit failures with its documented error; the writer refuses non-finite numbers and writes LF on every OS; the sanitiser drops a mixed naive/aware session pair instead of raising (#7439, #7441, #7440).
**Independent Test**: `tests/status/test_store_line_framing.py` and `tests/specify_cli/events/test_sanitizer.py` red on the base, green after.
**Prompt**: `tasks/WP01-status-event-log-framing-and-writer.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-015, FR-016, NFR-002, NFR-003, NFR-004, C-001, C-003, C-004, SC-001, SC-002
**Model tier**: Claude (`claude-opus-5-5`)

### Included Subtasks

T001 Red-first tests for row framing and JSON-limit errors across the store readers (#7439) in new `tests/status/test_store_line_framing.py` (WP01)
T002 Shared line splitter + decode helper in `src/specify_cli/status/store.py`, wired into the five reader sites (WP01)
T003 Red-first tests for the writer byte rule: NaN/Infinity refusal, LF temp-file newline, events parity pin (#7441) (WP01)
T004 `serialize_event_line` `allow_nan=False` → `StoreError`; `append_raw_rows_atomic` temp file `newline="\n"` (WP01)
T005 Red-first sanitiser tests then fix for the mixed naive/aware session pair (#7440) in `src/specify_cli/events/sanitizer.py` (WP01)
T006 Changelog fragments for #7439, #7440, #7441; targeted validation; tracer entries (WP01)

### Implementation Notes

- Commit order: T001 (red) → T002 (fix) → T003 (red) → T004 (fix) → T005 test commit → T005 fix commit → T006.
- No change to blank-line or `strip()` rules, partition rules, or the torn-tail repair.

### Parallel Opportunities

- T005 (sanitiser) is file-independent of T001–T004 and could run alongside them.

### Dependencies

- None.

### Risks & Mitigations

- Git-text readers are not newline-translated → the splitter must treat `\r\n` as one break. Lone-CR divergence from the Java decoder is accepted and recorded.
- A historical NaN row now refuses on `doctor mission-state --fix` re-serialisation → say so in the #7441 fragment.

---

## Work Package WP02: WP task-file facts — one locator, list-only roster (Priority: P1) 🎯 MVP

**Goal**: One core locator (case-insensitive id, regular files only) serves the dependency guard, the subtask roster and the WP view; the roster accepts only task ids and refuses anything else with a remedy; the archive gate gains the dated sanctioned correction for Mission 058 (#7443, #7442).
**Independent Test**: lowercase `wp02-x.md` dependencies are honoured; a directory match fails closed; a map-shaped roster refuses naming the file and the list form; the WP view shows an empty authored list instead of crashing; mark-status refuses Mission-wide with the remedy.
**Prompt**: `tasks/WP02-wp-task-file-locator-and-roster.md`
**Requirement Refs**: FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-015, FR-016, NFR-002, NFR-003, NFR-004, C-001, C-005, C-007, SC-002, SC-003
**Model tier**: Claude (`claude-opus-5-5`)

### Included Subtasks

T007 Red-first locator tests: lowercase file dependencies, directory match, README exclusion, across dependency guard, roster and view (#7443) (WP02)
T008 New `src/specify_cli/core/wp_task_files.py` (one public matcher + separator) with focused unit tests (WP02)
T009 Rewire `status/emit.py` `_match_wp_files`, `core/subtask_rows._locate_wp_file` and `status/wp_view._locate_wp_metadata` to the shared matcher; non-regular matches fail closed (WP02)
T010 Red-first roster tests: map, list, float, date, bool, None, oversized int refuse; str/int accepted; view tolerant; mark-status Mission-wide refusal (#7442) (WP02)
T011 One roster-entry rule in `normalize_authored_subtask_roster` with a typed `SubtaskRosterResolutionError` subclass; `authored_subtask_roster` adds the file name; `_authored_group` catches it (WP02)
T012 Dated `_OPERATOR_SANCTIONED_CORRECTIONS` entry for the six Mission 058 WP files in `tests/architectural/test_archive_root_byte_identical.py` (WP02)
T013 Changelog fragments for #7442, #7443; targeted validation incl. corpus reader and named gates; tracer entries (WP02)

### Implementation Notes

- Commit order: T007 (red) → T008 + T009 (fix) → T010 (red) → T011 (fix) → T012 → T013.
- `emit.py`: touch only `_match_wp_files` (`:591-607`) and its two call sites (`:384`, `:618`); open PR #7490 edits other hunks of the same file.

### Parallel Opportunities

- None inside the WP (shared files). The WP runs in parallel with WP01, WP03, WP04.

### Dependencies

- None.

### Risks & Mitigations

- Mission 058 rosters refuse once T011 lands until WP05 runs → WP05 follows immediately; `test_dogfood_corpus_backfilled.py` is run here and in WP05.
- Dead-symbol / layer gates → the new matcher has three `src` callers; core imports no status module at module scope.

---

## Work Package WP03: Mission metadata loads a BOM-prefixed meta.json (Priority: P2)

**Goal**: `load_meta` and `parse_meta_file` decode with `utf-8-sig` by default, so a BOM-prefixed `meta.json` reads like the same file without one; the kernel decoder and the strict loader's BOM-intolerant mode are unchanged (#7445, Option A).
**Independent Test**: BOM-prefixed `meta.json` returns the mapping through `load_meta` (raise and `none` modes), `parse_meta_file`, and the status emit Mission-id lookup; `load_meta_strict(bom_tolerant=False)` still rejects it.
**Prompt**: `tasks/WP03-load-meta-accepts-bom.md`
**Requirement Refs**: FR-013, FR-015, FR-016, NFR-002, NFR-003, NFR-004, C-002, C-004, SC-005
**Model tier**: cheaper (`opencode` / `glm-5.3`)

### Included Subtasks

T014 Red-first BOM tests in `tests/specify_cli/test_mission_metadata.py` (reader + one symptom-level caller) (WP03)
T015 Change the two encoding defaults to `_UTF8_SIG` and refresh the three stale docstring/comment spots in `src/specify_cli/mission_metadata.py` (WP03)
T016 Changelog fragment for #7445; targeted validation incl. meta-decode gates; tracer entry (WP03)

### Implementation Notes

- No new `json.loads` site and no new `load_meta` call site (census gates).

### Parallel Opportunities

- Independent of every other WP.

### Dependencies

- None.

### Risks & Mitigations

- Residual BOM-rejecting readers (planning_commit, ref_advance, mission_finalize, charter activation) stay as documented follow-up; do not widen.

---

## Work Package WP04: Glossary conflict listing in one pass (Priority: P3)

**Goal**: `_extract_conflicts_from_events` builds its known-id set once and adds each appended id, removing the quadratic rescan without changing output or de-duplication (#7463).
**Independent Test**: repeated resolved-only events of one id yield one conflict; n requested + n resolved distinct ids yield 2n in event order; before/after timings recorded for the PR.
**Prompt**: `tasks/WP04-glossary-conflicts-single-pass.md`
**Requirement Refs**: FR-014, FR-015, FR-016, NFR-001, NFR-002, NFR-004, C-006, SC-006
**Model tier**: cheaper (`opencode` / `glm-5.3`)

### Included Subtasks

T017 Characterisation + scale tests in `tests/agent/cli/commands/test_glossary.py` `TestExtractConflicts` (green before and after; documented FR-014 exception to red-first) (WP04)
T018 Hoist `existing_ids` above the resolved-event loop and add each appended id in `src/specify_cli/cli/commands/glossary.py` (WP04)
T019 Before/after timing table (n = 500, 1000, 2000, 4000) recorded in the WP history for the PR body; changelog fragment for #7463; validation (WP04)

### Implementation Notes

- No change to filters, ordering, record shape, or the existing `# noqa: C901`.

### Parallel Opportunities

- Independent of every other WP.

### Dependencies

- None.

### Risks & Mitigations

- Hoist without the add changes de-duplication → T017's characterisation test pins it.

---

## Work Package WP05: Repair Mission 058 subtask rosters (Priority: P1)

**Goal**: Rewrite the 28 map-shaped `subtasks:` entries in Mission 058's six WP files as plain task ids in the same order, changing no other byte, under the sanctioned correction WP02 adds (#7442 repair).
**Independent Test**: on the WP02 tip `authored_subtask_roster` refuses all six 058 WPs; after this WP it returns `T001…T028` in order, the archive gate and corpus reader pass, and the diff shows only the 28 entry rewrites.
**Prompt**: `tasks/WP05-repair-mission-058-subtask-rosters.md`
**Requirement Refs**: FR-012, NFR-005, C-005, C-008, SC-004
**Model tier**: cheaper (`opencode` / `glm-5.3`)

### Included Subtasks

T020 Baseline evidence: on the WP02 tip, the roster read of each 058 WP refuses (the red check for FR-012) (WP05)
T021 Line-wise rewrite of the 28 entries across `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP01…WP06` (WP05)
T022 Verification: roster reads return the ids in order, diff is byte-minimal, archive gate + corpus reader + prose ratchet pass; tracer entry (WP05)

### Implementation Notes

- Edit line-wise; never round-trip the files through a YAML writer.

### Parallel Opportunities

- None (single concern).

### Dependencies

- Depends on WP02 (the roster rule and the sanctioned-correction entry).

### Risks & Mitigations

- Archive gate needs a fetched `main` ref; run `git fetch origin main` first if the gate reports no merge base.

---

## Dependency & Execution Summary

- **Sequence**: WP01, WP02, WP03, WP04 in parallel; WP05 after WP02.
- **Parallelization**: four independent code WPs (disjoint files); finalize-tasks settles topology by size (expected `lanes_with_coord`).
- **MVP Scope**: WP02 + WP05 (the P2 issue that permanently blocks the `for_review` gate and the dependency-gate bypass), then WP01.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001, FR-002, FR-003, FR-004, FR-005 | WP01 |
| FR-006, FR-007, FR-008, FR-009, FR-010, FR-011 | WP02 |
| FR-012 | WP05 |
| FR-013 | WP03 |
| FR-014 | WP04 |
| FR-015, FR-016 | WP01, WP02, WP03, WP04 |
| NFR-001 | WP04 |
| NFR-002, NFR-004 | WP01, WP02, WP03, WP04 |
| NFR-003 | WP01, WP02, WP03 |
| NFR-005 | WP05 |
| C-001 | WP01, WP02 |
| C-002 | WP03 |
| C-003 | WP01 |
| C-004 | WP01, WP03 |
| C-005 | WP02, WP05 |
| C-006 | WP04 |
| C-007 | WP02 |
| C-008 | WP05 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red tests: row framing + JSON-limit errors | WP01 | P1 | No |
| T002 | Shared splitter + decode helper in store.py | WP01 | P1 | No |
| T003 | Red tests: writer byte rule | WP01 | P1 | No |
| T004 | allow_nan=False + LF temp file | WP01 | P1 | No |
| T005 | Sanitiser mixed session pair (test then fix) | WP01 | P3 | Yes |
| T006 | WP01 fragments + validation | WP01 | P1 | No |
| T007 | Red tests: shared locator behaviour | WP02 | P1 | No |
| T008 | New core/wp_task_files.py + unit tests | WP02 | P1 | No |
| T009 | Rewire emit, subtask_rows, wp_view | WP02 | P1 | No |
| T010 | Red tests: list-only roster | WP02 | P1 | No |
| T011 | Roster-entry rule + typed error + view catch | WP02 | P1 | No |
| T012 | Sanctioned archive-correction entry | WP02 | P1 | No |
| T013 | WP02 fragments + validation | WP02 | P1 | No |
| T014 | Red tests: BOM meta.json | WP03 | P2 | No |
| T015 | utf-8-sig defaults + docstrings | WP03 | P2 | No |
| T016 | WP03 fragment + validation | WP03 | P2 | No |
| T017 | Characterisation + scale tests | WP04 | P3 | No |
| T018 | Hoist + add known-id set | WP04 | P3 | No |
| T019 | Timings + fragment + validation | WP04 | P3 | No |
| T020 | Baseline refusal evidence for 058 | WP05 | P1 | No |
| T021 | Rewrite 28 roster entries | WP05 | P1 | No |
| T022 | Verify repair | WP05 | P1 | No |
