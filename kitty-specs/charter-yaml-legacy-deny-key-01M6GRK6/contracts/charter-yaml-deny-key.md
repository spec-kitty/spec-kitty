# Contract: a `deactivated_<kind>` key on `charter.yaml` (#6855)

**Status**: accepted by this mission · **Owner**: `charter.activation.schemas.CharterYaml`
**Decision record**: ADR 2026-10-19-1 Decision 1 (constraint C-003) and its 2026-10-20 amendment;
grounding in [`../research.md`](../research.md) R2–R5.

## What is contract, and what is not

`charter.yaml` is the git-tracked, authorable charter document. It carries the **allow**
vocabulary: the flat `activated_<plural>` keys, `activated_kinds` and
`mission_type_activations`, whose single authority is
`charter.activation.pack_manager.ACTIVATION_YAML_KEYS`. It carries **no** deny vocabulary.
A deactivation (`deactivated_<plural>`, an exclusion) is recorded only in the activation
ledger, `.kittify/charter/activation.yaml`.

A `deactivated_<kind>` key found on a `charter.yaml` is therefore a hand edit of a shape no
writer produces, and every surface treats it the same way:

| Surface | Verdict on the key |
|---|---|
| activation read (`_stored_deny`) | reported once per process, **never applied** |
| `spec-kitty doctor charter-packs` | `LEGACY_DENY_KEY` — an **error** |
| `plan_ledger_migration` / `spec-kitty migrate activation-ledger` | **refuses** the move while the key is present |
| `CharterYaml.model_validate` | **refuses** the document, naming the ledger and the remedy |

## The model's guarantees

1. **Refusal, not acceptance.** A document containing any root key whose name starts with
   `deactivated_` raises `pydantic.ValidationError`. The refusal is raised by a
   `mode="before"` validator (`CharterYaml._refuse_deny_keys`), so it replaces pydantic's
   generic `extra_forbidden` text for this case.
2. **The message carries the contract.** It names the offending keys, the ledger
   `.kittify/charter/activation.yaml`, the fact that such a key was never applied, and the
   remedy (remove the key by hand, then `spec-kitty upgrade` or
   `spec-kitty migrate activation-ledger`).
3. **No deny field is declared, ever.** Declaring one would (a) advertise an illegal shape
   as legal, contradicting the decision above, and (b) be dumped by `emit_yaml` and emitted
   by `charter.activation.compiler` into every regenerated `charter.yaml`, because that
   compiler builds the emitted document from this model. The strictness guards that already
   exist — `extra="forbid"`, `frozen=True`, the rejection of a nested `activation:` mapping,
   the rejection of an unknown `activated_*` key, and the three-state `None`/`[]`/non-empty
   semantics — are unchanged.
4. **The prefix is the boundary, not a kind table.** The refusal restates the ledger's own
   `_DENY_PREFIX` posture: a `deactivated_<x>` for a kind a later CLI adds is preserved and
   reported by the ledger, and it is equally not `charter.yaml` content. `schemas.py` adds no
   second enumeration of artifact kinds and no import from the activation writer/ledger layer
   (`pack_manager` imports `schemas`, so that would be circular).

## Pinned by

- `tests/charter/test_charter_yaml_model.py::TestDenyKeysAreNotCharterYamlContent` — the
  concrete legacy document: refused, with the message facts, and a positive control.
- `tests/charter/test_activation_vocabulary_setequal.py` — the derived pin: the ledger's
  `DENY_KEYS` is non-empty and deny-shaped, disjoint from `ACTIVATION_YAML_KEYS`, declared by
  no model field, and refused for every key with the same-fixture positive control.

## Non-goals

- Migrating or repairing an existing hand-edited `charter.yaml`: the remedy is the operator's
  (`remove by hand, then upgrade`), exactly as the doctor finding already says.
- Changing the read path, doctor, the migration, the writer or any emitted bytes.
