# Implementation Plan: Prose-only down-route scan-scope exemption (#6999)

**Branch**: `kitty/mission-prose-only-scan-scope-exemption-01M6BTRX` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/spec.md`

## Summary

A proven prose-only PR currently drops the whole heavy architectural battery
(#4842), including the gates that read comment and docstring text. #6996 gave
each heavy gate a declared scan scope and a scoped-leg mechanism. This mission
exempts declared scan-scope matches from the subtraction: the battery `if:`
runs the battery when a prose-only diff touches a declared scan scope, and the
scoped selection then narrows each leg to exactly the gates whose declaration
matches. Content stays in `scripts/ci/prose_only.py`; paths stay in
`scripts/ci/gate_selection.py`; the prose verdict enters the selection as an
explicit input from the `prose-scan` job output, never re-derived in the router.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor; CI runs 3.12), GitHub Actions YAML
**Primary Dependencies**: stdlib `fnmatch`/`ast`; `PyYAML` for registry/router parsing; pytest (+xdist) for tests
**Storage**: N/A — `.github/ci-module-registry.yml` and `.github/workflows/ci-router.yml` are the data surfaces
**Testing**: pytest. `tests/ci` (unit + workflow-YAML goldens, `fast` marker, `ci` module shard) and `tests/architectural/test_battery_scan_scope_routing.py` (the #6996 property). `tests/ci/_gh_if.py` evaluates the real `if:` strings.
**Target Platform**: GitHub Actions (ubuntu-24.04) PR, push and merge_group events
**Project Type**: Single Python project with a CI routing layer under `scripts/ci/`
**Performance Goals**: A prose-only diff runs at most its declared scan-scope matches per leg (5 gates for a `scripts/**` prose diff), never the ~635-gate battery
**Constraints**: The change must not add a CI job, must not add a router group, and must keep the fail-safe (`mode=full`) on any doubt. No gate may be skipped or weakened (C-001).
**Scale/Scope**: Two workflow spots (one job `if:`, one selection step env/flag), one selection parameter in `scripts/ci/gate_selection.py`, one CLI flag each in `scripts/ci/battery_scope.py`, four golden/unit test updates plus new pins, one docs page section, one changelog entry.

## Charter Check

*GATE: passed before Phase 0; re-checked after Phase 1 design.*

- **Single canonical authority**: the gate→scope map stays
  `special_tiers.architectural.scan_scopes`; the router group stays its
  test-pinned transcription. No new list is introduced (NFR-002).
- **ATDD-first / red-first**: the defect is reproduced through the existing
  entry points (`select_battery_gates`, the workflow `if:` evaluator) before
  the fix; the failing reproduction is kept as the regression pin.
- **Architectural gate discipline**: no gate is edited, skipped, xfailed or
  deselected. A change under `tests/architectural/**` or `scripts/ci/**` runs
  the whole battery on this PR by the existing rules, which is correct.
- **Locality of change**: the diff is confined to the routing seam and its
  pins; no refactor of `gate_selection`'s group model.
- **Living documentation**: `docs/development/reference/ci-gate-mechanics.md`
  (the "When" column of the heavy legs) and the changelog change with the code.
- **Terminology canon**: "prose-only", "down-route", "scan scope", "scoped
  leg", "heavy battery" are used as the repository already defines them.
- **No full heavy suite locally** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): the
  verification runs the affected `tests/ci` files and the
  `test_battery_scan_scope_routing.py` property, not a whole-tree battery.

## Project Structure

### Documentation (this mission)

```
kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/
├── spec.md              # requirements (committed)
├── research.md          # discovery + decisions (committed with the plan)
├── plan.md              # this file
├── contracts/
│   └── prose-only-scan-scope-exemption.md   # the selection + if: contract
├── quickstart.md        # how to verify by hand
├── issue-matrix.json    # #6999 row (in-mission)
└── tasks.md             # /spec-kitty.tasks output
```

No `data-model.md`: the mission introduces no persisted entity; the only data
surfaces are two existing YAML files whose shape is unchanged.

### Source Code (repository root)

```
.github/
├── ci-module-registry.yml           # unchanged (declarations already exist)
└── workflows/ci-router.yml          # battery if: + selection step env

scripts/ci/
├── gate_selection.py                # select_battery_gates(..., prose_only=False)
├── battery_scope.py                 # decide(..., prose_only=False), --prose-only
└── prose_only.py                    # unchanged (content classifier, single source)

docs/
├── changelog/CHANGELOG.md           # [Unreleased] entry (#6999)
└── development/reference/ci-gate-mechanics.md   # heavy-leg "When" column + prose note

tests/ci/
├── test_battery_scope.py            # prose-mode unit pins + mutation control
├── test_ci_module_wiring.py         # #4842 golden updated, cites the ruling
└── test_ci_config_battery_routing.py# if:-shape pin updated, cites the ruling
```

## Design

### Seam 1 — the battery `if:` (`ci-router.yml`)

```
(... existing group OR ...) &&
(needs.prose-scan.outputs.prose_only != 'true' ||
 needs.prose-scan.outputs.scan_scope_match == 'true')
```

- The outer `&& prose_only != 'true'` subtraction becomes a two-term guard.
- The guard's second term is a NEW `prose-scan` output,
  `scan_scope_match` (any changed path matches the router's `arch_scan_scope`
  globs, via `gate_selection.matches_declared_scan_scope`), NOT a second
  reference to `needs.changes.outputs.arch_scan_scope`. Reason found during
  implementation: a second reference keeps the group in the parsed job-gate set
  even after the group's own OR term is deleted, which made the #6994 planted
  control (`test_planted_the_group_dropped_from_the_battery_if_reds`) pass
  vacuously. With the companion, the parsed group set (`job_gates`,
  `HEAVY_BATTERY_NON_SRC_GROUPS`) is unchanged (C-002) and the plant still reds.
- A prose-only diff that matches no declared scope keeps `scan_scope_match=false`
  and the battery stays skipped (SC-002).
- A prose-only diff that matches a declared scope reaches the step below.

### Seam 2 — the scoped selection (`battery_scope.py` + `gate_selection.py`)

`select_battery_gates(changed_paths, *, router=None, registry_path=None, mode="pr", prose_only=False)`

- `mode == "full"` → `None` (whole leg), unchanged and first.
- `prose_only=True` → return only the heavy-leg gates whose declared scan scope
  matches; skip the code-group / `battery_code_helpers` widening (prose-only
  proves no behaviour change), never return `None`.
- `prose_only=False` → today's behaviour byte-for-byte.

`battery_scope.decide(paths, *, part, mode="pr", prose_only=False, repo=...)`
passes the flag through; `select --prose-only` accepts `true|false`
(case-insensitive) with default `false`. The heavy-battery step reads the
`prose-scan` job output into `PROSE_ONLY` and passes `--prose-only`.

- Missing base / git error / selection error → `mode=full` (unchanged).
- The plugin still restricts a scoped leg to `SK_BATTERY_GATES_FILE`; a leg
  holding none is skipped (`run=false`) by the existing code.

### Non-vacuity

- The same-fixture positive control: the prose fixture selects the five
  `scripts/**` scanners; the identical fixture with `prose_only=False` (code
  semantics) returns `None` (whole battery) — proving the prose branch is what
  narrows, not the fixture.
- Half-by-half proof: both legs' unions equal the selection and their
  intersection is empty.
- Production path: the golden evaluates the real `ci-router.yml` `if:` string,
  and `decide` is called through the same CLI the workflow runs.

## Risks

- **A prose-only diff that touches both a declared scope and a battery code
  helper** (`scripts/ci/gate_selection.py` itself is a helper): the prose branch
  deliberately narrows instead of widening. Safe because prose-only proves no
  behaviour change; noted in the contract for reviewers.
- **Router/dorny transcription drift**: `arch_scan_scope` is transcribed into
  `ci-router.yml` and pinned by
  `tests/architectural/test_battery_scan_scope_routing.py`; this mission does
  not touch the transcription, so the existing pin keeps guarding it.
- **Skip-if-green on ready_for_review**: unchanged; the escape hatch is a
  re-run, as documented.

## Complexity Tracking

No charter violations. No new module, job, group, or registry row.
