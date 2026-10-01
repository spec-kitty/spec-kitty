# Mission Specification: Mission Status contract v1

**Mission Branch**: `issue-5558-mission-status-contract-v1`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Issue #5558 - "Mission Status contract v1: contracts/mission-status/openapi.yaml (split layout, Node-free tooling, CI)". Part of #5528; takes over the transport question from the closed #460; implements the content specified in #5529 (overview) and #957 (detail). Design: the maintainer design comment on #5528 (comment 5937187090).

## Summary

The Mission Status Read API is built contract-first. A versioned OpenAPI 3.1 document is the seam between a future read service and the dashboard and Desktop screens, so both sides can be built in parallel against one file. This Mission delivers that file, the conventions that let it scale past one module, and the CI that keeps it honest:

- a split, multi-file contract under `contracts/` (`_shared/` plus `mission-status/`), covering a read-only v1 slice of five resources;
- Node-free validate, bundle, lint and breaking-change checks in a new path-filtered workflow;
- a reality-check test that proves the contract fits this repository's own Missions as today's readers see them;
- a release workflow that publishes the bundled document and its checksum, with a dry run proven in the PR;
- CODEOWNERS for `contracts/`.

It adds a contract and CI only. No Python product code under `src/` changes, no status event schema changes, and no CLI behaviour changes.

## Terminology (binding for this spec and for the contract)

- **Mission**, never "feature" (charter Terminology Canon). Contract schema names, examples and descriptions follow the same rule.
- **Status lane**: one of the work-package lifecycle states of the status domain (glossary term `lane`: planned, claimed, in_progress, for_review, in_review, approved, done, blocked, canceled; plus the non-display values genesis and uninitialized). This is the only meaning the contract gives the word lane.
- **Execution lane**: a parallel implementation lane recorded in a Mission's `lanes.json` (`lane_id`, `wp_ids`, `write_scope`, `depends_on_lanes`, `parallel_group`). It is a different concept that happens to share a word. Execution lanes are not part of v1 and appear nowhere in the contract. This spec never uses the bare word "lane" for either; the glossary lists `lane` only for the status meaning, and `execution lane` is not yet a glossary term (see Risks).
- **Stream cursor**: the event-log tail position `{offset, invariant}` of the CLI's tail reader (a byte offset on a line boundary plus a SHA-256 of the last consumed line). **Page cursor**: the opaque pagination token in `_shared/`. The two are different schemas with different names; the bare word "cursor" is not used in contract field names.
- **Lifecycle status**: the Mission-level value (active, planned, done, draft, discarded). **Mission phase**: a step of the Mission workflow (specify, plan, tasks, implement, review). **Phase label**: the optional free-text `phase` grouping field in a work package's frontmatter. Three different things, three different names.
- **Bundle**: the single resolved `openapi.yaml` produced from a module's split files by CI. It is a build product and is never committed.
- **Provisional**: an element marked `x-provisional` that may change without a major version bump until decided on #5528.

## Clarifications

The following are binding maintainer and design decisions. They are not options for a reviewer or implementer to re-litigate; a reviewer checks the spec, plan and implementation against them. Decisions CL-1 to CL-10 were fixed before this spec was written; D-1 to D-14 further down are derived by the spec author from the grounded data shapes and are explicitly open to reviewer challenge.

### CL-1 - Build now; the PR stays a draft until the design is acknowledged

The Mission is built now. The single Mission PR is opened and stays a **draft** until a maintainer acknowledges the design on #5528. Until then it is not marked ready for review and not labelled `ready-for-squad`. The PR body links the acknowledgement once it exists. This is how the contributing guide's "large changes are agreed first" rule is satisfied for a change that introduces a new top-level tree, a new toolchain and a new release stream.

### CL-2 - The reality-check test, its marker, and its CI placement

- The reality-check test is `tests/contract/test_mission_status_reality.py` (a new path) and carries `pytest.mark.corpus` as a real marker application (a module-level `pytestmark` entry or a decorator), not a prose mention.
- `contracts/**` is added to the CI router's `corpus` path filter in `.github/workflows/ci-router.yml`, so a contracts-only change selects the router's marker-selected corpus job.
- The new path-filtered contracts workflow also runs the reality check, **without** running it twice per change.

What the architectural gates actually demand (read from this checkout; the spec requires all of it, see FR-020):

1. `tests/architectural/test_ci_corpus_trigger_completeness.py` pins the set of corpus-marked test modules to a hand-maintained registry (`_CORPUS_MARKED_MODULES`) with equality in both directions. The new module must be added to that registry in the same change, or the gate fails. The same file's `_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS` document the corpus path set and gain `contracts/**` and `contracts/` to stay a faithful mirror of the router. It also requires the `corpus` marker to stay registered in `pytest.ini`; that marker's description lists the corpus paths and is updated to name `contracts/**`.
2. `tests/architectural/test_no_duplicate_suite_execution.py` treats every workflow with a change-triggered event (pull_request, or push with branch or path filters; unknown trigger shapes count as change-triggered; only schedule, workflow_dispatch, workflow_call, release and tags-only push are exempt) whose job reaches pytest as a suite execution. Each such `(workflow, job)` pair must be listed in `AUTHORIZED_PER_CHANGE_SUITE_JOBS` with a rationale, and each authorised job may invoke pytest once. A new path-filtered contracts job that runs pytest is therefore a deliberate, reasoned ledger addition, never a free addition.
3. `tests/architectural/test_workflow_coherence.py` requires the set of workflows that invoke pytest to equal the allowlist `WORKFLOW_FILES` in `tests/architectural/_gate_coverage.py` (a new pytest-invoking workflow file, of any trigger, must be added there), and requires every router filter glob to match at least one tracked path (`contracts/**` does, `contracts/fixtures/` exists today).
4. `.github/ci-module-registry.yml` already lists `tests/contract` as a registry-excluded directory whose only per-PR home is the marker-selected router corpus job, and records that claiming it in a module row "would double-run it". The registry is therefore **not** edited by this Mission.

The required end state is an invariant, not a specific job layout: on any change that touches `contracts/**`, the reality-check test body executes in **exactly one** blocking per-change job (never zero, never two), and both architectural gates above stay green with every ledger or allowlist addition justified in the plan.

### CL-3 - Release tag namespace

The release tag is `contract-mission-status-v1.0.0`: no leading `v`, so the CLI's `v*.*.*` release machinery never sees it. This was verified on this checkout: `.github/workflows/release.yml` has a single tag trigger, `v*.*.*` (plus a manual dispatch that takes an existing release tag); `scripts/release/validate_release.py` (`discover_release_tags`) keeps only tags that start with `v` and match the release version pattern; `src/specify_cli/release/changelog.py` lists tags with the pattern `v*`. Non-`v` tags already exist in the repository (`crossrepo-bugfix-pack-2026-02-24`, `saas-hardening-2026-02-24`). The contract release workflow's tag trigger must not match any CLI release tag, and the CLI release trigger must not match a contract tag; this is asserted (FR-022).

### CL-4 - Release workflow ships in the PR; the tag is pushed after merge

The PR ships the release workflow with a `workflow_dispatch` dry run that builds the bundle and its sha256 as a workflow artifact, and that dry run is green in the PR. After merge, a maintainer pushes the tag `contract-mission-status-v1.0.0`. That tag push is recorded as a **close-out step** of this Mission (in the PR body and the Mission close-out record), not as a follow-up issue. Because GitHub resolves a manually dispatched workflow from the default branch, the dry run's evidence in the PR must come from a run that exists on the PR branch (see FR-022 and Open Question OQ-2).

### CL-5 - Contract-first, split layout, conventions

- OpenAPI 3.1, contract-first. Humans edit split files; CI produces the bundle; the bundle is never committed.
- Layout: `contracts/README.md` (conventions); `contracts/_shared/` (cross-module pieces only: `Problem` as `application/problem+json`, the page cursor, `PageInfo`; `schemas/`, `parameters/`, `responses/`, each with an `_index.yaml` registry); `contracts/mission-status/` with a root `openapi.yaml` (info, servers, tags, and a path-to-file map only), `paths/` (one file per path item, named after the path with `/` turned into `_` and `{param}` kept, for example `missions_{missionId}.yaml`), `schemas/` (one file per schema, named like the schema, plus `_index.yaml`), `parameters/`, `responses/`, `examples/`, and `CHANGELOG.md`.
- Each module is one document with its own `info.version` and the `/api/v1` prefix. Later modules (for example write surfaces) are sibling folders versioned independently.
- `$ref`s between files are relative file paths; there are no hand-written `~1` JSON pointers; the root maps paths to files.
- `contracts/fixtures/` (the existing handoff fixtures read by `tests/contract/test_handoff_fixtures.py`) is left untouched.

### CL-6 - Node-free tooling and CI shape

