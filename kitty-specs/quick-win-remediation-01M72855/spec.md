# Mission Specification: Quick-win remediation

**Mission Branch**: `kitty/mission-quick-win-remediation-01M72855` (lands on `fix/quick-win-remediation`, then a pull request to `main`)
**Created**: 2026-11-10
**Status**: Draft
**Input**: Quick-win remediation bundling #7439, #7440, #7441, #7442 (with the Mission 058 data repair), #7443, #7445 and #7463. Operator decisions of 2026-11-10 are binding and recorded as resolved Decision Moments.

## Intent Summary

Operators and agents who run Spec Kitty's status, planning and glossary commands are hitting seven small, separately reported defects. Each one makes a command fail on valid input, refuse a Mission it should read, crash, write a log the events contract forbids, or slow down sharply on large logs. This mission fixes each with the smallest change that brings core in line with the rulings the `spec-kitty-events` contract already records (line framing, the byte rule, R25, R26, R29, decision 9 and decision 16), so no contract change is needed. One in-repo Mission (058) stores its subtasks in a shape the stricter rule refuses; its data is repaired once, in the same pull request.

- **Primary actor**: an operator or agent running `spec-kitty` status, task, planning or glossary commands against a Mission.
- **Trigger**: a Mission whose files contain one of the reported inputs (a row with U+2028 inside a string, a BOM-prefixed `meta.json`, a lowercase `wp02-*.md` task file, a map-shaped subtask entry, a non-finite number in an event, a mixed naive/aware session pair, or a long glossary event log).
- **Desired outcome**: valid input is read; invalid input is refused with the documented error type and a message that names the file and the remedy; nothing is half-written.
- **Invariant**: every change is strictly widening for valid input, or fail-closed and legible for invalid input. No reader that accepts input today stops accepting the same valid input.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Status commands read every valid event-log row (Priority: P1)

An operator runs `spec-kitty agent tasks status` on a Mission whose `status.events.jsonl` holds a valid row with U+2028, U+2029, U+0085, VT or FF inside a JSON string. Today the whole Mission is unreadable ("Invalid JSON") and the lenient reader drops the row silently. After the fix every status reader reads the row as one event. A row that breaks a JSON limit (an integer of more than 4,300 digits, or very deep nesting) is refused with the documented store error instead of escaping as a raw Python error.

**Why this priority**: one such row blocks every status command for the Mission.

**Independent Test**: write a log with such a row and read it through each status reader; write a log with an oversized integer and a deeply nested value and check the error type.

**Acceptance Scenarios**:

1. **Given** a log row whose `reason` contains U+2028, **When** any status reader reads the log, **Then** it returns one event with the string intact, and a second, ordinary row in the same log is also returned.
2. **Given** rows separated by CRLF, or by a lone CR, **When** the log is read, **Then** each row is read once.
3. **Given** a row holding a 4,301-digit integer or 100,000-deep nesting, **When** a strict reader reads it, **Then** it refuses with the store error naming the line; the lenient reader skips that row and keeps the others; the scratch-log seeding refuses with its documented error type.

---

### User Story 2 - The event log writer emits only contract bytes (Priority: P2)

An agent records a status event whose evidence holds a non-finite number, or runs on Windows. Today the writer emits `NaN`/`Infinity` (not JSON) and, on Windows, rewrites the whole log with CRLF while reporting LF bytes to observers. After the fix a non-finite number is refused with the store error and nothing is written, and the log is LF-only on every operating system.

**Why this priority**: a log written this way is refused by the events write service and drifts between platforms.

**Independent Test**: append an event carrying `NaN`; check that the append refuses and the file is unchanged. Inspect how the writer opens its temporary file and the bytes it writes.

**Acceptance Scenarios**:

1. **Given** an event with `evidence = {"x": Infinity}`, **When** it is appended, **Then** the append refuses with the store error naming the event and the log file is byte-identical to before.
2. **Given** any append, **When** the temporary file is opened, **Then** it is opened with LF line endings, and the written bytes contain no CRLF.
3. **Given** an event of JSON-native values, **When** it is serialised, **Then** the line equals the `spec-kitty-events` byte rule for the same record.

---

### User Story 3 - Event sanitising never crashes on session timestamps (Priority: P3)

