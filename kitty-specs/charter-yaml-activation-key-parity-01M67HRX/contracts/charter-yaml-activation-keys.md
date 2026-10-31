# Contract: the flat activation-key vocabulary of `charter.yaml`

**Mission**: `charter-yaml-activation-key-parity-01M67HRX` (issue #6556)
**Surfaces**: `charter.activation.schemas.CharterYaml` (the model),
`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` (the authority),
`charter.activation.pack_manager.prepare_activation_write` (the writer).

## C1 — One authority defines the legal key set

The set of flat activation keys a git-tracked `charter.yaml` may carry is
`:data:`charter.activation.pack_manager.ACTIVATION_YAML_KEYS`` and nothing else. It is derived
from :class:`charter.offering.artifact_kinds.ArtifactKind` (every charter-activatable kind maps
to `activated_<plural>`, plus the `mission_type_activations` outlier and the coarse
`activated_kinds` ledger key). No module restates the vocabulary; consumers derive it.

Today that is 13 keys:

```
activated_kinds
mission_type_activations
activated_directives
activated_tactics
activated_styleguides
activated_toolguides
activated_paradigms
activated_procedures
activated_agent_profiles
activated_mission_step_contracts
activated_glossary_packs
activated_skills
activated_anti_patterns
```

## C2 — The model declares exactly those fields

`CharterYaml` is the declared shape of `charter.yaml` and forbids extra keys
(`extra="forbid"`). Its activation-shaped fields — every field named
`mission_type_activations` or starting with `activated_` — are set-equal to
`ACTIVATION_YAML_KEYS`, in both directions:

- a key the authority gains and the model does not declare fails
  `tests/charter/test_activation_vocabulary_setequal.py::test_charter_yaml_activation_fields_set_equal_to_authority`
  with the missing names listed, and
- a field the writer refuses (for example `activated_assets`, because
  `ArtifactKind.ASSET` is not charter-activatable) fails the same test as a stray field.

Pydantic needs the fields at class-definition time, so they are static and the equality is
pinned by that test rather than derived at import time — `charter.activation.pack_manager`
already imports `charter.activation.schemas`, so a module-level back-import would be circular.

## C3 — Writer and model accept the same documents

For every key in the authority, a document produced by
`prepare_activation_write` on a legacy (unmigrated) project — where activation is still written
to `charter.yaml` rather than `.kittify/charter/activation.yaml` — validates through
`CharterYaml.model_validate`. Proven by
`tests/charter/test_charter_yaml_model.py::TestWriterAndModelAgreeOnActivationKeys`.

## C4 — Strictness is part of the contract

Unchanged by this mission and required to stay unchanged: `frozen=True`, `extra="forbid"`, the
rejection of a nested `activation:` mapping, and the three-state semantics of each field
(`None` = key absent = kind unrestricted, `[]` = explicit fail-closed empty, non-empty list =
the activated set).

## Out of scope

Migration of the legacy surface to the activation ledger (#6496, ADR `2026-10-19-1`) and the
deny vocabulary (`deactivated_<kind>`, ledger-only — a legacy-surface deny write is refused, so
the model keeps rejecting those keys).
