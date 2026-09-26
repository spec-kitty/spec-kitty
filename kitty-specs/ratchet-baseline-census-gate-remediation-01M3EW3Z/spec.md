# Mission Specification: Ratchet, baseline & census gate remediation

**Mission Branch**: `claude/spec-kitty-remediation-wfje22` (planning base and merge target)
**Created**: 2026-09-26
**Status**: Draft (revision 2: post-spec squad folded)
**Input**: Operator request: "Load charter, review #5104. Dispatch research and grounding squad. Then start a spec-kitty mission to remediate these issues."
**Epic**: #5104 (children #2631, #2972, #3011, #3026, #5085); folds #3962
**Grounding evidence**: `research/grounding-*.md` (pre-spec squad), `research/postspec-*.md` (post-spec squad), HEAD `6f24a8d7`
**Decision Moments**: DM-01M3EW4J8E (#3011 → retire), DM-01M3EW4PB6 (#3026 → retire dead machinery), DM-01M3EW4T8P (#5085 → full migration in scope), DM-01M3EW4YH9 (#2631 → act now, split bridge parity, defer oracle)

## Intent Summary (operator-confirmed 2026-09-26)

- **Primary actor**: a maintainer or agent whose change touches `tests/architectural/` gates or the parity/equivalence suites.
- **Trigger**: a routine, unrelated change (a line shift, a new test file, a refactor) turns a gate red, or a gate silently checks nothing, or an agent is pointed at scaffolding whose enforcing test was deleted.
- **Desired outcome**: every ratchet, allowlist and census gate in scope either measures the property it claims and can demonstrably fail, or is deliberately retired with its residue removed.
- **Invariant**: no behavioural or negative invariant is lost; every retained ban is non-vacuous (concrete floor + self-mutation through the real scan path); baselines only shrink.
- **Out of scope**: retiring the `test_bridge_parity` two-run oracle (blocked on #2633), the #2633 delegate deletions themselves, and a wholesale sweep of the #2972 census.

## Grounding summary

Verified independently by the pre-spec and post-spec squads on HEAD:

| Issue | Claim in issue | State on HEAD |
|-------|----------------|---------------|
| #3011 | `rekey_inventory.py` corrupts adjudicated rows; gate `test_surface_resolution_audit.py` holds | Converter defect live, but the gate was deleted (mission 01KZME3P WP13); `audit.py` exits 1 (8 missing + 8 ghost rows); nothing runs `--check`. Only `test_single_mission_surface_resolver.py` imports the audit's scanner functions |
| #3026 (+#3962) | Inert-slot cap covers a token, not the unfireable-owner property; gate holds | #3285 removed the enforcing tests; `MAX_UNASSIGNED_ENTRIES`, `MAX_MASKING_SUPPRESSIONS`, `owner_exists`, `owner_is_complete` have no callers; `unassigned_entries` / `masking_suppressions` are the only unread `_baselines.yaml` leaves; 2 baseline rows are already stale (`styleguide-references`, `model`). #3962 asks for the same restore-or-delete call |
| #5085 | Positional-anchor ban misses `(Path, int)` allowlists outside substrate-importing files | Wider: three blind spots (import gate, `Path(...)` entries, `rel:lineno:op` keys) hide 88 line-pinned Python entries (6 join, 2 kernel, 80 census = 22 destructive + 56 mutation + 2 overwrite); 2 join entries are dead (`kernel/paths.py:88`, `runtime/home.py:79`). A further 6 `path:line` pins live in `_exemptions/os-detect-ban-*.txt`. 28 of the 80 census keys collide under (path, qualname, op) |
| #2631 | Audit the parity/equivalence family | 45 modules / 761 tests, all passing; 4 net-negative suites; `test_contract_registry_parity` already deleted; `test_bridge_parity` holds 13–15 P0 acceptance test functions (squads counted differently; node-ID set pinned at implement) next to a two-run oracle whose fixture setup costs ~389 s |
| #2972 | Census, "do not mission" | Disposition reaffirmed; its S8997 routing target #1842 is closed |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Line drift never turns an allowlist gate red (Priority: P1)

A maintainer inserts or removes lines in a source file that an architectural allowlist exempts. Today the gate goes red (or, worse, a new violation lands on a dead pinned line and passes silently). After this mission, every allowlist and exemption file in `tests/architectural/` identifies its exemptions by content, and the positional-anchor ban refuses any new line-pinned entry anywhere in that tree.

**Why this priority**: the recurring friction reported in 8 missions (#5085), and the only item with an active false-negative risk (dead entries that would bless a new violation).

**Independent Test**: insert lines above and inside every exempted site; every gate stays green. Add a line-pinned entry in any supported shape to any gate module or exemption file; the ban fails and names it.

**Acceptance Scenarios**:

1. **Given** the widened ban, **When** it runs on the planning base, **Then** it reports all 94 line-pinned entries (RED-first).
2. **Given** all entries migrated, **When** one line is inserted at the top of each referenced file and one line inside each exempted site's enclosing function, **Then** 0 gates change outcome.
3. **Given** a migrated hand-curated allowlist, **When** an exempted construct is removed from source, **Then** the gate fails and names the orphaned exemption.
4. **Given** a migrated census allowlist, **When** an exempted construct is removed from source, **Then** the gate warns (existing documented census design) and does not fail.
5. **Given** a new module under `tests/architectural/` that declares a line-pinned allowlist without importing the ratchet substrate, **When** the ban runs, **Then** it fails.

---

### User Story 2 - No agent is pointed at a gate that no longer exists (Priority: P1)

An agent is told to "use the canonical converter" for the surface-resolution inventory, or reads an inert-slot cap comment that names a deleted test. Today both lead to dead or destructive paths. After this mission, the orphaned converter, inventory, audit entry point, orphaned gate data files, and the dead inert-slot caps and predicates are removed, and the ratchet refuses baseline leaves that no comparison enforces.

**Why this priority**: #3011 is P1 (data-destroying trap); non-enforcing baseline keys are the defect class that let #3026's caps rot unnoticed.

**Independent Test**: the retired symbols and files are absent from live tests, docs and tooling config; planting a non-enforcing leaf in `_baselines.yaml` fails the ratchet.

**Acceptance Scenarios**:

1. **Given** the retirement, **When** `test_single_mission_surface_resolver.py` runs, **Then** it still passes.
2. **Given** the retirement, **When** docs, READMEs, docstrings and `pyproject.toml` are searched, **Then** no instruction or config entry references the retired converter, inventory, audit entry point or orphaned data files.
3. **Given** `_baselines.yaml` contains a leaf that no comparison enforces, **When** the ratchet runs, **Then** it fails and names the leaf (RED-first on the planning base, which carries 4 non-enforcing leaves: `unassigned_entries`, `masking_suppressions`, `category_1`, `skip_marker_blocks`; WP05 removes the first 2 before WP06 lands, so on WP06's lane base the check names the remaining 2).
4. **Given** any enforced leaf, **When** its value is lowered below the live measurement, **Then** the owning gate fails (proves "enforced" is real).
5. **Given** the inert-slot retirement, **When** `test_no_inert_schema_slots.py` runs, **Then** its remaining live checks pass and the baseline carries no stale rows.

---

### User Story 3 - Parity suites only pin behaviour (Priority: P2)

A maintainer refactors code covered by a parity/equivalence suite. Today some suites can never fail (they scan a deleted directory), some pin private names, and some co-change with every refactor. After this mission, each suite in the #2631 sweep has a recorded verdict, the confirmed net-negatives are converted or retired, and `test_bridge_parity`'s P0 acceptance tests run independently of the oracle.

**Why this priority**: lower frequency than US1; the value is removing false confidence and churn.

**Independent Test**: each converted ban fails when its target is empty or when a violation is planted; the verdict catalog lists every swept module; the P0 bridge tests run without the oracle fixture.

**Acceptance Scenarios**:

1. **Given** the converted runtime-parity import ban, **When** its scan target is empty, missing, or contains a planted violation, **Then** it fails.
2. **Given** the retired status-parity scaffold, **When** the status test directory runs, **Then** the relocated determinism and transition-matrix checks run in their owning test modules.
3. **Given** the split, **When** the bridge P0 acceptance tests are collected and run, **Then** the oracle fixture is not instantiated.
4. **Given** the verdict catalog, **When** a reviewer checks it, **Then** each swept module has a verdict with churn evidence and rationale.

---

### Edge Cases

- **Census key collisions (majority case, not an edge)**: 28 of 80 census keys share (path, qualname, op); identity must add a deterministic within-function ordinal discriminator (`op_ordinal`), or the entry is rejected at load.
- A migrated exemption whose target is renamed rather than deleted: hand-curated allowlists fail and name it; census allowlists warn (no silent re-bind in either case).
- The #3206 kernel exemptions move while #3206 is open: migration is content-keyed and therefore order-independent with #3206.
- A parity test retired as scaffold that actually guarded a live invariant: retirement requires naming the surviving test that enforces the invariant, or a cited reason plus a mutation demonstration that the retired test could not fail.
- Retiring files listed in `pyproject.toml` format exclusions: the exclusion entry must be removed in the same change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Widen positional-anchor ban scope | As a maintainer, I want the positional-anchor ban to inspect every module-level allowlist under `tests/architectural/` and every `_exemptions/*.txt` file regardless of what it imports, so that line-pinned allowlists cannot evade it; existing tests that encode the old scope are inverted, not deleted (#5085). | High | Open |
| FR-002 | Detect all line-pin shapes | As a maintainer, I want the ban to flag `(path, int)` tuples where the path is a string literal, `Path(...)` or a path-join expression, string keys matching `path:line` with any suffix, and `path:line` lines in exemption text files, using a predicate owned by the ban's test module so that no production contract changes (#5085). | High | Open |
| FR-003 | Bounded, reasoned exemptions | As a reviewer, I want any construct the ban cannot migrate to be exempted only by an explicit per-site exemption list pinned by exact-set equality, with a reason per site; at mission acceptance the list is empty (#5085). | High | Open |
| FR-004 | Migrate join allowlist | As a maintainer, I want `_KNOWN_JOIN_ALLOWLIST` migrated to content identity with its 2 dead entries removed (#5085). | High | Open |
| FR-005 | Migrate kernel exemptions | As a maintainer, I want the 2 `_PRE_EXISTING_EXEMPTIONS` entries in the kernel/doctrine import gate migrated to content identity, coordinated with #3206 (#5085). | Medium | Open |
| FR-006 | Migrate census keys | As a maintainer, I want the 80 `path:line:op` keys in the destructive-op (22), mutation (56) and overwrite (2) gates re-keyed to content identity, with an old→new mapping artefact proving the exempted site set is identical before and after (#5085, DM-01M3EW4T8P). | High | Open |
| FR-007 | Stale-entry detection | As a maintainer, I want each migrated hand-curated allowlist (join, kernel, os-detect) to fail when an entry no longer suppresses a live finding, while census allowlists keep their documented warn-on-stale behaviour, so that unrelated source deletions never fail a census gate (#5085, epic "no re-pin toll"). | High | Open |
| FR-008 | Retire surface-resolution converter | As an agent, I want `rekey_inventory.py`, `inventory.md`, `audit.py`'s entry point and the audit data it alone consumes removed, keeping only the scanner functions imported by `test_single_mission_surface_resolver.py` (#3011, DM-01M3EW4J8E). | High | Open |
| FR-009 | Remove converter instructions | As an agent, I want every doc, README, docstring and `pyproject.toml` exclusion that references a retired file removed or updated in the same change (#3011). | Medium | Open |
| FR-010 | Retire dead inert-slot machinery | As a maintainer, I want the uncalled inert-slot caps, owner predicates and their `_baselines.yaml` leaves removed, the baseline's stale rows and unused `owner`/`code_only` data dropped, and `baseline_entries` shrunk accordingly (#3026, #3962, DM-01M3EW4PB6). | Medium | Open |
| FR-011 | Refuse non-enforcing baseline leaves | As a maintainer, I want the charter ratchet to fail when any `_baselines.yaml` leaf is not consumed by a comparison that fails when the live measurement exceeds it; the allowed set is derived from the ratchet's comparison tables, and decorative or advisory leaves (`category_1`, `skip_marker_blocks`) are either made enforcing or removed (#3026 defect class). | High | Open |
| FR-012 | Retire orphaned gate data | As a maintainer, I want gate data files whose consuming gate no longer exists (`resolution_gate_allowlist.yaml`, and any other file plan confirms is unread) removed, with their references (ban exclusion lists, comments) updated (#3011/#3026 defect class). | Medium | Open |
| FR-013 | Non-vacuous runtime-parity bans | As a maintainer, I want the runtime-parity rich/typer import ban to scan the live runtime package with a minimum-file floor and a planted-violation test; the `spec_kitty_runtime` ban (duplicated by `test_shared_package_boundary.py`) and the two surface-shape pins retired; the same vacuous scan of the deleted `src/specify_cli/next` in `tests/contract/test_next_no_unknown_state.py` is fixed (#2631). | Medium | Open |
| FR-014 | Retire retired-subsystem parity scaffold | As a maintainer, I want the sync/backport and tombstone tests in `status/test_parity.py` retired, and its determinism and transition-matrix checks relocated to their owning test modules (#2631). | Medium | Open |
| FR-015 | Convert private-patching context parity | As a maintainer, I want the charter context parity suite converted from patching private functions to an on-disk fixture driven through public entry points and test-only environment knobs (#2631). | Medium | Open |
| FR-016 | Clean stale parity residue | As a maintainer, I want the stale xfail markers, stale docstrings, name-only `missing_seams` check, self-referential docstring test and retired-name tombstone named in `research/grounding-2631_2972.md` removed from kept suites (#2631). | Low | Open |
| FR-017 | Split bridge parity suite | As a maintainer, I want every P0 acceptance test in `test_bridge_parity.py` (13–15 functions depending on how parametrised arms are counted; pinned by node-ID set equality at implement time) moved to a module that does not depend on the two-run oracle fixture, leaving the oracle retirable in isolation (#2631). | Medium | Open |
| FR-018 | Record parity verdicts | As a reviewer, I want a keep/convert/retire verdict with churn evidence and rationale for every module in the #2631 sweep recorded in the mission's design-decisions tracer, in the #2620 catalog format (#2631). | Medium | Open |
| FR-019 | Follow-up and routing issues | As the operator, I want follow-up issues filed for (a) retiring the bridge-parity oracle after #2633 (#5116, filed), (b) the silent `model` suppression in the agent-profile schema left unguarded by #3285 (#5117, filed), (c) routing the #2972 S8997 subset now that #1842 is closed (#5118, filed), and (d) migrating the remaining hand-rolled descriptor matchers onto the shared matching authority (filed at closeout). | Medium | Open |
| FR-020 | Census campsite and matrix | As the operator, I want #2972 findings cleaned only in test files this mission already touches, and #2972 and #3962 recorded in the issue matrix (#2972, #3962). | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Drift tolerance | Inserting one line at the top of **every** file referenced by a migrated allowlist, and one line inside **every** exempted site's enclosing function, changes the outcome of 0 gates; verified by an automated test over a temporary copy. | Reliability | High | Open |
| NFR-002 | Gate non-vacuity | Every new or widened ban has (a) a floor asserting ≥ N items inspected with N the planning-base count minus retirements, and (b) a self-mutation test that plants a violation into input read by the **real** scan function; 100% of retained bans in scope satisfy both. | Reliability | High | Open |
| NFR-003 | Shrink-only, per-site counting | No `_baselines.yaml` value in scope increases; exemptions are counted per exempted site (not per list row); the per-site exemption total in scope decreases by ≥ 2 (the dead join entries). | Maintainability | High | Open |
| NFR-004 | Gate runtime | The widened positional-anchor ban completes in < 10 s over `tests/architectural/`; the split bridge P0 module completes in < 60 s. | Performance | Medium | Open |
| NFR-005 | Quality gates | Changed files pass `ruff check`, `ruff format --check` and `mypy` with zero new suppressions; functions stay at complexity ≤ 15. | Maintainability | High | Open |
| NFR-006 | No lost invariant | For every retired test, the verdict record names a surviving enforcing test, or gives a cited reason plus a mutation demonstration that the retired test could not fail; 0 retirements without one. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | ATDD red-first | Each WP lands a failing-first acceptance test as its first commit, RED on the planning base and GREEN at WP completion (charter C-011). Retirement WPs prove red-first through a behavioural test or the gate that detects the defect (e.g. the widened ban, the non-enforcing-leaf check, a stricter loader, or a survivor re-pointed at the kept module), never by adding "symbol is gone" tombstone tests (the class #3285 removed). The only exception mechanism is an operator-approved charter exception recorded in the plan's Complexity Tracking table with a named evidence substitute; one is recorded (WP09, analysis finding D1). | Technical | High | Open |
| C-002 | Oracle retirement deferred | The bridge-parity two-run oracle is not retired or relaxed; it waits for #2633. | Technical | High | Open |
| C-003 | Census not missioned | #2972 is consumed only as campsite work on touched files. | Business | Medium | Open |
| C-004 | One identity mechanism | Migrations use the existing content-identity substrate (`composite_key` / `ContentDescriptor`); the census helper's duplicate qualname logic is unified onto it rather than kept as a second mechanism. | Technical | High | Open |
| C-005 | No production behaviour change | Changes are confined to `tests/`, test helpers, docs, tooling config and mission artefacts; no `src/` behaviour changes. Comment-only `src/` edits needed for SC-003 are allowed when an AST-equality check proves the module is unchanged (plan decision D-OP-3). | Technical | High | Open |
| C-006 | Branch and publication | Work lands on `claude/spec-kitty-remediation-wfje22`; publication is by PR to `main`; implementers do not merge. | Business | High | Open |

**C-006 rationale (analysis finding D2).** The session harness pins the development branch `claude/spec-kitty-remediation-wfje22`, so the mission cannot use the charter's preferred `issue-<n>-<slug>` name. Publication is unchanged: one PR targets `main` and the operator merges. The charter's issue-branch preference is advisory guidance under "Collaboration Strategy" ("Issue branch first"); the binding rules of "Agent Push Authorization" (never push `main`, publish through a named branch and a PR, do not merge) are all met. This is a recorded naming deviation, not a charter exception.

### Key Entities

- **Allowlist / exemption entry**: a record that exempts one source construct from a gate; identified by content, never by line. Hand-curated entries are `ContentDescriptor`s (path + qualname + token substring + `occurrence`); census entries are `CensusKey`s (path + qualname + token line + op + `op_ordinal`).
- **Hand-curated vs census allowlist**: hand-curated lists (join, kernel, os-detect) are small and fail on stale entries; census lists record pre-existing operation sites and warn on stale entries.
- **Baseline leaf**: a numeric ceiling in `tests/architectural/_baselines.yaml`; valid only if a comparison fails when the live measurement exceeds it.
- **Parity suite verdict**: keep / convert / retire, with discriminator class (behavioural invariant vs positive shape), churn evidence and rationale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 line-pinned entries remain under `tests/architectural/` (Python allowlists and exemption text files), down from 94; the FR-003 exemption list is empty.
- **SC-002**: the NFR-001 drift test passes over every referenced file and exempted site.
- **SC-003**: 0 references to retired files or symbols remain in live docs, tests, source or tooling config.
- **SC-004**: 0 `_baselines.yaml` leaves are non-enforcing.
- **SC-005**: 100% of modules in the #2631 sweep have a recorded verdict; 0 parity bans pass when their scan target is empty.
- **SC-006**: all five child issues of #5104 plus #3962 have an issue-matrix row, and the four FR-019 follow-up issues (a–d) exist.

## Assumptions and dependencies

- #3206 stays open during the mission; FR-005 is content-keyed and order-independent with it.
- #2633 does not land during the mission; if it does, C-002 is revisited at the next point-cut, not silently expanded.
- FR-015 uses the existing test-only environment knobs (e.g. `SPEC_KITTY_PACKS_ROOT`); if plan finds that impossible without a `src/` change, FR-015 is deferred rather than breaching C-005.
- Coordinate with #2560 and #4506 (touch adjacent gates) at plan time.
