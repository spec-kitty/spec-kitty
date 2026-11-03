---
work_package_id: WP01
title: A named refusal for a deny key on charter.yaml
dependencies: []
requirement_refs:
- FR-001
- FR-003
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- SC-002
- SC-004
planning_base_branch: issue-6855-charter-yaml-legacy-deny-key
merge_target_branch: issue-6855-charter-yaml-legacy-deny-key
branch_strategy: Planning artifacts for this mission were generated on issue-6855-charter-yaml-legacy-deny-key. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6855-charter-yaml-legacy-deny-key unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Red-first fix
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/schemas.py
- src/charter/activation/pack_manager.py
- tests/charter/test_charter_yaml_model.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – A named refusal for a deny key on charter.yaml

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record what you changed with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- `CharterYaml.model_validate` **still refuses** a `deactivated_<kind>` key on a
  `charter.yaml` document — the mission decided the contract in favor of strictness (ADR
  2026-10-19-1 Decision 1 / C-003; see `spec.md` "Which side the evidence supports").
- The refusal names the contract instead of the bare pydantic
  `extra_forbidden`: the activation ledger path `.kittify/charter/activation.yaml`, the fact
  that such a key was never applied where it sits, and the remedy
  (`spec-kitty upgrade` / `spec-kitty migrate activation-ledger`).
- The `CharterYaml` docstring and `_stored_deny`'s docstring stop reading as if a hand-written
  deny key on `charter.yaml` were a legitimate shape (FR-003).
- No field is added to the model, `model_config` is unchanged, and no emitted bytes change
  (C-001, NFR-002, NFR-003).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6855 (closes).
- Design: [`plan.md`](../plan.md) D1–D2; grounding and rejected alternatives:
  [`research.md`](../research.md) R2–R5.
- The deny vocabulary is owned by `charter.activation.activation_ledger.DENY_KEYS`
  (`deactivated_<plural>` per activatable kind, derived from `ArtifactKind`), and the ledger's
  own prefix constant is `activation_ledger._DENY_PREFIX = "deactivated_"`.
- **Import-graph constraint (NFR-001)**: `charter.activation.pack_manager` imports
  `charter.activation.schemas`, so `schemas.py` must not import `pack_manager` or
  `activation_ledger` at module scope. The validator uses the literal prefix; no lazy import is
  needed. `tests/charter/test_activation_vocabulary_setequal.py::test_schemas_import_does_not_pull_in_pack_manager`
  is the standing gate.
- **Do not declare a `deactivated_*` field.** `charter.activation.compiler` builds the emitted
  `charter.yaml` from this model, so a declared `None`-defaulted field would be dumped by
  `emit_yaml` and emitted into every regenerated charter, breaking
  `consolidate-charter-bundle-01KXSYB9`#NFR-005 byte stability and contradicting C-003.
- Reference implementation shape is in [`plan.md`](../plan.md) D1. Keep the message prose
  close to it; do not invent a second wording for the same fact.

## Branch Strategy

- **Strategy**: planning artifacts were generated on
  `issue-6855-charter-yaml-legacy-deny-key`; completed changes must merge back into
  `issue-6855-charter-yaml-legacy-deny-key`.
- **Planning base branch**: `issue-6855-charter-yaml-legacy-deny-key`
- **Merge target branch**: `issue-6855-charter-yaml-legacy-deny-key`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change these by hand unless
> the branch topology changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first message cases

- **Purpose**: prove the current failure does not state the contract, before changing the model.
- **Steps**:
  1. In `tests/charter/test_charter_yaml_model.py`, add a `#6855` block that reuses the file's
     existing sound document builder and validates the same mapping with a
     `deactivated_tactics: ["x"]` key added.
  2. Assert `pytest.raises(ValidationError)` and that the message contains
     `.kittify/charter/activation.yaml` and `never applied`.
  3. Add the positive control: the same mapping **without** the deny key validates.
  4. Run the new tests and record the red (the message assertions fail on the current
     `extra_forbidden` text; the positive control passes).
- **Files**: `tests/charter/test_charter_yaml_model.py`
- **Parallel?**: no — must go first.
- **Notes**: use literals for the two facts (`deactivated_tactics`, the ledger path) in this
  file, mirroring how #6556 pinned its three keys here on purpose; the derived vocabulary pin is
  WP02's job.

### Subtask T002 – The `mode="before"` refusal

- **Purpose**: make the refusal intentional and legible (FR-001).
- **Steps**:
  1. In `src/charter/activation/schemas.py`, add a module-level
     `_DENY_KEY_PREFIX = "deactivated_"` beside the `CharterYaml` definition (or with the other
     module constants) and a `@model_validator(mode="before")` classmethod on `CharterYaml`.
  2. The validator sorts every string root key that starts with the prefix; when non-empty it
     raises `ValueError` naming the keys, the ledger, the "never applied" fact and the remedy.
     Otherwise it returns the input untouched.
  3. Import `model_validator` from pydantic and `Mapping` from `collections.abc`; keep mypy
     `--strict` clean (annotate `data: Any -> Any`).
