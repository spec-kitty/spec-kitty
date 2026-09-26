# Mission Specification: CI Coverage Honesty

**Mission Branch**: `feat/ci-coverage-honesty`
**Created**: 2026-09-25
**Status**: Draft
**Input**: Make a green `main`/nightly mean the tests actually ran — close the CI shard-selection blind spots that let regressions ship undetected, and make the honest nightly a release gate.

## Context & Motivation

The per-module CI selector (`.github/ci-module-registry.yml` + `scripts/ci/gate_selection.py`) keys test shards on **source roots** but has **no model of which source a test exercises**. Push-to-`main` is diff-scoped exactly like a PR (the nightly full run is the only cross-module net). Two masking mechanisms result:

- **Foreign-coverage masking** — a row keyed on narrow roots (e.g. `agent` → `src/specify_cli/agent_utils/**`) runs its whole mirror `tests/<module>/`, which hosts cross-cutting tests of *other* subsystems. Those tests are skipped whenever only the exercised subsystem changes. `tests/agent/` imports its own root in only ~4 of ~86 files; the `agent` and `review` shards each ran **0 of the last 15** `main` "CI Modules" runs.
- **Non-enrollment** — some suites belong to no module row at all: `live_work` (1 test dir in `out_of_matrix_test_dirs`), `tests/integration/**` (1015 tests, 843 marker-orphaned) plus `tests/next/**` (the `integration_tests_next` tier declares both but is unwired), and in-matrix-dark packages `config`, `calibration`, `tasks_authoring`, `diagnostics`, `bootstrap` (their tests exist only in out-of-matrix dirs). (`specify_cli.schemas` is a data-only dir — `wps.schema.json`, no `__init__.py` — already content-tested; not an import-coverage target.)

The authority guard `tests/architectural/test_gate_selection_authority.py` did not catch this because it validates a **phantom directory** (`tests/agent_utils`, which does not exist) via a self-referential mirror. Real regressions have shipped to a green `main` undetected (a charter `generate --force` bug — since fixed; a review-cycle fail-close bug — tracked as `#5036`). This mission makes the signal honest and turns the honest nightly into a release precondition.

Parent epic: CI pipeline honesty (`#4437`). Root-cause writeup: `#5034`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every shard tests its own source (Priority: P1)

A maintainer changes a source package and trusts that CI's green tick means the tests covering that package actually ran.

**Why this priority**: This is the core honesty defect. Without it, a green `main` is not evidence the changed code was tested, which is the failure that shipped real regressions.

**Independent Test**: The foreign-coverage guard records a committed measured baseline (per-row own-root ratios + the dark-root set) and passes at that baseline; it fails only when a NEW dark root appears or a ratio regresses.

**Acceptance Scenarios**:

1. **Given** the committed foreign-coverage baseline, **When** the guard runs on the current tree, **Then** it passes (records `next`→`specify_cli.runtime` as honest dark-root debt), and **When** a row later declares a root no test imports, **Then** it fails naming that new dark root.
2. **Given** a row's own-root ratio, **When** it drops below the committed baseline, **Then** the guard fails (shrink-only ratchet); improving it ratchets the baseline up.
3. **Given** the authority guard test, **When** it derives a module's test tree, **Then** it references only directories that exist on disk (no phantom `tests/agent_utils`) — and stays green.

---

### User Story 2 - No source package is dark (Priority: P1)

A maintainer changes any `src/**` package and at least one in-matrix test that exercises it runs on that change.

**Why this priority**: Non-enrolled packages (`schemas`, `config`, `live_work`, …) run in no per-PR/main lane; a regression there is invisible until unrelated work happens to select it. Equal-severity honesty gap to Story 1.

**Independent Test**: The src-reachability guard hard-fails on any *truly-dark* package (imported by no test anywhere) and holds a shrink-only baseline of in-matrix-dark packages (tested only nightly/out-of-matrix); remediation shrinks that baseline.

**Acceptance Scenarios**:

