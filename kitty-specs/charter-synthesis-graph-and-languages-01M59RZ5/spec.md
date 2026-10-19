# Mission Specification: Charter synthesis graph and languages

**Mission Branch**: `issue-6442-charter-synthesis-graph-work`
**Created**: 2026-10-19
**Status**: Draft
**Input**: GitHub issues #6442, #6443, #6444 (follow-ups of Mission `charter-governance-resolution-01M57Z77`, PR #6440), plus the four local-only test failures recorded in that Mission. Operator decisions of 2026-10-19 are recorded as Decision Moments in `decisions/`.

## Background

Research (read-only squad, 2026-10-19) corrected the issue texts:

- **#6442.** No synthesized styleguide gets a source directive today. Only tactics carry `source_urns`; the `styleguide --applies--> <source>` branch of the derived-edge builder fires only on replayed provenance. A synthesized styleguide therefore has no edge and reaches context only as a root (compiled references of an unconfigured project, or an explicit list).
- **#6443.** `PROJECT_001` (slug `mission-type-scope-directive`) is built from the `project_intent` answer and scoped to "All project work packages". It is not tied to a mission type. Its only edge, `directive --requires--> mission_type:X` (#3052), is emitted only when the answer names a shipped mission type, and no traversal follows it.
- **#6444.** There are two parallel language authorities. The evidence code reader observes files and returns one language. `infer_repo_languages` reads declared languages only and returns a list. Their vocabularies differ (the reader knows go/rust/ruby, the declared side knows swift), against the charter's single-canonical-authority principle. `.kt` sources are counted as `java`. A declared "Kotlin" resolves to `unknown`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Synthesized styleguides follow their directive (Priority: P1)

An operator answers the testing, quality-gates and documentation questions in the charter interview and synthesizes. Each generated styleguide is linked from the shipped directive it elaborates. It reaches an agent's action context only while that directive is in force. An operator who deactivates the directive, or removes the styleguide from an explicit list, does not get it back on the next synthesis.

**Why this priority**: it is the same defect class as #6404. Governance an operator turned off must not keep arriving.

**Independent Test**: synthesize with a testing answer, deactivate `DIRECTIVE_034`, and confirm the testing styleguide is absent from `charter context --action implement`. Reactivate it and confirm the styleguide is present.

**Acceptance Scenarios**:

1. **Given** an interview with a `testing_philosophy` answer, **When** the operator synthesizes, **Then** the project graph holds `directive:DIRECTIVE_034 --suggests--> styleguide:<testing slug>`, stamped as a synthesized edge.
2. **Given** that edge and `DIRECTIVE_034` not in force, **When** context is built for any action, **Then** the testing styleguide is not delivered, neither in the action bundle nor in the compiled charter references.
3. **Given** an explicit `activated_styleguides` list, **When** synthesis creates a styleguide for the first time, **Then** its id is appended. **When** the operator removes it and synthesizes again, **Then** it is not re-appended.
4. **Given** `activated_styleguides` is absent, **When** synthesis runs, **Then** the key is still absent.
5. **Given** a project overlay carrying a legacy `styleguide --applies--> X` edge, **When** synthesis reconciles, **Then** the edge is removed and reported.
6. **Given** a `language_scope` styleguide, **When** synthesis runs, **Then** it has no source edge and keeps today's activation semantics.

---

### User Story 2 - The project-intent directive says what it is (Priority: P2)

An operator reads the synthesized directive list. The always-synthesized directive is named for what it holds, the project's intent, and its graph carries no link that pretends to scope it to a mission type.

**Why this priority**: the misleading name and the dead edge mislead operators and future graph work, but delivery is already correct.

**Independent Test**: synthesize in a fresh project and check the directive slug, title and edges. Run `spec-kitty upgrade` on a project with the old artifact and check that it is renamed with references intact.

**Acceptance Scenarios**:

1. **Given** a fresh synthesis, **When** the directive is generated, **Then** its slug is `project-intent-directive`, its title names project intent, and it has no `requires --> mission_type:*` edge, even when the answer names a shipped mission type.
2. **Given** a project with an existing `mission-type-scope-directive` artifact, its provenance, its graph node and possibly a reference in `activated_directives`, **When** `spec-kitty upgrade` runs, **Then** the artifact, its provenance, graph node and every activation reference move to the new slug. The declared `PROJECT_00N` id is unchanged, the dead edge is gone, and a second run is a no-op.
3. **Given** the renamed directive, **When** context is built, **Then** it is delivered exactly as before: as a root whenever directives are in force.

