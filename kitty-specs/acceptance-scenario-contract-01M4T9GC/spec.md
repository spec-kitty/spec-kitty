# Mission Specification: Acceptance scenario contract, per-PR check and nightly evidence

**Mission Branch**: `ccr-002603b2-bip646`
**Created**: 2026-10-13
**Status**: Draft
**Input**: Issues #6133 (epic), #6134, #6135, #6136, #6137. Design of record: `docs/architecture/acceptance-scenario-contract.md`; decision: ADR `docs/adr/4.x/2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md` (accepted by the owner on 2026-10-13).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A contributor gets scenario feedback on the pull request (Priority: P1)

A contributor adds or edits a `.feature` file under `tests/scenarios/`, or a step definition under `acceptance-jvm/`. Today nothing checks it until the next nightly. After this Mission, the pull request runs a check that needs no JDK and fails when a feature file does not parse, a tag breaks the vocabulary, or a step of a gating scenario has no binding.

**Why this priority**: scenarios are about to be drafted in bulk; a broken scenario found the next morning costs a day per round trip.

**Independent Test**: run the check against the real scenario tree (green) and against one broken fixture per rule (each red).

**Acceptance Scenarios**:

1. **Given** the current scenario tree, **When** the check runs, **Then** it passes and reports how many scenarios and steps it checked.
2. **Given** a feature file whose non-`@wip` scenario uses step text with no matching step definition, **When** the check runs, **Then** it fails and names the file, line and step text.
3. **Given** a `@wip` scenario with an unbound step, **When** the check runs, **Then** it passes and lists the unbound step as information.
4. **Given** a pull request that changes only `tests/scenarios/**` or `acceptance-jvm/**`, **When** CI routes it, **Then** the job that runs the check is selected.

---

### User Story 2 - The QA consumer can trace every nightly result to a build (Priority: P1)

The nightly `acceptance-bdd` job uploads one artifact per OS. Today the `@wip` pass overwrites the gating pass's Cucumber JSON and JUnit XML, and nothing records which CLI build, commit, OS or pass produced a result. After this Mission, each pass has its own folder, each leg writes a versioned `evidence.json`, and Allure results carry environment metadata.

**Why this priority**: the gating evidence is currently lost before upload, so the nightly cannot prove what it checked.

**Independent Test**: run the Gradle build for both passes into one build directory and assert the gating results are unchanged after the `@wip` pass, and that `evidence.json` validates against its schema.

**Acceptance Scenarios**:

1. **Given** a gating pass followed by a `@wip` pass, **When** both finish, **Then** `build/acceptance/gating/` still holds the gating Cucumber JSON, JUnit XML and Allure results byte-for-byte.
2. **Given** a finished leg, **When** `evidence.json` is read, **Then** it carries `schema_version` 1, the commit SHA, the CLI version of the built wheel, the OS, the run URL when present, and per pass the outcome, scenario counts and result paths.
3. **Given** a leg where the gating results are missing, **When** the upload step runs, **Then** the step fails.

---

### User Story 3 - A scenario author knows exactly what a scenario may say (Priority: P2)

A scenario author, by hand or with AI help, drafts scenarios that cite promises. The contributor docs state the tag vocabulary, that the only link to a promise is the opaque `@promise:<id>` identifier, and the drafted-scenario flow.

**Why this priority**: the per-PR check enforces this vocabulary, so authors need it written down first.

**Independent Test**: the docs pages exist, list every tag in the vocabulary, and pass the docs gates.

**Acceptance Scenarios**:

1. **Given** the contributor guide, **When** an author reads it, **Then** it lists every tag, its rule, and which scenarios gate the nightly.

---

### User Story 4 - An engineer can write scenarios about Missions (Priority: P3)

An engineer wants to check Mission lifecycle behaviour. Builders reach a project with a Mission in a given state by running the CLI only, and new steps expose them.

**Why this priority**: the next promises to check need Mission state; it depends on the per-PR check landing first.

**Independent Test**: the new mission-lifecycle scenarios pass the per-PR check and run green in the gating pass.

**Acceptance Scenarios**:

1. **Given** `Given a project with a mission "<slug>"`, **When** the scenario runs `spec-kitty agent tasks status --json`, **Then** the assert steps see that Mission.
2. **Given** a builder, **When** it reaches a state, **Then** it has run only CLI commands through the driver and written no `.kittify/` or `kitty-specs/` file itself.

---

### Edge Cases

