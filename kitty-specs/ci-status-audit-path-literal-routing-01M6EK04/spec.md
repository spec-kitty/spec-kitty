# Feature Specification: Route the path-literal audit on a `status/**` diff

**Mission**: ci-status-audit-path-literal-routing-01M6EK04
**Mission ID**: 01M6EK04QX173M8CHW8EYKVZNT
**Created**: 2026-11-02
**Status**: Draft
**Issue**: [spec-kitty#6879](https://github.com/spec-kitty/spec-kitty/issues/6879)
**Input**: "ci: a src/specify_cli/status/** diff does not route tests/audit/**"

## Summary

A pull request that changes `src/specify_cli/status/**` runs no audit test. The `status`
filter group in `.github/workflows/ci-router.yml` selects the module matrix's `status`
row; `.github/ci-module-registry.yml` records `tests/audit` as an out-of-matrix directory
("no per-PR lane"), so the runtime-home guard limb
(`tests/audit/test_no_legacy_path_literals.py::test_no_handrolled_spec_kitty_home_in_global_state_modules`)
is never evaluated for that diff. That guard is the only thing standing between a
re-scattered `Path.home() / ".spec-kitty"` literal and `main`: #6367 added one to
`src/specify_cli/status/locking.py`, its PR's CI never ran `tests/audit`, and the
regression surfaced a day later as a nightly red escalated as #6582.

**Grounding on `9aed3a8012` (current `main`).** The gap is real and larger than the
issue states:

- A `src/specify_cli/status/**`-only diff matches the `status`, `mission_state`,
  `core_misc`, `execution_context` and `unit` groups. None of the jobs those groups gate
  runs anything under `tests/audit/**`.
- `tests/audit` is listed in the registry's `out_of_matrix_test_dirs`, so the module
  matrix never runs it.
- The only CI lane that names the tree — `ci-nightly.yml` `interpreter-matrix-shard-5` —
  runs it under `-m "fast or unit"`, and this module is `pytestmark = [pytest.mark.integration]`
  with no per-test `fast`/`unit` marker. Collected locally: `0 collected, 8 deselected`.
  **No lane in this repository executes the guard today**; the issue's premise that the
  nightly is its home is stale.

So the fix is not only "route `status/**` at it": the lane that we route to has to be a
lane the guard can actually run in (no marker filter).

## Approach (candidate 1 from the issue)

Add one narrowly scoped src-backed router group and one blocking router job that runs
exactly `tests/audit/test_no_legacy_path_literals.py`. Deliberately **not** chosen:

- candidate 2 (claim `tests/audit` in the module registry) — the census-gated two-file
  edit the issue defers to a maintainer decision, and it would drag the whole audit tree
  (~a full directory of integration tests) onto the per-PR path;
- candidate 3 (widen the guard into an existing per-PR job) — no existing per-PR job can
  host it: `architectural-fast`/`architectural-heavy` are file-partitioned batteries whose
  commands are pinned to the registry's `tests/architectural` base, and the duplicate-suite
  gate permits exactly one suite invocation per job (`AUTHORIZED_SUITE_INVOCATIONS_PER_JOB = 1`).

The broader blast radius the guard's scan roots (`src/specify_cli/**` + `src/kernel/**`)
imply is a CI-budget decision for the maintainers; this mission closes the reported
`status/**` gap and records the wider option in `## Deferred`.

## User Scenarios & Testing

### User story 1 — an operator's `status/**` PR catches a re-scattered literal (P1)

1. A contributor opens a PR whose only source change is `src/specify_cli/status/locking.py`
   that reintroduces `_NON_GIT_LOCK_HOME = ".spec-kitty"`.
2. `.github/workflows/ci-router.yml` selects the new `path_literal_audit` group on that
   diff and runs the new lane, which executes
   `tests/audit/test_no_legacy_path_literals.py`.
3. The guard fails on the new literal, naming `file:line` in the job log, and
   `router gate` (the required check) fails with it — on that PR, not a day later in the
   nightly.

**Independent test**: assert through the live router + workflow YAML that a
`src/specify_cli/status/**` diff selects the group and that the job gated on it runs
exactly that test file; then make the guard fail on a planted literal and watch the same
job's command fail.

### User story 2 — a change to the guard or its keystone still runs the guard (P2)

1. A PR edits `tests/audit/test_no_legacy_path_literals.py` itself, or the keystone
   resolver file whose literal the guard's non-vacuity test asserts
   (`src/specify_cli/paths/windows_paths.py`).
2. The same lane runs, so an edit that weakens the guard (or removes the keystone literal
   its non-vacuity limb detects) reds on its own PR.

**Independent test**: `select_gates` on each of those paths matches the new group.

### User story 3 — nothing else pays for it (P3)

1. A docs-only PR, a corpus-only PR, and a `src/specify_cli/dashboard/**` PR select no
   part of the new lane.
2. A prose-only `status/**` diff still down-routes it (the #4842 rule) like every other
   code shard.

**Independent test**: `select_gates` returns the group for none of those inputs; the job's
`if:` evaluates false on the prose-only golden context.

### Edge cases

- **The guard regresses to "no tests collected"** (a rename or a `-m` filter added to the
  command): exit 5 must fail the job, exactly like every directory lane in this repo.
- **The scrub row and the filter globs drift**: the transcription guard
  (`tests/architectural/test_ci_router_transcription_guards.py`) reds, so the group cannot
  exist in one authority only.
- **A `status/**` diff is proven prose-only**: the lane down-routes with the rest of the
  code shards (no new exemption is invented for it).
- **`src/kernel/paths.py` changes**: included in the group, because deleting its
  allowlisted literal inverts the guard's non-vacuity limb.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | A `status/**` diff routes to the guard | As a contributor, I want a `src/specify_cli/status/**` diff to run `tests/audit/test_no_legacy_path_literals.py` per PR so that a re-scattered runtime-home literal is caught on its own PR. | High | Open | [build] | no |
| FR-002 | The lane is one file, not the tree | As a maintainer, I want the new lane to execute exactly the one guard file (not `tests/audit/`), so its per-PR cost is a ~2 s pytest run and not a directory of integration tests. | High | Open | [build] | no |
| FR-003 | The guard's own inputs route it | As a maintainer, I want a change to the guard file, `src/specify_cli/paths/**` or `src/kernel/paths.py` to run the guard too, so an edit that weakens the guard or deletes the keystone literal its non-vacuity limb detects cannot land green. | Medium | Open | [build] | no |
| FR-004 | Wired into both routing authorities | As a maintainer, I want the group declared verbatim in the retirement scrub and the router filter block, with the `changes.outputs` row, the fail-closed `unmatched` union entry, the `router-gate` `needs` row, the heavy-battery OR term and the duplicate-suite ledger row, so the two-authority model's transcription guards stay green and the new check is required. | High | Open | [build] | no |
| FR-005 | The lane can actually run the guard | As a maintainer, I want the job's pytest invocation to carry no marker expression (the module is `integration`-marked and `-m "fast or unit"` deselects all 8 tests), so the lane executes 8 tests, not 0, and exit 5 fails the job. | High | Open | [build] | no |
| FR-006 | A live-routing regression guard | As a future maintainer, I want a test that reads the LIVE router and workflow YAML and asserts the `status/**` → guard-file routing plus its negative controls, so removing the group or the job reds in CI instead of silently reopening #6879. | High | Open | [ratchet] | no — paired with negative controls on the same router fixture (a paths-only and a docs-only diff must not match) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Cost bound | The new lane adds at most one job to a `status/**`-touching PR, `timeout-minutes` ≤ 10, and its pytest selection is ≤ 10 tests (today: 8). No existing job's command changes. | Performance | High | Open |
| NFR-002 | Required, not advisory | A failure in the new lane fails the run: it is in `router-gate`'s `needs` and is not in `scripts/ci/router_gate.ADVISORY_JOB_NAMES`, so no new required-check name has to be registered outside the existing `router gate`. | Reliability | High | Open |
| NFR-003 | No gate weakening | Every structural guard that constrains the router (`test_ci_router_transcription_guards.py`, `test_ci_quality_path_filters.py`, `test_gate_selection_authority.py`, `test_workflow_coherence.py`, `test_no_duplicate_suite_execution.py`) is green with the change, and none is edited to accept it except where the change adds a required ledger row (an additive entry with a rationale). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No module-registry row | `tests/audit` stays in `out_of_matrix_test_dirs`; claiming it (issue candidate 2) is a maintainer cost decision and is out of scope. | Technical | High | Active |
| C-002 | The guard's assertions are untouched | No change to `_HOME_LITERAL_ALLOWLIST`, the guard's scan roots or its limbs. Draining `src/specify_cli/status/locking.py` from the allowlist belongs to #6516 (PR #6883, open). | Technical | High | Active |
| C-003 | Two authorities, still two | The group's globs are declared in the scrub and transcribed in the router filter block only; no second hand-maintained path→group map is introduced. | Technical | High | Active |
| C-004 | Nothing is merged by this mission | The mission ends at a green draft PR flipped to ready for review. | Business | High | Active |

### Key entities

- **Router group** (`path_literal_audit`): a src-backed group in
  `.github/workflows/ci-router.yml` + a `groups[]` row in `tests/release/ci_retirement_scrub.json`.
- **Router job** (`tests-path-literal-audit`): the blocking job gated on that group, running
  one pytest file.
- **The guard**: `tests/audit/test_no_legacy_path_literals.py`, unmodified.

## Success Criteria

- **SC-001**: For a `src/specify_cli/status/**` diff, `scripts.ci.gate_selection.select_gates`
  reports the `path_literal_audit` group and the job gated on it runs
  `tests/audit/test_no_legacy_path_literals.py`; for a `docs/**` or
  `src/specify_cli/dashboard/**` diff it reports neither. — [build] · no-op passable: no
- **SC-002**: The lane's pytest command names exactly one test file and no marker
  expression, and that file collects 8 tests. — [build] · no-op passable: no
- **SC-003**: `tests/ci` and the router/architectural guard suites pass with the change,
  and the only structural edit outside the two routing authorities is the additive
  duplicate-suite ledger row. — [ratchet] · no-op passable: no