---

### User Story 3 - One language authority, polyglot and family-aware (Priority: P2)

An operator runs synthesis in a repository with a Kotlin backend and a TypeScript frontend. The evidence lists both languages. The neutrality gate accepts a slug that names either. Doctrine tagged for the JVM family applies, because Kotlin implies `jvm`. Synthesis evidence and doctrine scoping answer "which languages" from one authority with one vocabulary.

**Why this priority**: polyglot and Kotlin repositories get wrong evidence and wrong doctrine scoping today.

**Independent Test**: point synthesis evidence at a fixture with root `build.gradle.kts`, mostly `.kt` sources and a root `package.json` with TypeScript sources. Check `languages`, `primary_language`, the gate verdicts and the doctrine-scope match for a `jvm`-tagged fixture artifact.

**Acceptance Scenarios**:

1. **Given** a repository whose root manifests and sources span two languages, **When** evidence is collected, **Then** `languages` lists both, primary first, and `primary_language` is unchanged from today's single answer.
2. **Given** a single-language repository, **When** evidence is collected, **Then** `languages` holds one entry and the evidence hash equals today's hash.
3. **Given** a repository with mostly `.kt` sources, **When** evidence is collected, **Then** the language is `kotlin`, not `java`.
4. **Given** a project whose observed or declared languages include `java` or `kotlin`, **When** doctrine scoping runs, **Then** an artifact tagged `jvm` applies. An artifact tagged `java` applies to a Java project and not to a Kotlin-only project.
5. **Given** an interview answer "Kotlin and Spring", **When** declared languages are resolved, **Then** the result includes `kotlin` (and `jvm`), not `unknown`.
6. **Given** a synthesized artifact slug naming any listed language, or its family, **When** the neutrality gate runs, **Then** the artifact counts as language-scoped.
7. **Given** the evidence code reader and the declared-language resolver, **When** either needs the vocabulary or a family expansion, **Then** both use the same single authority. An architectural test fails on a second hand-kept language table.

---

### User Story 4 - Local-only reds explained and fixed (Priority: P3)

A contributor runs the upgrade and doctrine command tests locally and sees red. A classification run on 2026-10-19, in a clean `uv sync --frozen --all-extras` plus `pip install -e .` environment on `main` `f16633930`, found the following:

