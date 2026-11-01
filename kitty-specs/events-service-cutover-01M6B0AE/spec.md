# Mission Specification: Events service cut-over in core

**Mission Branch**: `issue-6915-events-service-cutover`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Operator brief (dispatch of spec-kitty/spec-kitty#6915 gaps 3 and 11; milestone "4.0.0 release scope"; plan `docs/plans/events-domain-move/plan.md` §4 step 5, "Core PR 2 (cut-over)"; ADR `2026-10-29-1`, Amendment 2026-10-30).

## Intent Summary

- **Primary actors:** a core maintainer (changes code, bumps pins, cuts releases) and core CI (proves conformance on every change and nightly).
- **Trigger:** spec-kitty-events published its first service release, `service-v0.1.0-rc.1`, carrying the Mission Status read service (four native builds and a jar), the contract bundles, the contract tools and the conformance fixtures.
- **Desired outcome:** core holds a verified pin of that release instead of its own frozen copies of the Java service and contracts; every conformance check core runs reads the pinned, digest-verified assets; and a release of core cannot ship unless the service pins verify.
- **Rule that always holds:** no service binary ships in core's wheel or sdist; a pinned asset is used only after its bytes match the pinned digest; a missing or mismatched asset fails a check, it never skips it.
- **Boundary:** the read service is pinned for CI conformance only; the CLI never launches it and ordinary user commands never fetch it. The write-service pin, the EventBridge binding (#6195), the charter-service pin, the install docs (gap 12) and the setup-doctor checks (gap 13) are out of scope.
- **Discovery:** the brief is complete (objective, constraints, slices, done criteria). One choice was forced by the code grounding and resolved from the brief: `make dev-setup` fetches the pinned **extras only** (DM `01M6B0JYP9B0CMBWRQ7TR7GBVN`).

## Domain Language

| Term | Meaning here | Avoid |
|---|---|---|
| Service pin | `pins/<service>.source.yaml`: the release tag, commit and per-asset sha256 core consumes | "lockfile" alone (packs have lockfiles too) |
| Pinned asset | one release file named by a pin (native build, jar, or an extras archive) | "artifact" (collides with Mission artifacts) |
| Extras | the shared archives of a release: contract bundles, contract tools, conformance fixtures | — |
| Cut-over | removing core's copies once the pinned release replaces them | "migration" (an upgrade migration is a different thing) |
| Consolidate | the local lane consolidation of this Mission; never a publish to origin | "merge" without a sense |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Core consumes a verified pin of the read service (Priority: P1)

A maintainer pins the released read service with the one canonical bump command. CI and a fresh development checkout fetch exactly the pinned assets and refuse anything whose digest does not match.

**Why this priority**: every other slice reads the pinned assets; without a sound pin nothing can be repointed or removed.

**Independent Test**: the committed pin loads and passes the offline pin gate; the fetch-and-check tooling, run locally, verifies every pinned asset for this host.

**Acceptance Scenarios**:

1. **Given** no read-service pin, **When** the maintainer runs the canonical vendor command for `service-v0.1.0-rc.1`, **Then** `pins/read-service.source.yaml` records the tag, its commit and a digest for each of the four native builds, the jar and the three extras, and nothing was hand-edited.
2. **Given** the pin, **When** the fetch tooling runs and then runs in check mode, **Then** each asset for this host is reported verified, and a corrupted cached copy is reported as a digest mismatch with a remedy.
3. **Given** a fresh checkout, **When** the maintainer runs the development setup, **Then** the pinned extras are present without the 95 MB read-service binary.

---

### User Story 2 - Conformance checks read the pinned assets (Priority: P1)

The Python oracle and golden checks compare against the fixtures, contract bundles and contract tools of the pinned release, and the nightly compares the pinned native binary with the Python oracle over the whole Mission corpus.

**Why this priority**: the read service's conformance is the reason the read service is pinned at all (ADR D-6).

**Independent Test**: the conformance, golden, oracle and contract tests pass with core's `services/` and `contracts/` sources absent; removing the pinned extras from the cache makes them fail with a remedy, not skip.

**Acceptance Scenarios**:

1. **Given** the pinned extras are fetched, **When** the conformance and golden tests run, **Then** they read the release's fixtures, bundles and tools and pass.
2. **Given** the extras are not fetched, **When** the same tests run, **Then** they fail and name the remedy (`make sync-services`).
3. **Given** a scheduled nightly run, **When** the corpus compare job runs, **Then** it starts the pinned native binary from the verified cache against the checkout and fails on any difference with the Python oracle.

---

### User Story 3 - Core no longer carries the events domain's Java service and contracts (Priority: P2)

The frozen copies leave core, along with every workflow, routing entry, ownership line, attribute, notice, exclude and test that only existed for them.

**Why this priority**: ADR `2026-10-29-1` names one owner for the events domain; core's copies are dead weight and a drift risk once the pin is in force.

**Independent Test**: `services/`, `contracts/` (except the five handoff fixtures), `mission-status-api.yml`, `contracts.yml` and `contracts-release.yml` are absent, the freeze gate is gone, and the touched routing and packaging gates are green.

**Acceptance Scenarios**:

1. **Given** the cut-over, **When** a maintainer lists the repository, **Then** only `contracts/fixtures/fixture_0*.json` remain of `contracts/`, and `services/` does not exist.
2. **Given** a diff touching only the service pin, **When** CI selects shards, **Then** the selection is non-empty and runs the pin gate.
3. **Given** a reader looking for the service or contract sources, **When** they open the docs or the ADR, **Then** a pointer names `spec-kitty-events` `service/` and `contracts/`.

---

### User Story 4 - A core release verifies the service pins (Priority: P2)

The release workflow and checklist verify the service pins next to the pack pins, and the built wheel is shown to contain the pins and no service binary.

**Why this priority**: gap 11 — a release must not ship pins that do not resolve to the released bytes.

**Independent Test**: the release workflow carries a service-pin fetch-and-check step beside the packs check and a wheel assertion; the checklist names the service steps.

**Acceptance Scenarios**:

1. **Given** a release run, **When** the pins step runs, **Then** every pinned asset for the runner's host is fetched and checked against its digest, and a mismatch fails the release before build.
2. **Given** the built wheel, **When** the content checks run, **Then** they find the pin files and no native build or jar.

---

### Edge Cases

- A cached asset whose bytes changed: check mode reports a mismatch; fetch mode evicts and refetches it.
- An extras archive containing a link, an absolute path or `..`: extraction refuses it and nothing is written.
- An extracted extras directory left from an earlier pin tag: it is keyed by the archive digest, so a pin bump never reads a stale tree.
- A contributor running only `make test-fast`: no pinned asset is needed (none of the affected tests is in that tier).
- The released `gradle_pin_check.py` scans a `contracts/` subproject core no longer has: core calls its acceptance-jvm entry point only.
- The vendor command refuses (a `SERVICE_VENDOR_*` code): the Mission stops and reports it; no hand-edit.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Read-service pin | As a maintainer, I want `pins/read-service.source.yaml` vendored from `service-v0.1.0-rc.1` by `spec-kitty service vendor` (four native builds, the jar, contract bundles, contract tools, conformance fixtures) so that core consumes one verified release. | High | Open | [build] | no — the pin gate parametrises over pin files and has no case until the file exists |
| FR-002 | Extras-only fetch | As a contributor, I want the fetch tooling to fetch and check only a pin's extras on request so that development setup and conformance jobs do not download a service binary. | High | Open | [build] | no — a planted pin fixture asserts the native asset is neither fetched nor checked |
| FR-003 | Verified extraction | As a test or script author, I want one tool to unpack a verified extras archive into a digest-keyed directory and report its path, refusing unsafe archive members, so that every consumer reads the same verified tree. | High | Open | [build] | no — planted traversal and link members must be refused |
| FR-004 | Development setup | As a contributor, I want `make dev-setup` to fetch the pinned extras so that a fresh checkout can run the conformance tests. | Medium | Open | [build] | no — the Makefile test asserts the call is present (it asserts absence today) |
| FR-005 | CI wiring | As a maintainer, I want the sync-services action in every CI job that runs a conformance or golden suite, the nightly compare and a service-pin gate job so that CI reads verified pinned assets. | High | Open | [build] | no — the existing wiring ratchet fails while a pin exists and no job uses the action |
| FR-006 | Repointed conformance and goldens | As a maintainer, I want the conformance, artifact-golden and torn-tail golden tests to read the pinned conformance fixtures so that they no longer depend on `services/`. | High | Open | [build] | no — they must pass with `services/` deleted |
| FR-007 | Repointed oracle and contract tests | As a maintainer, I want the Python oracle and the mission-status/mission-write contract tests to read the pinned contract bundles and contract tools so that they no longer depend on `contracts/` sources. | High | Open | [build] | no — they must pass with `contracts/mission-*` and `contracts/tools` deleted |
| FR-008 | Fail closed on a missing asset | As a maintainer, I want a test that needs a pinned asset to fail with a named remedy when the asset is absent so that a missing fetch is never a silent green. | High | Open | [build] | no — a test runs the helper against an empty cache and asserts the failure |
| FR-009 | Nightly corpus compare on the pinned binary | As a maintainer, I want a scheduled nightly job that starts the pinned native binary from the verified cache and runs the corpus compare so that core proves the build it pins against its live corpus. | High | Open | [build] | no — a workflow test pins the job's fetch, start and compare steps |
| FR-010 | acceptance-jvm tools from the pin | As a maintainer, I want acceptance-jvm's tool install and Gradle pin check (nightly, sonar, cloud setup) to run the pinned contract tools so that they no longer depend on `contracts/tools`. | Medium | Open | [build] | no — a test asserts no workflow or script runs `contracts/tools/` |
| FR-011 | Remove the copies | As a maintainer, I want `services/`, `contracts/` (except `fixtures/fixture_0*.json`), `mission-status-api.yml`, `contracts.yml` and `contracts-release.yml` removed so that the events domain has one owner. | High | Open | [build] | no — an acceptance test asserts their absence and fails today |
| FR-012 | Remove the coupling | As a maintainer, I want every router, module-registry, retirement-scrub, fleet-verdict, CODEOWNERS, `.gitattributes`, NOTICE, sdist-exclude and gate entry that only served the removed copies dropped or re-pointed so that no configuration names a missing path. | High | Open | [build] | no — a test asserts no workflow/config names `services/` |
| FR-013 | Remove the freeze gate and copy-only tests | As a maintainer, I want the freeze gate, the build-pin tests and the tool/source-layout tests that test code now owned by spec-kitty-events deleted so that core tests only what core owns. | Medium | Open | [build] | no — the freeze gate fails once `contracts/*` is gone |
| FR-014 | Release pin check | As a release manager, I want `release.yml` to fetch and check the service pins next to the packs check, and to assert the wheel holds the pins and no service binary, so that a release cannot ship an unverifiable pin. | High | Open | [build] | no — a workflow test pins the steps |
| FR-015 | Release checklist | As a release manager, I want `RELEASE_CHECKLIST.md` to list the service-pin steps so that a manual release follows the same checks. | Medium | Open | [build] | no — a test asserts the checklist names the command |
| FR-016 | Governance and doc pointers | As a reader, I want CLAUDE.md, AGENTS.md, the charter, the pins README, the plan and the relevant docs to state that core pins the read service and no longer holds `services/`, with pointers to spec-kitty-events, so that guidance matches the code. | Medium | Open | [build] | yes — prose; reviewed, plus the terminology guard |
| FR-017 | Changelog | As a reader, I want an Unreleased changelog entry so that the cut-over is recorded. | Low | Open | [build] | yes — prose; reviewed |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Pure wheel | The built wheel and sdist contain 0 service binaries and 0 jars; the packaging guards pass. | Security | High | Open |
| NFR-002 | Small development fetch | `make dev-setup`'s service fetch downloads at most 1 MB on a cold cache (extras only, ≈230 KB today). | Performance | Medium | Open |
| NFR-003 | Corpus parity | The nightly compare reports 0 differing rows over at least the recorded floor of 500 Missions (677 at grounding). | Reliability | High | Open |
| NFR-004 | Code quality | New and changed Python passes `ruff check`, `ruff format --check` and `mypy` with 0 issues; every new function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-005 | Coverage | Every new branch or helper is executed by a test in this PR (diff-cover ≥ 90 %). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One bump path | The pin changes only through `spec-kitty service vendor`; a refusal stops the Mission and is reported, never worked around. | Technical | High | Open |
| C-002 | Read service is CI-only | The CLI never launches the read service; `spec-kitty service fetch --all` keeps excluding it. | Technical | High | Open |
| C-003 | No companion wheel | Nothing builds on PR #6949; its files are not touched beyond what this cut-over needs. | Business | High | Open |
| C-004 | Gates re-pointed, never loosened | No allowlist grows; a gate whose subject is removed is deleted with it (the freeze gate) or re-pointed to the new subject. | Technical | High | Open |
| C-005 | No change in spec-kitty-events | Events-side gaps found here are reported as residuals, not fixed. | Business | High | Open |
| C-006 | Out of scope | The write-service pin, #6195, charter-service pins, launcher behaviour, install docs (gap 12) and setup-doctor (gap 13) are not changed. | Business | High | Open |
| C-007 | Test policy | `make test-fast`, the owning test directories and the specific architectural gate files; never `make test-full` or the bare `tests/architectural/`. | Technical | High | Open |

### Key Entities

- **Service pin**: tag, commit, protocol versions, required core range, per-target asset (name, sha256), extras (name, sha256).
- **Pinned asset cache**: per service and tag, verified files; extras unpacked beside them, keyed by the archive digest.
- **Conformance fixtures / contract bundles / contract tools**: the three extras archives and the paths inside them that core's tests read.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 files remain under `services/`, and exactly 5 files (`fixture_0*.json`) remain under `contracts/`. — [build] · no-op passable: no
- **SC-002**: 100 % of the conformance, golden and oracle tests that read Java-service or contract data pass from the pinned release with the core copies absent. — [build] · no-op passable: no
- **SC-003**: The nightly compare over the pinned binary reports 0 differing Missions (677 compared at grounding). — [ratchet] · no-op passable: no
- **SC-004**: A release run refuses before build when any pinned service asset fails its digest. — [build] · no-op passable: no
- **SC-005**: 0 workflow, configuration or test references to a removed path remain. — [build] · no-op passable: no

## Assumptions

- `service-v0.1.0-rc.1` stays published with the digests recorded at grounding.
- GitHub release downloads are reachable from CI runners (they are today for packs and the vendor command).
- Attestation verification (`gh attestation verify`) is a follow-up; it cannot run in the authoring sandbox (Sigstore trust root unreachable) and the vendor command does not perform it (its own documented follow-up).

## Residuals (out of scope, recorded for the PR)

- Write-service pin: waits for a spec-kitty-events `service-v*` release carrying `command-cli` (events PR #173 merged; next tag).
- Charter-service pin: waits for the charter repository's first `service-v*` tag.
- spec-kitty-events carries no Python tests for `contracts/tools` or for the contract source layout yet; core's deleted tool and source-layout tests should be ported there.
- `gradle_pin_check.py` (events) has no acceptance-jvm-only CLI flag; core uses its `check_acceptance_jvm` function.
