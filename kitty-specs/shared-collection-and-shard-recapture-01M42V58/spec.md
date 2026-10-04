# Mission Specification: Shared battery collection and complete shard-timing provenance

**Mission Branch**: `issue-5559-shared-collection-and-shard-recapture`
**Created**: 2026-10-04
**Status**: Draft
**Input**: GitHub issues #5559, #5561 and #5536, shaped by four operator rulings recorded as Decision Moments (see "Scope rulings").

## Intent Summary

**Reader**: a Spec Kitty maintainer who lands pull requests and watches CI.

**Primary actor and trigger**: a maintainer opens or updates a pull request, or the nightly and scheduled workflows fire.

**Outcome**: the full test-universe collection no longer runs inside a test while that test's own workers compete for the CPU. Each job that needs it collects once, before its tests start, and every test in that job reuses the result. Every CI module's shard timings rest on a measured capture that is refreshed on a schedule.

**Rule that must always hold**: a reused collection is trusted only when it was produced from exactly the checkout and environment the consumer sees. On any doubt the consumer collects for itself. Reuse must never turn a red gate green.

**Boundary**: this mission changes test infrastructure, CI scripts, CI workflows, committed CI data and documentation. It changes no product behaviour.

### Why the issues are one mission

All three are residue of mission `ci-runtime-stabilisation-01M3TZH6` (PR #5560). They share the committed timing data and the same CI workflows, and recapturing the `ci` module row depends on the collection behaviour this mission changes.

### Scope rulings

| Decision Moment | Ruling |
|---|---|
| `01M42V5PVVQ0W5D0SJ60A4X6AA` | #5559 is re-scoped. Each per-PR job already collects exactly once, on its own runner, so sharing between the workers of one job changes nothing. |
| `01M42VM0CEBBZHCJEAN4KTDYYC` | The design is an uncontended collection step before the tests start, in each consuming job. One collection for all consumers is not possible: the battery legs and the `ci` module shard run in two independently triggered workflows on two interpreter versions. |
| `01M42V5RDSJN1R0C7R4YKEB0E1` | The recapture covers every allowlisted module, the allowlist is removed, and the scheduled recapture is extended to every module. |
| `01M42VM1YPDQPPGP1FK0W9AECK` | A capture is valid when the test run completed (all passed, or some tests failed) and recorded durations. This follows the existing recapture trust rule and replaces the "exit status 0" wording of the parent issue's triage. |

**What this does and does not claim.** The measured 114 / 166 / 170 s is one collection running inside a test fixture under contention from four test workers; uncontended on CI it takes about 35–45 s. The mission moves that collection out of the test and out of contention. A first run of a given checkout still collects once per consuming job (three per pull-request update); the mission does not reduce that number. A re-run of the same checkout restores the stored collection instead of collecting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The collection stops competing with the tests (Priority: P1)

A maintainer pushes to a pull request. The two architectural battery legs and the `ci` module shard each need the full list of collected tests with their markers. Today the first test that needs it collects inside its own setup while four test workers compete for the same CPUs. After this mission each of those jobs collects before its tests start, and the tests read the stored result.

**Why this priority**: the setup time of the slowest collecting test is within 10–66 s of the 180 s bound for the slowest battery test, and the margin shrank over three measured runs. Crossing the bound reds the battery for every pull request.

**Independent Test**: run the per-PR workflows on a pull request three times and read the job summaries: in every consuming job the collection ran before the tests, every collecting test reports that it reused the stored collection, and its setup time is recorded.

**Acceptance Scenarios**:

1. **Given** a consuming job whose pre-test step stored a collection, **When** a test needs the test universe, **Then** it uses the stored collection and starts no collection of its own.
2. **Given** a stored collection that does not match the consumer's checkout or environment, **When** a test needs the test universe, **Then** it ignores the stored collection, collects for itself, and reports that it did.
3. **Given** the pre-test step failed or did not run, **When** a test needs the test universe, **Then** it collects for itself and the gate verdict is the one a fresh collection gives.
4. **Given** a re-run of a job on an unchanged checkout, **When** the pre-test step runs, **Then** it restores the stored collection instead of collecting again.

---

### User Story 2 - Reuse within one machine (Priority: P2)

A maintainer runs the full local suite, or the nightly workflow runs everything in one job. Several test files need the same collection. After this mission the first one collects, and the others reuse the result as long as the checkout and environment are unchanged.

**Why this priority**: it removes repeated multi-minute collections from single-job runs, and it is the mechanism Story 1 relies on. Requested by ruling `01M42VM0CEBBZHCJEAN4KTDYYC`.

**Independent Test**: in one clean checkout, request the test universe twice and observe one collection; commit a change to a test file and observe a second collection.

**Acceptance Scenarios**:

1. **Given** a clean, unchanged checkout, **When** two test files request the test universe, even from parallel workers, **Then** exactly one collection runs and both receive identical results.
2. **Given** a checkout with uncommitted changes, **When** the test universe is requested, **Then** nothing is read from or written to the store.
3. **Given** a test that points the collection at a temporary tree instead of the repository, **When** it requests the test universe, **Then** it never receives the repository's stored collection, and its own result never replaces it.
4. **Given** a collection attempt that failed, or a stored collection that is truncated, unreadable, empty or implausibly small, **When** the test universe is requested, **Then** nothing from it is reused and the caller sees the same failure or a fresh collection.

---

### User Story 3 - Every module's shard count rests on a measured capture (Priority: P2)

A maintainer changes how a CI module is sharded, or reviews why a shard is slow. Today 17 modules carry timing data whose test count disagrees with what is collected, excused by an allowlist; others have drifted or carry no capture record at all. After this mission every module has been captured by the canonical producer, carries a valid provenance record, and the allowlist no longer exists.

**Why this priority**: shard counts derived from stale durations cannot be validated by the within-module skew check, and the allowlist is priced debt under the charter (ADR `2026-09-30-1`).

**Independent Test**: read the committed timing data and registry at the capture commit: every registry module has a valid provenance record, the committed test count of every module equals the collected count in strict mode, and no module is excused.

**Acceptance Scenarios**:

1. **Given** the committed timing data at the capture commit, **When** the strict agreement check runs, **Then** every registry module agrees and no mechanism excuses a module.
2. **Given** a registry module with no valid provenance record, **When** the provenance check runs, **Then** it fails and names the module.
3. **Given** a recapture that changes a module's durations, **When** its shard count changes, **Then** the count is raised to the nearest higher one the existing skew check accepts, and is never reduced.

---

### User Story 4 - Recaptured modules stay fresh (Priority: P3)

Tests are added to and removed from modules on the primary branch (`main`) every day. A maintainer should not have to notice count drift and recapture by hand. After this mission the scheduled recapture covers every registry module, not only `charter`. Requested by ruling `01M42V5RDSJN1R0C7R4YKEB0E1`.

**Why this priority**: without it, Story 3's result decays within days and the scheduled strict check goes red with no automatic remedy.

**Independent Test**: run the recapture's real entry point against a fixture where one non-charter module has drifted; it recaptures that module only and produces the refreshed data. The first scheduled run on the primary branch after landing is recorded as post-merge evidence.

**Acceptance Scenarios**:

1. **Given** a module whose committed test count differs from the collected count, **When** the scheduled recapture runs, **Then** that module is recaptured and the refreshed data is proposed through the existing publication path.
2. **Given** no module has drifted, **When** the scheduled recapture runs, **Then** nothing is captured and nothing is proposed.
3. **Given** the capture of one module fails, **When** the scheduled recapture runs, **Then** the failure is reported by name, that module's committed data is unchanged, the other modules are still processed, and the run is marked failed.
4. **Given** more drifted modules than fit in the job's time budget, **When** the scheduled recapture runs, **Then** it captures what fits, reports what it deferred, and the next run continues with the rest.
5. **Given** an earlier recapture proposal is still open, **When** the scheduled recapture runs again, **Then** it refreshes that proposal instead of failing or opening a second one.

---

### Edge Cases

- The pre-test step is skipped, cancelled or fails: tests collect for themselves.
- Consumer and producer differ in interpreter version, platform or installed dependencies: no match, no reuse.
- Collection depends on files outside the test tree (parametrised test ids built from product code, doctrine packs, workflow files, documentation or mission directories): any committed change anywhere in the repository invalidates a stored collection.
- Collection depends on environment switches that add or remove skip markers: a different value means no match.
- Two parallel workers request the test universe at the same moment with nothing stored: one collects, the other waits and reuses.
- A stored collection from another commit is present: it does not match and is not used.
- A non-Linux job, or any environment where the store cannot be used: the caller collects for itself.
- The command-line caller of the collection and the test that spawns a collection in a subprocess behave like any other caller.
- A recapture changes the `ci` module's own test count because this mission adds tests to it: the `ci` row is captured last.
- A recapture moves a module's durations so that its shard count fails the skew check: the registry count is corrected in the same change.
- Between a count drift on the primary branch and the merge of the recapture proposal, the scheduled strict check is red. This is an accepted, honest signal; the proposal is its remedy.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Keyed store for the collection | As a maintainer, I want a completed test-universe collection stored on the machine under a key, so that a later request with the same key reuses it. | High | Open | [build] | no |
| FR-002 | Key is the whole checkout plus the environment | As a maintainer, I want the key derived from the identity of the entire committed repository tree, the interpreter version, the platform, the installed dependency set and a declared list of collection-affecting environment switches, so that no hand-maintained list of input files can go stale. | High | Open | [build] | no |
| FR-003 | No reuse on a modified checkout | As a maintainer, I want the store neither read nor written when the checkout has uncommitted changes, so that local edits always get a fresh collection. | High | Open | [build] | yes — paired with a same-fixture control proving a clean checkout does reuse |
| FR-004 | Stored record proves its origin | As a maintainer, I want each stored collection to carry the commit and tree it was produced from, and a consumer to reject any record whose origin differs from its own checkout, so that a key collision or misplaced file cannot be trusted. | High | Open | [build] | yes — paired with a same-fixture control proving a matching record is consumed |
| FR-005 | One collection under concurrency | As a maintainer, I want concurrent requests with nothing stored to result in exactly one collection, with the others waiting and reusing it, so that parallel workers do not multiply the cost. | High | Open | [build] | no |
| FR-006 | Patched roots are isolated | As a maintainer, I want a request aimed at any tree other than the repository to neither read nor replace the repository's stored collection, so that fixture trees cannot green-wash a real gate. | High | Open | [build] | yes — paired with a same-fixture control proving the repository request does reuse the store |
| FR-007 | Failures and damage are never reused | As a maintainer, I want a failed collection never stored, and a stored collection that is truncated, unreadable, empty or implausibly small (below a stated sanity floor) treated as absent, so that a broken run cannot satisfy a later gate. | High | Open | [build] | yes — paired with a same-fixture control proving a successful collection is stored and reused |
| FR-008 | Pre-test collection in consuming jobs | As a maintainer, I want each per-PR job that needs the test universe (both battery legs and the `ci` module shard) to collect it in a step before its tests start, so that the collection does not run under test-worker contention. | High | Open | [build] | no |
| FR-009 | Re-runs restore instead of collecting | As a maintainer, I want the pre-test step to restore a stored collection for the same key when one exists from an earlier run, and to pass it through the same consumer verification, so that re-running a job does not repeat the collection. | Medium | Open | [build] | yes — paired with a same-fixture control proving a restored record with a different origin is rejected |
| FR-010 | Reuse is reported | As a maintainer, I want every request for the test universe to emit one machine-readable line stating whether it reused or collected, with the key, and each consuming job to publish those lines in its summary, so that I can see whether reuse happened. | High | Open | [build] | no |
| FR-011 | Silent fallback is a failure | As a maintainer, I want a consuming job whose pre-test step succeeded but whose tests then collected for themselves to be reported as a failure of the reuse evidence, so that a key that never matches cannot hide behind the fallback. | High | Open | [build] | no |
| FR-012 | Store is bounded | As a maintainer, I want the store kept outside tracked files, holding only the current key's record and evicting older ones when it writes, so that it cannot grow or be committed. | Low | Open | [build] | no |
| FR-013 | Recapture every unmeasured or drifted module | As a maintainer, I want all 17 modules in the mismatch allowlist, plus every other registry module whose count has drifted or whose provenance is missing or invalid (today `charter`, `agent` and `consolidation`), recaptured by the canonical producer from a fully synced environment, so that every committed duration and test count is measured. | High | Open | [build] | no |
| FR-014 | The allowlist is removed | As a maintainer, I want the mismatch allowlist, its baseline count and the tests that only police the allowlist's shape deleted, with the agreement check becoming an invariant that excuses no module and keeps its self-mutation proof, so that no excuse mechanism remains. | High | Open | [build] | no |
| FR-015 | Provenance completeness is enforced | As a maintainer, I want a check that fails, naming the module, when any registry module lacks a provenance record from a completed capture (all tests passed or some failed) with recorded durations, so that unmeasured rows cannot return. | High | Open | [build] | no |
| FR-016 | Shard counts satisfy the skew check on measured data | As a maintainer, I want every module's shard count, after the recapture, to pass the existing within-module skew check against the recaptured durations, with a count that fails it raised to the nearest higher count that passes and no count reduced without an operator ruling, so that no shard count rests on stale durations. | Medium | Open | [ratchet] | yes — paired with a same-data control proving a deliberately wrong count fails the skew check |
| FR-017 | Scheduled recapture covers all modules | As a maintainer, I want the scheduled recapture to find drifted modules with a count-only pass and capture only those, each in isolation from the others, so that the measured cost is paid only where data is stale. | High | Open | [build] | no |
| FR-018 | Per-module failure isolation | As a maintainer, I want a failed capture of one module named in the run summary, its committed data left unchanged, the remaining modules still processed and the run marked failed, so that one bad module neither blocks nor hides. | Medium | Open | [build] | no |
| FR-019 | Time budget with carry-over | As a maintainer, I want the scheduled recapture to stop starting new captures when its time budget is spent and report the modules it deferred, so that it completes within its job limit and the next run continues. | Medium | Open | [build] | no |
| FR-020 | An open proposal is refreshed | As a maintainer, I want a scheduled recapture that finds an earlier proposal still open to update it, so that proposals do not pile up or block the run. | Medium | Open | [build] | no |
| FR-021 | The reported publish failure is classified and made loud | As a maintainer, I want the publish-step failure reported in #5536 classified with evidence, and a rejected push reported with a message that names the missing permission, so that the operator knows what to fix. | High | Open | [build] | no |
| FR-022 | Measured evidence | As a maintainer, I want the mission's evidence to record the local reuse and capture measurements, and to carry a table for three per-PR runs (reuse lines of every consuming job, pre-test step duration, setup time of the slowest collecting test) that is filled from the pull request's first three runs and holds no value that was not observed, so that the result is stated from measurement. | Medium | Open | [build] | no |
| FR-023 | Documentation matches shipped behaviour | As a maintainer, I want the CI gate mechanics and parallel-testing references to describe the stored collection, its invalidation rule, the reuse report and the all-module recapture, so that the next maintainer does not rediscover them. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No collection inside a test | In each of three consecutive per-PR runs, 0 collections start inside a test in the battery legs and the `ci` shard, and every collecting test in those jobs reports `reused`. A fallback in a job whose pre-test step succeeded fails the evidence. | Performance | High | Open |
| NFR-002 | Slowest collecting test | When the stored collection is reused, setup of any test that needs the test universe takes at most 15 s in each of three consecutive per-PR runs (114 / 166 / 170 s before this mission; bound 180 s). The first draft said 10 s; restated after the first CI run measured 4.90 s and 12.36 s. | Performance | High | Open |
| NFR-003 | Pre-test step cost | The pre-test collection step takes at most 320 s per job on a first run and at most 15 s on a restored re-run. The first draft said 90 s, from a planning figure of 35–45 s; the first CI run measured 89.6, 187.3 and 232.6 s, and the operator set 320 s to leave room for a loaded runner. | Performance | High | Open |
| NFR-004 | Key computation cost | Computing the key takes at most 1 s per requesting process. | Performance | Medium | Open |
| NFR-005 | Gate equivalence | For an identical checkout and environment, the reused universe equals a fresh collection element for element: checked on every nightly run by one fresh collection compared against the stored one, with 0 differences. | Reliability | High | Open |
| NFR-006 | Agreement at the capture commit | In strict mode at the commit that lands the recapture, 100% of registry modules have a committed test count equal to the collected count. Later drift is handled by FR-017. | Reliability | High | Open |
| NFR-007 | Scheduled recapture fits its job | The scheduled recapture finishes within its job time limit in 100% of runs, deferring modules under FR-019 instead of timing out. | Reliability | Medium | Open |
| NFR-008 | New-code quality | New and changed code has at least 90% test coverage, cyclomatic complexity of at most 15 per function, and zero lint, format and type findings. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No product behaviour change | Changes are confined to test infrastructure, CI scripts, CI workflows, committed CI data and documentation. Existing product helpers may be called but not altered. | Technical | High | Open |
| C-002 | No gate is weakened | No existing gate's assertion, floor or selection is loosened. Reuse changes only where the collected data comes from. | Technical | High | Open |
| C-003 | Fail safe | Every doubt about a stored collection resolves to a fresh collection, never to trusting it. | Technical | High | Open |
| C-004 | Canonical producer only | Timing data is written only by the existing capture producer. Shard counts stay declared in the registry and validated by the existing skew check; the mission adds no second derivation. | Technical | High | Open |
| C-005 | No heavy suites in mission work | Implementers and reviewers run targeted files and named gate files, not whole heavy directories. Measured captures are run by the orchestrator, serially, from a fully synced environment on the project's pinned interpreter. | Process | High | Open |
| C-006 | No new allowlist | The mission introduces no new allowlist or baseline entry. | Technical | High | Open |
| C-007 | Bin-packing unchanged | The shard derivation algorithm is not changed. | Technical | Medium | Open |
| C-008 | Existing publication path | The generalised scheduled recapture proposes changes through the path the charter-only recapture already uses; it never pushes to the primary branch. | Process | High | Open |
| C-009 | No version numbers | The mission assigns no release version to its changes. | Process | Medium | Open |
| C-010 | Two interpreters stay two | The mission does not align the interpreter versions of the two workflows; each consuming job stores and reuses its own collection. | Technical | Medium | Open |

### Key Entities

- **Test universe**: the full list of collected tests with their markers, as one collection run reports it.
- **Collection key**: a digest of the committed repository tree and the collecting environment.
- **Stored collection**: a test universe saved with its key and its origin (commit and tree).
- **Reuse report line**: one line per request stating `reused` or `collected` and the key.
- **Module timing record**: per CI module, the measured per-test durations and test count.
- **Capture provenance record**: per CI module, which run captured it and how that run ended.
- **Mismatch allowlist**: the list of modules excused from the count agreement check; removed by this mission.

### Adjudicated out of scope

These are recorded so they are not re-raised; none produces work.

- **#5561 item "hoist duplicated floor constants"**: the only duplicated pair named in the parent issue is already retired. The remaining same-named floors hold different per-gate values, and ADR `2026-09-14-1` rules on them per ratchet.
- **#5561 item "derive `_ROUTED_MODULES` instead of pinning it"**: the mutation-ownership routing census and the overwrite-ownership routing census assert that the live set equals the pinned set in both directions. A derived set would compare a value with itself.
- **Battery per-file timing recapture** (see #5555): it uses the same capture pattern but a different data set and workflow; folding it would double the measured-capture work.
- Gate cost/benefit decision (see #2913), charter shard cost (see #5526), a new module row (see #5275).

### Operator action outside this mission

The publish failure reported in #5536 is a rejected push (HTTP 403): the token stored for the scheduled recapture cannot write to the repository. Code cannot fix that. The mission makes the failure name the missing permission; the operator replaces or re-scopes the token. Until then the scheduled recapture captures but cannot propose.

### Planning checks

These were assumptions in the first draft; each is load-bearing and is verified during planning before work is cut.

- The CI cache can restore a stored collection in a re-run of either workflow, keyed on the collection key.
- No parametrised test id embeds the temporary home directory the collection runs under (it would break NFR-005).
- The total serial capture time for the modules in FR-013, measured on one module of each size class before the full pass. `charter` alone takes about 18 minutes.
- Which environment switches change collection, as the declared list for FR-002.
- The nightly workflow's job layout, to place the NFR-005 comparison.

### Issue references

- Addressed: #5559, #5561, #5536.
- Context only: parent #5104 and closed parent #5086; follow-up of #5510; see #5189, #4315, #4865, #5098, #5555, #2913, #5526, #5275.
- Pull requests, for context: PR #5560 (landed the sibling mission) and PR #5557 (its closed predecessor).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In three consecutive per-PR runs, no test in a consuming job performs a collection, and every collecting test reports that it reused the stored one. — [build] · no-op passable: no
- **SC-002**: In those three runs, the slowest collecting test's setup takes at most 15 seconds each time. — [build] · no-op passable: no
- **SC-003**: A committed change anywhere in the repository, an uncommitted change, a different interpreter and a different environment switch each cause a fresh collection on the next request, demonstrated once per case. — [build] · no-op passable: no
- **SC-004**: At the capture commit, no module is excused from the count agreement check and all registry modules agree in strict mode. — [build] · no-op passable: no
- **SC-005**: Every registry module has a valid capture provenance record, and removing one makes the provenance check fail. — [build] · no-op passable: no
- **SC-006**: Run through its real entry point against a fixture with one drifted non-charter module, the recapture refreshes that module and no other; the first scheduled run on the primary branch after landing is recorded as post-merge evidence. — [build] · no-op passable: no
- **SC-007**: A deliberately planted violation makes each consuming gate fail both when the test universe is reused and when it is collected fresh. — [ratchet] · no-op passable: no
