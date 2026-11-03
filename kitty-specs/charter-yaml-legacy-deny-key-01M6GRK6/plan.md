# Implementation Plan: A legacy `deactivated_<kind>` key on `charter.yaml`

**Branch**: `issue-6855-charter-yaml-legacy-deny-key` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-yaml-legacy-deny-key-01M6GRK6/spec.md`

## Summary

`CharterYaml` (the pydantic model of the git-tracked `charter.yaml`) declares the *allow*
vocabulary (`ACTIVATION_YAML_KEYS`) and nothing else, so a hand-written
`deactivated_<kind>` key on a legacy `charter.yaml` fails `model_validate` with a bare
`extra_forbidden`. #6855 asks which side of the contract is right. The evidence (ADR
2026-10-19-1 Decision 1 / C-003 and its 2026-10-20 amendment, `doctor`'s `LEGACY_DENY_KEY`
error, `plan_ledger_migration`'s refusal, and #6556's own mission spec) decides it for
strictness: `deactivated_*` is ledger content, never `charter.yaml` content.

The change therefore does **not** widen the model. It makes the existing refusal
intentional and legible — a `mode="before"` validator refuses a `deactivated_` key with a
message naming `.kittify/charter/activation.yaml`, the "never applied" fact and the remedy —
corrects the two docstrings that read as if the shape were legitimate, and pins the decision
in `tests/charter/test_activation_vocabulary_setequal.py` beside the allow-side parity gate.
No field is added, so `model_dump`/`emit_yaml`/`compiler` emit exactly the same bytes as
today.

## Technical Context

**Language/Version**: Python 3.11 (pydantic v2, `src/charter/activation/schemas.py`)
**Primary Dependencies**: pydantic v2 (`BaseModel`, `ConfigDict`, `model_validator`)
**Storage**: files — `.kittify/charter/charter.yaml`, `.kittify/charter/activation.yaml`
(the ledger, #6496)
**Testing**: pytest (`tests/charter/test_charter_yaml_model.py`,
`tests/charter/test_activation_vocabulary_setequal.py`), targeted `-m "unit or fast"` runs
**Target Platform**: library/CLI shipped in the `spec-kitty-cli` wheel — OS independent
**Project Type**: single Python package tree (`src/charter`, `src/specify_cli`, `src/kernel`)
**Performance Goals**: no measurable change — one prefix scan over the document's root keys
in a before-validator on a model constructed a handful of times per command (NFR-004)
**Constraints**: no module-level import from `schemas` into the activation writer/ledger
layer (import cycle); no writer, ledger, migration, compiler or serialization change (NFR-003)
**Scale/Scope**: 2 source files (`src/charter/activation/schemas.py`, one docstring in
`src/charter/activation/pack_manager.py`), 2 test files, 1 changelog fragment; no on-disk
bytes change for any project

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the deny vocabulary keeps its owner
  (`activation_ledger.DENY_KEYS`, derived from `ArtifactKind`); the model refuses by the
  ledger's own `deactivated_` prefix and adds no second kind table (C-002).
- **Architectural alignment** — `charter.activation.schemas` must not import
  `pack_manager`/`activation_ledger` at module scope; the validator uses the literal prefix,
  keeping the import graph unchanged (NFR-001, pinned by
  `test_schemas_import_does_not_pull_in_pack_manager`).
- **Locality of change (DIRECTIVE_024 / smallest-viable-diff)** — one model validator, two
  docstring paragraphs, one test block; no rewrite of the activation layer.
- **ATDD-first / red-first (DIRECTIVE_034)** — the failing test comes first: the ledger's
  deny vocabulary is refused *without* a contract message and the docstrings do not state the
  posture; the test goes red on the message assertions before the validator lands.
- **Terminology** — "activation ledger", "exclusion", "legacy surface", "effective deny" are
  used as `docs/context/charter.md` defines them; the key is called a deny-list key /
  exclusion, never "deactivated list".
- **Ratchet discipline** — the pin extends the existing set-equality guard file with a
  derived (never hand-listed) deny vocabulary; no allowlist.
- **No heavy suites** — targeted `tests/charter` runs only (NO_FULL_HEAVY_SUITES_IN_MISSION).

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-yaml-legacy-deny-key-01M6GRK6/
├── plan.md              # This file
├── research.md          # Grounding: reproduction, ADR evidence, rejected alternatives
├── spec.md              # Requirements
├── tasks/               # Work package prompts (/spec-kitty.tasks)
└── traces/              # approach / design-decisions / tooling-friction tracers
```

### Source Code (repository root)