- `test_doctrine_asset` and `tests/cross_cutting/packaging/` pass. The earlier reds came from a stale venv or install.
- **Six `test_upgrade_command.py` tests** are real reds on `main` (nightly 39195441445, auto-issues #6437 and #6432). Since `ef23380b7` (migration ledger), `spec-kitty upgrade` in a project that is not a git repository crashes in `m_3_2_0rc35_unified_bundle.apply` with `NotInsideRepositoryError`, even under `--dry-run`. `tests/specify_cli/cli/commands` and `tests/specify_cli/upgrade` are out of the PR matrix, so this merged green.
- **The shipped-graph orphan ceiling** (`25 > 21`) is a real red on `main`. PR #6379 vendored four edge-less `mission_step_contract:plan/*` nodes and did not raise the documented residual.
- **Four nag / agent-check tests** are CI-environment reds. The harness container exports `SPEC_KITTY_NO_NAG=1`, and the root test fixture keeps pre-existing `SPEC_KITTY_*` values.
- **`test_upgrade_command_skill_drift::test_6155_*`** is open issue #6416 (the first upgrade after `init` is not a no-op). It is out of scope and is not changed here.

**Independent Test**: re-run the five groups in a clean environment, with `SPEC_KITTY_NO_NAG=1` still exported. Only `test_6155_*` stays red, attributed to #6416.

**Acceptance Scenarios**:

1. **Given** a project directory that is not a git repository, **When** `spec-kitty upgrade` (also with `--dry-run`) runs, **Then** the unified-bundle migration is skipped as not applicable, with a warning and without a record, instead of crashing. It is selected again once the project is a git repository.
2. **Given** the shipped graph, **When** the orphan-residual test runs, **Then** the ceiling covers the four `plan/*` step contracts, and the residual document lists them with a dated rationale citing #6379.
3. **Given** `SPEC_KITTY_NO_NAG=1` in the outer environment, **When** the nag tests run, **Then** they pass, because each one clears the variable it depends on. The flakiness doc names the harness variables that leak.
4. Nothing is skipped, xfailed or quarantined.

### Edge Cases

- A table directive (for example `DIRECTIVE_034`) is not selected and not active: the edge is still emitted (operator decision), so the styleguide is not delivered until that directive is in force.
- An org pack requires a synthesized styleguide's id: it stays a root (org-required wins, as for tactics).
- An unreadable created-artifact record: synthesis appends nothing for any kind and warns (fail closed).
- An existing `.kittify/charter/synthesized-tactics.yaml` from the previous Mission: honoured unchanged for tactics.
- The migration meets a target slug that already exists: it refuses with a clear message and changes nothing.
- A repository with only nested manifests in two languages: today's file-count rule picks the primary, and both enter `languages` when each clears the inclusion rule.
- A language with no doctrine (go, rust): still listed, still resolves to the "no specialist guidance" path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Styleguide source table | As an operator, I want each testing, quality-gates and documentation styleguide linked by `directive --suggests--> styleguide` from DIRECTIVE_034, DIRECTIVE_030 and DIRECTIVE_037 respectively, always, so that it is governed by the directive it elaborates. | High | Open | [build] | no |
| FR-002 | Sourced styleguides are reach-only | As an operator, I want a synthesized styleguide with a synthesized source edge never seeded as a root (action bundle or compiled references) unless org-required, so that it is delivered only while its directive is in force. | High | Open | [build] | no — paired with the unsourced language_scope styleguide on the same fixture |
| FR-003 | Removal sticks for styleguides | As an operator, I want synthesis to append a styleguide to an explicit `activated_styleguides` only the first time it creates it, recorded per kind in the created-artifact record, never creating the key, so that my removal sticks. | High | Open | [build] | no |
| FR-004 | One reach-only model for both kinds | As a maintainer, I want the reach-only predicate, edge stamping, ownership and created-artifact record parameterised by kind (tactic, styleguide) rather than duplicated, so that there is one implementation. | Medium | Open | [ratchet] | yes — behaviour for tactics is pinned by the existing tests |
| FR-005 | Legacy styleguide applies edges stripped | As an operator, I want reconcile to remove and report a `styleguide --applies--> X` edge in the project overlay, so that no dead edge stays. | Medium | Open | [build] | no |
| FR-006 | Project-intent directive naming | As an operator, I want the always-synthesized directive named `project-intent-directive` with a project-intent title, so that the name matches its content. | Medium | Open | [build] | no |
| FR-007 | No mission-type requires edge | As an operator, I want synthesis to stop emitting `directive --requires--> mission_type:X` for that directive, and reconcile to drop an existing one, so that the graph claims no link that no traversal uses. | Medium | Open | [build] | no |
| FR-008 | Rename migration | As an operator, I want `spec-kitty upgrade` to move an existing `mission-type-scope-directive` artifact, provenance, graph node and activation references to the new slug, keeping its id, idempotently and refusing on a collision, so that existing projects converge. | Medium | Open | [build] | no |
| FR-009 | Single language authority | As a maintainer, I want one module to own the language vocabulary, family expansion, observed detection and declared resolution, with the evidence code reader and `infer_repo_languages` delegating to it, so that there is a single canonical authority. | High | Open | [ratchet] | no — an architectural test pins one vocabulary table |
| FR-010 | Multi-language evidence | As an operator, I want evidence to carry `languages` (primary first) for every language with a top-depth manifest or a source share at or above a documented threshold, keeping `primary_language`, so that polyglot repositories are described. | High | Open | [build] | no |
| FR-011 | Gate exempts any listed language | As an operator, I want the neutrality gate to treat a slug naming any listed language, or a family of one, as language-scoped, so that polyglot synthesis is not mislinted. | Medium | Open | [build] | no |
| FR-012 | Stable hash for single-language repos | As an operator, I want `languages` to enter the evidence hash only when it holds more than one language, so that single-language provenance does not look stale after upgrade. | High | Open | [build] | no — paired with the two-language fixture on the same test |
| FR-013 | Kotlin token and jvm family | As an operator, I want `.kt`-majority sources and a declared "Kotlin" to resolve to `kotlin`, and both `java` and `kotlin` to imply `jvm`, so that doctrine tagged `jvm` applies to either and `java`-tagged doctrine applies only to Java. | High | Open | [build] | no |
| FR-014 | Additive JSON surfaces | As an integrator, I want `languages` added to the evidence JSON of `charter status` and `charter synthesize --dry-run`, with existing keys unchanged, so that consumers do not break. | Medium | Open | [build] | no |
| FR-015 | Upgrade outside a git repository | As an operator, I want the unified-bundle migration to report itself not applicable (skipped, unrecorded, warned) when the project is not inside a git repository, so that `spec-kitty upgrade` does not crash with `NotInsideRepositoryError`. | High | Open | [build] | no |
| FR-016 | Orphan residual matches the shipped graph | As a maintainer, I want the documented orphan ceiling and residual document to include the four `mission_step_contract:plan/*` nodes vendored by #6379, so that the gate is green and honest. | Medium | Open | [build] | no |
| FR-017 | Nag tests hermetic against harness env | As a contributor, I want the tests that depend on the upgrade nag to clear `SPEC_KITTY_NO_NAG` themselves, and the flakiness doc to name the harness variables that leak, so that an agent container does not turn them red. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Default in-force snapshot | The golden default in-force snapshot test (no org packs, no keys, no selections) passes unchanged, except for the documented directive slug rename. | Reliability | High | Open |
| NFR-002 | Static quality | Zero new ruff, ruff-format or mypy --strict findings on changed files; no new `noqa` or `type: ignore`; every new or changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Test coverage of new code | Every new branch and helper is exercised by a focused test in the same work package (diff-cover ≥ 90%). | Maintainability | High | Open |
| NFR-004 | Red-first proof | Every behavioural FR has a test that fails on the pre-fix source, recorded in the work package review. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Removal sticks | An operator's removal of an artifact (unless org-required or enforced) is never silently reinstalled or regenerated into force (ADR 2026-10-06-2, amendment 2026-10-19). | Business | High | Open |
| C-002 | Synthesis never creates an activation key | Synthesis appends only to an existing explicit `activated_*` list. | Technical | High | Open |
| C-003 | Absent-key semantics unchanged | The absent-key semantics of #4253 and #4400 do not change. | Technical | High | Open |
| C-004 | Built-in pack untouched | No change under `packs/built-in/`. `charter pack vendor --check` and `charter pack regenerate-graph --check` stay green; the `jvm` retag of shipped JVM toolguides is a port to spec-kitty-open-packs. | Technical | High | Open |
| C-005 | Charter API boundary | Callers outside `src/charter/` reach new charter behaviour only through `charter.activation.api` or `charter.offering.api`. | Technical | High | Open |
| C-006 | No quarantine | No test is skipped, xfailed or quarantined to get green. | Technical | High | Open |
| C-007 | Terminology | Mission terminology only; never "feature". | Business | Medium | Open |

### Key Entities

- **Created-artifact record**: the per-project record of artifact ids synthesis has created, per kind (tactic, styleguide). It decides first-time appends. Today it is `.kittify/charter/synthesized-tactics.yaml` with `created_tactics`.
- **Styleguide source table**: the fixed map from interview section to shipped directive id that sources a synthesized styleguide.
- **Language authority**: the single owner of the language vocabulary, family map (`java` → `jvm`, `kotlin` → `jvm`), observed languages (from files) and declared languages (from the charter or interview).
- **Code signals / evidence**: gains `languages`; keeps `primary_language`, `scope_tag` and `stack_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fixture project, deactivating `DIRECTIVE_034` removes the synthesized testing styleguide from `charter context --action implement`, and reactivating it restores the styleguide. — [build] · no-op passable: no
- **SC-002**: Re-synthesizing after removing a synthesized styleguide from `activated_styleguides` leaves it removed. — [build] · no-op passable: no
- **SC-003**: `spec-kitty upgrade` on a fixture with the old directive slug yields the new slug, the same id and intact references; a second run reports nothing to do. — [build] · no-op passable: no
- **SC-004**: A Kotlin + TypeScript fixture yields `languages == [kotlin, typescript]` (or the documented order) and `jvm` doctrine applies; a Python-only fixture's evidence hash is byte-identical to `main`. — [build] · no-op passable: no
- **SC-005**: In a clean environment with `SPEC_KITTY_NO_NAG=1` exported, `test_upgrade_command.py` and `test_doctrine_regenerate_graph.py` pass; only `test_6155_*` stays red, attributed to #6416. — [build] · no-op passable: no