- A step definition uses a Cucumber parameter type other than `{string}`, `{int}` or `{word}`: the check fails with a message naming the annotation, so the reader cannot silently fall behind the runner.
- A step matches two step definitions: the check fails (Cucumber would raise an ambiguity at run time).
- `Scenario Outline` steps contain `<placeholders>`: they are matched after substituting each `Examples` row.
- `And` / `But` / `*` steps inherit the keyword of the previous step.
- A `@wip` scenario without `@wip-owner:` or `@wip-since:`, or with an invalid date: the check fails.
- A `@promise:` tag with an empty or malformed identifier, or the same promise tag twice on one scenario: the check fails.
- Feature-level tags apply to every scenario in the file; `Rule` tags apply to its scenarios.
- The `@wip` pass finds no `@wip` scenario: it passes and `evidence.json` records zero scenarios for that pass.
- `evidence.json` is written even when the gating pass fails, so a red leg still uploads its evidence.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Document the tag vocabulary | As a scenario author, I want `tests/scenarios/README.md` and `docs/development/testing/acceptance-scenarios.md` to state each tag (`@promise:<id>`, `@wip` with `@wip-owner:`/`@wip-since:`, `@manual`, `@defect:<issue>`, `@qa:<ref>`, bare tags), its rule, which scenarios gate the nightly, that the identifier is the only link to a promise, and the drafted-scenario flow, so that I can write a valid scenario. (#6134) | High | Open | [build] | no — the docs gates fail on a missing or malformed page, and the check in FR-003 reads the same vocabulary |
| FR-002 | Mark the ADR accepted | As a maintainer, I want ADR 2026-10-13-1 to read Accepted with the owner and date, so that the record matches the decision. (#6133) | Medium | Open | [build] | no — the status line changes from Proposed |
| FR-003 | Feature files parse | As a contributor, I want the per-PR check to fail when a `.feature` file under `tests/scenarios/` does not parse or a scenario has no steps, so that a malformed file never reaches the nightly. (#6135) | High | Open | [build] | no — a broken fixture must turn the check red |
| FR-004 | Tags follow the vocabulary | As a contributor, I want the per-PR check to fail when a tag breaks the FR-001 vocabulary, so that every scenario's tags are machine-readable. (#6135) | High | Open | [build] | no — one broken fixture per tag rule must turn it red |
| FR-005 | Gating steps are bound | As a contributor, I want the per-PR check to fail when a step of a non-`@wip` scenario matches zero or more than one step definition read from the `@Given`/`@When`/`@Then` annotations in `acceptance-jvm`, and to fail on an unsupported parameter type, so that a gating scenario cannot reach the nightly with an undefined or ambiguous step. (#6135) | High | Open | [build] | no — unbound-step and ambiguous-step fixtures must turn it red, with the real tree as the positive control |
| FR-006 | WIP steps are informational | As a scenario author, I want unbound steps in `@wip` scenarios reported as information only, so that drafted scenarios can land before their steps are bound. (#6135) | Medium | Open | [build] | no — a `@wip` fixture with an unbound step must stay green while the same step in a non-`@wip` fixture is red |
| FR-007 | Route scenario changes to the check | As a contributor, I want `ci-router.yml` to select the job that runs the check when `tests/scenarios/**` or `acceptance-jvm/**` changes, so that scenario-only pull requests are checked without a JDK. (#6135) | High | Open | [build] | no — the router's selection test must show the job selected for those paths |
| FR-008 | Separate results per pass | As the QA consumer, I want each nightly pass to write to `acceptance-jvm/build/acceptance/<pass>/` (`gating` or `wip`) with `allure-results/`, `cucumber.json` and `junit/`, with the pass chosen by one Gradle property from which the tag filter is derived, so that the `@wip` pass can no longer overwrite the gating evidence. (#6136) | High | Open | [build] | no — gating results must be byte-identical after a following `@wip` pass |
| FR-009 | Allure run metadata | As the QA consumer, I want `environment.properties` (CLI version of the built wheel, commit SHA, OS, JDK version, pass) and `executor.json` (CI run URL and number, when present) written into each pass's `allure-results/` before scenarios run, so that every Allure result names its build. (#6136) | High | Open | [build] | no — the files must exist with the named keys |
| FR-010 | Versioned evidence bundle | As the QA consumer, I want `acceptance-jvm/build/acceptance/evidence.json` written per leg with `schema_version` 1, commit SHA, CLI version, OS, run URL, and per pass the outcome, scenario counts and result paths, even when the gating pass fails, so that I can read one file to know what a leg checked. (#6136) | High | Open | [build] | no — the file must validate against its schema with counts matching the run |
| FR-011 | Strict upload | As the QA consumer, I want the upload to keep the name `acceptance-bdd-results-<os>`, upload only `acceptance-jvm/build/acceptance/`, fail when files are missing, and keep them for 30 days, and the job's dead `pull_request` condition removed. (#6136) | Medium | Open | [build] | no — a workflow test must pin each value |
| FR-012 | Mission state builders | As an engineer, I want builders in `kitty.acceptance.environment` that reach a project with a Mission, and a work package in a given lane, only by running CLI commands through the driver, so that scenarios about Missions stay black-box. (#6137) | Medium | Open | [build] | no — a scenario using the builder must see the Mission through `agent tasks status --json` |
| FR-013 | Mission lifecycle steps and scenarios | As an engineer, I want the steps `Given a project with a mission "<slug>"`, `Given the work package "<wp>" of mission "<slug>" is in lane "<lane>"`, assert steps on `spec-kitty agent tasks status --json`, and a small `tests/scenarios/mission/` area using them, each scenario with a positive control. (#6137) | Medium | Open | [build] | no — each scenario carries a positive control and passes the FR-005 check |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast per-PR check | The per-PR scenario check runs in under 5 seconds on the current tree on a CI runner, and adds no dependency beyond the Python standard library. | Performance | High | Open |
| NFR-002 | No JDK per PR | No per-PR job installs a JDK or runs Gradle because of this Mission. | Operability | High | Open |
| NFR-003 | Code quality | New Python passes `ruff`, `ruff format` and `mypy` with zero findings; every function has cyclomatic complexity of at most 15; diff coverage of new Python is at least 90%. | Maintainability | High | Open |
| NFR-004 | Cross-OS evidence | `evidence.json` and the per-pass folders are produced identically on Linux, macOS and Windows legs (no shell-specific path handling in the Gradle build). | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Identifier only | No promise wording, slug, status or rationale enters this repository; the only link is `@promise:<id>`, checked for shape only (ADR 2026-10-13-1). | Governance | High | Open |
| C-002 | Black-box steps | Steps and builders drive the CLI as a process through the driver; they never import Python and never write project state files directly (ADR 2026-10-11-3). | Technical | High | Open |
| C-003 | No promise index in core | Nothing re-introduces `tests/scenarios/promise-index.json`, a sync token, or an identifier-existence check (ADR 2026-10-11-3 amendment). | Governance | High | Open |
| C-004 | Pinned JVM toolchain | Java changes keep the Java 25 toolchain, the pinned Gradle, and dependency verification metadata; no new Java dependency unless its verification metadata is regenerated. | Technical | High | Open |
| C-005 | Local JDK gap | The local environment has JDK 21; Java changes are verified by compiling under the CI JDK 25 (`sonar.yml` compile step or a temporary JDK 25), and the plan names how. | Technical | Medium | Open |
| C-006 | Public repository wording | Issue, commit and PR text uses neutral engineering language only. | Governance | High | Open |

### Key Entities

- **Scenario**: a Gherkin scenario under `tests/scenarios/<area>/`, with inherited and own tags and an ordered list of steps.
- **Step definition**: a `@Given`/`@When`/`@Then` annotation with a Cucumber expression, read from `acceptance-jvm`.
- **Tag vocabulary**: the fixed set of tag forms and their rules.
- **Pass**: one run of the scenarios with one tag filter, `gating` or `wip`.
- **Evidence bundle**: per leg, the per-pass result folders plus `evidence.json`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request that breaks a feature file, a tag or a gating step's binding fails CI within the PR run, with no JDK installed — [build] · no-op passable: no
- **SC-002**: After a nightly leg, the gating results in the uploaded artifact equal those the gating pass wrote (0 overwritten files) — [build] · no-op passable: no
- **SC-003**: Every uploaded leg carries an `evidence.json` naming its commit, CLI version, OS and per-pass outcome — [build] · no-op passable: no
- **SC-004**: At least two mission-lifecycle scenarios run green in the gating pass on all three OSes — [build] · no-op passable: no

## Assumptions

- The issues and the merged design are the agreed discovery outcome; no further interview is needed.
- #6098 (When-step wording) may rename the Act step later; the check reads step definitions from the source, so a rename needs no change to the check.
- "Run URL" comes from the standard GitHub Actions environment variables when present and is omitted locally.