1. **Given** the committed truly-dark baseline (23 packages tested nowhere today, F18), **When** a NEW truly-dark package appears, **Then** the guard HARD-fails naming it (no new untested-anywhere code can land); data-only packages (no non-`__init__` `.py`) excluded.
2. **Given** the committed in-matrix-dark baseline (27 packages today, many deliberately nightly-only), **When** a NEW in-matrix-dark package appears, **Then** the guard fails; **When** remediation enrols one, **Then** the baseline shrinks and the guard asserts the shrink.
3. **Given** the newly-minted `live_work` row (for per-PR execution of its 149 tests) and the 5 enrolled dark packages, **When** WP02 lands, **Then** those 6 leave the in-matrix-dark baseline; `shard_count` is measured, not guessed.

---

### User Story 3 - Orphaned integration suite runs nightly and reds self-surface (Priority: P1)

A maintainer relies on the nightly to run the full behavioral corpus (including the 1015-test integration suite) and to make any red loudly visible and tracked.

**Why this priority**: The integration corpus currently runs in no CI lane; and even the suites that do run nightly fail only into logs (`if: always()` fail-loud, `#4212`) with no tracked artifact. Both undermine the nightly as a safety net.

**Independent Test**: Assert a workflow invokes the integration corpus on the nightly cadence, and that a simulated nightly red produces exactly one deduped P0 issue plus a job failure.

**Acceptance Scenarios**:

1. **Given** the nightly cadence, **When** it runs, **Then** all of `tests/integration/**` executes (run-all-regardless), bounded within the per-shard job timeout (sharded if needed).
2. **Given** a nightly run-all-regardless suite goes red, **When** the run completes, **Then** the job fails loudly AND a `priority:P0` issue is opened/updated, deduped by a stable per-suite key (never a new issue per night).
3. **Given** the suite goes green on a later night, **When** the run completes, **Then** the auto-P0 for that suite key is resolved/closed (not left dangling).

---

### User Story 4 - A release cannot ship on unproven tests (Priority: P1)

A release owner runs the release workflow; it refuses to build/publish unless a nightly run for the exact release commit is green, and it triggers that nightly as a precondition.

**Why this priority**: The honest nightly is only a real gate if releases depend on it. Today `release.yml` (tag push / dispatch) has no dependency on nightly test evidence; `release-readiness.yml` validates only release metadata and explicitly disclaims owning test evidence.

**Independent Test**: Simulate a release run against a commit with no green nightly and assert publication is blocked; simulate against a green nightly for the same SHA and assert it proceeds.

**Acceptance Scenarios**:

1. **Given** a release run for commit `X`, **When** no green nightly exists for `X`, **Then** the release triggers a nightly for `X` and blocks build/publish until it is green.
2. **Given** a red or missing nightly for the release commit, **When** the release proceeds to publish, **Then** it fails closed (no publish).
3. **Given** a green nightly for the exact release commit, **When** the release runs, **Then** build/publish proceeds.

### Edge Cases

