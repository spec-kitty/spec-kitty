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
2. **Given** that edge and `DIRECTIVE_034` not in force, **When** context is built for any action, **Then** the testing styleguide is not delivered: it is not a compiled-references root, and no graph walk reaches it.
7. **Given** that edge and `DIRECTIVE_034` in force, **When** context is built for an action the directive is scoped to (software-dev `implement`, `review`), **Then** the styleguide is newly delivered in the action bundle through the `suggests` edge. This holds also in a configured project whose `activated_styleguides` key is absent. This is an intended delivery change.
8. **Given** an explicit `activated_styleguides` list and synthesized styleguides that already existed before this Mission, **When** synthesis runs, **Then** they are not appended (they were never created for the first time by a recording run), so they stay as delivered today. This is intended: removal sticks.
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
2. **Given** a project with an existing `mission-type-scope-directive` directive, **When** `spec-kitty upgrade` runs, **Then** every slug-keyed file and reference moves to `project-intent-directive`, as listed in FR-008. The declared `PROJECT_00N` id and graph URN are unchanged, the overlay label names project intent, the dead `requires --> mission_type:*` edge is gone, synthesize and resynthesize keep working (no `GeneratedArtifactMissingError`), and a second run is a no-op.
4. **Given** a project that synthesizes with the new CLI before upgrading, **When** synthesis writes the directive, **Then** the legacy slug-keyed files are moved first by the same helper the migration uses, so there are never two files declaring `PROJECT_00N`.
3. **Given** the renamed directive, **When** context is built, **Then** it is delivered exactly as before: as a root whenever directives are in force.

---

### User Story 3 - One language authority, polyglot and family-aware (Priority: P2)

An operator runs synthesis in a repository with a Kotlin backend and a TypeScript frontend. The evidence lists both languages. The neutrality gate accepts a slug that names either. Doctrine tagged for the JVM family applies, because Kotlin implies `jvm`. Synthesis evidence and doctrine scoping answer "which languages" from one authority with one vocabulary.

**Why this priority**: polyglot and Kotlin repositories get wrong evidence and wrong doctrine scoping today.

**Independent Test**: point synthesis evidence at a fixture with root `build.gradle.kts`, mostly `.kt` sources and a root `package.json` with TypeScript sources. Check `languages`, `primary_language`, the gate verdicts and the doctrine-scope match for a `jvm`-tagged fixture artifact.

**Acceptance Scenarios**:

