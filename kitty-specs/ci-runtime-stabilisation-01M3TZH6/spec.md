# Mission Specification: CI runtime stabilisation

**Mission Branch**: `issue-5510-ci-runtime-stabilisation`
**Created**: 2026-10-01
**Status**: Draft (post-spec squad folds applied)
**Input**: Operator brief "CI runtime remediation/stabilisation" (issue #5510), built on a 24-hour CI census (2026-09-30T05:06Z → 2026-10-01T05:06Z) and a profile-loaded pre-spec squad synthesis (research brief + options memo).

## Context

A 24-hour census of the CI pipeline (837 workflow runs, 6,564 jobs, 24,166 runner-minutes) found:

- Pull-request CI waits a median 33 minutes whenever the architectural battery runs (81% of PR router runs), against 4.6 minutes when it is skipped. The battery decides the PR wallclock in 42% of completed pipelines, finishing a median 11.8 minutes after every other test job; its failures are deterministic ratchet/census gates that only report after 16–25 minutes.
- The battery uses half its runner: its worker setting resolves to 2 workers on a 4-vCPU runner. Its worst run reached 25:09 against a 30-minute job timeout.
- About 12–15% of runner-minutes are duplicate work: three legacy router test jobs re-run 99.9% of the module rows' tests (~1,104 min/day); a PR turning ready-for-review re-runs an already-green commit (~1,210 min/day); the corpus suite runs two or three times (~540 min/day on co-run commits). No live check compares the test sets that different jobs select.
- Several battery test files repeat identical whole-tree scans or suite re-collections within the same file.
- The nightly run does not run the full architectural battery (it runs 664 of 3,561 battery tests, 18.6%), contradicting ADR 2026-09-26-1 and the premise of the by-design closure of #5302. Pull requests that change only CI configuration never run the battery, so the gates that guard that configuration never run on the change that edits it.
- The consolidation module shard is a single unsplit shard balanced on uniform weights, because its committed timings (782 entries) no longer match the ~1,617 tests it collects. Its last 7 green runs took 15.5–26.2 minutes; the census p90 of 47.7 minutes (slow runs of 35–48 minutes that set the four longest pipelines) included PR-specific outliers (research D-21).
- The CI module registry still describes the battery as always-on.

Operator decisions recorded as Decision Moments: skip-if-green guard for ready-for-review re-runs, applied in full to the router, module and packs workflows with an ADR amendment; main-push concurrency is out of scope (Follow-up: #5511); CI-config-only changes run the full battery through a new path group; the Packs workflow owns the corpus suite and corpus failures become advisory; consolidation shard split, dead-symbol scan caching and a two-shard battery are in scope.

Terminology: "CI path routing" below means the router's changed-path → job selection (the `ci-router.yml` filter block and job `if:` gates); "gate selection" means the derived `scripts/ci/gate_selection.py` reading of it. Bare "routing" is not used (Terminology Canon).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Honest nightly architectural safety net (Priority: P1)

A maintainer relies on the nightly run as the full backstop for every gate that pull-request CI path routing may skip. Tonight's nightly runs every architectural test the per-PR fast gate job and battery shards could run, and a red result surfaces in the nightly summary that the release gate reads.

**Why this priority**: Every narrowing or re-selection elsewhere in this mission is only safe if the full battery runs somewhere unconditionally; today the documented guarantee is false.

**Independent Test**: Dispatch the nightly workflow and confirm the architectural backstop collects exactly the set produced by collecting `tests/architectural` with the per-PR marker exclusions and named deselects, and that its outcome is in the nightly summary's dependency set and the release nightly gate.

**Acceptance Scenarios**:

1. **Given** a nightly run, **When** the architectural backstop executes, **Then** the set of collected test node-ids equals fast-gate set ∪ shard-1 set ∪ shard-2 set, which equals a collect-only run of `tests/architectural` minus the per-PR marker exclusions and named deselects.
2. **Given** an architectural test fails in the nightly backstop, **When** the nightly summary is produced, **Then** the nightly reports failure and the release nightly gate sees it.

---

### User Story 2 - Faster, earlier battery verdict on a code PR (Priority: P1)

A contributor pushes a source change. The deterministic ratchet and census gates report within minutes in their own job; the remaining battery runs on all runner cores, split across two shards, so the full architectural verdict arrives in roughly half today's time.

**Why this priority**: The battery is the single most frequent critical-path job and the most common late red.

**Independent Test**: Dispatch the router workflow (pr and full modes) on the mission branch and compare fast-gate and battery-shard durations, worker counts and peak memory against the census baseline.

**Acceptance Scenarios**:

1. **Given** a PR that breaks a ratchet gate, **When** CI runs, **Then** the fast gate job reports the failure within 5 minutes of pipeline start.
2. **Given** a PR that triggers the battery, **When** CI runs, **Then** the battery executes as two shards whose logs show four workers each, and fast gate ∪ shard 1 ∪ shard 2 equals the battery selection with the three sets pairwise disjoint.
3. **Given** a battery test file is added (or a file is injected that no shard claims), **When** the partition check runs, **Then** a file in no set or in two sets fails the check.

---

### User Story 3 - No duplicate runs or selections (Priority: P2)

A maintainer watching runner usage sees each test executed once per change by the job that owns it: no legacy router copies of module rows, a single corpus lane, and no full re-run when a draft PR that already passed is marked ready for review.

**Why this priority**: Duplicates waste 12–15% of runner-minutes and slow every other queue; without a live check they creep back.

**Independent Test**: Run the cross-job overlap check against the live workflow definitions; mark an already-green draft PR ready for review and observe that the expensive jobs skip, naming the matched prior run.

**Acceptance Scenarios**:

1. **Given** a change that selects the cli, status or consolidation module rows, **When** CI runs, **Then** those tests run only in the module rows.
2. **Given** a change that previously triggered the router corpus job, **When** CI runs, **Then** the corpus tests run exactly once, in the Packs corpus lane.
3. **Given** a workflow is edited so that two same-tier per-PR jobs select overlapping test node-ids, **When** the overlap check runs, **Then** it fails unless every overlapping node is covered by a reasoned allowlist entry.
4. **Given** a draft PR whose (workflow, PR, head commit, base commit) already has a successful pull-request run, **When** it is marked ready for review, **Then** that workflow's expensive jobs (every path-gated job) skip, its log names the matched prior run, its required check reports success, and downstream coverage aggregation reuses the matched run's coverage artifacts. (Always-on lanes, including the fast gate job and the prose scan, still run; on a prose-only change the docs test job may also run — see SC-005.)
5. **Given** a draft PR whose prior run failed, was cancelled, is still in progress, or ran against a different base commit, **When** it is marked ready for review, **Then** the workflow runs normally.

---

### User Story 4 - CI-configuration changes are guarded on their own PR (Priority: P2)

A maintainer edits a workflow, a composite action under `.github/actions/**`, a CI script, the module registry, shard timings, `pytest.ini`, `pyproject.toml` or the `Makefile`. The architectural battery — which holds the gates that check exactly those files — runs on that PR instead of on some later unrelated PR.

**Why this priority**: Today a CI-config defect surfaces on the next source PR and is attributed to the wrong change.

**Independent Test**: Feed CI-config-only changed-path sets to gate selection and confirm it selects the battery, while the `ci` path group still gates no other router job.

**Acceptance Scenarios**:

1. **Given** a PR that changes only `.github/workflows/**` (or any other path in the CI-config set), **When** CI path routing runs, **Then** the battery is selected.
2. **Given** a prose-only PR, **When** CI path routing runs, **Then** the heavy battery shards are not selected (the always-on fast gate job still runs).

---

### User Story 5 - Consolidation shard no longer sets the slowest pipelines (Priority: P3)

A contributor touching consolidation code waits for two balanced consolidation shards instead of one long one.

**Why this priority**: Its outlier runs set the four longest pipelines in the census and it is balanced on stale, uniform weights, but it is triggered less often than the battery and its recent green runs (15.5–26.2 minutes) are shorter than the census suggested.

**Independent Test**: Run the consolidation module row and compare per-shard durations with the census.

**Acceptance Scenarios**:

1. **Given** a change selecting the consolidation module, **When** CI runs, **Then** the consolidation tests run in two shards balanced by re-captured timings, each finishing within the NFR-006 bound and within 25% of each other's duration.

---

### User Story 6 - Repeated scans computed once (Priority: P3)

The heaviest battery files compute each distinct whole-tree scan or suite collection once per file, while self-mutation tests that point the scan at a temporary tree still get a fresh, honest scan.

**Independent Test**: Run each affected file with durations and confirm the duplicate scan cost is gone and every self-mutation test still fails on its injected violation.

**Acceptance Scenarios**:

1. **Given** two tests in one file request the same scan of the same root, **When** the file runs, **Then** the scan executes once.
2. **Given** a self-mutation test scans a temporary tree, **When** it runs, **Then** it receives a scan of that tree, not a cached result for the real tree.

### Edge Cases

- A ready-for-review event arrives while the draft run for the same commit is still in progress: the workflow runs normally (never skips on an unfinished run).
- A re-run attempt or `workflow_dispatch` on the same commit is never suppressed by the skip-if-green guard.
- The base branch moved between the draft run and ready-for-review: the prior run tested a different merge tree, so the workflow runs normally.
- Shard timing data is missing or its length differs from the collected test count: balancing does not silently fall back; the mismatch is visible as a warning and summary line.
- A new battery test file has no timing data: it is still assigned to exactly one shard.
- More workers raise peak memory of AST-scanning tests: caches hold findings, not syntax trees.
- A source path matching no path group still triggers run-all (unchanged, #3463).
- Stress-marked tests that only the deleted router jobs ran keep a lane that executes them.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Nightly full-battery backstop | As a maintainer, I want a nightly job whose collected architectural set equals fast gate ∪ battery shards (a collect-only run of `tests/architectural` minus the per-PR marker exclusions and named deselects), wired into the nightly summary's dependencies and the release nightly gate, so that the "green nightly means the full suite ran" guarantee holds (folds #3265). | High | Open | [build] | no — a set-equality check against a collect-only run fails on today's `fast or unit` nightly |
| FR-002 | Battery and corpus use all runner vCPUs | As a contributor, I want the battery shards, the nightly backstop and the corpus job to run with an explicit worker count equal to the runner's vCPUs (CI only), with CI-log evidence of four workers (`gw0`–`gw3`) and a guard against regressing to physical-core auto-detection, so that the runner is fully used. | High | Open | [build] | no — today's logs show only `gw0`/`gw1` |
| FR-003 | Fast-fail static gate job | As a contributor, I want the deterministic ratchet and census gates — an explicit, registry-held roster with a per-file time budget — to run in their own always-on fast job (operator decision DM 01M3V1FAQV07WJF3RYAFN9J7GC; modelled on the existing terminology / layer-rules / archive-freeze fast lanes and added to the per-change suite-job ledger), removed from the battery shards, so that their red shows within minutes. | High | Open | [build] | no — today these gates only report inside the 23-minute battery |
| FR-004 | Two-shard battery with partition proof | As a contributor, I want the remaining battery split across two shards by file — shard count held in the module registry, balanced by the single shared shard selector in file-granularity mode — with a three-way partition check (fast ∪ shard 1 ∪ shard 2 = selection, pairwise disjoint) computed from the commands the workflows actually run and evaluable by the existing gate-coverage model, so that wallclock halves without losing a test. | High | Open | [build] | no — an injected unassigned file is the positive control |
| FR-005 | Visible timing-data mismatch | As a maintainer, I want the shared shard selector to surface a timing-length mismatch as a warning and step-summary line, and never to fall back silently to uniform weights for the battery, so that shard imbalance is visible (#5092 acceptance criterion 2). | Medium | Open | [build] | no — today the fallback is silent |
| FR-006 | Per-file caching of repeated scans | As a contributor, I want repeated scans and suite collections in the interpreter-shard-coverage, clock-call-ban and dead-symbol gate files computed once per file, keyed on the resolved scan root and its inputs, holding findings rather than syntax trees, with self-mutation tests still scanning their own tree, so that duplicate work disappears without weakening any gate. | Medium | Open | [build] | no — each self-mutation test must still fail on its injected violation |
| FR-007 | CI-config changes select the battery | As a maintainer, I want a new non-source `ci_config` path group (workflows, `.github/actions/**`, CI scripts, `pytest.ini`, `pyproject.toml`, `Makefile`, module registry, shard timings) that gates only the battery, added to the router filter block and the battery's `if:` gate and to the oracle's heavy-battery non-source group set, with the existing `ci` group and its registry mirror untouched and the reversal of #4386 / #5302 recorded as a router-two-authority contract amendment, so that CI-config gates run on the change that edits CI config. | High | Open | [build] | no — gate selection for a workflow-only diff selects no battery today |
| FR-008 | Remove duplicate router module-path jobs | As a maintainer, I want the legacy router cli, status and consolidation test jobs removed (router gate dependencies and per-change suite-job ledger updated), and the stress-marked tests they alone ran kept in a lane that executes them, so that those tests run once, in their module rows. | High | Open | [build] | no — the overlap check (FR-010) fails while the jobs exist |
| FR-009 | Single, advisory corpus lane | As a maintainer, I want the Packs workflow to be the only owner of the corpus suite — its trigger paths covering every path that triggered the router corpus job — with the router corpus job removed, the dead coverage target corrected, and corpus failures explicitly advisory (operator-accepted downgrade from the required router gate), so that the corpus runs once per change (partial #3315). | Medium | Open | [build] | no — the overlap check (FR-010) fails while both lanes exist |
| FR-010 | Live cross-job test-set uniqueness check | As a maintainer, I want the existing gate-coverage model re-keyed to the live per-PR jobs and the live half of the same-tier uniqueness test restored, using one real collect-only run of the tree plus per-job marker/argument filtering (module rows and battery legs expanded through the shared shard selector), comparing the resulting node-id sets pairwise (conservatively, regardless of path conditions) within the same OS-family tier — not interpreter-keyed, because module rows run Python 3.11 while router and Packs jobs run 3.12 and interpreter-keyed tiers would hide the very duplicates being removed (research D-14) — against a reasoned, shrink-only allowlist of at most 10 entries, so that duplicate selections cannot creep back. | High | Open | [build] | no — fails on today's workflows (router cli/status/consolidation/corpus overlaps) |
| FR-011 | Skip-if-green on ready-for-review | As a contributor, I want the router, module and packs workflows, on a ready-for-review event, to skip their expensive jobs when a successful pull-request run of the same workflow exists for the same (PR, head commit, base commit) — decided by one shared CI helper folded into each workflow's selection output, printing the matched run, with coverage aggregation reusing the matched run's coverage artifacts and the policy recorded as an amendment to ADR 2026-09-23-1 — so that an already-green commit is not re-run. | High | Open | [build] | no — negative cases (failed/cancelled/in-progress prior run, moved base, re-run, dispatch) must still run |
| FR-012 | Split the consolidation module shard | As a contributor, I want the consolidation module row split into two shards with re-captured timings, so that it stops setting the longest pipelines (partial #5086). | Medium | Open | [build] | no — registry shard count and timing length are checked |
| FR-013 | Registry describes the battery truthfully | As a maintainer, I want the module registry's battery entry (trigger, shard count, fast-gate roster, deselects) and the tests that pin it to describe the actual behaviour, so that the registry is not a second, wrong authority. | Medium | Open | [ratchet] | no — the registry pin test fails if the entry drifts from the workflow |
| FR-014 | Decision records and docs updated | As a maintainer, I want dated amendment sections on ADR 2026-09-26-1 (nightly backstop, sharded battery, worker policy) and ADR 2026-09-23-1 (skip-if-green), the router-two-authority contract amendment, and the testing docs updated, so that the documentation matches shipped behaviour. | Medium | Open | [build] | no — a static ADR-amendment test (WP19, red-first) fails until both dated amendments exist and link the mission contracts; the remaining prose is review-verified with docs-freshness and terminology checks |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Battery wallclock | The slowest of the fast gate job and the two battery shard jobs completes in a median of ≤ 14 minutes over ≥ 3 recorded CI runs on the mission branch (baseline: 23.4 minutes for the single battery job). | Performance | High | Open |
| NFR-002 | Early red | The fast static gate job completes within ≤ 5 minutes of pipeline start in ≥ 3 recorded CI runs. | Performance | High | Open |
| NFR-003 | Timeout headroom | The per-PR fast gate job and heavy battery leg timeouts stay ≤ 30 minutes, and each completes within ≤ 60% of its job timeout on its slowest recorded run (headroom rule); the nightly backstop's timeout is ≤ 40 minutes under the same headroom rule (slowest recorded backstop run ≤ 24 minutes); zero per-test timeout failures; the slowest single battery test is ≤ 180 seconds — a breach of that bound at closeout is either fixed or carries a recorded operator waiver in the evidence file. | Reliability | High | Open |
| NFR-004 | No duplicate selections | The cross-job uniqueness check (FR-010) reports 0 overlapping node-ids outside the allowlist on the mission's final tree, and the allowlist holds ≤ 10 entries, each with a recorded reason. | Efficiency | High | Open |
| NFR-005 | Memory headroom | Peak resident memory of each battery shard job, as recorded in the job log by a memory sampler, stays below 12 GB on the 16 GB runner. | Reliability | Medium | Open |
| NFR-006 | Consolidation shard duration | Each consolidation module shard completes within a p90 of ≤ 15 minutes over ≥ 3 recorded CI runs, and the two shards' durations differ by ≤ 25% (balance). Baseline (research D-21): the single shard's last 7 green runs took 15.5–26.2 minutes on uniform weights (782 timings vs ~1,617 collected tests); the census p90 of 47.7 minutes included PR-specific outliers. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No architectural gate weakened | For every changed-path set, the set of architectural tests that run per PR is a superset of today's set; the nightly additionally runs the full battery. (The corpus downgrade to advisory is the single operator-accepted exception, scoped to FR-009.) | Technical | High | Open |
| C-002 | Raw-source tests stay always-on | Tests that read raw source or prose stay in an always-on lane (#4851). | Technical | High | Open |
| C-003 | Router two-authority contract | The router filter block and the job `if:` gates in `ci-router.yml` remain the two CI path routing authorities and stay in lockstep; `scripts/ci/gate_selection.py` remains a derived parser and is not given a parallel encoding; the FR-007 change is recorded as a contract amendment. | Technical | High | Open |
| C-004 | Battery stays non-required | The path-scoped battery jobs remain non-required checks (ADR 2026-09-23-1). | Technical | High | Open |
| C-005 | Local and module-shard parallelism unchanged | The `Makefile` keeps its auto worker setting; module shards stay serial. | Technical | Medium | Open |
| C-006 | Main-push concurrency out of scope | Per-commit concurrency for pushes to `main` is not changed in this mission (Follow-up: #5511). | Business | Medium | Open |
| C-007 | Coordinate dead-symbol edits | Edits to the dead-symbol gate files are sequenced after or coordinated with PR #5503. | Technical | Medium | Open |
| C-008 | Unmatched source still runs everything | A source path matching no path group still triggers run-all (#3463 class). | Technical | High | Open |
| C-009 | No local heavy suites | No local full run of `tests/architectural` or whole-repo suites; full validation comes from the mission PR's CI and dispatched router runs (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Technical | High | Open |
| C-010 | Single authorities extended, not duplicated | Shard partitions live in the module registry and the single shared shard selector; cross-job uniqueness lives in the gate-coverage model and the same-tier uniqueness test; no new parallel roster or uniqueness authority is introduced. | Technical | High | Open |
| C-011 | Measurement evidence recorded | Every NFR measurement and the SC-001 / SC-002 measurements cite workflow run IDs (pr- and full-mode dispatches plus the PR's own runs) in a mission evidence file written by the orchestrator at closeout. SC-001 is measured from pipeline start to the conclusion of the last battery job (fast gate and both heavy legs); SC-002 from pipeline start to the fast gate job's conclusion. | Technical | Medium | Open |

### Key Entities

- **Architectural battery**: the architectural gate selection that runs per PR; after this mission it consists of an always-on fast static gate job (operator decision DM 01M3V1FAQV07WJF3RYAFN9J7GC) plus two file-partitioned heavy shards that are selected by code-scoped and `ci_config` changes.
- **Fast static gate roster**: the registry-held list of deterministic ratchet and census gate files, each with a time budget, that run in the fast job.
- **Battery shard partition**: the assignment of every remaining battery test file to exactly one shard, proved complete and disjoint together with the fast roster.
- **CI path routing authorities**: the router filter block and the job `if:` gates in `ci-router.yml` (router-two-authority contract); gate selection is their derived reading.
- **Nightly backstop**: the scheduled full-battery run feeding the nightly summary and release nightly gate.
- **Overlap allowlist**: the reasoned, shrink-only, capped list of tolerated cross-job test overlaps.
- **Green-run match**: (workflow, pull-request event, PR, head commit, base commit, success) — the key that lets a ready-for-review run skip.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PR that triggers the battery gets its full architectural verdict in a median of ≤ 15 minutes from pipeline start (from about 25), measured from pipeline start to the conclusion of the last battery job (C-011 evidence). — [build] · no-op passable: no
- **SC-002**: A deterministic ratchet/census failure is reported to the contributor within 5 minutes of pipeline start (from 16–25 minutes), measured from pipeline start to the fast gate job's conclusion (C-011 evidence). — [build] · no-op passable: no
- **SC-003**: The nightly run executes 100% of the architectural tests the per-PR fast gate job and battery shards can run (from 18.6%). — [build] · no-op passable: no
- **SC-004**: Duplicate per-PR test selections across same-tier jobs drop to zero outside a reasoned allowlist of at most 10 entries. — [build] · no-op passable: no
- **SC-005**: An already-green commit marked ready for review consumes no expensive CI jobs, where "expensive" means every path-gated job; the always-on lanes (including the fast gate job and the prose scan, and `tests (docs)` when the prose scan reports prose-only) still run, as pinned by WP18's recorded residual. — [build] · no-op passable: no
- **SC-006**: A CI-configuration-only change runs the architectural gates on its own PR. — [build] · no-op passable: no

## Assumptions

- The public-repository runner keeps 4 vCPUs and 16 GB memory.
- Simultaneous multithreading yields a measurable speed-up for the battery workload; NFR-001 is verified empirically, not assumed.
- Measurement uses the mission PR's own CI runs (FR-007 makes them trigger the battery) plus dispatched router runs in pr and full modes, with run IDs recorded per C-011.
- #4729 and #4351 are already fixed and will be recorded as verified-already-fixed; #4914, #2927, #3463 and #5200 are context only.

## Dependencies

- PR #5503 (merged) supplies the dead-symbol session cache; WP13 adds its per-file finalizer (C-007).
- ADR 2026-09-23-1, ADR 2026-09-26-1 and the router-two-authority contract (`kitty-specs/ci-pipeline-reinstatement-01M1X35E/`) govern CI path routing and the nightly design; #4386 and #5302 record the rulings that FR-007 amends.

## Out of Scope

- Main-push concurrency for CI Modules, Packs and CI Aggregate (Follow-up: #5511, parent #4437).
- Introducing parallel workers into the serial module shards.
- Rewriting slow tests themselves (#5353 family) beyond removing duplicated scans.
- Re-capturing timings for module rows other than consolidation (#5086 remainder).