- Validate and bundle: a small Gradle build under `contracts/` using the openapi-generator Gradle plugin (JVM), which reads multi-file specs; it validates each module and bundles it with the `openapi-yaml` generator.
- Lint: vacuum (a Go binary) with a Spectral-format ruleset kept in `contracts/`.
- Breaking changes: oasdiff (a Go binary) compares each module's bundle with its last release; a breaking change fails unless the major version moves.
- Tool versions are pinned, downloaded artefacts are checksum-verified, and third-party GitHub Actions are pinned to full commit SHAs (the repository's existing workflows do the same).
- The workflow is path-filtered on `contracts/**` and separate from the Python suites, so the Python suites' critical path is unchanged.
- `CODEOWNERS` for `contracts/` names `@stijn-dejongh` and `@MOES-Media`. No `.github/CODEOWNERS` exists today; it is a new file. The charter records that nothing on GitHub enforces review, so this is advisory routing, and the PR body says so.
- No Node toolchain is introduced anywhere.

### CL-7 - The v1 slice

Read-only resources, all under `/api/v1`: `GET /project`, `GET /missions`, `GET /missions/{missionId}`, `GET /missions/{missionId}/work-packages/{wpId}`, and `GET /events` (`text/event-stream`, one schema per event's `data`, documented as a convention because OpenAPI has no native event-stream schema).

### CL-8 - Data decisions

- Raw nine-status-lane counts, with no grouping. Board columns are a documented consumer mapping, not part of the contract.
- Identity is the ULID `missionId`. `displayNumber` is display-only (numbers repeat).
- Lifecycle status uses today's five values: `active`, `planned`, `done`, `draft`, `discarded`.
- Topology has five values: `lanes`, `single_branch`, `coord`, `lanes_with_coord`, `unknown`.
- Staleness and next action are marked `x-provisional` until decided on #5528.
- Mission phases: specify, plan and tasks come from artifacts and lifecycle events; implement and review are derived from status lanes and are marked as derived.
- No absolute paths (`feedback_path`, `record_path`, `prompt_path`, `feature_dir`) and no e-mail addresses in any payload or example. Actors are agent, profile and role handles.
- Every v1 schema field cites its source in the status domain.

### CL-9 - Scope exclusions

Out of v1: artifact reads (#5533) and write surfaces (#5231). Out of this Mission: the read service implementation and the dashboard and Desktop screens (separate Missions against this contract).

### CL-10 - Silent success is forbidden

Every check this Mission adds (validate, bundle, lint, breaking-change diff, reality check, release dry run, pin and checksum verification) must fail loudly when it cannot do its job: missing tool, empty corpus, missing release tag, checksum mismatch, zero inputs. A check that "passes" because it examined nothing is a defect. FR-021 and the fail-loud matrix in FR-025 make this testable.

### Derived decisions (spec author; reviewable)

These follow from the grounded data shapes and from the decisions above. A reviewer may overturn any of them; if so, the affected FRs change with them.

- **D-1 Status-lane field names.** Contract properties that carry a status lane use the stem `statusLane` (`statusLane`, `statusLaneCounts`, `fromStatusLane`, `toStatusLane`) and the enum schema is `StatusLane`, so a reader of the contract cannot confuse a status lane with an execution lane. The `lane` stem is not used.
- **D-2 Closed response schemas.** Response object schemas are closed (`additionalProperties: false`, or `unevaluatedProperties: false` where composed). Documented open maps are the only exceptions (for example subtask id to status lane). Without this the reality check would pass on payloads carrying any junk, which is the vacuous-pass failure this Mission exists to avoid. Adding a response property is still a non-breaking, minor-version change.
- **D-3 Citation extensions.** Every property of every resource schema carries `x-source` (repo-relative file path plus symbol, optionally a line number) or, where the value is computed from several sources, `x-derived` (a one-sentence derivation plus the `x-source` of each input). Line numbers rot; the path and symbol are what the citation check resolves.
- **D-4 `wpTotal` definition.** `wpTotal` is the number of work packages in the reduced status snapshot (`len(snapshot.work_packages)`), i.e. event-sourced, not a count of `tasks/WP*.md` files. A work package with a file but no events, or events but no file, is counted differently by the existing dashboard; the contract follows the snapshot.
- **D-5 Lifecycle derivation.** `lifecycleStatus` re-expresses the existing derivation over the nine-status-lane counts with unchanged semantics, quirks included (a Mission whose only remaining work packages are `blocked` reads as `planned`; all-`canceled` with `accepted_at` set reads as `done`). v1 pins today's behaviour; it does not fix quirks.
- **D-6 Mission-level fields without a reader are excluded.** `openDecisionCount` (no reader exists), `retrospective` (the reducer matches an `event_name` envelope that does not occur in the corpus, so it is effectively never populated, and its record path is an absolute host path), `done evidence` (free-text commands and file lists), `claim.shellPid` (host-local), and any `promptPath` are not in v1.
- **D-7 Provisional semantics.** Changes to an `x-provisional` element are recorded in the module `CHANGELOG.md` under a "Provisional" heading and do not by themselves require a major version bump. Removing `x-provisional` is a minor-version change, also recorded. The breaking-change check still runs over provisional elements and reports them separately; it never excludes them silently.
- **D-8 Event stream scope.** Every event's `data` carries `missionId` and the stream cursor of that Mission's own log. A stream cursor is valid for exactly one physical event log (the primary and the coordination copy of a Mission's log are different files with different offsets). The event stream therefore never forwards raw log rows: it emits named, projected kinds only. v1 requires at least: a status-lane transition kind, a Mission lifecycle marker kind, and a log-truncated (resync) kind. Annotation and retrospective rows are not exposed in v1 (free-text notes and absolute record paths).
- **D-9 Event projection is mandatory.** The CLI's tail reader passes every JSON row through (status transitions, annotations, lifecycle rows, retrospective rows), and the corpus contains absolute paths and e-mail addresses in exactly those rows. The contract's event schemas therefore define the projected shape, and the leak rules (FR-012) apply to event data.
- **D-10 Actor handles.** An actor is projected to `{tool, role, profile, model}`, each a nullable `ActorHandle` string constrained to a conservative handle pattern (letters, digits, `.`, `_`, `:`, `-`; no `@`, no `/`, no whitespace; at most 128 characters). A source actor string that does not match is projected to `null`, never passed through. Colon-encoded forms such as `claude:sonnet:implementer:implementer` match.
- **D-11 `topology`.** A Mission with no stored topology (49 of 538 at survey time), or with a stored value outside the four known shapes, projects to `unknown`. It does not inherit the runtime's "unstamped means lanes" default, because that would state something the metadata does not say.
- **D-12 First-release baseline.** For the breaking-change check, "no previous release tag exists" is a distinct, loudly reported state, allowed only for the module's initial version; see FR-016.
- **D-13 `missionType` is an open string.** Mission types can come from organisation packs, so the contract does not close the set to the three observed built-in values. A typeless Mission is `null`.
- **D-14 Free text.** Authored markdown (`promptMarkdown`, returned only on request) is passed through as authored and is the only field excluded from the leak scan, and says so in its schema description. Every other string value is subject to the leak scan; a structured string that fails it (for example a cancellation reason containing an e-mail address) is projected to `null`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a screen or a service against one pinned, trustworthy file (Priority: P1)

A developer building the dashboard or Desktop screens, and a developer building the read service, each work against the same versioned contract. They take the bundled `openapi.yaml` from a release, verify its sha256, and generate or mock from it. Every field they see names where it comes from in the status domain, and fields that are not settled are marked provisional.

**Why this priority**: it is the reason the Mission exists; both sides can only proceed in parallel if the file is trustworthy and pinnable.

**Independent Test**: build the bundle from a clean checkout, verify that it contains the five v1 paths, that every property of every resource schema carries a source citation, that every provisional element carries `x-provisional`, and that every cited path resolves in the checkout.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the contract build runs, **Then** one bundled `openapi.yaml` is produced containing exactly the five v1 path items and no unresolved reference.
2. **Given** a resource schema property with no citation, **When** the citation check runs, **Then** it fails naming the property (and a property citing a path that does not exist also fails).
3. **Given** the bundle, **When** a consumer reads `GET /missions` and `GET /missions/{missionId}`, **Then** the status-lane vocabulary is the raw nine values, lifecycle status has five values and topology has five values, with no board-column grouping anywhere.

### User Story 2 - A maintainer is protected from drift and accidental breaking changes (Priority: P1)

A maintainer opens a PR that touches `contracts/**`. A dedicated workflow validates, bundles, lints and breaking-change-checks every module, without touching the Python suites' critical path. Each check has been shown to fail on a planted violation, so a green check means something.

**Why this priority**: an unguarded contract drifts from reality and from its consumers; a guard that cannot fail is worse than none.

**Independent Test**: for each of validate, bundle, lint and breaking-change diff, a planted violation makes that check (and only that check's job) fail with a message naming the cause; the same fixture without the violation passes.

**Acceptance Scenarios**:

1. **Given** a module whose path file references a schema file that does not exist, **When** validate runs, **Then** it fails and names the unresolved reference.
2. **Given** a response schema that violates a ruleset rule, **When** lint runs, **Then** it fails; the clean fixture passes under the same ruleset (positive control).
3. **Given** a baseline bundle and a candidate that removes a response property or an enum value, **When** the breaking-change check runs without a major version bump, **Then** it fails; with a major bump it passes.
4. **Given** a PR that touches only `contracts/**`, **When** CI runs, **Then** the contracts workflow runs and none of the Python module-shard jobs is newly selected by this Mission's edits beyond the corpus lane named in CL-2.

### User Story 3 - The contract is proven against this repository's own Missions (Priority: P1)

Before anything is built on the contract, a test builds the overview and detail payloads for every Mission in this repository's `kitty-specs/` with today's readers and validates each against the contract. A contract that does not match the status ledger fails here.

**Why this priority**: a contract written from prototypes or memory will not match the stored data; this is the gate that makes the "grounded in what the domain actually stores" claim checkable.

**Independent Test**: run `tests/contract/test_mission_status_reality.py`; it validates at least the floor number of Missions and every work package of those Missions, with zero exclusions, and fails on a planted mismatch.

**Acceptance Scenarios**:

1. **Given** the repository's committed Missions, **When** the reality check runs, **Then** every Mission's overview and detail payload, and every work package's detail payload, validates against the contract.
2. **Given** a planted payload carrying an e-mail address, an absolute path, an unknown status lane, or an extra property, **When** the same validation runs, **Then** it fails (and an identical clean payload passes).
3. **Given** a Mission with no stored topology, no event log, a null display number or a null status lane, **When** its payload is built, **Then** it validates using the documented nullable or `unknown` forms rather than being skipped.

### User Story 4 - Cut a release consumers can pin (Priority: P2)

A maintainer pushes the tag `contract-mission-status-v1.0.0` after merge. The release workflow publishes the bundled `openapi.yaml` and its sha256, and consumers pin by checksum. Before merge, a dry run of the same workflow in the PR builds the same two files as an artifact.

**Why this priority**: the pin is what consumers rely on, but it cannot be exercised for real until after merge, so the PR proves everything except publication.

**Independent Test**: the dry run's artifact contains a non-empty bundle and a checksum file, and `sha256sum -c` over them succeeds; a corrupted checksum makes the dry run fail.

**Acceptance Scenarios**:

1. **Given** the PR, **When** the release workflow's dry run runs, **Then** it uploads the bundle and its sha256 as an artifact, verifies them, and does not publish anything.
2. **Given** a tag whose version differs from the module's `info.version`, **When** the release workflow runs, **Then** it fails before publishing.
3. **Given** the contract tag and the CLI release tags, **When** the workflow trigger patterns are compared, **Then** neither matches the other's tags.

### User Story 5 - Future modules follow the same conventions, and the right people review (Priority: P2)

A contributor adding a second module (for example write surfaces) reads `contracts/README.md`, copies the layout, and the same workflow covers it. `CODEOWNERS` routes `contracts/` changes to the contract owners.

**Why this priority**: the conventions are the long-term value; this Mission only needs to make them discoverable and enforced.

**Independent Test**: add a throwaway second module folder following the README and confirm the workflow picks it up with no workflow edit; remove its root file and confirm the discovery check fails rather than skipping.

**Acceptance Scenarios**:

1. **Given** `contracts/README.md`, **When** a reader looks for naming, `$ref`, versioning and provisional conventions, **Then** each is stated with an example.
2. **Given** `.github/CODEOWNERS`, **When** it is parsed, **Then** `contracts/` is owned by both named handles.

### Edge Cases

- **Empty or shrunken corpus.** The reality check requires a floor of at least 500 Missions with `meta.json` (538 at survey time). Zero Missions, or fewer than the floor, fails loudly; it never passes vacuously. It also fails if it validated zero work packages, or if a status lane, topology value or lifecycle value that must be exercised never occurs and no fixture covers it.
- **Values the corpus cannot exercise.** `discarded_at` occurs in zero committed Missions, so `discarded` cannot be proven from the corpus. A fixture-built payload (positive control) proves the branch, and the examples validate.
- **No previous release tag.** The first release has no baseline. The breaking-change check reports that state explicitly (FR-016), allows it only for the initial module version, and fails in every other case, including a shallow checkout that cannot see tags.
- **Field absent from real data.** `topology` is absent on about 9 percent of Missions; `mission_number` is null on about half; `mid8` resolves to an empty string when there is no `mission_id`; a work package with no events has a null status lane; many Missions have no event log on the primary checkout (coordination or single-branch Missions) and read as `draft`; resolved-binding fields exist for only about a quarter of work packages. Each projects to a documented nullable, empty or `unknown` form. A required property absent from real data is a contract defect to fix, never a reason to skip the Mission.
- **Unknown enum values.** A status lane, lifecycle status or topology value from real data outside the contract's enum fails the reality check loudly (the contract lags the domain); it is neither coerced silently nor dropped. Topology is the one deliberate exception: unstamped and unrecognised values map to `unknown` (D-11).
- **Sentinels and variants in real data.** The model sentinel `__resolved_model_absent__` projects to null; frontmatter `agent` values can be dicts, plain strings or colon-encoded strings; observed `execution_mode` values include a quoted `"code_change"`; actors can be an e-mail address, `user`, `finalize-tasks`, `migration`. The projection normalises each explicitly and documents it; it does not skip the record.
- **Duplicate display numbers.** Display numbers repeat (41, 45, 65, 80 and 83 repeat in the corpus). `displayNumber` is never used as an identifier, and the reality check asserts `missionId` is unique across the corpus.
- **Missions without a usable ULID.** The dashboard's `legacy:<slug>` and `orphan:<slug>` pseudo-keys are dormant in this corpus and are not part of v1. A Mission directory with no valid ULID `mission_id` is not representable; the reality check fails on one rather than inventing an id.
- **Absolute paths and e-mail in source rows.** About 383 event lines contain an absolute path (`feedback_path` on 271 events, `record_path` on retrospective rows) and e-mail addresses occur in `MissionCreated` `payload.actor` and `accepted_by`. None may reach a payload, an event or an example.
- **Readers that write.** Some existing read paths write to disk (the dashboard's encoding auto-fix; a past query-only `next` call that rewrote a tracked `status.json`). The reality check proves the readers it uses left every tracked Mission artifact byte-identical.
- **Router reshaping while this PR is open.** An open CI-rework PR (#5557) re-homes the corpus lane (a blocking router job running named node ids, with the marker-selected remainder run elsewhere). After rebase the test must still be selected by exactly one blocking per-change job; this is re-verified, not assumed.
- **Dangling citations.** An open PR (#5545) removes the CLI-bundled dashboard, which many citations name. A citation that stops resolving fails the citation check loudly after rebase; it is re-pointed or the derivation is recorded in the contract itself.
- **Unknown or pre-existing red tests.** The reality check is judged against a recorded baseline (see Risks), so a pre-existing red elsewhere on the base is neither blamed on nor hidden by this Mission.
- **Mid-flight Missions.** See Reflexivity below.

### Reflexivity: Missions in flight

This Mission adds a contract tree, CI workflows, one CODEOWNERS file and tests. It does not change `src/`, the status event schema, `meta.json` handling, any CLI command, or any migration. Missions already in flight are unaffected in how they run. One coupling is new and is stated plainly: the reality check reads the repository's committed Missions, so a committed Mission whose stored data a reader cannot project will fail a corpus-marked job for an unrelated PR, and this Mission's own scaffold directory is part of that corpus. The router's corpus path filter deliberately excludes bare `status.events.jsonl` and `kitty-specs/**` (so routine status churn does not trigger the lane), but the lane's tests read whatever status data is on the checkout when they run. Triage of such a failure follows the baseline and attribution rules in Risks.

## Requirements *(mandatory)*

<!--
  Legend (tactic acceptance-criteria-non-vacuity): delivery [build] = new behaviour. No-op passable? = whether a
  do-nothing change would already satisfy the criterion's check. Every "no" below is backed by a named observable
  that a no-op cannot produce, in the Acceptance Criteria that follow the table.
-->

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Contracts layout and README conventions | As a contributor, I want one documented layout and naming scheme so that every later module is built the same way. | High | Open | [build] | no |
| FR-002 | Shared building blocks | As a module author, I want `Problem`, the page cursor and `PageInfo` (plus shared parameters and responses) defined once so that modules do not diverge. | High | Open | [build] | no |
| FR-003 | `GET /project` resource | As a screen developer, I want the project name and Mission count so that I can render a project header. | High | Open | [build] | no |
| FR-004 | `GET /missions` overview resource | As a screen developer, I want one overview record per Mission, paginated and deterministically ordered, so that I can render the Mission list without reading any work package. | High | Open | [build] | no |
| FR-005 | `GET /missions/{missionId}` detail resource | As a screen developer, I want a Mission's phases and work package summaries so that I can render a Mission page. | High | Open | [build] | no |
| FR-006 | `GET /missions/{missionId}/work-packages/{wpId}` resource | As a screen developer, I want one work package's authored plan, resolved state, review evidence, readiness and history, with the prompt body only on request, so that I can render a work package page. | High | Open | [build] | no |
| FR-007 | `GET /events` event stream resource | As a screen developer, I want a documented change stream with one schema per event kind so that I can update views without polling. | High | Open | [build] | no |
| FR-008 | Fixed v1 vocabularies | As a consumer, I want the status-lane, lifecycle, topology and phase vocabularies fixed and ungrouped so that my own mapping is stable. | High | Open | [build] | no |
| FR-009 | Identity and display rules | As a consumer, I want a ULID `missionId` as the only identifier and `displayNumber` as display-only so that repeated numbers cannot collide. | High | Open | [build] | no |
| FR-010 | Source citation on every field | As a reviewer, I want each v1 field to cite where the status domain stores or derives it so that I can check the contract against the code. | High | Open | [build] | no |
| FR-011 | Provisional marking | As a consumer, I want unsettled fields marked `x-provisional` so that I do not build on them as if they were stable. | High | Open | [build] | no |
| FR-012 | No host paths, no e-mail addresses | As a maintainer of a public repository and an operator of private ones, I want no absolute path and no e-mail address in any payload, event or example so that the API cannot leak local identity. | High | Open | [build] | no |
| FR-013 | Closed schemas and validating examples | As a consumer and as the reality check, I want closed response schemas and examples that validate so that a payload with a wrong or extra field fails. | High | Open | [build] | no |
| FR-014 | Validate and bundle check | As a maintainer, I want every module validated and bundled to one document in CI so that structural errors and unresolved references fail the PR. | High | Open | [build] | no |
| FR-015 | Lint check | As a maintainer, I want a Spectral-format ruleset enforced by vacuum so that conventions are machine-checked. | High | Open | [build] | no |
| FR-016 | Breaking-change check | As a consumer, I want a breaking change to fail CI unless the major version moves so that I can pin a major version safely. | High | Open | [build] | no |
| FR-017 | Contracts workflow shape | As a maintainer, I want a path-filtered workflow separate from the Python suites so that contract work does not slow the Python critical path. | High | Open | [build] | no |
| FR-018 | Pinned and verified tooling | As a maintainer, I want pinned tool versions, verified checksums and SHA-pinned actions so that the build is reproducible and supply-chain safe. | High | Open | [build] | no |
| FR-019 | Reality-check test | As a maintainer, I want the contract validated against payloads built from this repository's own Missions with today's readers so that a contract that does not match the ledger fails before anything is built on it. | High | Open | [build] | no |
| FR-020 | CI placement of the reality check | As a maintainer, I want the reality check selected by exactly one blocking per-change job and the architectural gates kept green so that it neither goes unrun nor runs twice. | High | Open | [build] | no |
| FR-021 | Planted-violation proof for every check | As a reviewer, I want each check shown failing on a planted violation, with a clean positive control, so that a green check is evidence. | High | Open | [build] | no |
| FR-022 | Release workflow, dry run and tag namespace | As a consumer, I want a release that publishes the bundle and its checksum under a tag the CLI release machinery cannot see, and a maintainer wants that proven in the PR except for publication. | High | Open | [build] | no |
| FR-023 | CODEOWNERS for `contracts/` | As a maintainer, I want contract changes routed to the contract owners so that the contract has accountable reviewers. | Medium | Open | [build] | no |
| FR-024 | Module versioning and CHANGELOG | As a consumer, I want a module `info.version`, a `CHANGELOG.md` and stated versioning rules so that I can tell what changed between pins. | Medium | Open | [build] | no |
| FR-025 | Loud failure when a check cannot do its job | As a maintainer, I want every check to fail loudly rather than pass vacuously so that a green run always means the check examined something. | High | Open | [build] | no |

### Acceptance Criteria

Each criterion names the observable that changes and how it fails. "Planted" means a fixture or throwaway change committed only to demonstrate failure (see FR-021 for where the evidence lives).

**FR-001 - Layout and conventions**

- A layout check over `contracts/` fails (naming the offending path) when: a file under a module's `paths/` is not named after a path item per the `/` to `_`, `{param}` kept rule; the root `openapi.yaml` maps a path to a file that does not exist; a `paths/` file is referenced by no root entry (orphan); a schema file's name differs from the schema it defines; an `_index.yaml` lists a file that does not exist or omits one that does; a `$ref` is a URL, an absolute path, or contains a `~1` pointer; `_shared/` is referenced for a module-specific piece; or a bundled document (a file containing the resolved, inlined component set of a module) is tracked under `contracts/`. Each is a planted violation with a clean positive control on the same fixture.
- `contracts/README.md` states, with one example each: the layout, the path-file naming rule, relative `$ref` rules, `_shared/` admission criteria, per-module `info.version` and the `/api/v1` prefix, the `x-source`, `x-derived` and `x-provisional` extensions, the status lane versus execution lane terminology, and the rule that the bundle is a build product. A markdown lint of the README and both `CHANGELOG.md` files passes under the repository's `.markdownlint-cli2.jsonc`.
- `git diff --stat` for the PR shows no change under `contracts/fixtures/`.

**FR-002 - Shared building blocks**

- `contracts/_shared/` defines `Problem` (media type `application/problem+json`), a page cursor schema, `PageInfo`, and the shared parameters and responses the five resources use, each listed in its `_index.yaml`. Every non-2xx response in the module references the shared `Problem` response. A planted path file declaring an error response with a different content type fails lint.
- The page cursor is opaque to consumers and has no schema relationship to the stream cursor.

**FR-003 - `GET /project`**

- Returns `name` (the project slug, cited to `.kittify/config.yaml` `project.slug` and `ProjectIdentity.project_slug` in `src/specify_cli/identity/project.py`) and `missionCount` (the number of Missions in the registry, cited to `build_mission_registry` in `src/specify_cli/dashboard/scanner.py`). There is no separate display name in the domain, and the response has no project path, no worktree path and no tokens.
- The reality check asserts `missionCount` equals the number of overview records it built.

**FR-004 - `GET /missions`**

- Each record carries the fields in the Contract Field Catalogue (Mission overview). A response schema missing any catalogue field, or carrying one not in the catalogue, fails the reality check (closed schema, D-2).
- Ordering is deterministic and documented in the operation description; two requests over unchanged data return the same order. The list is paginated with the shared page cursor; the first page, a middle page and an exhausted cursor each have an example.
- Overview payloads are built without reading any work package file (`tasks/WP*.md`): `wpTotal` is the snapshot's work package count (D-4).

**FR-005 - Mission detail**

- Returns the overview fields plus `phases` and `workPackages`. `phases` always contains exactly the five Mission phases (specify, plan, tasks, implement, review); each entry carries a `basis` that is `artifact`, `lifecycle_event` or `derived_from_status_lanes`, and the implement and review entries are always `derived_from_status_lanes` with the derivation rule written in the schema description. A phase entry without a `basis`, or an implement or review entry claiming an artifact basis, fails validation.
- `workPackages` entries are summaries (identifier, title, phase label, status lane, dependencies, readiness, subtask progress, last transition time) and never include the prompt body.

**FR-006 - Work package**

- Returns the fields in the Contract Field Catalogue (Work package). The prompt body (`promptMarkdown`) is returned only when the request asks for it with an explicit query parameter, and an example proves both the absent and the present case. No property named `promptPath` or `prompt_path` exists.
- Resolved state is read from the status snapshot, never from stale runtime keys left in WP frontmatter (`agent`, `shell_pid`, `lane`, `assignee`, `review_status`); a planted payload built from frontmatter-only state is detected by the reality check where it disagrees with the snapshot.
- The review block exposes the review reference (`review-cycle://...` or the legacy free text reference), the verdict (`approved` or `changes_requested`) and the reviewer handle; it never exposes `feedback_path`.

**FR-007 - Event stream**

- `events.yaml` declares a `200` response with content type `text/event-stream`, documents the stream convention (event name, `id`, resume behaviour, heartbeat if any, the rule that consumers ignore unknown event names) in prose, and maps each event name to one data schema. The mapping is checked: every event name referenced in the description has a schema, and every schema in the mapping is referenced by exactly one name. A planted event name with no schema, or a schema with no name, fails the check.
- At minimum three kinds are defined (D-8): a status-lane transition, a Mission lifecycle marker, and a log-truncated resync kind with `reason` limited to `size_shrink` and `content_mismatch`. Every event's data carries `missionId` and a stream cursor.
- Resume: the request carries a stream cursor; the documented refusal reasons are exactly `negative`, `out_of_range`, `misaligned` and `content_mismatch` (the reason values of the tail reader's `ResumeRefused`, `specify_cli/status/tail_reader.py:84`), each mapped to a `Problem` response. An example exists for each.
- Raw log rows never appear: a planted event example carrying an absolute path or e-mail fails the leak scan (FR-012).

**FR-008 - Vocabularies**

- `StatusLane` lists exactly the nine display values: planned, claimed, in_progress, for_review, in_review, approved, done, blocked, canceled. `statusLaneCounts` has exactly those nine keys, each required, none grouped, and neither `genesis` nor `uninitialized` is a key (a Mission's event-less work package reads as a null `statusLane`).
- `LifecycleStatus` is exactly active, planned, done, draft, discarded. `Topology` is exactly lanes, single_branch, coord, lanes_with_coord, unknown. Adding or removing a value in any of the three fails the breaking-change check without a version move and fails an enum-pinning check in the reality check's fixtures.
- The README documents the board-column mapping as a consumer convention and the contract contains no `columns` or board grouping schema.

**FR-009 - Identity**

- `missionId` is a 26 character Crockford ULID (pattern `^[0-9A-HJKMNP-TV-Z]{26}$`, the pattern of the status domain's identifier), and is the only identifier in every path parameter that selects a Mission. `displayNumber` is nullable, described as display-only, and is not accepted as a path parameter anywhere. `mid8` is nullable (null when there is no Mission id), never an empty string.
- The reality check fails if two corpus Missions share a `missionId`, and passes when Missions share a `displayNumber`.

**FR-010 - Citations**

- A citation check fails when a property of a resource schema has neither `x-source` nor `x-derived`, when a cited file does not exist in the checkout, or when a cited symbol is not found in the cited file. It fails by naming the property and the unresolved citation. It requires a non-zero number of citations to have been checked (it fails on zero).
- Where a citation can name a status-domain reader (`src/specify_cli/status/`, `src/specify_cli/mission_metadata.py`, `src/mission_runtime/`), it does so in preference to the dashboard scanner; a derivation that exists only in `src/specify_cli/dashboard/scanner.py` (lifecycle derivation, workflow phase, next action) is cited there and also restated in the schema description, so the contract stands on its own if that code moves.

**FR-011 - Provisional**

- Staleness (per work package; the domain's `StaleState`: fresh, stale or not applicable, plus reason and minutes since last commit, which needs git and worktrees and so is not computable from events alone) and next action (a nullable prose string; the domain returns one of three prose strings or null) carry `x-provisional: true` with a description naming the open decision on #5528. A check fails if either lacks the marker, and fails if any element carries `x-provisional` without a description that names what is undecided.
- Provisional fields are nullable. Because the reality check cannot compute staleness (it has no worktrees), its payloads carry null there; `examples/` carries populated provisional values that validate, so the non-null branches are exercised.

**FR-012 - No leaks**

- No property in the contract tree is named `feedback_path`, `record_path`, `prompt_path`, `feature_dir`, `worktree` path, `project_path`, or camel-case forms of those (`feedbackPath`, `recordPath`, `promptPath`, `featureDir`), and no property carries an absolute path. A planted property with any of those names fails a name check.
- A value scan runs over every example and every payload the reality check builds (all string values except `promptMarkdown`, D-14). A value is an absolute host path if it starts with `/`, `~/` or a drive prefix, or contains a home-directory, user-profile or temporary-directory path segment (the platform conventions for Linux, macOS and Windows hosts); a value is an e-mail address if it matches the usual local-part-at-domain shape. The scan has a same-fixture positive control (a planted value of each kind is detected) and a floor (it fails when it scanned zero values).
- Actor values are `ActorHandle` strings (D-10). The reality check's corpus contains source actors that are e-mail addresses or free text; the check asserts they projected to null, so the redaction is exercised, not assumed.
- Residual risk, stated: a handle-shaped string can still be a person's account name (the status domain has recorded an operator's OS or git user name in actor-like fields). The contract cannot prove a handle is not a person's name; the shape rule and the value scan reduce, not eliminate, that risk (see Risks).

**FR-013 - Closed schemas and examples**

- Response object schemas are closed (D-2). `examples/` holds at least one validating example per resource and per event kind, plus the provisional-populated and discarded-Mission examples. A validate step fails when an example does not validate against the schema it is attached to, and when `examples/` contains a file no schema or operation references.

**FR-014 - Validate and bundle**

- The workflow validates every module found under `contracts/` (a module is a directory with a root `openapi.yaml`) and bundles each to one `openapi.yaml`. It reports the number of modules validated and fails when that number is zero.
- The bundle contains the five v1 path items and no remaining relative file `$ref`. A planted dangling reference, a planted schema that breaks OpenAPI 3.1, and a planted module whose root file is missing each fail the job.
- Bundling is deterministic: two consecutive builds of the same checkout produce byte-identical files (the sha256 of both is compared and the job fails on a difference).
- The bundle is uploaded as a workflow artifact and is never committed (a tracked bundle fails FR-001's check).

**FR-015 - Lint**

- The ruleset is a Spectral-format file kept under `contracts/`. It enforces at least: `operationId` present and unique, every operation tagged, every non-2xx response referencing `Problem`, every schema property described, `x-source` or `x-derived` on resource schema properties (FR-010), no property with a forbidden name (FR-012), enum values in a fixed case convention, and closed response schemas (D-2). Each rule has a planted-violation fixture and the clean fixture passes under the same ruleset.
- Lint fails when the ruleset file is missing or empty, when vacuum loads zero rules, or when it lints zero files.

**FR-016 - Breaking-change check**

- For each module the check compares the freshly built bundle with the bundle of the module's last release (the most recent tag matching `contract-<module>-v<semver>`), rebuilt or downloaded as a verified release asset. A breaking change (removed path, removed or renamed response property, narrowed enum, newly required request parameter, changed type) fails unless the candidate's `info.version` has a higher major version than the baseline. A non-breaking addition passes with a minor or patch bump and fails if `info.version` did not change at all while the bundle did (CHANGELOG discipline, FR-024).
- First release: when no tag matching the module's pattern exists, the job prints an explicit "no baseline" notice and records it in the job summary; this is allowed only when `info.version` is the module's initial version and the module's `CHANGELOG.md` carries the initial entry, and fails otherwise. The job also fails (it does not report "no baseline") when it cannot list tags reliably, for example in a shallow checkout (`git rev-parse --is-shallow-repository` is true) or when tag listing errors.
- Provisional elements are diffed and reported in their own section (D-7); they are never dropped from the comparison.
- Because no real release exists yet, the negative proof of this check runs against a committed pair of small baseline and candidate fixtures, outside any path validated as a real module, with a clean positive control.

**FR-017 - Workflow shape**

- A new workflow file (new path, for example `.github/workflows/contracts.yml`) triggers on pull requests and pushes to `main` filtered to `contracts/**` and its own file, has least-privilege `permissions`, and shares no job with the Python suites. A guard test over the new workflow files fails when a trigger is not path-filtered to `contracts/**` (and the workflow's own path), or when the file invokes a Node toolchain (`node`, `npm`, `npx`, `yarn`, `pnpm`, `setup-node`).
- The Mission's edits to the Python suites' selection are limited to the corpus glob in CL-2. No existing job's `needs`, matrix or marker expression changes.
- If the workflow invokes pytest on a change-triggered event, FR-020's ledger and allowlist rules apply; a guard proves the file is consistent with them.

**FR-018 - Pinned and verified tooling**

- Gradle (distribution checksum verified), the openapi-generator plugin, vacuum and oasdiff each have an exact version and, for downloaded binaries and distributions, a recorded sha256 in a committed manifest. The workflow verifies each checksum before the binary or distribution is executed; a mismatching or missing checksum fails the job before execution (planted: an altered checksum fails). Every `uses:` in the new workflow files is pinned to a full 40 character commit SHA with a version comment; a guard test fails on a floating tag or branch ref (planted: an unpinned `uses:` is detected, the pinned one passes).
- No tool is installed through an unpinned package-manager command in the workflow. Downloads use HTTPS only.

**FR-019 - Reality check**

- `tests/contract/test_mission_status_reality.py` builds, for every Mission directory under `kitty-specs/` that has a `meta.json`, the overview payload and the detail payload, and for every work package in that Mission the work package payload, using today's readers: `materialize_snapshot` for the status snapshot, the `meta.json` key whitelist, `compute_weighted_progress`, `reconstruct_wp_view` (WPView) and `dependency_readiness_for_wp`, the lifecycle derivation, the tail reader for the stream cursor. The projection from reader output to contract payload is test-side (a test helper under `tests/contract/`; new path). It does not add a Python module under `src/`.
- It validates every built payload against the contract. A payload failing validation fails the test and names the Mission, the work package and the JSON pointer of the first failure; a mission is never silently skipped, and there is no exclusion list at delivery (a later exclusion needs an issue, an owner and a drain date, per the charter's allowlist rule, and is printed in the test output).
- Non-vacuity floors: at least 500 Missions and at least 3000 work packages validated; at least one Mission for each of the nine status lanes is represented in `statusLaneCounts`; each of `active`, `planned`, `done` and `draft` occurs; each of the four stamped topology values and `unknown` occurs; the test fails if any floor is not met and no fixture covers it. The floors are recorded with the survey numbers they came from.
- Positive and negative controls on one shared fixture: a payload of a real Mission validates; the same payload with a planted e-mail, absolute path, unknown status lane, or extra property fails.
- The test is read-only: it records a content hash of every tracked file under `kitty-specs/` before and after the build and fails if any differ.
- The contract it validates against is the contract the CI build resolves, not a hand copy: it either consumes the bundle the build produces or resolves the split files with a reference resolver whose output is proven equal to the bundle by a parity check that fails on divergence (Open Question OQ-1 chooses the mechanism; the requirement is that there is one resolution authority or a proven-equal pair).
- It gives a real verdict in every job that selects the `corpus` marker, including jobs with no JVM; if the contract or its resolver is unavailable it fails (it never skips and never passes).

**FR-020 - CI placement of the reality check**

- `contracts/**` is added to the `corpus` filter group in `.github/workflows/ci-router.yml` as an additive, single-line change; the existing globs are untouched.
- `tests/architectural/test_ci_corpus_trigger_completeness.py` is updated so its curated registry lists `tests/contract/test_mission_status_reality.py` and its documented glob set and data roots include `contracts/**` and `contracts/`; `pytest.ini`'s `corpus` marker description names `contracts/**`. Running that test file passes (it fails if the registry and the marked modules differ in either direction).
- Selection is demonstrated, not assumed: after rebasing on the latest `main`, `pytest --collect-only -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py` collects the test, and the job that is the test's blocking home is named in the PR with a link to a green run of it on a contracts-touching diff. The PR body records, per router shape on `main` at that moment, which job selects the test.
- Exactly-once: on a diff touching `contracts/**`, the number of blocking per-change jobs whose logs show the reality check's test id executing is exactly one. If the plan adds a pytest-invoking job to the contracts workflow, that `(workflow, job)` is added to `AUTHORIZED_PER_CHANGE_SUITE_JOBS` with a rationale, the workflow file is added to `WORKFLOW_FILES`, and the router's corpus job deselects the test; if the plan does not, the contracts workflow runs the reality check only on non-change events (the release workflow's dry run and tag run), and the router's corpus job is the per-change home. Either shape must leave `tests/architectural/test_no_duplicate_suite_execution.py`, `tests/architectural/test_workflow_coherence.py` and `tests/architectural/test_ci_corpus_trigger_completeness.py` passing. They are run as named files only (the charter forbids full architectural sweeps in mission work).
- `.github/ci-module-registry.yml` is unchanged by this Mission; if the plan finds a reason to edit it, the reason and the conflict handling with the open CI PRs are recorded in the plan.
- Every other new test names its marker and the CI job that collects it, verified by a collect-only run. A test in `tests/contract/` with only `fast` or `contract` markers is collected by no per-PR job; any such new test in that directory carries `corpus`, and tests for the workflow files go in `tests/ci/`, whose module-matrix row already selects changes under `.github/workflows/**`.

**FR-021 - Planted-violation proof**

- For each of validate, bundle, lint, breaking-change diff, citation check, leak scan, layout check, pin and checksum verification, reality check, and the release dry run, there is at least one planted violation that makes that check fail, with the failure message naming the cause, and a clean control on the same fixture that passes. The evidence is real CI output: either fixtures a negative-test job in the workflow runs and asserts the failure of, or throwaway commits whose failing runs are linked in the PR body. A check with no demonstrated failing run is treated as not delivered.
- Where a negative-test job runs a check against a planted fixture, the job passes only if the check failed for the expected reason (it asserts the message), not merely because it exited non-zero.

**FR-022 - Release workflow and dry run**

- A new release workflow (new path, for example `.github/workflows/contracts-release.yml`) triggers on tags matching `contract-*-v*.*.*` and on `workflow_dispatch`, and on a path-filtered `pull_request` run for its dry-run mode so that the dry run's green result exists in the PR (CL-4; Open Question OQ-2). The dry run builds the bundle for the selected module, writes `openapi.yaml.sha256`, verifies it with `sha256sum -c`, uploads both as a workflow artifact, and executes no publication step. The publication step (creating the release with those two assets) runs only on a tag push.
- Tag rules, checked before publication and in the dry run: the tag matches `contract-<module>-v<semver>`; `<module>` names an existing module; `<semver>` equals that module's `info.version`; the module's `CHANGELOG.md` has a heading for that version. Each violation fails the job (planted: a mismatched version fails).
- Namespace guard: a test evaluates the release workflow's tag glob against the CLI release tags and the CLI release trigger glob against `contract-mission-status-v1.0.0`; neither matches. The test fails when a contract tag would match `v*.*.*`. It does not call the CLI release scripts with the contract tag as a live tag.
- The release workflow is not wired into `.github/workflows/release-readiness.yml`, `release.yml` or any CLI release gate. The contract release does not alter `release.yml`.
- After merge (close-out step, CL-4): a maintainer pushes `contract-mission-status-v1.0.0`; the evidence is a published release with exactly the bundle and its sha256, the downloaded checksum verifying, and the digest matching a locally rebuilt bundle. This evidence is recorded in the Mission close-out record and cannot be produced in the PR.

**FR-023 - CODEOWNERS**

- `.github/CODEOWNERS` (new) contains a rule for `contracts/` owned by `@stijn-dejongh` and `@MOES-Media`. A guard test parses the file and fails if the rule is missing, if either handle is missing, or if the pattern does not cover `contracts/mission-status/`. The PR body states that review is not enforced by branch protection today.

**FR-024 - Versioning and CHANGELOG**

- The `mission-status` module has `info.version` set to its first release value and a `CHANGELOG.md` with an initial entry and sections for added, changed, removed and provisional elements. `contracts/README.md` states the versioning rule: breaking changes move the major version, additive changes the minor version, documentation-only changes the patch version; a bundle change with no `info.version` change fails the breaking-change job. Both `CHANGELOG.md` files and the README satisfy the repository's markdown lint.

**FR-025 - Fail-loud matrix**

The table below is binding; each row has a planted-violation test (FR-021).

| Check | Cannot do its job when | Required behaviour |
|-------|------------------------|--------------------|
| Validate | no module found; a module has no root `openapi.yaml`; the validator tool is missing or its checksum mismatches; a `$ref` does not resolve | Non-zero exit; message names the module and the cause; reports module count; zero modules fails |
| Bundle | output missing, empty, or has fewer than the five v1 paths; two builds differ | Non-zero exit naming the missing or differing artefact |
| Lint | ruleset missing or empty; zero rules loaded; zero files linted; binary missing or checksum mismatch | Non-zero exit naming the cause |
| Breaking-change diff | no baseline and not the initial version; shallow checkout or tag listing error; baseline cannot be fetched or its checksum mismatches; oasdiff missing | Non-zero exit; the one allowed no-baseline state is printed loudly and recorded in the job summary |
| Citation check | zero citations found; a cited path or symbol does not resolve | Non-zero exit naming the property |
| Leak scan | zero values scanned; a planted value of any kind not detected | Non-zero exit |
| Reality check | fewer than the floor of Missions; zero work packages; contract or resolver unavailable; payload invalid; readers modified a tracked file | Test failure, never skip, never pass |
| Release dry run and release | bundle empty; sha256 mismatch; tag not matching the rules; module or version missing | Non-zero exit before any publication step |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Reality-check runtime | The reality check over the corpus at delivery completes in at most 120 seconds wall-clock on a standard hosted runner (538 Missions and roughly 34000 event lines at survey time), measured from the CI job log and recorded in the PR. It is not asserted inside the test (no timing flake), but the plan records the measurement and the job's existing timeout leaves at least 50 percent headroom. | Performance | Medium | Open |
| NFR-002 | Deterministic bundle | Two builds of the same commit produce byte-identical bundles (equal sha256), checked in CI. | Reliability | High | Open |
| NFR-003 | Supply chain | 100 percent of downloaded tool artefacts have a pinned version and a verified sha256; 100 percent of `uses:` references in the new workflows are SHA-pinned; zero floating references. | Security | High | Open |
| NFR-004 | Leak-free artefacts | Zero absolute host paths and zero e-mail addresses in the contract tree, in `examples/`, and in every payload the reality check builds (excluding authored `promptMarkdown`). | Security | High | Open |
| NFR-005 | No new Python critical-path cost | The contracts workflow adds no job to the Python module-shard matrix and changes no existing job's `needs`; the only router edit is the single corpus glob. Measured by diffing the workflow files. | Performance | Medium | Open |
| NFR-006 | Reproducible locally | A contributor with a JDK and network access can run validate and bundle locally with one documented command; the README states the prerequisite and the command. The Mission's own required checks run in CI and do not depend on local runs. | Usability | Low | Open |
| NFR-007 | Test discipline | New Python test code passes ruff check and ruff format (both hard-enforced) and has line and branch coverage of at least 90 percent of the new test-helper code by the helper's own tests. Mission work runs targeted test files and the named architectural gate files only, never a full architectural, end-to-end or full-suite sweep; commands and counts are recorded in the PR. | Quality | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Draft PR until design acknowledged | One PR for the Mission, opened as a draft from `issue-5558-mission-status-contract-v1` onto `main`; not marked ready until the design is acknowledged on #5528 (CL-1). Implementers never merge. | Process | High | Open |
| C-002 | Contract and CI only | No file under `src/` changes; no status event schema, `meta.json` handling, CLI command or migration changes. Test helpers live under `tests/`. | Technical | High | Open |
| C-003 | Minimal shared-CI edits | `.github/workflows/ci-router.yml` receives only the additive corpus glob (FR-020); `.github/ci-module-registry.yml` is not edited. Open PRs #5545 and #5557 touch both files; edits are additive, rebased last, and the named gates re-run after rebase. | Technical | High | Open |
| C-004 | `contracts/fixtures/` untouched | The existing handoff fixtures and their reader `tests/contract/test_handoff_fixtures.py` are not modified. | Technical | High | Open |
| C-005 | Node-free | No Node, npm, npx, yarn or pnpm in the contracts tooling, workflows or tests. | Technical | High | Open |
| C-006 | Public repository hygiene | Nothing in the spec, plan, contract, examples, tests or commit messages contains an absolute host path, an e-mail address, a credential, or a reference to a private discussion. Upstream issue and PR numbers may be cited. | Security | High | Open |
| C-007 | Terminology | "Mission", never "feature", in all new text and identifiers; "status lane" and "execution lane" are never conflated; the glossary list is checked for the terms used. | Governance | High | Open |
| C-008 | No version numbers in scope | The release stream's own version (`contract-mission-status-v1.0.0`, `info.version`) is the artefact's identity, not a CLI release scope; nothing in this Mission names or alters a CLI release version. | Governance | Medium | Open |
| C-009 | Pre-existing failures reported, not absorbed | Pre-existing red tests encountered are recorded against a baseline taken on the base commit and reported as the charter's pre-existing failure rule requires; they are never made green by this Mission, and never blamed on it without the baseline. | Governance | High | Open |
| C-010 | ATDD order | The reality-check test (and each check's planted-violation fixture) is committed first and shown red against an empty or wrong contract before the contract makes it green; reviewers verify red then green. | Quality | High | Open |
| C-011 | Docs and ADR | No ADR is authored here. The open ADR amendment on the read API's placement and transport (the ADR still records an in-process module and CLI JSON verbs, with no HTTP server in the CLI) is a separate decision on #5528, not this Mission's scope. | Governance | Medium | Open |

### Key Entities *(include if the mission involves data)*

- **Contract module**: a self-contained OpenAPI 3.1 document split across files, with its own `info.version`, `CHANGELOG.md` and release stream (`mission-status` first).
- **Shared building blocks**: cross-module pieces in `contracts/_shared/` (`Problem`, page cursor, `PageInfo`, shared parameters and responses).
- **Bundle**: the single resolved document built by CI from a module; the release asset; never committed.
- **Release asset pair**: the bundle `openapi.yaml` and its `openapi.yaml.sha256`.
- **Mission overview**: one record per Mission with identity, vocabulary values, raw status-lane counts, progress, timestamps and the stream cursor.
- **Mission detail**: the overview plus the five Mission phases and work package summaries.
- **Work package detail**: authored plan, resolved state, readiness, review evidence and history for one work package; prompt body only on request.
- **Event stream**: the `text/event-stream` change feed of projected, named event kinds, each with a data schema, a `missionId` and a stream cursor.
- **Corpus**: this repository's own `kitty-specs/` Missions, the data the reality check validates against.

### Contract Field Catalogue (requirements)

Evidence is cited as `path:line` at this checkout (HEAD descends from main at d78aa2345; the citations were re-verified, see the drift note below). `src/` is implied. "Null" means the schema allows `null`. "Provisional" means `x-provisional: true`. Types are the contract's types, not the source's.

**Project** (`GET /project`)

| Field | Type | Null | Source |
|-------|------|------|--------|
| name | string | no | `.kittify/config.yaml` project.slug; `specify_cli/identity/project.py:44-58` (`ProjectIdentity`) |
| missionCount | integer | no | `specify_cli/dashboard/scanner.py:565-612` (`build_mission_registry`) |

**Mission overview** (items of `GET /missions`; also the head of detail)

| Field | Type | Null | Source |
|-------|------|------|--------|
| missionId | string, ULID | no | `meta.json` `mission_id`; `specify_cli/mission_metadata.py:226-269`; ULID pattern `specify_cli/status/models.py:99` |
| mid8 | string | yes | `mission_runtime/identity.py:64-96` (`resolve_mid8`; empty becomes null) |
| slug | string | no | `specify_cli/mission_metadata.py:254-256` |
| friendlyName | string | no | `meta.json` `friendly_name`; `specify_cli/dashboard/scanner.py:730-737` (falls back to slug) |
| displayNumber | integer | yes | `meta.json` `mission_number`; `specify_cli/mission_metadata.py:107-116`. Display-only, not unique |
| missionType | string | yes | `meta.json` `mission_type`; `specify_cli/mission_metadata.py:262`. Open set (D-13) |
| targetBranch | string | no | `meta.json` `target_branch`; `specify_cli/mission_metadata.py:61` |
| topology | enum (5) | no | `meta.json` `topology`; `mission_runtime/context.py:44-56`; unstamped or unknown is `unknown` (D-11) |
| createdAt | string, date-time | no | `meta.json` `created_at`; `specify_cli/mission_metadata.py:62` |
| statusLaneCounts | object, nine required integer keys | no | `StatusSnapshot.summary`, `specify_cli/status/models.py:740-765`; nine keys at `:29-68` |
| wpTotal | integer | no | `len(snapshot.work_packages)`; `specify_cli/status/progress.py:201` (D-4) |
| blockedCount | integer | no | derived: `statusLaneCounts.blocked` (`x-derived`) |
| progress | object: weightedPercentage, donePercentage, doneCount, semantics (const `weighted_readiness`) | no | `specify_cli/status/progress.py:79-116`, `:119-206`, `:48`; weights `:34-46` |
| lifecycleStatus | enum (5) | no | derived over `statusLaneCounts` from `specify_cli/dashboard/scanner.py:219-246` (D-5) |
| acceptedAt, mergedAt, discardedAt | string, date-time | yes | `meta.json`; `specify_cli/dashboard/scanner.py:235,244`; `specify_cli/mission_metadata.py:705-731` |
| lastEventId | string | yes | `snapshot.last_event_id`; `specify_cli/status/models.py:749` |
| lastActivityAt | string, date-time | yes | derived: maximum work package `last_transition_at` (`x-derived`; there is no Mission-level event time) |
| eventCount | integer | no | `snapshot.event_count`; `specify_cli/status/models.py:748` |
| streamCursor | object: offset (integer), invariant (64 hex characters) | no | `specify_cli/status/tail_reader.py:59-73`, `:52` (empty digest at offset 0), `:327-339`; bound to one log file (D-8) |
| nextAction | string | yes | Provisional. `specify_cli/dashboard/scanner.py:249-273` (three prose strings or null); the runtime's `Decision` (`runtime/next/decision.py:94-131`) is per-agent and is not v1 |

**Mission detail** (adds to the overview)

| Field | Type | Null | Source |
|-------|------|------|--------|
| phases | array of exactly five: name (specify, plan, tasks, implement, review), status (pending, in_progress, complete), basis (artifact, lifecycle_event, derived_from_status_lanes) | no | specify, plan, tasks: artifact presence `specify_cli/dashboard/scanner.py:365-390` and lifecycle events `specify_cli/status/lifecycle_events.py:75-104`; implement, review: derived from status lanes (`x-derived`); there is no implement or review lifecycle event |
| workPackages | array of summaries | no | per work package fields below |

**Work package** (`GET .../work-packages/{wpId}`; summaries reuse a subset)

| Field | Type | Null | Source |
|-------|------|------|--------|
| wpId | string | no | `specify_cli/status/wp_metadata.py:222` |
| title | string | no | `specify_cli/dashboard/scanner.py:953-962`; `wp_metadata.py:223` |
| phaseLabel | string | yes | frontmatter `phase`; `specify_cli/status/wp_metadata.py:269` |
| authored.role, authored.agentProfile, authored.model | string | yes | `specify_cli/status/wp_view.py:117-135` |
| authored.subtasks, ownedFiles, dependencies, requirementRefs | array of string | no (may be empty) | `specify_cli/status/wp_view.py:132-135`, `wp_metadata.py:226` |
| executionMode, taskType, priority, mergeTargetBranch, trackerRefs | string or array | yes | `specify_cli/status/wp_metadata.py:235-265` (normalisation of quoted values documented) |
| statusLane | StatusLane | yes | snapshot `lane`; `specify_cli/status/wp_view.py:80,181` (null when no events) |
| assignment (agent, assignee, role, agentProfile, agentProfileVersion, model, provider) | handle strings | yes each | `specify_cli/status/wp_view.py:66-91,159-195`; sentinels to null `:176-194` |
| subtasks | object: subtask id to StatusLane | no | `specify_cli/status/wp_view.py:85` |
| subtaskProgress | object: done, total | no | `specify_cli/dashboard/scanner.py:1042-1057` |
| implementerOfRecord | handle | yes | `specify_cli/status/reducer.py:123-172` (schema 2 snapshots only) |
| lastTransitionAt, forceCount, lastEventId | string, integer, string | no | snapshot keys present on every entry (`specify_cli/status/reducer.py`, survey of committed `status.json`) |
| actor | object: tool, role, profile, model (handles) | no | `specify_cli/status/models.py:114-142`; `actor_identity_str` `:146-159` (D-10) |
| cancellation | object: reasonSource, reason | yes | `specify_cli/status/reducer.py:114-115` |
| readiness | object: satisfied (boolean), unsatisfied (array of wpId) | no | `specify_cli/core/dependency_graph.py:34-72` (missing dependency lane defaults to planned, `:87`) |
| readyToStart | boolean | no | `specify_cli/orchestrator_api/commands.py:1250-1271` |
| review.latestResult | object: reviewer (handle), verdict (approved, changes_requested), reference (string) | yes | `specify_cli/status/reducer.py:201-216`; `specify_cli/status/models.py:285-305` |
| review.override | object: at, actor (handle), reason | yes | `specify_cli/status/wp_review.py:28-53`; `models.py:428-445` |
| history | array of: eventId, at, kind (transition, annotation, lifecycle), fromStatusLane, toStatusLane, actor, force, reason, reviewVerdict, deltaKeys (names only) | no | `specify_cli/status/models.py:318-424`, `:665-722` |
| staleness | object: status (fresh, stale, not_applicable), reason, minutesSinceCommit | yes | Provisional. `specify_cli/core/stale_detection.py:38-53` |
| promptMarkdown | string | yes | on request only; `specify_cli/dashboard/scanner.py:1126`. No `promptPath` (D-6, D-14) |

**Events** (`GET /events`)

| Event kind | Data fields | Source |
|------------|-------------|--------|
| status-lane transition | missionId, eventId, wpId, fromStatusLane, toStatusLane, at, actor, force, streamCursor | `specify_cli/status/models.py:318-360` (`StatusEvent`); cursor injection `specify_cli/status/tail_reader.py:314-315` |
| Mission lifecycle marker | missionId, eventId, eventType (a lifecycle event type name), at, streamCursor | `specify_cli/status/lifecycle_events.py:75-104` |
| log truncated | missionId, reason (size_shrink, content_mismatch), detectedAtOffset, streamCursor reset to offset 0 | `specify_cli/status/tail_reader.py:177-195` |

**Citation drift check.** The data-shape evidence this catalogue builds on was re-verified on this checkout (HEAD dcee47338, a descendant of d78aa2345). Citations held, with one cosmetic difference: the `MissionStatus` class is declared at `specify_cli/status/aggregate.py:168` while the survey's cited field range `:181-187` is correct. No semantic drift was found.

## Out of Scope

- The read service implementation (separate Mission, built against this contract) and the dashboard and Desktop screens (built in the UI repository against this contract).
- Artifact reads (#5533) and write surfaces (#5231).
- Execution-lane data (`lanes.json`), board-column grouping, retrospective data, done evidence, host-local claim data (shell process ids), the runtime's per-agent next-step decision, open decision counts.
- Any change under `src/`, any status or `meta.json` schema change, any CLI behaviour change, any migration.
- Authoring or amending an ADR (see C-011), fixing the quirks of the existing lifecycle derivation (D-5), fixing the existing readers' defects, or adding the glossary term `execution lane` (noted in Risks).
- Publishing the release inside the PR (the tag is pushed after merge, CL-4).
- Changes to `contracts/fixtures/` or to the CLI's own release process.

## Assumptions

- The maintainer-ratified design in the #5528 design comment stands; the PR is a draft until it is acknowledged (CL-1).
- The status domain's readers (`materialize_snapshot`, `reconstruct_wp_view`, `compute_weighted_progress`, `dependency_readiness_for_wp`, the lifecycle derivation) are stable enough to cite and to call from a test; they are not modified here.
- The corpus (`kitty-specs/` on `main`) is large enough (538 Missions at survey time, 517 with event logs, 3125 work package files, 34146 event lines) that the floors in FR-019 are meaningful, and its stored data is representative of what a read service will serve.
- A JDK, Gradle and network access are available on the CI runner for the contracts workflow; the corpus lane's jobs do not have a JVM (OQ-1).
- `pytest.ini` keeps the `corpus` marker; the CI router keeps a marker or node-id based corpus lane in some shape (the open CI-rework PR changes the shape, not the existence).

## Risks and Dependencies

| # | Risk or dependency | Effect | Mitigation |
|---|--------------------|--------|------------|
| R-1 | Open PR #5557 (CI rework) edits `ci-router.yml`, `ci-modules.yml`, `module-tests.yml`, `ci-aggregate.yml` and `.github/ci-module-registry.yml`, and re-homes the corpus lane to a named-node-id blocking router job with the marker-selected remainder elsewhere. | A marker-only corpus test could become advisory or orphaned after that merges; the one-line glob edit can conflict. | Additive single-line edit; rebase last; re-verify selection by collect-only plus a named job link (FR-020); if the blocking home is node-id based, the reality check's id is added to it or the contracts workflow becomes its blocking home. |
| R-2 | Open PR #5545 (remove the bundled dashboard) edits `ci-router.yml`, `ci-module-registry.yml`, `ci-windows.yml`, `ci-nightly.yml` and the ADR, and removes the dashboard code that many citations name. | Citations to `specify_cli/dashboard/` dangle after it merges. | Citation check fails loudly (FR-010); prefer status-domain citations; restate dashboard-only derivations in the contract; re-point after rebase. |
| R-3 | Baseline of known-red tests on `main`. The corpus and contract tests have failed on `main` for unrelated reasons before. | Misattributing a red. | Record, at implement start, a baseline run of the targeted files (`tests/contract` corpus-marked tests, the three named architectural gates, `tests/ci`) on the base commit; judge the reality check and the gates against it; report pre-existing reds as the charter requires and never absorb them (C-009). |
| R-4 | The reality check couples contract validity to live `kitty-specs/` data. | A flawed stored Mission turns a corpus-marked job red on an unrelated PR. | Zero exclusions at delivery; a failure is triaged as contract gap, reader defect, or data defect, with a recorded owner for the latter two; never silenced. |
| R-5 | A JVM-less corpus job must still render a real verdict (FR-019). | A tooling dependency leaks into an unrelated lane, or the test skips. | OQ-1 resolves it; never skip; parity check if two resolution paths exist. |
| R-6 | The leak guarantee relies on shape and scan rules, and a handle-shaped string can still be an account name; the status domain has recorded OS and git user names in actor-like fields before. | Residual identity exposure through handles. | Handle pattern plus value scan plus corpus assertion that known e-mail sources project to null; residual risk stated in the README; no claim of a stronger guarantee. |
| R-7 | The issue-matrix scaffold collects `#N` tokens from the spec and plan prose as issue rows. | Approval refusals for prose such as clarification numbers. | The spec cites only real upstream issue and PR numbers (#5528, #5558, #5529, #957, #460, #5533, #5231, #5545, #5557) and names its own decisions CL-n and D-n; each cited number gets an honest verdict row, with a not-applicable verdict for the two PRs. |
| R-8 | The requirement parser reads every `FR-` token in the spec as a local requirement. | A false unmapped requirement at finalize. | Only FR ids defined in this spec appear in the prose; no other Mission's requirement ids are cited. |
| R-9 | `execution lane` is not a glossary term, and the glossary's `lane` is the status meaning. | Residual terminology ambiguity in code and docs outside this Mission. | The contract and README define both terms; adding the glossary term is out of scope and noted for the maintainers. |
| R-10 | Gradle wrapper binaries are committed binaries, and a Go binary download needs network. | Supply-chain and reproducibility concerns. | Prefer a pinned Gradle distribution with `distributionSha256Sum` and a pinned setup action over a committed wrapper jar; FR-018. |
| R-11 | `prose_only` PR classification in the router treats corpus globs as doc paths. | Adding `contracts/**` to the corpus group changes how a mixed contracts plus docstring-only Python change is classified. | The plan reads `scripts/ci/prose_only.py` and `scripts/ci/gate_selection.py` and records the effect; a guard or test pins any behaviour that changes. |
| R-12 | The release job cannot be fully exercised from a PR (publication needs a tag; a manually dispatched workflow resolves from the default branch). | An untested publication step. | Dry run on the PR branch proves everything except the publication call; the post-merge close-out step verifies the real release (FR-022). |
| R-13 | Existing quirks (blocked-only reads as planned; all-canceled and accepted reads as done; `tasks status` counts differently) are pinned, not fixed. | A consumer may expect saner semantics. | Documented in the schema descriptions and the CHANGELOG as v1 behaviour; a later minor or major version may change them. |

### Open Questions (plan phase; none block the spec)

These are design points the maintainer decisions leave to the plan. Each has a constraint the plan must satisfy, so none is a blocker for the spec or its review.

- **OQ-1 Contract resolution in the reality check.** The reality check must give a real verdict in jobs that have no JVM, but the bundle comes from the JVM build. The plan chooses between (a) giving the corpus jobs a JDK and the Gradle step, (b) resolving the split files in Python with a reference resolver and proving it equal to the CI bundle in the contracts workflow, or (c) another route. Constraints: no skip; no second unproven resolution authority; the verdict is real in every job that selects the `corpus` marker.
- **OQ-2 Where the dry run's evidence comes from.** The release workflow's dry run must be green in the PR, but a manual dispatch needs the workflow on the default branch. The plan chooses the trigger (a path-filtered `pull_request` run in dry-run mode alongside `workflow_dispatch` and the tag trigger). Constraint: if that run reaches pytest, FR-020's ledger and allowlist rules apply, and the publication step must be unreachable on any event except a tag push.
- **OQ-3 Unscoped event streams.** A stream cursor is valid for one Mission's log. The plan decides whether an unscoped `GET /events` (no `missionId` filter) supports resume or is live-only. Constraint: every event carries `missionId` and its own stream cursor; the resume refusal reasons are fixed in FR-007.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The bundle built from a clean checkout contains exactly the five v1 path items and zero unresolved file references; two consecutive builds have equal sha256. — [build] · no-op passable: no
- **SC-002**: The reality check validates at least 500 Missions and at least 3000 work packages (the survey counts 538 and 3125), with zero failures and zero exclusions, and each floor in FR-019 holds. — [build] · no-op passable: no
- **SC-003**: Every check listed in FR-021 has at least one linked, real failing run on a planted violation with an asserted failure message, and one passing control run; none is demonstrated only by a local run. — [build] · no-op passable: no
- **SC-004**: 100 percent of properties in resource schemas carry `x-source` or `x-derived`, and 100 percent of cited paths and symbols resolve in the checkout. — [build] · no-op passable: no
- **SC-005**: Zero absolute host paths and zero e-mail addresses across the contract tree, `examples/` and all reality-check payloads (excluding authored `promptMarkdown`), with the scan's positive controls detecting planted values of each kind. — [build] · no-op passable: no
- **SC-006**: The release dry run is green in the PR and its artifact contains a non-empty bundle and an `openapi.yaml.sha256` that passes `sha256sum -c`. — [build] · no-op passable: no
- **SC-007**: On a diff touching `contracts/**`, the reality check's test id executes in exactly one blocking per-change job, and the three named architectural gate files (corpus trigger completeness, no duplicate suite execution, workflow coherence) pass with every ledger or allowlist addition carrying a rationale. — [build] · no-op passable: no
- **SC-008**: The PR diff touches zero files under `src/`, zero files under `contracts/fixtures/`, zero lines of `.github/ci-module-registry.yml`, and adds exactly one glob line to `.github/workflows/ci-router.yml`; no Node tooling appears anywhere in the diff. — [build] · no-op passable: yes - paired with SC-007 and SC-002, which a diff that does nothing cannot satisfy
- **SC-009**: Post-merge close-out: the tag `contract-mission-status-v1.0.0` exists, its release has exactly the bundle and its sha256, the downloaded checksum verifies, and the digest equals a locally rebuilt bundle; recorded in the Mission close-out record, not a follow-up issue. — [build] · no-op passable: no
- **SC-010**: The PR is a draft until a maintainer acknowledgement is linked on #5528, and the PR body follows the repository's five-section PR body contract and lists the baseline of known-red tests used for judging. — [build] · no-op passable: no