- **Legitimately foreign test dir** (e.g. an aggregate module with no single mirror): the foreign-coverage guard must allow an explicit, justified allow-list entry rather than forcing a false split — the allow-list is the recorded exception, not a silent pass.
- **New src package added later**: the src-reachability guard must fail closed on a brand-new dark package, forcing enrollment at introduction time.
- **Integration wall-clock blows the timeout**: if the single integration lane overruns, it must shard by measured durations rather than silently truncate; per-PR promotion stays out of scope (→ `#5037`).
- **Auto-P0 when GitHub API/token is unavailable** (e.g. fork run): escalation degrades to fail-loud only, never crashes the workflow, and never leaks a token.
- **Release run for a commit whose nightly is in-flight**: the release waits for that nightly's terminal result rather than racing it.
- **Consecutive red nights**: exactly one open P0 per suite key; subsequent reds update, not multiply.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Foreign-coverage guard | As a maintainer, I want each registry row's test dirs to actually exercise that row's `roots:` above a threshold (with a recorded allow-list for justified aggregates) so that no shard is selected while the tests for its own source are skipped. | High | Open |
| FR-002 | Src-reachability guard | As a maintainer, I want every `src/**` package to be exercised by at least one in-matrix test dir so that no source package is dark on PR/main. | High | Open |
| FR-003 | Fix phantom-mirror authority bug | As a maintainer, I want `test_gate_selection_authority.py` to validate only directories that exist on disk so that the authority guard stops self-validating against a non-existent `tests/agent_utils`. | High | Open |
| FR-004 | Ratchet agent own-root coverage | As a maintainer, I want the `agent` row to explicitly own `tests/specify_cli/agent_utils` (alongside `tests/agent`) so its recorded own-root ratio ratchets up — improving honest coverage of `agent_utils`. (Per F17 the per-root floor is already met via `tests/agent/test_agent_utils_status.py`; this is a shrink-only improvement, not a red-fix.) | Medium | Open |
| FR-005 | Enrol live_work for per-PR execution (#4732) | As a maintainer, I want `tests/specify_cli/live_work` enrolled into an in-matrix module row (removed from out_of_matrix) with that row's shard timings re-measured, so live_work's 149 tests run per-PR/main. (A *dedicated* live_work shard via the scrub+ci-router path is deferred as a follow-up — the registry's transcription guards make it disproportionate here; enrolment fully achieves the per-PR-execution intent.) | High | Open |
| FR-006 | Wire integration + next into nightly + retire dead tier (#4729) | As a maintainer, I want `tests/integration/**` AND `tests/next/**` run on the nightly cadence (run-all-regardless), and the dead `integration_tests_next` special tier retired with its `test_module_shard_registry` assertion repointed to the new lane, so the corpus runs and no dead tier is left declared. (Tier retirement lands in WP03 alongside the replacement lane so the guard is repointed, never left red.) | High | Open |
| FR-007 | Nightly-red → auto-P0 escalation | As a maintainer, I want a red nightly run-all-regardless suite (incl. the integration lane) to fail loudly AND open/update a `priority:P0` issue deduped by a stable per-suite key (and resolve it on green) so that hidden reds self-surface. | High | Open |
| FR-008 | Release gates on green nightly | As a release owner, I want the release workflow to dispatch a nightly for the exact release commit (by the release tag, using a dedicated `actions:write` token) and block build/publish until it is green so that releases cannot ship on unproven tests. Requires operator secret `RELEASE_NIGHTLY_DISPATCH_TOKEN`. | High | Open |
| FR-009 | Enrol remaining dark packages | As a maintainer, I want `config`, `calibration`, `tasks_authoring`, `bootstrap` brought under an in-matrix test dir (their tests exist in out-of-matrix dirs — promote them) so the in-matrix-dark baseline shrinks. (`schemas` = data-only, excluded. `diagnostics` is imported only by `tests/e2e` — a per-PR *path-routed* dir, so it IS covered but not as a module shard; it stays in the recorded in-matrix-dark baseline as honest debt, not force-enrolled.) | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Measured sharding | Any new/changed `shard_count` is derived from measured per-test durations via `scripts/ci/capture_shard_timings.py` + LPT bin-packing; inter-shard skew ≤ 20%. Never guessed. | Reliability | High | Open |
| NFR-002 | Guard speed | The new architectural guards (FR-001/FR-002) each complete in ≤ 5 s locally so they can join the always-on architectural battery without bloating it. | Performance | Medium | Open |
| NFR-003 | No per-PR wall-clock regression | This mission adds no test execution to the per-PR/main lanes beyond the enrolled `live_work` + dark-package dirs; integration stays nightly-only. Per-PR total wall-clock does not increase by more than the enrolled dirs' measured time. | Performance | High | Open |
| NFR-004 | Integration lane budget | The nightly integration lane's worst shard lands under the `module-tests.yml` per-shard job timeout (shard by measured durations if the monolith overruns). | Reliability | High | Open |
| NFR-005 | P0 dedup bound | At most one open auto-P0 issue exists per suite key at any time; escalation is idempotent across consecutive red nights. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Registry-row-driven | Adding a module is a registry row, never a new per-module workflow file; the reusable-workflow-per-caller ceiling (20) is not exceeded. | Technical | High | Open |
| C-002 | Authority gates | Changes to the selection authority are gated by `test_gate_selection_authority.py` and `test_pyproject_shape.py`; both must pass. | Technical | High | Open |
| C-003 | Integration stays nightly-only | Per-PR promotion of `tests/integration/**` is out of scope; it is deferred to the assessment ticket (`#5037`). | Technical | High | Open |
| C-004 | CI honesty only, not the exposed bugs | This mission fixes CI selection/honesty; it does not fix the product bugs the honesty exposes (charter already fixed; review-cycle fail-close is `#5036`). | Business | High | Open |
| C-005 | Fail-closed escalation | Auto-P0 escalation must degrade to fail-loud when the GitHub API/token is unavailable, never crash the workflow, and never leak a token (fork-safe). | Technical | High | Open |

### Key Entities

- **Module row**: a `.github/ci-module-registry.yml` entry — `module`, `roots`, `cov_targets`, `test_dirs`, `shard_count`, `tier`. The unit of selection and the place a fix is expressed.
- **Selection authority**: `scripts/ci/gate_selection.py` — maps a changed-path set to selected modules/shards; the single parsed source both `ci-router.yml` and `ci-modules.yml` consume.
- **Foreign-coverage guard / src-reachability guard**: new architectural invariants (in `tests/architectural/`) that assert, respectively, test↔root alignment per row and full `src/**` reachability by in-matrix tests.
- **Nightly run-all-regardless suite**: a `ci-nightly.yml` job that runs to completion under `if: always()`; the unit an auto-P0 is keyed to.
- **Auto-P0 record**: a `priority:P0` GitHub issue keyed by a stable per-suite id, opened/updated on red and resolved on green.
- **Release gate**: the dependency edge from `release.yml` build/publish onto a green nightly for the exact release SHA.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every registry module row, a source-only diff to its `roots:` selects a shard that runs ≥1 test importing that source — **0 foreign-only shards** (excluding recorded allow-list aggregates).
- **SC-002**: two committed shrink-only baselines that can never GROW without a guard failure (no new masking can land): a **truly-dark baseline** (packages tested nowhere — measured 23 today, F18; import-analysis structurally can't see subprocess/CLI-tested modules, so this is a ratchet not a zero-floor) and an **in-matrix-dark baseline** (tested only nightly — measured 27, F18). This mission shrinks the in-matrix-dark baseline by 5 (`live_work` + subpkgs, `config`, `calibration`, `tasks_authoring`, `bootstrap`). Data-only packages (no non-`__init__` `.py` module) excluded; `diagnostics` stays as recorded debt (e2e-covered, not a module shard).
- **SC-003**: All `tests/integration/**` (≈1015) AND `tests/next/**` tests execute in the nightly cadence; the dead `integration_tests_next` tier is retired.
- **SC-004**: A red nightly run-all-regardless suite yields **exactly one** tracked `priority:P0` (deduped) plus a loud job failure within one nightly cycle; a subsequent green resolves it.
- **SC-005**: A release run **cannot publish** unless a nightly for the exact release commit is green (verified by a blocked run against a non-green commit and an allowed run against a green one).
- **SC-006**: The authority guard references **zero** non-existent test directories (no phantom mirrors).

## Assumptions

- The nightly (`ci-nightly.yml`) remains the full-mode run-all-regardless cadence and is the correct home for the integration corpus and the release precondition.
- `agent_utils` has (or can be given) tests that genuinely import `agent_utils`; if coverage is currently thin, minimal focused tests are authored to satisfy FR-004.
- The GitHub Actions runtime for the release workflow can dispatch and await `ci-nightly.yml` for a specific SHA (via `workflow_dispatch` + `workflow_run`/polling).
- The foreign-coverage threshold and the aggregate allow-list are implementation details to be fixed in the plan phase; the spec fixes only the invariant, not the number.
