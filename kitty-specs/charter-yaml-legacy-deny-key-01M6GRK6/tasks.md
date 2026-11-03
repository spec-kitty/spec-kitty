---
description: "Work packages for the legacy charter.yaml deny-key contract decision (#6855)"
---

# Work Packages: A legacy `deactivated_<kind>` key on `charter.yaml`

**Inputs**: Design documents from `kitty-specs/charter-yaml-legacy-deny-key-01M6GRK6/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Test work is required: the mission is red-first by charter (ATDD-First
Discipline, DIRECTIVE_034) and its whole outcome is a pinned refusal.

**Organization**: Two work packages. WP01 makes the refusal intentional (validator +
docstrings + model-level tests); WP02 pins the contract beside the allow-side vocabulary
gate and records the change. WP02 depends on WP01 because it asserts WP01's message.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/` at the repository root.

---

## Work Package WP01: A named refusal for a deny key on `charter.yaml` (Priority: P1)

**Goal**: `CharterYaml.model_validate` keeps refusing a `deactivated_<kind>` key, and now says
why: the key belongs in the activation ledger, it was never applied where it sits, and here is
the remedy. The two docstrings that read as if the shape were legitimate are corrected.
**Independent Test**: validate a sound document plus `deactivated_<kind>` and assert the
`ValidationError` names the ledger and "never applied"; the same document without the key still
validates.
**Prompt**: `tasks/WP01-named-deny-key-refusal.md`
**Requirement Refs**: FR-001, FR-003, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-003, SC-002, SC-004

### Included Subtasks

T001 [P] Add the red-first message cases to `tests/charter/test_charter_yaml_model.py` and record the red
T002 Add the `mode="before"` deny-key refusal to `CharterYaml`
T003 State the deny-side contract in the `CharterYaml` docstring
T004 Correct the `_stored_deny` docstring in `pack_manager.py` (no behaviour change)
T005 Run the targeted charter tests, ruff and mypy on the touched files

### Implementation Notes

- The refusal is by the `deactivated_` prefix (the ledger's own `_DENY_PREFIX` posture), never
  by restating a kind table in `schemas.py` (C-002). No field is added (C-001).
- `mode="before"` so the message replaces the generic `extra_forbidden`, and so a valid
  document is untouched.
- Do not change `model_config` (`extra="forbid"`, `frozen=True`) or the three-state semantics.

### Parallel Opportunities

- T003 and T004 touch different files from T002 and can be written together with it; T001 must
  go first (red-first).

### Dependencies

- None (starting work package).

### Risks & Mitigations

- A before-validator could shadow other validation errors: it raises only for the deny prefix
  and returns the input untouched otherwise; the pre-existing strictness tests must pass
  unmodified.

---

## Work Package WP02: Pin the deny-side contract and record the change (Priority: P2)

**Goal**: The deny vocabulary of the activation ledger is provably outside `CharterYaml`'s
declared shape, every deny key is refused, and the decision is recorded in the changelog
fragment.
**Independent Test**: the new block in `tests/charter/test_activation_vocabulary_setequal.py`
derives `activation_ledger.DENY_KEYS`, asserts disjointness, asserts no model field is a deny
key, and asserts the named refusal for each key with a positive control.
**Prompt**: `tasks/WP02-pin-deny-vocabulary.md`
**Requirement Refs**: FR-002, FR-004, C-002, SC-001, SC-003
**Depends on**: WP01

### Included Subtasks

T006 [P] Derive the deny vocabulary in `tests/charter/test_activation_vocabulary_setequal.py` and pin disjointness + no deny fields
T007 Parametrize the refusal pin over `DENY_KEYS` with the contract-message facts and a positive control
T008 Add the changelog fragment and run the changelog style and spelling checks
T009 Run the targeted tests plus the import-graph and vocabulary gates

### Implementation Notes

- Read the deny vocabulary from `charter.activation.activation_ledger.DENY_KEYS` (the authority),
  never a hand-written list; keep the file's existing lazy-import discipline (C-002).
- The positive control must use the same fixture as the refusal case, minus the deny key, so the
  failure is attributable to the key.
- Fragment path: `docs/changelog/unreleased/6855-charter-yaml-legacy-deny-key.internal.md`;
  rename to the PR number once it exists.

### Parallel Opportunities

- T008 is independent of T006/T007 (different file).

### Dependencies

- **WP01** — the pin asserts the refusal message WP01 introduces.

### Risks & Mitigations

- A vacuous pin (asserting only "some ValidationError") would not guard the contract:
  assert the two stable message facts.
- The fragment filename collides if two PRs use the issue number: rename to the PR number.

---

## Subtask Index

| Subtask | Description | WP | Parallel |
|---------|-------------|----|----------|
| T001 | Red-first message cases (`test_charter_yaml_model.py`) | WP01 | no |
| T002 | `mode="before"` deny-key refusal in `schemas.py` | WP01 | yes |
| T003 | `CharterYaml` docstring states the deny-side contract | WP01 | yes |
| T004 | `_stored_deny` docstring correction | WP01 | yes |
| T005 | Targeted tests + ruff + mypy | WP01 | no |
| T006 | Deny vocabulary derivation + disjointness/field-absence pins | WP02 | yes |
| T007 | Parametrized refusal pin + positive control | WP02 | no |
| T008 | Changelog fragment + style/spelling checks | WP02 | yes |
| T009 | Targeted tests + import-graph gate | WP02 | no |

## Dependencies

- WP02 depends on WP01.
