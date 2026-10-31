# Mission Specification: CharterYaml activation-key parity

**Mission Branch**: `issue-6556-charter-yaml-activation-key-parity` (planning base and merge target; the PR head branch for this issue)
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6556 — "CharterYaml schema model rejects activation keys charter activate writes". Guidance from the operator: reproduce first, then make the schema and the writer agree, with **one authority** for what keys are legal; check whether #6496 (activation moved into `.kittify/charter/activation.yaml`) makes the schema simply stale.

## Context and grounding (recorded, not a requirement)

`charter.activation.schemas.CharterYaml` is documented as the structured shape of the
git-tracked, authorable `charter.yaml`, and forbids extra keys. Its activation fields are
a hand-written list of ten names. The single vocabulary authority for the flat activation
keys that a `charter.yaml` may carry is
`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` (derived from `ArtifactKind`), and it
holds thirteen keys.

Reproduced on current `main` (`512567eee7`) through the pre-existing writer entry point
(`prepare_activation_write` → `apply_yaml_write`, the seam `charter activate` uses on an
unmigrated/legacy-scope project): the writer puts `activated_skills` (and
`activated_glossary_packs`, `activated_anti_patterns`) on `charter.yaml`, and
`CharterYaml.model_validate(load_charter_yaml(...))` then rejects the document with
`extra_forbidden`. `activated_assets`, named in the issue, is **not** an activation key any
more (`ArtifactKind.ASSET.activatable is False`; the writer refuses it with "Unknown
activation ledger key(s)"), so the issue's four-key list is stale by one — the model must not
gain an `activated_assets` field.

Conclusion of grounding: after #6496 the *writer* is right and the *model's hand-written
list* is stale. The fix is a schema/authority parity fix, not a writer change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A caller can schema-validate a legitimate charter.yaml (Priority: P1)

A caller that reads `charter.yaml` (today `charter synthesize`'s soundness check and the
model's own tests; tomorrow any reader) validates the document through `CharterYaml`. A
charter written by the activation writer, on a project that has not been migrated to the
activation ledger, carries flat `activated_<kind>` keys. Today the read fails on
`activated_skills`, `activated_glossary_packs` and `activated_anti_patterns` even though
every one of them is a legal, writer-produced key.

**Why this priority**: it is the reported defect; without it the model cannot be used as the
schema for `charter.yaml` at all.

**Independent Test**: write each legal activation key through the legacy writer into a
fixture project's `charter.yaml`, then load and `model_validate` the document; every key
validates.

**Acceptance Scenarios**:

1. **Given** a legacy (unmigrated) project whose `charter.yaml` is sound, **When** the
   activation writer writes `activated_skills`, **Then** the resulting document validates
   through `CharterYaml`.
2. **Given** the same fixture, **When** `activated_glossary_packs` or
   `activated_anti_patterns` is written, **Then** the resulting document validates.
3. **Given** a charter with no activation keys, **When** it is validated, **Then** it still
   validates (no regression).

---

### User Story 2 - The key vocabulary cannot drift again (Priority: P2)

A maintainer adds a new charter-activatable `ArtifactKind` (as happened twice: glossary
packs #5409-family, skills). `ACTIVATION_YAML_KEYS` grows automatically because it is
derived. The model's field list is static, so it silently falls behind — exactly the drift
this issue is. A maintainer must be told, by a failing test with an actionable message,
that the model needs the new field, and must not be able to declare an activation-shaped
field outside the authority either.

**Why this priority**: the reported symptom is one instance; the cause is drift between a
static list and a derived authority.

**Independent Test**: the guard test compares `CharterYaml`'s activation-shaped fields with
`ACTIVATION_YAML_KEYS` as sets, both directions, and reports the missing/extra names.

**Acceptance Scenarios**:

1. **Given** the authority gains a key with no model field, **When** the guard runs, **Then**
   it fails naming the missing key.
2. **Given** a model field with no authority key (for example `activated_assets`), **When**
   the guard runs, **Then** it fails naming the stray field.

---

### User Story 3 - Strictness is preserved (Priority: P3)

The model's `extra="forbid"`, its rejection of a nested `activation:` mapping, its
three-state `None`/`[]`/non-empty semantics and its frozen config are deliberate guards
(paula BLOCKER-1, charter contract G3). Making the model accept the full legal vocabulary
must not loosen any of them: an unknown key that is not part of the authority is still
rejected.

**Why this priority**: a schema "fix" that turns into `extra="allow"` would delete the
structural guard the model exists for.

**Independent Test**: the existing strictness tests pass unchanged, plus a case showing a
non-activation unknown key is still refused.

**Acceptance Scenarios**:

1. **Given** a document with `activation: {...}` nested at the root, **When** validated,
   **Then** it is rejected.
2. **Given** a document with an unrelated unknown root key such as `activated_not_a_kind`,
   **When** validated, **Then** it is rejected.

### Edge Cases

- **Legacy `deactivated_<kind>` keys.** Never written to a legacy `charter.yaml` surface (a
  deny write on an unmigrated project is refused by
  `activation_ledger.refuse_unmigrated_deny_write`), so the model keeps rejecting them.
  They are ledger content, not `charter.yaml` content.
- **A charter that carries every legal activation key at once.** Must validate; the parity
  test is per-key and the end-to-end test writes one key, so add one all-keys document case.
- **`mission_type_activations` and `activated_kinds`.** Already declared; they stay declared
  and in the authority set (they are in `ACTIVATION_YAML_KEYS`), so the guard covers them.
- **The field set must not be derived at import time.** `charter.activation.schemas` is on
  the import path of `charter.activation.pack_manager`; a module-level import of the
  authority into `schemas.py` would be a circular import. The model therefore keeps static,
  typed fields and the parity is pinned by a test, matching the idiom
  `tests/charter/test_activation_vocabulary_setequal.py` already uses for the other three
  copies of this vocabulary.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Model accepts every legal activation key | As a caller that validates `charter.yaml`, I want `CharterYaml` to accept every key in `ACTIVATION_YAML_KEYS` so that a legitimate charter never fails schema validation. | High | Open | [build] | no |
| FR-002 | Model declares no activation field outside the authority | As a maintainer, I want no activation-shaped model field that is not a legal activation key, so that the model cannot advertise a key the writer refuses (for example `activated_assets`). | High | Open | [ratchet] | no |
| FR-003 | Authority parity is guarded by a test | As a maintainer adding a new activatable kind, I want a failing gate that names the missing model field, so that the model cannot silently fall behind the derived authority again. | High | Open | [ratchet] | no |
| FR-004 | Writer-to-model end-to-end proof | As a reviewer, I want a regression that writes legal activation keys through the pre-existing activation writer and then validates the on-disk `charter.yaml` through the model, so that "the schema and the writer agree" is proven behaviourally, not only by key-list equality. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new import cycle | `import charter.activation.schemas` must still succeed on its own and importing it must not import `charter.activation.pack_manager` at module scope; the change adds no module-level import from `schemas` into the activation writer/manager layer. | Maintainability | High | Open |
| NFR-002 | Strictness unchanged | `CharterYaml.model_config` keeps `extra="forbid"` and `frozen=True`; the nested-`activation:` rejection, the three-state `None`/`[]`/non-empty semantics and the `schema_version` pattern are unchanged, verified by the pre-existing tests passing unmodified. | Reliability | High | Open |
| NFR-003 | No writer change | `src/charter/activation/schemas.py` is the only `src/` file changed; no activation writer, ledger, migration or `charter.yaml` serialization behaviour changes, so no on-disk bytes change for any project. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No `activated_assets` | The model must not gain an `activated_assets` field: `ASSET` is not charter-activatable and the writer refuses the key (`charter.activation.activation_ledger` vocabulary, doctrine-kinds docs). The issue's four-key list is stale on this one. | Technical | High | Open |
| C-002 | Keep the authority single | `ACTIVATION_YAML_KEYS` stays the only definition of the legal key set. The model restates the *names* as typed fields (pydantic requires static fields) and the guard test pins the restatement to the authority; no third derivation is introduced. | Technical | High | Open |
| C-003 | Change is additive | Existing authored charters that validate today must still validate: only new optional fields are added, all defaulting to `None` (absent-key semantics). | Business | High | Open |

### Key Entities

- **`CharterYaml`** (`src/charter/activation/schemas.py`): the frozen pydantic model of the
  git-tracked `charter.yaml`; gains the activation fields it is missing.
- **`ACTIVATION_YAML_KEYS`** (`src/charter/activation/pack_manager.py`): the derived
  authority for the flat activation-key vocabulary; not changed by this mission.
- **Legacy activation writer** (`prepare_activation_write` → `apply_yaml_write`): the
  pre-existing entry point the reproduction and the end-to-end regression go through; not
  changed by this mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 13 keys in `ACTIVATION_YAML_KEYS` validate through `CharterYaml` — 0 validation errors, 13/13 keys covered by a parametrized case. — [build] · no-op passable: no
- **SC-002**: The parity gate fails if the authority and the model's activation-shaped fields differ in either direction (2 planted-drift cases: a missing key, a stray field). — [ratchet] · no-op passable: no
- **SC-003**: The legacy writer → `charter.yaml` → `CharterYaml.model_validate` path succeeds for all three previously-rejected keys (3/3), and the pre-existing model tests pass unchanged (0 modified assertions in the strictness tests). — [build] · no-op passable: no
