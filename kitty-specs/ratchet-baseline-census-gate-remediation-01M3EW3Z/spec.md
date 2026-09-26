# Mission Specification: Ratchet, baseline & census gate remediation

**Mission Branch**: `claude/spec-kitty-remediation-wfje22` (planning base and merge target)
**Created**: 2026-09-26
**Status**: Draft
**Input**: Operator request: "Load charter, review #5104. Dispatch research and grounding squad. Then start a spec-kitty mission to remediate these issues."
**Epic**: #5104 (children #2631, #2972, #3011, #3026, #5085)
**Grounding evidence**: `research/grounding-3011.md`, `research/grounding-3026.md`, `research/grounding-5085.md`, `research/grounding-2631_2972.md` (read-only squad, HEAD `34f19c6f`)
**Decision Moments**: DM-01M3EW4J8E (#3011 → retire), DM-01M3EW4PB6 (#3026 → retire dead machinery), DM-01M3EW4T8P (#5085 → full migration in scope), DM-01M3EW4YH9 (#2631 → act now, split bridge parity, defer oracle)

## Intent Summary (operator-confirmed 2026-09-26)

- **Primary actor**: a maintainer or agent whose change touches `tests/architectural/` gates or the parity/equivalence suites.
- **Trigger**: a routine, unrelated change (a line shift, a new test file, a refactor) turns a gate red, or a gate silently checks nothing, or an agent is pointed at scaffolding whose enforcing test was deleted.
- **Desired outcome**: every ratchet, allowlist and census gate in scope either measures the property it claims and can demonstrably fail, or is deliberately retired with its residue removed.
- **Invariant**: no behavioural or negative invariant is lost; every retained ban is non-vacuous (concrete floor + self-mutation test); baselines only shrink.
- **Out of scope**: retiring the `test_bridge_parity` two-run oracle (blocked on #2633), the #2633 delegate deletions themselves, and a wholesale sweep of the #2972 census.

## Grounding summary

The squad found the issues' premises partly stale on HEAD:

| Issue | Claim in issue | State on HEAD |
|-------|----------------|---------------|
| #3011 | `rekey_inventory.py` corrupts adjudicated rows; gate `test_surface_resolution_audit.py` holds | Converter defect live, but the gate was deleted (mission 01KZME3P WP13); `audit.py` fails on HEAD (8 missing + 8 ghost rows); nothing runs `--check` |
| #3026 | Inert-slot cap covers a token, not the unfireable-owner property; gate holds | The enforcing tests (unassigned cap, masking cap, anti-weasel, owner-existence) were removed by #3285; caps and their `_baselines.yaml` keys are read by nothing |
| #5085 | Positional-anchor ban misses `(Path, int)` allowlists outside substrate-importing files | Confirmed and wider: three blind spots (import gate, `Path(...)` entries, `rel:lineno:op` keys) hide 88 line-pinned entries; 2 of 6 `_KNOWN_JOIN_ALLOWLIST` entries are already dead |
| #2631 | Audit the parity/equivalence family | 45 modules swept; 4 net-negative suites (vacuous import bans on a deleted directory, retired-sync scaffold, private-function patching, stale xfails); `test_contract_registry_parity` already deleted; `test_bridge_parity` now also holds 17 P0 acceptance tests |
| #2972 | Census, "do not mission" | Disposition reaffirmed; its S8997 routing target #1842 is closed |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Line drift never turns an allowlist gate red (Priority: P1)

A maintainer inserts or removes lines in a source file that an architectural allowlist exempts. Today the gate goes red (or, worse, a new violation lands on the pinned line and passes silently). After this mission, every allowlist in `tests/architectural/` identifies its exemptions by content, and the positional-anchor ban refuses any new line-pinned entry anywhere in that tree.

**Why this priority**: it is the recurring friction reported in 8 missions (#5085) and the only one of the five with an active false-negative risk (dead entries that would bless a new violation).

**Independent Test**: insert a blank line above an exempted call site; every gate stays green. Add a `(Path("x.py"), 12)` entry or a `"x.py:12:op"` key to any gate module; the ban fails and names it.

**Acceptance Scenarios**:

1. **Given** the widened ban, **When** it runs on HEAD before migration, **Then** it reports all 88 line-pinned entries (RED-first).
2. **Given** all entries migrated, **When** a blank line is inserted above any exempted site, **Then** the owning gate stays green.
3. **Given** a migrated allowlist, **When** an exempted construct is deleted from source, **Then** a stale-entry check fails and names the orphaned exemption.
4. **Given** a new module under `tests/architectural/` that declares a line-pinned allowlist without importing the ratchet substrate, **When** the ban runs, **Then** it fails.

---

### User Story 2 - No agent is pointed at a gate that no longer exists (Priority: P1)

An agent is told to "use the canonical converter" for the surface-resolution inventory, or reads an inert-slot cap comment that names a test. Today both lead to dead or destructive paths. After this mission, the orphaned surface-resolution converter, inventory and audit entry point, and the dead inert-slot caps and predicates, are removed, and the ratchet refuses nested baseline keys that no test reads.

**Why this priority**: #3011 is P1 (data-destroying trap); dead baseline keys are the defect class that let #3026's caps rot unnoticed.

**Independent Test**: grep the repo for the retired converter, inventory and cap symbols; none remain outside historical mission artefacts. Add an unread nested key to `_baselines.yaml`; the ratchet fails.

**Acceptance Scenarios**:

1. **Given** the retirement, **When** `test_single_mission_surface_resolver.py` runs, **Then** it still passes (the scanner functions it uses are kept).
2. **Given** the retirement, **When** any doc, README or docstring is searched for instructions to run the converter, **Then** none remain.
3. **Given** `_baselines.yaml` contains a nested key that no test reads, **When** the ratchet runs, **Then** it fails and names the key (RED-first on HEAD: `unassigned_entries`, `masking_suppressions`).
4. **Given** the inert-slot retirement, **When** `test_no_inert_schema_slots.py` runs, **Then** its remaining live checks still pass.

---

### User Story 3 - Parity suites only pin behaviour (Priority: P2)

A maintainer refactors code covered by a parity/equivalence suite. Today some suites can never fail (they scan a deleted directory), some pin private names, and some co-change with every refactor. After this mission, each suite in the #2631 sweep has a recorded keep/convert/retire verdict, the confirmed net-negatives are converted or retired, and `test_bridge_parity` is split so its P0 acceptance tests stand alone.

**Why this priority**: lower frequency than US1; value is removing false confidence and churn.

**Independent Test**: each converted ban carries a minimum-file-count floor and fails when pointed at an empty directory; the verdict catalog lists every swept module.

**Acceptance Scenarios**:

1. **Given** the converted runtime-parity import bans, **When** their scan target is empty or missing, **Then** they fail rather than pass vacuously.
2. **Given** the retired status-parity scaffold, **When** the status test directory runs, **Then** the relocated determinism and transition-matrix checks still run in their owning test modules.
3. **Given** the split, **When** the P0 acceptance tests for #4980/#4975 run, **Then** they run without the two-run oracle's setup.
4. **Given** the verdict catalog, **When** a reviewer checks it, **Then** each swept module has a verdict with churn evidence and rationale.

---

### Edge Cases

- A census key whose operation appears more than once in the same function: content identity must still be unique (qualname + token + occurrence), or the entry is rejected at load.
- A migrated exemption whose target is renamed rather than deleted: the stale-entry check fails and names it (no silent re-bind).
- An allowlist legitimately keyed by line inside a YAML census data file: explicitly enumerated in the ban's exemption list with a reason, or migrated (decided in plan).
- The #3206 kernel exemptions move while #3206 is open: migration is content-keyed, so it is order-independent with #3206.
- A parity test retired as scaffold actually guarded a live invariant: the invariant must be shown to live elsewhere (named test) before retirement.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Widen positional-anchor ban scope | As a maintainer, I want the positional-anchor ban to inspect every module-level allowlist under `tests/architectural/` regardless of what it imports, so that line-pinned allowlists cannot evade it (#5085). | High | Open |
| FR-002 | Detect all line-pin shapes | As a maintainer, I want the ban to flag `(path, int)` entries where the path is a string or a `Path(...)` call, and string keys of the form `path:line[:suffix]`, so that the three known blind spots are closed (#5085). | High | Open |
| FR-003 | Enumerated, reasoned exemptions only | As a reviewer, I want any remaining line-keyed construct to be exempted only by an explicit symbol-keyed exemption list with a reason per entry, so that exemptions are visible and shrink-only (#5085). | High | Open |
| FR-004 | Migrate join allowlist | As a maintainer, I want `_KNOWN_JOIN_ALLOWLIST` migrated to content-identified entries and its 2 dead entries removed, so that it tolerates line drift and cannot bless a new join (#5085). | High | Open |
| FR-005 | Migrate kernel exemptions | As a maintainer, I want the 2 `_PRE_EXISTING_EXEMPTIONS` entries in the kernel/doctrine import gate migrated to content identity, coordinated with #3206 (#5085). | Medium | Open |
| FR-006 | Migrate census keys | As a maintainer, I want the 80 `path:line:op` keys in the destructive-op, mutation and overwrite gates re-keyed to content identity through the census helper, so that no architectural allowlist is line-pinned (#5085, operator decision DM-01M3EW4T8P). | High | Open |
| FR-007 | Stale-entry detection | As a maintainer, I want every migrated allowlist to fail when an entry no longer resolves to a live construct, so that dead exemptions cannot accumulate (#5085). | High | Open |
| FR-008 | Retire surface-resolution converter | As an agent, I want `rekey_inventory.py`, `inventory.md` and `audit.main()` removed while the scanner functions used by live tests are kept, so that no one can run a converter that destroys adjudicated rows (#3011, DM-01M3EW4J8E). | High | Open |
| FR-009 | Remove converter instructions | As an agent, I want every doc, README, docstring and formatter exclusion that references the retired converter or inventory removed or updated, so that no instruction points at a deleted tool (#3011). | Medium | Open |
| FR-010 | Retire dead inert-slot caps | As a maintainer, I want the unread inert-slot caps, owner predicates and their `_baselines.yaml` keys removed, so that the module no longer advertises enforcement it does not perform (#3026, DM-01M3EW4PB6). | Medium | Open |
| FR-011 | Refuse unread baseline keys | As a maintainer, I want the charter ratchet to fail when `_baselines.yaml` carries a nested key that no test reads, so that a gate's deletion cannot leave a silently dead cap again (#3026 defect class). | High | Open |
| FR-012 | Non-vacuous runtime-parity bans | As a maintainer, I want the runtime-parity import bans to scan the live runtime package with a minimum-file floor, and the positive shape pins on public/private surface retired, so that the bans can fail (#2631). | Medium | Open |
| FR-013 | Retire retired-subsystem parity scaffold | As a maintainer, I want the sync/backport and tombstone tests in the status parity suite retired, and its determinism and transition-matrix checks relocated to their owning test modules, so that nothing behavioural is lost (#2631). | Medium | Open |
| FR-014 | Convert private-patching context parity | As a maintainer, I want the charter context parity suite converted from patching private functions to an on-disk fixture, so that it stops co-changing with every refactor (#2631). | Medium | Open |
| FR-015 | Clean stale parity residue | As a maintainer, I want leftover expected-failure markers, stale docstrings, name-only checks and self-referential docstring tests removed from the kept parity suites named in the grounding report (#2631). | Low | Open |
| FR-016 | Split bridge parity suite | As a maintainer, I want the P0 acceptance tests separated from the two-run oracle in the bridge parity suite, so that the P0 tests stay and the oracle can later be retired independently (#2631). | Medium | Open |
| FR-017 | Record parity verdicts | As a reviewer, I want a keep/convert/retire verdict with churn evidence for every module in the #2631 sweep recorded in the mission's design-decisions tracer, extending the #2620 catalog format (#2631). | Medium | Open |
| FR-018 | Follow-up and routing issues | As the operator, I want follow-up issues filed for (a) retiring the bridge-parity oracle after #2633, (b) the silent `model` suppression in the agent-profile schema left unguarded by #3285, and (c) routing the #2972 S8997 subset now that #1842 is closed. | Medium | Open |
| FR-019 | Census campsite and matrix | As the operator, I want #2972 findings cleaned only in test files this mission already touches, and #2972 recorded in the issue matrix as campsite/deferred (#2972). | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Drift tolerance | Inserting one blank line at the top of each file referenced by a migrated allowlist changes the outcome of 0 gates. | Reliability | High | Open |
| NFR-002 | Gate non-vacuity | Every new or widened ban has a self-mutation test that plants a violation and asserts failure, and a concrete non-zero floor on the number of items inspected. 100% of retained bans in scope satisfy both. | Reliability | High | Open |
| NFR-003 | Shrink-only baselines | No `_baselines.yaml` value in scope increases; the net count of exemption entries in scope decreases by at least 2 (the dead join entries). | Maintainability | High | Open |
| NFR-004 | Gate runtime | The widened positional-anchor ban completes in under 10 seconds on the full `tests/architectural/` tree. | Performance | Medium | Open |
| NFR-005 | Quality gates | Changed files pass `ruff check`, `ruff format --check` and `mypy` with zero new suppressions; functions stay at complexity ≤ 15. | Maintainability | High | Open |
| NFR-006 | No lost invariant | For every retired test, a named surviving test (or an explicit "scaffold, no invariant" verdict) is recorded; 0 retirements without one. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | ATDD red-first | Each WP lands a failing-first acceptance test as its first commit, RED on the planning base and GREEN at WP completion (charter C-011). | Technical | High | Open |
| C-002 | Oracle retirement deferred | The bridge-parity two-run oracle is not retired or relaxed in this mission; it waits for #2633. | Technical | High | Open |
| C-003 | Census not missioned | #2972 is consumed only as campsite work on touched files; no directory-wide sweep. | Business | Medium | Open |
| C-004 | Canonical substrate | Migrations use the existing content-identity substrate (`composite_key` / `ContentDescriptor`); no second identity mechanism is introduced. | Technical | High | Open |
| C-005 | Tests only | Changes are confined to `tests/`, test helpers, docs, tooling config and mission artefacts; no `src/` behaviour changes (the surface-resolution audit package lives under `tests/architectural/`). | Technical | High | Open |
| C-006 | Branch and publication | Work lands on `claude/spec-kitty-remediation-wfje22`; publication is by PR to `main`; implementers do not merge. | Business | High | Open |

### Key Entities

- **Allowlist / exemption entry**: a module-level record that exempts a specific source construct from a gate; identified by content (path + qualname + token), never by line.
- **Census key**: an entry in a destructive-op, mutation or overwrite census recording a known pre-existing operation site.
- **Baseline key**: a numeric ceiling in `tests/architectural/_baselines.yaml` that a gate reads and may only shrink.
- **Parity suite verdict**: keep / convert / retire, with discriminator class (behavioural invariant vs positive shape), churn evidence and rationale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 line-pinned allowlist entries remain under `tests/architectural/` outside the enumerated exemption list (down from 88 found by the widened ban).
- **SC-002**: a one-line insertion above any exempted site turns 0 gates red.
- **SC-003**: 0 references to the retired converter, inventory or inert-slot caps remain in live docs, tests or source.
- **SC-004**: 0 `_baselines.yaml` keys are unread by a test.
- **SC-005**: 100% of modules in the #2631 sweep have a recorded verdict; 0 parity bans pass when their scan target is empty.
- **SC-006**: all five child issues of #5104 have an issue-matrix row, and follow-up issues exist for the three items in FR-018.

## Assumptions and dependencies

- #3206 stays open during the mission; FR-005 is content-keyed and therefore order-independent with it.
- #2633 does not land during the mission; if it does, C-002 is revisited at the next planning point-cut rather than silently expanded.
- The scanner functions in the surface-resolution audit package remain in use by `test_single_mission_surface_resolver.py`, `test_no_worktree_name_guess.py` and `_ratchet_keys.py`; planning confirms the exact kept surface.