An agent writes a status or decision event with a naive `session_started_at` and an aware `session_ended_at` (or the reverse). Today the sanitiser raises `TypeError`: the status write aborts and the decision event is lost with a warning. After the fix both timestamps are dropped and no duration is emitted, as the sanitiser's documentation already promises for malformed timestamps.

**Why this priority**: rare in practice, but it loses data silently on the decision path.

**Independent Test**: sanitise events with each mixed pairing and with two naive timestamps.

**Acceptance Scenarios**:

1. **Given** a naive start and an aware end (and the reverse), **When** the event is sanitised, **Then** no exception is raised, both session timestamps are removed and no duration is present.
2. **Given** two naive timestamps, **When** the event is sanitised, **Then** the duration is still computed (unchanged).

---

### User Story 4 - One rule finds a work package's task file (Priority: P1)

An operator names a task file `tasks/wp02-x.md` (lowercase). Today the subtask roster finds it but the dependency guard does not, so the dependency guard reads "no dependencies" and the WP can be claimed past its dependencies. A directory named like a task file is taken as the WP's file. After the fix the dependency guard, the subtask roster and the WP view use one locator with one case rule, and a match that is not a regular file makes the gates refuse.

**Why this priority**: the case split silently bypasses the dependency gate.

**Independent Test**: create a lowercase task file declaring a dependency and try to claim the WP; create a directory named like a task file and read the roster.

**Acceptance Scenarios**:

1. **Given** `tasks/wp02-x.md` declaring a dependency on an unfinished WP, **When** WP02 is moved to `claimed`, **Then** the dependency guard refuses, as it does for `WP02-x.md`.
2. **Given** a directory `tasks/WP03-dir.md`, **When** WP03's roster or dependencies are read, **Then** the read refuses as unresolvable and names the path; the WP view shows no task file.
3. **Given** `tasks/README.md` or `tasks/readme.md`, **When** any WP is located, **Then** the README is never matched.

---

### User Story 5 - A map-shaped subtask entry is refused with a remedy (Priority: P1)

An operator authors `subtasks:` as a list of maps (`- id: T001`, `title: …`). Today each map is turned into its text form, so the `for_review` gate can never match a checked subtask and the WP is blocked permanently with no explanation. After the fix the roster accepts only task ids (strings or integers), and any other entry is refused with an error naming the WP file and the expected list form. Mission 058, the one in-repo Mission with map entries, is repaired in the same pull request.

**Why this priority**: P2 issue; a permanently blocked gate with no explanation.

**Independent Test**: read the roster of a WP file with a map entry, a boolean, a float, a date, a null and an oversized integer; read the same WP through the WP view; run `mark-status` in that Mission.

**Acceptance Scenarios**:

1. **Given** a WP whose `subtasks:` holds a map, **When** the `for_review` gate or the roster is read, **Then** it refuses with a subtask-roster error that names the WP file, the entry position, and the expected form (e.g. `- T001`).
2. **Given** an entry that is a boolean, float, date, null or list, **When** the roster is read, **Then** it refuses the same way; **given** an integer longer than 4,300 digits, **Then** it refuses with the same error, not a raw `ValueError`.
3. **Given** entries `T001` and `7`, **When** the roster is read, **Then** they are accepted as before.
4. **Given** a map-shaped WP, **When** the WP view is built for any `agent tasks` command, **Then** it does not crash and shows an empty authored subtask list.
5. **Given** any WP in a Mission has a map-shaped entry, **When** `mark-status` runs for any WP of that Mission, **Then** it refuses for the whole Mission with a message naming the offending file and the remedy, until that file is fixed.
6. **Given** this pull request, **When** Mission 058's six WP files are read, **Then** each `subtasks:` entry is a plain task id in the original order, and every other byte of those files is unchanged.

---

### User Story 6 - A BOM-prefixed meta.json is read like any other (Priority: P2)

An operator's editor saved `meta.json` with a UTF-8 byte-order mark. Today the canonical metadata loader refuses it, and callers that treat a malformed file as "no Mission" make the Mission invisible. After the fix the loader and the metadata-file parser read it like the same file without a BOM.

**Why this priority**: a Mission silently disappears from status and resolution.

**Independent Test**: write a BOM-prefixed `meta.json` and load it through each entry point and through one caller that resolves a Mission id.

