# Implementation Plan: Acceptance test measures the activation field set, not a count

**Branch**: `issue-7038-acceptance-activation-field-pin` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/acceptance-activation-field-pin-01M6EJZV/spec.md`
**Input**: Mission specification from `kitty-specs/acceptance-activation-field-pin-01M6EJZV/spec.md`

## Summary

One acceptance test in `tests/acceptance/test_unmigrated_cli_still_runs.py` pins
`len(fields) == 10` for `CharterYaml`'s activation fields while the model declares 13. The model
is right (13 is `ACTIVATION_YAML_KEYS`' size and is held by an independent parity gate); the test
is stale and, because it derived its names from the model, could only ever fail on a legitimate
addition. The change removes the hand-restated vocabulary from the test: it reads the field set
from `charter.activation.pack_manager.ACTIVATION_YAML_KEYS`, keeps the behavioural proof (a
document carrying every writable activation key validates through `CharterYaml` and loads through
the real `charter context` CLI), adds a non-vacuity guard, and renames the test. No `src/` file
changes.

## Technical Context

**Language/Version**: Python 3.11 (project `.python-version`; CI matrix also runs other
interpreters, exercised by the acceptance job)
**Primary Dependencies**: pytest, pydantic (the `CharterYaml` model), ruamel.yaml (fixture I/O),
the spec-kitty CLI itself (the acceptance test shells out to the real binary)
**Storage**: N/A — the fixture is a temporary git repo with `.kittify/charter/charter.yaml`
**Testing**: pytest; the affected test is `pytest.mark.integration` + `pytest.mark.git_repo` in
`tests/acceptance/`; the vocabulary authority is guarded by
`tests/charter/test_activation_vocabulary_setequal.py` (`unit`, `fast`)
**Target Platform**: Linux CI (GitHub Actions) and developer machines
**Project Type**: single Python package (`src/`) with an acceptance suite (`tests/acceptance/`)
**Performance Goals**: the test keeps its current shape — one fixture repo and one CLI subprocess;
no new process spawns
**Constraints**: no production-code change; no second vocabulary literal; no skipped/xfailed gate
**Scale/Scope**: 1 test function (~10 lines), 1 file, plus the Mission's `kitty-specs/` artifacts

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Single canonical authority | PASS | The test stops restating the vocabulary and reads `ACTIVATION_YAML_KEYS`; no new literal list. |
| Locality of change (DIRECTIVE_024) | PASS | One test function in the file the issue names; no `src/` change. |
| ATDD-first (DIRECTIVE_034) | PASS | The failing test is the pre-existing entry point; it is red on `main` before the change and green after. |
| Test non-vacuity (DIRECTIVE_041) | PASS | The test still loads a real document through the model and the real CLI; an explicit non-empty guard prevents an empty loop. |
| No gate weakening (charter Standing Orders) | PASS | The test is not skipped, xfailed, deleted or emptied; `extra="forbid"` remains exercised by the load. |
| Pre-existing failure reporting | PASS | Issue #7038 owns this red; this Mission closes it. |
| Terminology canon (Mission vs feature) | PASS | "Mission" used in the spec-kitty sense throughout. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Only the targeted acceptance test and the two vocabulary/model test modules are run. |

No violations; no justified exceptions needed. Complexity Tracking is therefore empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/acceptance-activation-field-pin-01M6EJZV/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings
├── spec.md              # Mission specification
├── tasks.md             # /spec-kitty.tasks output
└── tasks/               # Work-package files and the issue matrix
```

No `data-model.md`, `contracts/` or `quickstart.md`: the mission changes no data shape and exposes
no new interface, so those Phase 1 artifacts would be empty ceremony (see "Phase 1 design" below).

### Source Code (repository root)

```
tests/
└── acceptance/
    └── test_unmigrated_cli_still_runs.py   # the one test that changes

src/
└── charter/
    └── activation/
        ├── schemas.py                      # CharterYaml — read-only for this mission
        └── pack_manager.py                 # ACTIVATION_YAML_KEYS — read-only authority

tests/charter/
├── test_activation_vocabulary_setequal.py  # owns model-vs-authority set equality (read-only)
└── test_charter_yaml_model.py              # unit field test, precedent for the fix (read-only)
```

**Structure Decision**: the existing single-package layout is used unchanged; this is a test-only
edit inside `tests/acceptance/`.

## Phase 0: Research

Recorded in `kitty-specs/acceptance-activation-field-pin-01M6EJZV/research.md`. Resolved there:

- Which side is wrong: the test (model right), with the #6496 → #6556 history and the green
  parity gate as evidence.
- Why bumping the count is not the fix: it re-creates a hand-restated vocabulary, which the
  charter's single-authority rule forbids, and keeps a pin that can only fail on legitimate growth.
- The shape of the fix: authority-sourced key list, behavioural proof kept, non-vacuity guard,
  lazy import, rename.

No `NEEDS CLARIFICATION` items remain.

## Phase 1: Design

The only design decisions here are the test's shape and the ownership split between gates:

1. **Vocabulary owner**: `ACTIVATION_YAML_KEYS` (authority). The test reads it, never restates it.
2. **Set-equality owner**: `tests/charter/test_activation_vocabulary_setequal.py` — unchanged. It
   already names missing/stray keys with an actionable message. The acceptance test must not
   duplicate it (C-002); duplicating would make a future drift fail twice for one cause and
   invite the two copies to disagree again.
3. **Behavioural owner**: this acceptance test. A `charter.yaml` carrying every writable activation
   key must validate through `CharterYaml` (so `extra="forbid"` proves every key is a declared
   field) and load through `spec-kitty charter context --action implement --json` on the
   unmigrated fixture.
4. **Non-vacuity**: `assert fields` fails if the authority is ever empty, so the loop cannot pass
   over nothing.
5. **Naming**: `test_charter_yaml_loads_every_activation_field_the_writer_may_write` — states the
   property, not a number.

No data-model, contract or quickstart artifact is produced because nothing about the data shape or
external interface changes; the existing schema contract
(`kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/charter-yaml-schema.md`) stays as is.

## Complexity Tracking

No charter violations; nothing to justify.

## Implementation Concern Map

### IC-01 — The acceptance fixture follows the vocabulary authority

- **Purpose**: remove the stale, self-referential count from the acceptance test so a legitimate
  model growth cannot strand it again.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004; NFR-001, NFR-002; C-001, C-002, C-003
- **Affected surfaces**: `tests/acceptance/test_unmigrated_cli_still_runs.py` (one test function
  plus a small lazy-import helper)
- **Sequencing/depends-on**: none
- **Risks**: the fix must not degrade into a vacuous loop; the fixture must keep the two
  pre-existing activation values it sets today; `activated_assets` must not be reintroduced.

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| The derived loop becomes vacuous if the authority is empty | Explicit `assert fields` non-vacuity guard (FR-003). |
| The test starts duplicating the parity gate | Ownership stated in C-002 and in the docstring, pointing at the parity gate. |
| A model field is accidentally dropped in future | The document carries every authority key, so `extra="forbid"` reds the test on `model_validate`. |
| Import-order dependency introduced | Function-scoped import of `pack_manager`, matching the #6556 precedent. |