1. **Given** a repository whose root manifests and sources span two languages, **When** evidence is collected, **Then** `languages` lists both, primary first, and `primary_language` is unchanged from today's single answer, except that Kotlin repositories now report `kotlin` (scenario 3).
2. **Given** a single-language repository other than Kotlin, **When** evidence is collected, **Then** `languages` holds one entry and the evidence hash equals today's hash.
3. **Given** a repository with a JVM manifest (Gradle or Maven) and more `.kt` than `.java` sources, **When** evidence is collected, **Then** the primary language is `kotlin`, not `java`. With more `.java` sources it is `java`, and when both clear the inclusion threshold both are listed.
4. **Given** a project whose observed or declared languages include `java` or `kotlin`, **When** doctrine scoping runs, **Then** an artifact tagged `jvm` applies. An artifact tagged `java` applies to a Java project and not to a Kotlin-only project.
5. **Given** an interview answer "Kotlin and Spring" or "Kotlin, Gradle, JUnit", **When** declared languages are resolved, **Then** the result is `[kotlin]`, never `unknown` and never `java`. A build or test tool token (gradle, maven, junit) adds `jvm` only when no JVM language is declared ("Gradle" alone gives `[jvm]`). Families of declared languages are expanded at match time and never persisted into `catalog.languages`, so the compiled charter of a project declaring "Java, Gradle" does not change.
8. **Given** the shipped `java-supply-chain` and `maven-review-checks` toolguides, retagged `jvm` in this Mission, **When** a project declares "Kotlin, Gradle", **Then** both apply. `java-jenny` and `java-conventions` stay Java-only.
6. **Given** a synthesized artifact slug naming any observed or declared language, or a family of one, **When** the neutrality gate runs, **Then** the artifact counts as language-scoped.
7. **Given** the evidence code reader, the declared-language resolver and doctrine scope matching, **When** any of them needs the recognition vocabulary or a family expansion, **Then** all use the one language catalog. An architectural test fails on a second hand-kept language table; the review fence-language map in `specify_cli/review/fix_prompt.py` is a different concept and is allowlisted with a rationale. The doctrine-derived "has specialist guidance" vocabulary (#5284) stays separate and unchanged.

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
- An existing `.kittify/charter/synthesized-tactics.yaml` from the previous Mission (unreleased): its `created_tactics` are still honoured when the record moves to its per-kind home.
- The migration meets a target slug that already exists: it refuses with a clear message and changes nothing.
- A repository with only nested manifests in two languages: today's file-count rule picks the primary, and both enter `languages` when each clears the inclusion rule.
- Polyglot evidence still loads the synthesis corpus of the primary language only.
- A table directive missing from the DRG snapshot (for example a test double): the edge is not emitted, so no URN dangles.
- A project that is not a git repository and has no charter: `spec-kitty upgrade` completes, it does not crash.
- A language with no doctrine (go, rust): still listed, still resolves to the "no specialist guidance" path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Styleguide source table | As an operator, I want each testing, quality-gates and documentation styleguide sourced (as `source_urns`, like tactics) from DIRECTIVE_034, DIRECTIVE_030 and DIRECTIVE_037 respectively, always when that directive exists in the DRG, giving `directive --suggests--> styleguide`, so that it is governed by the directive it elaborates. The section's tactic is not linked by this table. | High | Open | [build] | no |
| FR-002 | Sourced styleguides are reach-only | As an operator, I want a synthesized styleguide with a synthesized source edge never seeded as a compiled-references root unless org-required, so that it is delivered only while its directive is in force (the action bundle seeds no styleguide roots today and keeps it so, pinned by a test). | High | Open | [build] | no — the compiled-references root is the red-first case, paired with the unsourced language_scope styleguide on the same fixture |
| FR-003 | Removal sticks for styleguides | As an operator, I want synthesis to append a styleguide to an explicit `activated_styleguides` only the first time it creates it, recorded per kind in one created-artifact record that also honours the unreleased `synthesized-tactics.yaml` `created_tactics`, never creating the key, so that my removal sticks. | High | Open | [build] | no |
| FR-004 | One reach-only model for both kinds | As a maintainer, I want the reach-only predicate, edge stamping, ownership and created-artifact record parameterised by kind (tactic, styleguide) rather than duplicated, so that there is one implementation. | Medium | Open | [ratchet] | yes — behaviour for tactics is pinned by the existing tests |
| FR-005 | Legacy styleguide applies edges stripped | As an operator, I want reconcile to remove and report a `styleguide --applies--> X` edge in the project overlay, so that no dead edge stays. | Medium | Open | [build] | no |
| FR-006 | Project-intent directive naming | As an operator, I want the always-synthesized directive named `project-intent-directive` with a project-intent title, so that the name matches its content. | Medium | Open | [build] | no |
| FR-007 | No mission-type requires edge | As an operator, I want synthesis to stop emitting `directive --requires--> mission_type:X` for that directive, and reconcile to drop an existing one, so that the graph claims no link that no traversal uses. | Medium | Open | [build] | no |
| FR-008 | Rename migration and shared helper | As an operator, I want one charter-layer helper, called by an upgrade migration and by synthesize/resynthesize before they write, to move a legacy `mission-type-scope-directive` to `project-intent-directive`: the artifact file under `.kittify/charter-packs/`, the harness input under `.kittify/charter/generated/directives/`, the provenance file and its slug fields, the synthesis-manifest entry (`path`, `slug`) with recomputed hashes, the overlay node label, the `requires --> mission_type:*` edge (dropped), and stem tokens in the resolved activation write target, followed by a bundle restamp. The id, URN and the interview section label `mission_type` are kept, the artifact body is not rewritten, it is idempotent, and it refuses on a target collision having changed nothing. | Medium | Open | [build] | no |
| FR-009 | Single language catalog and authority | As a maintainer, I want one I/O-free language catalog in `charter.offering.shared` (tokens, extensions, manifests, declared patterns, families) and one activation-layer authority that resolves observed and declared languages from it, with the evidence code reader, `language_scope` and `applies_to_languages_match` all delegating, so that there is a single canonical authority that respects the offering/activation layering. | High | Open | [ratchet] | no — an architectural test pins one vocabulary table |
| FR-010 | Multi-language evidence | As an operator, I want evidence to carry `languages` (primary first) for every language with a top-depth manifest or a source share at or above a documented threshold, keeping `primary_language`, so that polyglot repositories are described. | High | Open | [build] | no |
| FR-011 | Gate exempts any listed language | As an operator, I want the neutrality gate to treat a slug naming any observed or declared language, or a family of one, as language-scoped, so that polyglot and language_scope synthesis is not mislinted. | Medium | Open | [build] | no |
| FR-012 | Stable evidence hash for single-language repos | As an operator, I want `languages` to enter the evidence hash only when it holds more than one language, so that the evidence identity shown by `charter status` and stored in provenance does not churn for single-language repositories. Kotlin repositories change hash, because their primary language changes. | High | Open | [build] | no — paired with the two-language fixture on the same test |
| FR-013 | Kotlin token and jvm family | As an operator, I want a JVM-manifest repository with more `.kt` than `.java` sources, and a declared "Kotlin", to resolve to `kotlin`, and declared build and test tool tokens (gradle, maven, junit) to add `jvm` only when no JVM language is declared. Both `java` and `kotlin` match `jvm`-tagged doctrine through match-time expansion, and `java`-tagged doctrine applies only to Java. | High | Open | [build] | no |
| FR-014 | Additive JSON surfaces | As an integrator, I want `languages` added to the evidence JSON of `charter status` and `charter synthesize --dry-run`, with existing keys unchanged, so that consumers do not break. | Medium | Open | [build] | no |
| FR-015 | Upgrade outside a git repository | As an operator, I want the upgrade runner to treat a migration that needs a git repository as not applicable (skipped, unrecorded, warned) when the project is not inside one, without editing the shipped migration, so that `spec-kitty upgrade` does not crash with `NotInsideRepositoryError`. | High | Open | [build] | no |
| FR-016 | Orphan residual matches the shipped graph | As a maintainer, I want the shipped-graph orphan ceiling to cover the four `mission_step_contract:plan/*` nodes vendored by #6379, preferably derived from the existing shipped-orphan set rather than a second hand-kept number, with a dated addendum in the residual document, so that the gate is green and honest. | Medium | Open | [build] | no |
| FR-017 | Nag tests hermetic against harness env | As a contributor, I want the tests that depend on the upgrade nag to clear `SPEC_KITTY_NO_NAG` themselves, and the flakiness doc to name the harness variables that leak, so that an agent container does not turn them red. | Low | Open | [build] | no |
| FR-018 | Shared JVM doctrine retagged | As a Kotlin operator, I want `java-supply-chain` and `maven-review-checks` tagged `jvm` in core `packs/built-in`, re-seeded into spec-kitty-open-packs, and the core vendor pin bumped to that open-packs commit, so that no Kotlin project loses JVM guidance. | High | Open | [build] | no |
| FR-019 | Decisions recorded | As a maintainer, I want ADR 2026-04-17-1 (request hash inputs), ADR 2026-04-19-6 (generated-artifact layout and slug) and ADR 2026-10-06-2 (removal sticks for styleguides, per-kind record) amended, so that the governed contracts match the code. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Default in-force snapshot | The golden default in-force snapshot (no org packs, no keys, no selections, no synthesized artifacts) stays byte-identical. A second golden for a synthesized fixture project is added, and its diff against `main` is reviewed and documented: styleguides move from root to reach-only, new implement/review delivery, the directive label. | Reliability | High | Open |
| NFR-005 | Detection cost | The extra source counting for JVM and polyglot detection runs only when a JVM manifest or two or more candidate languages are present, and `tests/charter/synthesizer/test_performance_envelopes.py` stays within budget. | Performance | Medium | Open |
| NFR-002 | Static quality | Zero new ruff, ruff-format or mypy --strict findings on changed files; no new `noqa` or `type: ignore`; every new or changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Test coverage of new code | Every new branch and helper is exercised by a focused test in the same work package (diff-cover ≥ 90%). | Maintainability | High | Open |
| NFR-004 | Red-first proof | Every behavioural FR has a test that fails on the pre-fix source, recorded in the work package review. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Removal sticks | An operator's removal of an artifact (unless org-required or enforced) is never silently reinstalled or regenerated into force (ADR 2026-10-06-2, amendment 2026-10-19). | Business | High | Open |
| C-002 | Synthesis never creates an activation key | Synthesis appends only to an existing explicit `activated_*` list. | Technical | High | Open |
| C-003 | Absent-key semantics unchanged | The absent-key semantics of #4253 and #4400 do not change. | Technical | High | Open |
| C-004 | Built-in pack edits follow the vendor flow | The only `packs/built-in/` change is the FR-018 retag. It is re-seeded into spec-kitty-open-packs and pinned back, so `charter pack vendor --check` and `charter pack regenerate-graph --check` are green on the final tree. A shipped migration is never edited (DIRECTIVE_044). | Technical | High | Open |
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
- **SC-004**: A Kotlin + TypeScript fixture yields `languages` holding both, with `kotlin` first when it has more sources, and `jvm` doctrine applies to it. A Python-only fixture's evidence hash is byte-identical to `main`. A project declaring "Kotlin, Gradle" receives `java-supply-chain` and `maven-review-checks`. — [build] · no-op passable: no
- **SC-005**: In a clean environment with `SPEC_KITTY_NO_NAG=1` exported, `test_upgrade_command.py` and `test_doctrine_regenerate_graph.py` pass; only `test_6155_*` stays red, attributed to #6416. — [build] · no-op passable: no