**Acceptance Scenarios**:

1. **Given** a BOM-prefixed `meta.json`, **When** it is loaded through the canonical loader (raising and "none on malformed" modes) or the metadata-file parser, **Then** the same mapping is returned as for the file without the BOM.
2. **Given** that file, **When** a status caller resolves the Mission id from it, **Then** the Mission is visible.
3. **Given** the strict loader with BOM tolerance turned off, **When** it reads that file, **Then** it still rejects it (unchanged negative control).

---

### User Story 7 - Glossary conflict listing scales linearly (Priority: P3)

An operator runs `spec-kitty glossary conflicts` on a Mission with thousands of glossary events. Today each resolved event rescans every conflict collected so far, so the time grows with the square of the log. After the fix the listing does one pass with a running set of known conflict ids, and a repeated resolved event still yields one conflict.

**Why this priority**: latency only, with a correctness trap (de-duplication).

**Independent Test**: list conflicts for n requested plus n resolved events with distinct ids, and for repeated resolved events of one id.

**Acceptance Scenarios**:

1. **Given** three resolved-only events with the same conflict id, **When** conflicts are listed, **Then** exactly one conflict is returned (green before and after).
2. **Given** n requested and n resolved-only events with distinct ids, **When** conflicts are listed, **Then** 2n conflicts are returned in event order.

### Edge Cases

