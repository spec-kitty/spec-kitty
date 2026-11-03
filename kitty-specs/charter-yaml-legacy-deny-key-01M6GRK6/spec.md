# Mission Specification: A legacy `deactivated_<kind>` key on `charter.yaml`

**Mission Branch**: `issue-6855-charter-yaml-legacy-deny-key` (planning base and merge target; the PR head branch for this issue)
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6855 — "CharterYaml rejects a legacy charter.yaml carrying a hand-written deactivated_<kind> key". Operator guidance on this run: if backward compatibility conflicts with a deliberate strictness decision, stop and report rather than loosening validation silently, and say which side the evidence supports.

## Context and grounding (recorded, not a requirement)

`charter.activation.schemas.CharterYaml` is the declared shape of the git-tracked, authorable
`charter.yaml`; `model_config` sets `extra="forbid"` as the structural guard against a stray
nested `activation:` mapping (paula BLOCKER-1). Its flat activation fields restate
`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` and are pinned set-equal to it by
`tests/charter/test_activation_vocabulary_setequal.py` (#6556). `ACTIVATION_YAML_KEYS` is the
*allow* vocabulary only: `deactivated_<kind>` is not in it, and no denominator field is
declared, so a hand-written deny key fails `model_validate` with a bare
`extra_forbidden` — the deny-side twin of #6556, deferred out of it because the contract had
to be decided first.

Reproduced on current `main` (`f1e860a17f`):

```text
CharterYaml.model_validate({**sound_document, "deactivated_tactics": ["x"]})
# ValidationError: deactivated_tactics -- Extra inputs are not permitted [extra_forbidden]
```

**Which side the evidence supports: the model keeps refusing.** Three independent, current
sources say a deny key on `charter.yaml` is an error state, not a legitimate shape:

1. **ADR 2026-10-19-1, Decision 1 (constraint C-003)** — "`deactivated_*` keys never appear in
   `charter.yaml` or `config.yaml`". The deny-list lives only in
   `.kittify/charter/activation.yaml` (moved there by #6496).
2. **The 2026-10-20 amendment to that ADR** — a `deactivated_<kind>` key found on an
   unmigrated surface "is never applied: each command warns once, doctor reports
   `LEGACY_DENY_KEY` (an error), and the migration refuses it". `activation_ledger.
   _legacy_key_finding` returns that finding as an *error*, and `plan_ledger_migration`
   refuses the whole move while the key is present.
3. **#6556's own mission spec (`kitty-specs/charter-yaml-activation-key-parity-01M67HRX`,
   Edge Cases)** — "the model keeps rejecting them. They are ledger content, not
   `charter.yaml` content."

The only counter-evidence is `_stored_deny`'s docstring, which says a legacy surface's
hand-written deny key "is reported, never applied". That sentence describes the *read* path
(which never goes through the model, and reports the key), not a claim that the document is a
sound `charter.yaml`. Read as a licence for the model to accept the key it is misleading, and
that misreading is exactly what #6855 reports.

Accepting the key would also be a real regression, not just a contract question:
`deactivated_*` fields on the model would be dumped by `model_dump`/`emit_yaml` and by
`charter.activation.compiler`, which builds the emitted `charter.yaml` from this model — so a
`None`-defaulted field list would start emitting `deactivated_<kind>: null` into every
generated charter, breaking the byte-stability contract consolidated-charter-bundle-01KXSYB9#NFR-005 pins the `_OPTIONAL_EMPTY_OMIT_KEYS`
machinery exists to protect.

Conclusion of grounding: **keep refusing; make the refusal intentional, named and pinned.**
The bare pydantic `extra_forbidden` does not communicate the contract, so the model gains a
`mode="before"` validator that refuses a `deactivated_` key with a message naming the ledger,
the fact that such a key is never applied, and the remedy — while still refusing. The two
docstrings that read as if the shape were legitimate are corrected, and the decision is pinned
in the file the issue names, beside the allow-side gate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer reading a validation failure learns the contract (Priority: P1)

A caller validates a `charter.yaml` that a user hand-edited to carry
`deactivated_tactics: [x]` — a legacy shape that no writer produces and that the ledger,
doctor and migration all treat as an error. Today the failure is
`Extra inputs are not permitted`, which reads like a model bug and is the reason #6855 was
filed. It must instead say that a `deactivated_<kind>` key belongs in the activation ledger,
was never applied where it sits, and how to remove it.

**Why this priority**: it is the reported defect. The contract is decided in favour of
strictness; what is missing is that the refusal states the decision.

**Independent Test**: validate a sound document plus `deactivated_<kind>` and assert the
raised `ValidationError` still raises (no acceptance) and carries the ledger path and the
"never applied" wording.

**Acceptance Scenarios**:

1. **Given** a sound `charter.yaml` mapping, **When** a `deactivated_tactics` key is added and
   the document is validated, **Then** validation still fails, and the message names
   `.kittify/charter/activation.yaml`, says the entry was never applied, and names the remedy.
2. **Given** the same fixture without the deny key, **When** it is validated, **Then** it
   validates (no regression).

---

### User Story 2 - The strictness decision is a pinned invariant (Priority: P2)

A maintainer adds an activation-shaped field, or "completes" the vocabulary by declaring the
deny keys, believing #6556 asked for that. The deny side must be as pinned as the allow side:
the model declares no `deactivated_` field, and the deny vocabulary of the ledger is not part
of the `charter.yaml` allow vocabulary.

**Why this priority**: this issue exists because the allow/deny asymmetry was undocumented and
untested; pinning only the message would leave the contract free to be reversed silently.

**Independent Test**: a test in `tests/charter/test_activation_vocabulary_setequal.py` derives
the ledger's deny vocabulary (`charter.activation.activation_ledger.DENY_KEYS`) and asserts
(a) it is disjoint from `ACTIVATION_YAML_KEYS`, (b) no model field is a deny key, and
(c) the model refuses every one of them.

**Acceptance Scenarios**:

1. **Given** the ledger's deny vocabulary, **When** the guard runs, **Then** no deny key is a
   model field and every deny key is refused by `CharterYaml.model_validate`.
2. **Given** a model that declares a `deactivated_<kind>` field, **When** the guard runs,
   **Then** it fails naming the field and the ADR constraint it breaks.

### Edge Cases

- **An unknown deny key, not a current kind** (`deactivated_future_kind`): the ledger's own
  posture is to preserve and ignore it, but it still never appears on `charter.yaml`, so the
  model still refuses it. The refusal is by the `deactivated_` prefix, matching
  `activation_ledger._DENY_PREFIX`, not by a second kind table.
- **`deactivated_assets`**: assets are not activatable, so they have no deny-list; the prefix
  refusal covers it and no kind-specific exception is added.
- **A `deactivated_`-prefixed key that is not a string** — YAML keys are strings; a
  non-string key stays refused by `extra="forbid"` as before.
- **The all-allow-keys document** (#6556's parity case) must still validate: the new
  validator inspects only the deny prefix and changes nothing else.
- **Import graph**: `charter.activation.schemas` must not import `pack_manager` or
  `activation_ledger` at module scope (`pack_manager` imports this module; a back-import would
  be circular). The validator uses the literal prefix and a lazy import at most.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | A deny key is refused with a contract message | As a caller that validates `charter.yaml`, I want a `deactivated_<kind>` key refused with a message naming the activation ledger, the "never applied" fact and the remedy, so that the failure states the contract instead of looking like a model bug. | High | Open | [build] | no |
| FR-002 | The deny vocabulary is not declared on the model | As a maintainer, I want `CharterYaml` to declare no `deactivated_` field, so that the model never advertises a key the ledger, doctor and migration all treat as an error. | High | Open | [ratchet] | no |
| FR-003 | The docstrings state the decided contract | As a maintainer reading `CharterYaml` or `_stored_deny`, I want the deny-key posture stated as "refused and reported on `charter.yaml`", so that neither reads as if a hand-written deny key were a legitimate shape. | Medium | Open | [build] | no |
| FR-004 | The decision is pinned beside the allow-side gate | As a maintainer, I want a test in `tests/charter/test_activation_vocabulary_setequal.py` that derives the ledger's deny vocabulary and pins refusal, disjointness and the absence of deny fields, so that the strictness decision cannot be reversed silently. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new import cycle | `import charter.activation.schemas` succeeds on its own and does not import `charter.activation.pack_manager` at module scope; the added validator creates no module-level dependency on the activation writer/ledger. | Maintainability | High | Open |
| NFR-002 | Strictness unchanged, nothing loosened | `CharterYaml.model_config` keeps `extra="forbid"` and `frozen=True`; the nested-`activation:` rejection, the three-state `None`/`[]`/non-empty semantics, the `schema_version` pattern and the activation-field/authority set-equality all hold, verified by the pre-existing tests passing unmodified. | Reliability | High | Open |
| NFR-003 | No on-disk or writer change | No activation writer, ledger, migration, compiler or serialization behaviour changes; `emit_yaml`/`model_dump` output for every existing document is byte-identical (0 new keys emitted), so no project's `charter.yaml` changes. | Compatibility | High | Open |
| NFR-004 | Refusal cost is structural and bounded | The added validation is one prefix scan per root key at model construction: no I/O, no catalogue read, no module-level import and no per-kind loop. The existing model fixtures and the #6556 all-keys case stay in the `unit`/`fast` tier. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | ADR C-003 is binding | ADR 2026-10-19-1 Decision 1 (C-003): `deactivated_*` keys never appear in `charter.yaml` or `config.yaml`. The model must not declare them, because a declared field would be dumped and emitted by `charter.activation.compiler` and break the byte stability consolidated-charter-bundle-01KXSYB9#NFR-005 requires. | Technical | High | Open |
| C-002 | One deny vocabulary | The deny vocabulary stays owned by `charter.activation.activation_ledger.DENY_KEYS` (derived from `ArtifactKind`). The model refuses by the `deactivated_` prefix (the ledger's own `_DENY_PREFIX` posture) and introduces no second kind table. | Technical | High | Open |
| C-003 | Do not silently loosen validation | If backward compatibility and the strictness decision conflict, the strictness decision wins and the conflict is reported, never resolved by widening the model. Acceptance of the key is rejected in this mission (recorded above with its evidence). | Business | High | Open |

### Key Entities

- **`CharterYaml`** (`src/charter/activation/schemas.py`): the frozen pydantic model of the
  git-tracked `charter.yaml`; gains a before-validator that refuses deny keys and a docstring
  paragraph stating the posture. Gains no field.
- **`DENY_KEYS`** (`src/charter/activation/activation_ledger.py`): the derived deny vocabulary
  (`deactivated_<plural>` per activatable kind); unchanged, and now the test-time comparand
  for the pin.
- **`_stored_deny`** (`src/charter/activation/pack_manager.py`): the read-path docstring whose
  "reported, never applied" sentence is corrected to say the key is an error state, not a
  supported `charter.yaml` shape; no behaviour change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every key in the ledger's deny vocabulary is still refused by `CharterYaml` — 0 accepted, 100% covered by a parametrized case derived from `DENY_KEYS`. — [ratchet] · no-op passable: no
- **SC-002**: The refusal message for a deny key names the ledger path and the "never applied" fact — 2/2 required substrings asserted on the raised error. — [build] · no-op passable: no
- **SC-003**: The deny vocabulary is disjoint from `ACTIVATION_YAML_KEYS` and from the model's declared fields — 0 intersections, asserted both ways. — [ratchet] · no-op passable: no
- **SC-004**: The pre-existing strictness and parity tests pass unmodified (0 assertions edited in `tests/charter/test_charter_yaml_model.py`), and the document assembled by `test_document_carrying_every_authority_key_validates` (the #6556 all-keys case) still validates and still dumps the same model fields (0 new keys). — [build] · no-op passable: no