```
src/
└── charter/
    └── activation/
        ├── schemas.py          # CharterYaml — validator + docstring
        ├── pack_manager.py     # _stored_deny docstring only (no behaviour change)
        └── activation_ledger.py  # DENY_KEYS / _DENY_PREFIX — the deny authority (unchanged)

tests/
└── charter/
    ├── test_charter_yaml_model.py              # model behaviour (unchanged assertions + new message cases)
    └── test_activation_vocabulary_setequal.py  # the pin, beside the allow-side gate
```

**Structure Decision**: the existing charter/activation layout is kept. The only new
behaviour is one before-validator in the model that already owns "the shape of
`charter.yaml`"; the pin lands in the file the issue names and that already owns the
allow-side vocabulary guard, so the allow and deny halves of the contract sit together.

## Design

### D1 — A `mode="before"` validator that refuses, with a contract message

`CharterYaml` gains:

```python
_DENY_KEY_PREFIX = "deactivated_"

@model_validator(mode="before")
@classmethod
def _refuse_deny_keys(cls, data: Any) -> Any:
    if isinstance(data, Mapping):
        denied = sorted(k for k in data if isinstance(k, str) and k.startswith(_DENY_KEY_PREFIX))
        if denied:
            raise ValueError(
                f"{', '.join(denied)} cannot appear on charter.yaml: a deactivation "
                f"(deactivated_<kind>) is recorded only in .kittify/charter/activation.yaml. "
                "A hand-written deny key on a legacy charter.yaml was never applied; remove it "
                "by hand, then run `spec-kitty upgrade` (or `spec-kitty migrate activation-ledger`)."
            )
    return data
```

`mode="before"` so the message is raised instead of pydantic's generic
`extra_forbidden`, and so it fires for a document that would otherwise be rejected anyway
(never for a valid one). The refusal is by prefix, matching
`activation_ledger._DENY_PREFIX` and its "an unknown `deactivated_<x>` is preserved and
reported" posture: no kind table is restated in the schema (C-002), and a kind a future CLI
adds is refused on `charter.yaml` too.

Rejected alternative A — **declare the deny fields** (risk: `compiler` builds the emitted
`charter.yaml` from this model, so `deactivated_*: null` would be emitted into every
generated charter unless every name were also added to `_OPTIONAL_EMPTY_OMIT_KEYS`; it would
also contradict ADR C-003 by declaring an illegal shape legal). Rejected alternative B —
**leave the bare `extra_forbidden`** (this is the reported defect: it reads like a model bug
and says nothing about the ledger). See [research.md](./research.md) for the full evidence.

### D2 — Correct the two docstrings that read as a licence

- `CharterYaml`'s class docstring gains a short paragraph: the deny side is deliberately not
  a field; a `deactivated_<kind>` key on `charter.yaml` is an error state (`LEGACY_DENY_KEY`
  in doctor, refused by the ledger migration), is never applied, and the model refuses it by
  design — so a future reader cannot "complete" the vocabulary by adding the fields.
- `pack_manager._stored_deny`'s "whose hand-written `deactivated_<kind>` key is reported,
  never applied" sentence is kept (it is the read-path truth) and extended with what the
  document *is*: not a supported shape — doctor reports it as an error and the ledger
  migration refuses it. Behaviour is unchanged.

### D3 — The pin, beside the allow-side gate

`tests/charter/test_activation_vocabulary_setequal.py` gains a "#6855" block:

- `test_deny_vocabulary_is_disjoint_from_the_activation_allow_vocabulary` — derived from
  `activation_ledger.DENY_KEYS` vs `ACTIVATION_YAML_KEYS`.
- `test_charter_yaml_declares_no_deny_field` — no model field starts with `deactivated_`.
- `test_charter_yaml_refuses_every_deny_key_with_the_contract_message` — parametrized over
  `DENY_KEYS`: still raises, and the message names the ledger and "never applied" (SC-002).
- A positive control on the same fixture: the same document *without* the deny key validates,
  so the refusal is attributable to the key (non-vacuity).

The vocabulary is read through the ledger module, not `pack_manager`, so the guard file keeps
its existing lazy-import discipline.

### Risks and mitigations

- **Risk**: a `mode="before"` validator could shadow validation errors for malformed input.
  *Mitigation*: it only raises for the deny prefix and returns the input untouched otherwise;
  the pre-existing strictness tests (nested `activation:`, `activated_not_a_kind`,
  `schema_version` pattern, frozen) run unmodified.
- **Risk**: the refusal message drifts from doctor/migration wording. *Mitigation*: assert the
  two stable facts (ledger path, "never applied") rather than the full prose.