- A lone CR inside a log is treated as a row break by core; the Java decoder does not. A lone CR cannot occur inside a valid JSON row, so only a hand-mangled log is affected; this is a known, recorded divergence.
- A log already holding a `NaN` row still reads; a later `doctor mission-state --fix` re-serialisation of that row now refuses (fail-closed, rare; called out in the changelog).
- On Windows, the first append after upgrade rewrites a CRLF log to LF once.
- Case-insensitive matching can turn `WP02-a.md` plus `wp02-b.md` into an ambiguous match; that refuses (correct fail-closed outcome; the repository corpus has none).
- Two naive session timestamps keep their duration; only a mixed pair is dropped.
- Any read-modify-write of a BOM-prefixed `meta.json` writes it back without the BOM.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Rows end only at line breaks | As an operator, I want every status event-log reader in the store module (strict text readers, lenient reader, scratch-log seeding) to end a row only at LF, CRLF or a lone CR, so that a valid row containing U+2028, U+2029, U+0085, VT, FF, FS, GS or RS is read as one event (#7439). | High | Open | [build] | no |
| FR-002 | JSON-limit failures use the documented error | As an operator, I want a row that exceeds the integer-digit limit or the nesting limit to be refused with the store error naming the line by the strict readers, skipped by the lenient reader, and refused with its documented error type by scratch-log seeding, so that no raw `ValueError` or `RecursionError` escapes (#7439). | High | Open | [build] | no |
| FR-003 | Non-finite numbers are refused before writing | As an agent, I want an event carrying NaN or Infinity to be refused with the store error naming the event, with the log file left byte-identical, so that the log never holds non-JSON numbers (#7441). | High | Open | [build] | no |
| FR-004 | LF-only log writes on every OS | As an operator on Windows, I want the event-log writer to write LF line endings, so that the on-disk bytes match the bytes reported to observers and the events contract (#7441). | Medium | Open | [build] | no |
| FR-005 | Mixed session pair is dropped, not raised | As an agent, I want the event sanitiser to drop both session timestamps and emit no duration when one is naive and the other aware, so that the event is written instead of aborted or lost (#7440). | Medium | Open | [build] | no |
| FR-006 | One case-insensitive task-file locator | As an operator, I want the dependency guard, the subtask roster and the WP view to locate a WP's task file with one shared rule (WP id case-insensitive, existing separator tail, README excluded case-insensitively), so that a lowercase task file's dependencies are honoured (#7443). | High | Open | [build] | no |
| FR-007 | Non-regular matches fail closed | As an operator, I want a task-file match that is not a regular file (a directory or dangling link) to make the roster and dependency reads refuse as unresolvable, and the read-only view treat it as no file, so that a directory is never taken as a WP's file (#7443). | Medium | Open | [build] | no |
| FR-008 | Only task ids are roster entries | As an operator, I want a `subtasks:` entry that is not a string or a non-boolean integer to be refused with the subtask-roster error naming the WP file, the entry and the expected list form, so that the `for_review` gate explains the problem instead of blocking forever (#7442). | High | Open | [build] | no |
| FR-009 | Oversized integer entries refuse legibly | As an operator, I want an integer roster entry longer than 4,300 digits to be refused with the subtask-roster error, so that no raw `ValueError` escapes the roster (#7442). | Medium | Open | [build] | no |
| FR-010 | The WP view tolerates a refused roster | As an operator, I want the WP view used by `agent tasks` commands to show an empty authored subtask list for a refused roster, so that unrelated commands keep working (#7442). | High | Open | [build] | no |
| FR-011 | Mission-wide mark-status refusal is legible | As an operator, I want `mark-status` in a Mission holding any refused roster to refuse for that Mission with a message naming the offending file and the remedy, so that the new Mission-wide refusal tells me what to fix (#7442). | Medium | Open | [build] | no |
| FR-012 | Mission 058 roster data repaired | As a maintainer, I want the 28 map-shaped entries in Mission 058's six WP files rewritten as plain task ids in the same order, under a dated operator-sanctioned archive correction, in the same pull request as FR-008, so that the corpus readers stay green (#7442). | High | Open | [build] | no |
| FR-013 | BOM-prefixed meta.json loads | As an operator, I want the canonical metadata loader (all malformed-handling modes) and the metadata-file parser to read a BOM-prefixed `meta.json` exactly like the same file without a BOM, so that the Mission stays visible (#7445). | High | Open | [build] | no |
| FR-014 | Glossary conflict listing is single-pass | As an operator, I want conflict listing to keep one running set of known conflict ids across the resolved-event pass, so that its cost grows linearly with the log while a repeated resolved event still yields one conflict (#7463). | Medium | Open | [build] | yes — the deterministic tests (de-duplication, 2n count) also pass on the base; linearity is evidenced by the before/after timing table in the PR (operator decision: no wall-clock test), and the de-duplication test is the control against a hoist without the add |
| FR-015 | Accepted inputs stay accepted | As an operator, I want every input each touched reader accepts today (LF rows, ordinary strings, two naive or two aware session timestamps, `WP02-*.md` names, string and integer subtask ids, non-BOM `meta.json`, distinct conflict ids) to read exactly as before, so that the fixes only widen or legibly refuse. | High | Open | [ratchet] | yes — each widening/refusal test pairs its case with the accepted input on the same fixture |
| FR-016 | One changelog fragment per issue | As a release reader, I want one `fixed` changelog fragment per addressed issue, so that each user-visible change is announced once. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Linear glossary listing | Conflict listing performs at most one pass building the known-id set per call: for n requested plus n resolved events the result count is exactly 2n for n = 2,000; the before/after timing at n = 500, 1,000, 2,000 and 4,000 is recorded in the PR body (no wall-clock assertion in tests). | Performance | Medium | Open |
| NFR-002 | Zero lint and type debt | Every touched source file passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with 0 findings and 0 new `noqa` or `type: ignore` comments. | Maintainability | High | Open |
| NFR-003 | Red-first evidence | 100% of FR-001…FR-013 have a test committed before the fix that fails on the planning base and passes after the fix (FR-012's red check is a roster read of Mission 058 refusing once the roster rule lands); FR-014 is the documented exception: a characterisation test green before and after, plus the PR timing table. | Reliability | High | Open |
| NFR-004 | Targeted test runs only | Local validation runs only the named test files and named architectural gate files per WP (0 `make test-fast`, `make test-full` or bare-directory runs); commands and pass counts are recorded in the PR. | Reliability | Medium | Open |
| NFR-005 | Byte-preserving data repair | The Mission 058 repair changes 0 bytes outside the 28 `subtasks:` entries (verified by diff: only removed `title:`/`status:` lines and rewritten `- id:` lines). | Data integrity | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Converge on the events contract | Fixes match the existing `spec-kitty-events` rulings (line framing, byte rule, R25, R26, R29, decisions 9 and 16); no events contract change. | Technical | High | Open |
| C-002 | Kernel meta decoder unchanged | The kernel meta decoder and the strict loader's BOM-intolerant mode are not changed (#7445 Option A). | Technical | High | Open |
| C-003 | Store-module scope for line framing | Only the readers inside the status store module change for #7439; other JSONL splitters are a follow-up issue. | Technical | High | Open |
| C-004 | No version bump | No package version change and no `CHANGELOG.md` edit; changelog fragments only. | Business | High | Open |
| C-005 | Same-PR repair | The Mission 058 repair and the sanctioned-correction entry land in the same pull request as the roster refusal; removing the entry after merge is a follow-up named in the PR body. | Process | High | Open |
| C-006 | No wall-clock tests | No test asserts absolute elapsed time (repository flakiness policy). | Technical | Medium | Open |
| C-007 | Layer direction kept | The shared task-file locator lives in the core layer; core gains no module-level import of the status layer. | Technical | High | Open |
| C-008 | Hand-applied data edit | Mission 058's files are edited line-wise, never round-tripped through a YAML writer that may reformat them. | Technical | Medium | Open |

### Key Entities

- **Status event log** (`status.events.jsonl`): append-only JSON Lines file, one event per row, sole authority for WP lane state.
- **Store error**: the documented error type of the status store's readers and writers.
- **Subtask roster**: the ordered list of task ids a WP's frontmatter `subtasks:` declares; read by the `for_review` gate, `mark-status` and the WP view.
- **Subtask-roster error**: the documented error type of roster resolution.
- **WP task file**: `tasks/<WP id><separator>….md` inside a Mission directory.
- **Mission metadata** (`meta.json`): the Mission's identity and branch contract.
- **Glossary conflict record**: one entry per distinct conflict id in `glossary conflicts` output.
- **Sanctioned archive correction**: a dated, operator-approved exception in the archive byte-freeze gate for one historical file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A status event log holding a row with any of the eight non-line-break separators inside a string is read by 100% of the store's readers with 0 rows lost. — [build] · no-op passable: no
- **SC-002**: 0 raw `ValueError`, `RecursionError` or `TypeError` escapes from the event-log readers, the sanitiser or the roster for the reported inputs. — [build] · no-op passable: no
- **SC-003**: A WP named in lowercase is held by its dependencies in 100% of claim attempts, exactly like its uppercase twin. — [build] · no-op passable: no
- **SC-004**: Mission 058 and every other Mission in `kitty-specs/` resolve every WP roster without error after the pull request (0 refusals across the corpus). — [build] · no-op passable: no
- **SC-005**: A BOM-prefixed Mission is visible to status and resolution commands (1 of 1 test Missions found). — [build] · no-op passable: no
- **SC-006**: Glossary conflict listing for 2,000 requested plus 2,000 resolved events returns 4,000 conflicts with growth measured as linear in the PR timing table. — [build] · no-op passable: no
- **SC-007**: All seven issues are closed by the pull request and every follow-up named in Assumptions has a tracker issue. — [build] · no-op passable: no

## Assumptions

- The grounding briefs' reproductions on `main` @ `9518fb7154` hold on this branch (no code moved since).
- Production callers that already catch broad exceptions (event readback verification, the advisory owner lookup in `mark-status`) stay unaffected.
- The `spec-kitty-events` R24 divergence can be retired upstream once this lands; that is noted in the PR, not filed here.
- Open PR #7490 touches different hunks of the status emit module; whichever lands second rebases trivially.
- Follow-ups to file (out of scope here): the other JSONL splitters (git merge driver first); the other WP-file locators with their own case rules; one BOM policy in the kernel meta decoder; removing the Mission 058 sanctioned-correction entry once on `main`.

## Decisions

Resolved Decision Moments (operator decisions of 2026-11-10, delegated answers): scope (`01M7286JB208QGYSMM7XA3ARTK`), line framing (`01M7286MYPH1ASNXT7K7ZSKWSB`), writer bytes (`01M7286QGRFW0HPB55KMSFW3QW`), mixed session pair (`01M7286T39MV64VCB22WPSZS39`), task-file locator (`01M7286WQY7NYXCPNDH0S72M7N`), map-form roster (`01M7286ZAMNZ9S1E0CA4MZNG27`), meta BOM policy (`01M72871WDH3GYMFKTAHRZFJ14`), glossary rescan (`01M72874ECYSTEJVVRZNCD2M7E`).
