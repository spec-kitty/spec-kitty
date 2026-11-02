# Mission Specification: Acceptance test measures the activation field set, not a count

**Mission Branch**: `issue-7038-acceptance-activation-field-pin`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #7038 — `tests/acceptance/test_unmigrated_cli_still_runs.py::test_charter_yaml_with_all_ten_activation_fields_still_loads` pins 10 activation fields while `CharterYaml` declares 13.

## Intent Summary *(confirmed)*

- **Primary actor**: a maintainer running the acceptance suite on `main`, and a future contributor who adds an activatable artifact kind.
- **Trigger**: on current `origin/main` the test fails with `assert len(fields) == 10` / `AssertionError: assert 13 == 10`, with no local change.
- **Decision — the test is wrong, the model is right.** `CharterYaml` declaring 13 activation fields is intentional and pinned by an independent gate:
  - `charter.activation.pack_manager.ACTIVATION_YAML_KEYS` is the single vocabulary authority and holds 13 keys.
  - `tests/charter/test_activation_vocabulary_setequal.py::test_charter_yaml_activation_fields_set_equal_to_authority` asserts the model's activation fields are set-equal to that authority in both directions, and it passes today.
  - #6556 (`4d948f52c9`) deliberately added the last three fields — `activated_glossary_packs`, `activated_skills`, `activated_anti_patterns` — because `charter activate` on an unmigrated project writes them to `charter.yaml` and a schema-validated read then failed `extra_forbidden`. That fix updated the unit-level field test and added the parity gate, but missed this acceptance test.
  - The count was correct when the test was written (#6496, `a58a8ef830`, when the model had exactly 10) and went stale when the model legitimately grew.
- **Desired outcome**: the acceptance test takes its field set from the vocabulary authority instead of restating a count, so a legitimate future addition moves one place and the test follows; the file is green on `main`.
- **Also fixes a latent flaw**: the old pin derived the field names *from the model* and then asserted their *number*, so it could only ever fail on a legitimate addition and could never catch a wrong key set. Set-equality with the authority (already owned by the parity gate) is the meaningful guard; this test owns the behavioural load.
- **Non-goals**: no production-code change. `CharterYaml`'s declared fields, `extra="forbid"`, the three-state activation contract, and `ACTIVATION_YAML_KEYS` stay exactly as they are. The test is not deleted, skipped, xfailed, or reduced to a loop that can pass vacuously.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The acceptance fixture follows the activation vocabulary authority (Priority: P1)

A maintainer runs the unmigrated-CLI acceptance test and it builds its `charter.yaml` fixture from the single activation vocabulary authority, so a charter carrying every key the activation writer may write still loads through the model and the real CLI.

**Why this priority**: this is the only user story; the test is red on `main` today.

**Independent Test**: the test passes on the fixed tree, and it fails if the authority carries a key the model does not declare (the model rejects it as `extra_forbidden`) instead of failing on a stale number.

**Acceptance Scenarios**:

1. **Given** `ACTIVATION_YAML_KEYS`, **When** the fixture document carries every one of them and is validated through `CharterYaml.model_validate` and `spec-kitty charter context --action implement --json`, **Then** both succeed.
2. **Given** the authority gains an activatable key the model does not declare, **When** the test runs, **Then** it fails on the document load (`extra_forbidden`), not on a hard-coded count — the failure names the real defect.
3. **Given** an empty authority vocabulary, **When** the test runs, **Then** an explicit non-vacuity guard fails instead of the test passing over an empty loop.

### Edge Cases

- The fixture document already sets `activated_directives` and `mission_type_activations` from `_CHARTER_YAML`; the derived field loop must not overwrite them with `[]`, exactly as the current test excludes them.
- The authority must be imported lazily (function-scoped) as #6556 did in `tests/charter/test_charter_yaml_model.py`: `charter.activation.pack_manager` imports the schemas module on its own path, and the test should not add a new import-order dependency.
- `activated_assets` is deliberately **not** an activatable charter key (`ArtifactKind.ASSET.activatable is False`); the test must not expect or add it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Field set from the authority | As a maintainer, I want the acceptance test to read its activation field set from `pack_manager.ACTIVATION_YAML_KEYS` so a legitimate model addition cannot strand a stale count. | High | Open | [build] | no — the fixture is built from the real authority and validated |
| FR-002 | Keep the behavioural proof | As a maintainer, I want the test to keep proving that a `charter.yaml` carrying every writable activation key validates and loads through the real `charter context` CLI. | High | Open | [build] | no — a missing model field reds the test via `extra_forbidden` |
| FR-003 | Non-vacuity guard | As a reviewer, I want an explicit non-empty assertion so the derived loop cannot pass over an empty vocabulary. | Medium | Open | [build] | no — an empty authority is asserted against |
| FR-004 | Name the test for what it proves | As a reader, I want the test renamed and re-docstringed so it no longer claims "ten" fields and points at the parity gate that owns set-equality. | Low | Open | [build] | no — the identifier change is visible in the diff |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No production change | The diff touches no `src/` file; the library import graph is unchanged and `schemas` still does not import `pack_manager` at module scope. | Compatibility | High | Open |
| NFR-002 | Test cost unchanged | The test keeps its current cost (one fixture repo, one CLI subprocess, no new subprocesses) and stays in the acceptance module. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One authority | `ACTIVATION_YAML_KEYS` stays the only vocabulary authority; the test must not introduce a second literal list of keys. | Technical | High | Open |
| C-002 | One owner per gate | Set-equality of the model with the authority stays owned by `tests/charter/test_activation_vocabulary_setequal.py`; this test owns the behavioural load, not a duplicate parity assertion. | Technical | High | Open |
| C-003 | No gate weakening | The test is not skipped, xfailed, deleted, or emptied; the model's `extra="forbid"` guard is still exercised through the real load path. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/acceptance/test_unmigrated_cli_still_runs.py` is green on the branch, including the renamed test — [build] · no-op passable: no
- **SC-002**: The vocabulary parity gate and the `CharterYaml` model tests stay green (they own set-equality) — [ratchet] · no-op passable: no
- **SC-003**: No hard-coded activation-field count remains in `tests/acceptance/test_unmigrated_cli_still_runs.py` — [build] · no-op passable: no
