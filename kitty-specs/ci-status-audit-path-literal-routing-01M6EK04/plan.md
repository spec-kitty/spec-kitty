# Implementation Plan: Route the path-literal audit on a `status/**` diff

**Branch**: `issue-6879-ci-status-audit-path-literal-routing` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/ci-status-audit-path-literal-routing-01M6EK04/spec.md`
**Issue**: spec-kitty#6879 | **Input**: Mission specification (same directory)

## Summary

Add one narrow src-backed routing group (`path_literal_audit`) to
`.github/workflows/ci-router.yml` and one blocking router job
(`tests-path-literal-audit`) gated on it, which executes exactly
`tests/audit/test_no_legacy_path_literals.py`. The group's globs are the paths whose change
can make that guard meaningful or invert it: `src/specify_cli/status/**` (the reported
gap), `src/specify_cli/paths/**` and `src/kernel/paths.py` (the keystone resolver file
whose literal the guard's non-vacuity limb asserts), and the guard file itself.

No production Python changes. The deliverable is CI routing wiring plus a live-routing
regression guard, and the wiring must satisfy the router's existing structural guards.

## Technical Context

**Language/Version**: Python 3.12 (CI runner), GitHub Actions workflow YAML
**Primary Dependencies**: `scripts/ci/gate_selection.py` (the single gate-selection
authority, which *parses* the router's two hand-authored sources), `dorny/paths-filter`,
`astral-sh/setup-uv`
**Storage**: n/a
**Testing**: pytest; the routing guards live in `tests/ci/` and `tests/architectural/`
and are themselves run per PR by the module matrix (`ci` module row → `tests/ci`) and the
architectural battery
**Target Platform**: GitHub Actions on `ubuntu-24.04`
**Project Type**: single Python project (`src/specify_cli`, `src/kernel`, `src/charter`)
**Performance Goals**: the new lane adds ≤ 1 job to a `status/**`-touching PR; the pytest
selection is 8 tests (~2 s), so the lane's cost is environment install, not test time
**Constraints**: no gate weakening; no new required-check name outside the existing
`router gate`; `tests/audit` stays out of the module registry (C-001); the guard file is
not modified (C-002)
**Scale/Scope**: 2 routing authorities edited (scrub + router), 1 job added, 1 guard test
added, 1 additive ledger row

## Charter Check

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The group's globs are declared once in the retirement scrub and transcribed verbatim into the router filter block — the two authorities `scripts/ci/gate_selection.py` already parses. No second path→group map is introduced (C-003, `test_ci_router_transcription_guards.py`). |
| ATDD-first | The regression guard is written against the LIVE router and fails before the workflow change: it asserts the routing the fix must produce. |
| Domain-driven splits / tiered rigour | Small, single-concern change: one group, one job, one guard test. Proportional squad (one reviewer round, correctness + routing-boundary focus). |
| Locality of change (DIRECTIVE_024) | No existing job's command or `if:` changes; the only edits outside the two routing authorities are additive (workflow outputs/union/needs OR-term, one duplicate-suite ledger row). |
| Boy Scout Rule (DIRECTIVE_025) | Not exercised as scope creep: the adjacent `tests/audit` registry claim is a maintainer cost decision (C-001), recorded as Deferred, not folded in. |
| Acceptance-criteria non-vacuity | FR-006 pairs the positive routing assertion with negative controls on the same router fixture (docs-only, paths-only, dashboard diff); SC-002 asserts the collected test count, so "0 collected" cannot pass. |

No charter violation; nothing to justify in Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-status-audit-path-literal-routing-01M6EK04/
├── plan.md              # this file
├── spec.md              # mission spec (authored)
├── issue-matrix.md      # one row: issue #6879, claim, verdict
├── tasks.md             # work-package index (tasks step)
├── tasks/WP01.md        # the single work package
└── traces/              # approach / design-decisions / tooling-friction tracers
```

### Source Code (repository root)

```
.github/
├── workflows/ci-router.yml          # + path_literal_audit group, tests-path-literal-audit job,
│                                    #   changes.outputs row, unmatched union entry,
│                                    #   architectural-heavy OR term, router-gate needs row
└── ci-module-registry.yml           # UNCHANGED (tests/audit stays out-of-matrix, C-001)

tests/
├── release/ci_retirement_scrub.json # + groups[] row for path_literal_audit (verbatim source)
├── ci/test_path_literal_audit_routing.py   # NEW: the live-routing regression guard
└── architectural/test_no_duplicate_suite_execution.py
                                     # + one AUTHORIZED_PER_CHANGE_SUITE_JOBS row (additive,
                                     #   with rationale — the ledger the gate requires)
```

**Structure Decision**: single project; every edit is CI infrastructure or a CI guard test.
No `src/` change, so no coverage-target, shard-timing or docs-surface regeneration is
involved.

## Design decisions

1. **A new non-src group, not a widened existing one.** `status` already matches five
   groups; a new group is the only way to name "a status diff runs this one audit file"
   without changing the `status` module row's `test_dirs` (which are directories, and whose
   shard timings are measured data). The globs are `**/`-spelled (the `mission_state`
   precedent): a src-backed group must also be a module-registry row
   (`test_gate_selection_authority.py::test_select_modules_full_mode_selects_all_registry_modules`),
   and that row is exactly the out-of-scope candidate 2. Staying non-src also keeps the
   lane out of the code-shard set and out of the FR-004 unmatched union, which is what
   preserves run-all over the unmapped `src/specify_cli/paths/**`.
2. **A new job, not a step in an existing one.** `AUTHORIZED_SUITE_INVOCATIONS_PER_JOB = 1`
   (`tests/architectural/test_no_duplicate_suite_execution.py`) and the battery partition
   proof pin one suite invocation per job; `tests-events-consumers` (#6605) is the
   precedent for a narrow extra lane with a ledger rationale.
3. **No marker expression on the lane's pytest line.** The guard module is
   `pytestmark = [pytest.mark.integration]` and carries no `fast`/`unit` marker, which is
   why its only named lane (nightly interpreter shard-5, `-m "fast or unit"`) deselects all
   8 tests. The lane runs the file with no `-m`, so `exit 5` (nothing collected) fails it
   (FR-005).
4. **`src/kernel/paths.py` joins the group** because
   `test_home_literal_guard_is_non_vacuous` asserts the keystone literal is *detected*;
   deleting it inverts the guard and must run the guard (FR-003).
   **`src/specify_cli/paths/**` deliberately does not**: it is unmapped by every src-backed
   group today, so a diff there already forces run-all (which selects this lane). Naming it
   would satisfy the same FR-003 instinct while *narrowing* the fail-closed sensor to this
   one lane — the opposite of what the sensor is for. A pinned test records that
   (`test_the_unmapped_keystone_directory_still_forces_run_all`).
5. **Prose-only down-route is inherited, not re-invented.** The job's `if:` carries the
   same `prose_only != 'true'` term as every code shard (FR/edge case; pinned by the
   `test_golden_prose_only_pr_down_routes_matrix_arch_battery_and_code_shards` golden).

## Implementation Concern Map

### IC-01 — The routing authorities

- **Purpose**: Declare the new group in both hand-authored sources and gate the new job on
  it, so a `status/**` diff selects the lane and every transcription guard stays green.
- **Relevant requirements**: FR-001, FR-003, FR-004, NFR-002, C-003
- **Affected surfaces**: `tests/release/ci_retirement_scrub.json`,
  `.github/workflows/ci-router.yml`
- **Sequencing/depends-on**: none
- **Risks**: the router's derived set equalities — the src-backed group set = the scrub's
  src-backed set (so a NON-src group must live in `non_src_router_groups`, and must not be
  src-spelled), `changes.outputs` = routing groups, the unmatched union = src-backed groups
  (so this group must be absent), and the heavy battery OR-list = src-backed groups ∪ the
  battery's non-src groups (so this group must be absent there too). Miss one and a
  `tests/architectural` guard reds — which is the point of writing the guard test first.

### IC-02 — The lane body and its ledger row

- **Purpose**: Make the job execute exactly the guard file with no marker filter, and
  declare it as an authorised suite invocation.
- **Relevant requirements**: FR-002, FR-005, NFR-001
- **Affected surfaces**: `.github/workflows/ci-router.yml` (job steps),
  `tests/architectural/test_no_duplicate_suite_execution.py` (ledger row + rationale)
- **Sequencing/depends-on**: IC-01
- **Risks**: the timeout and step shape must match the repo's lane conventions (install in
  its own named step, `uv sync --frozen --all-extras`, sync-packs action).

### IC-03 — The live-routing regression guard

- **Purpose**: Pin the routing in a test that reads the live workflow YAML and the parsed
  router, with negative controls, so the fix cannot silently regress.
- **Relevant requirements**: FR-006, SC-001, SC-002
- **Affected surfaces**: `tests/ci/test_path_literal_audit_routing.py` (new file, `fast`
  marker so the `ci` module shard runs it per PR)
- **Sequencing/depends-on**: written first (red), satisfied by IC-01/IC-02
- **Risks**: must use the same harness as the sibling routing tests
  (`tests.ci.test_mission_state_audit_routing`, `tests/ci/_gh_if.eval_gh_if`) rather than
  re-deriving routing, or it becomes a second authority.