- **Files**: `src/charter/activation/schemas.py`
- **Parallel?**: yes (with T003/T004).
- **Notes**: `mode="before"` is required so the message replaces `extra_forbidden`. Do not add
  `deactivated_*` fields, do not relax `extra="forbid"`, and do not make the refusal
  kind-specific: the prefix is exactly the ledger's posture (an unknown `deactivated_<x>` from a
  later CLI is refused here too).

### Subtask T003 – `CharterYaml` docstring states the deny side

- **Purpose**: remove the reading that a hand-written deny key is a legitimate shape (FR-003).
- **Steps**: extend the `CharterYaml` class docstring with a short paragraph: the deny side is
  deliberately **not** declared; `deactivated_<kind>` is ledger content (ADR 2026-10-19-1
  Decision 1 / C-003), doctor reports one on `charter.yaml` as the `LEGACY_DENY_KEY` error and
  the ledger migration refuses it; the model refuses it by design, with a message naming the
  ledger — so a future reader cannot "complete" the vocabulary by adding the fields.
- **Files**: `src/charter/activation/schemas.py`
- **Parallel?**: yes.
- **Notes**: state the authority and the reason; do not re-state the whole ADR.

### Subtask T004 – `_stored_deny` docstring

- **Purpose**: keep the read-path truth and add what the document *is* (FR-003).
- **Steps**: in `src/charter/activation/pack_manager.py`, extend `_stored_deny`'s docstring:
  the key is reported (a command warns once, doctor reports `LEGACY_DENY_KEY` as an error) and
  never applied, and it is **not** a supported `charter.yaml` shape — the ledger migration
  refuses it and `CharterYaml` refuses to validate the document. Change no behaviour (the
  function body stays byte-identical).
- **Files**: `src/charter/activation/pack_manager.py`
- **Parallel?**: yes.
- **Notes**: docstring only. `bash` diff review must show no code change in this file.

### Subtask T005 – Targeted validation

- **Purpose**: prove the change and the unchanged strictness gates.
- **Steps**:
  1. `uv run --frozen pytest tests/charter/test_charter_yaml_model.py tests/charter/test_activation_vocabulary_setequal.py -q`
  2. `uv run --frozen ruff check src/charter/activation/schemas.py src/charter/activation/pack_manager.py tests/charter/test_charter_yaml_model.py`
  3. `uv run --frozen ruff format --check` on the same files.
  4. `uv run --frozen mypy src/charter/activation/schemas.py src/charter/activation/pack_manager.py`
     (or the repository's configured mypy invocation for these paths).
  5. Confirm the #6556 all-keys case still validates and dumps the same fields: re-run
     `tests/charter/test_charter_yaml_model.py::TestActivationIsFlatAtRoot::test_document_carrying_every_authority_key_validates`
     and assert no `deactivated_` key appears in `CharterYaml.model_dump()` for it (SC-004).
  6. Record the exact commands and counts in the mission's `## Progress & Status`.
- **Files**: none (validation only).
- **Parallel?**: no.

## Test Strategy

- The red-first test is T001; it must be seen failing on the message assertions before T002
  lands, then green.
- The full pre-existing `tests/charter/test_charter_yaml_model.py` suite must pass **unmodified**
  except for the new block — no assertion edits (SC-004).
- `tests/charter/test_activation_vocabulary_setequal.py` must pass unchanged from WP01's side;
  WP02 extends it.

## Risks & Mitigations

- **Shadowing other validation errors**: raise only for the deny prefix and return the input
  untouched otherwise.
- **Message drift from doctor/migration wording**: assert the two stable facts, not the prose.
- **Emitted-byte change**: the change adds no field and no `_OPTIONAL_EMPTY_OMIT_KEYS` entry, so
  `model_dump` output is unchanged; verify the #6556 all-keys fixture still dumps identically if
  a fixture exists.

## Review Guidance

- Confirm the model still **refuses** the key (a test that strips/reports instead of raising is
  a failure of this WP).
- Confirm the message names the ledger and "never applied", and that the bare `extra_forbidden`
  text is no longer the message for this case.
- Confirm `model_config` still has `extra="forbid"` and `frozen=True`, and that
  `CharterYaml.model_fields` gained no `deactivated_` field.
- Confirm `pack_manager.py` changed only its docstring (no code diff) and that
  `schemas.py` gained no module-level import from the writer/ledger layer.

## Progress & Status

- Implementation: pending.

## Definition of Done

- [ ] T001 red recorded, then green after T002.
- [ ] T002 validator in place, mypy/ruff clean.
- [ ] T003/T004 docstrings corrected; no behaviour change in `pack_manager.py`.
- [ ] Targeted tests green; pre-existing strictness tests unmodified.
