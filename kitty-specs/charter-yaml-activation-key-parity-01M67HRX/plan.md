# Implementation Plan: CharterYaml activation-key parity

**Branch**: `kitty/mission-charter-yaml-activation-key-parity-01M67HRX` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-yaml-activation-key-parity-01M67HRX/spec.md`

## Summary

`CharterYaml` (the pydantic model of the git-tracked `charter.yaml`) hand-declares ten flat
activation fields while the single vocabulary authority
`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` holds thirteen. The three missing
names — `activated_glossary_packs`, `activated_skills`, `activated_anti_patterns` — are
written to `charter.yaml` by the legacy activation writer, so a schema-validated read of a
legitimate charter fails. The fix adds the three fields (typed, `None` default, unchanged
three-state semantics), leaves `extra="forbid"` and the rest of the model untouched, and
pins the model↔authority relationship with a parity gate plus an end-to-end
writer→`charter.yaml`→model regression. Grounding (recorded in [research.md](./research.md))
shows the writer is correct and the model's static list is stale; `activated_assets` from
the issue text is **not** a legal key any more, so it is deliberately not added.

## Technical Context

**Language/Version**: Python 3.11 (pydantic v2, `src/charter/activation/schemas.py`)
**Primary Dependencies**: pydantic v2 (`BaseModel`, `ConfigDict`, `Field`); ruamel.yaml for
the writer/loader used by the end-to-end regression
**Storage**: files — `.kittify/charter/charter.yaml`, `.kittify/config.yaml`,
`.kittify/charter/activation.yaml` (the ledger, #6496)
**Testing**: pytest (`tests/charter/test_charter_yaml_model.py`,
`tests/charter/test_activation_vocabulary_setequal.py`), `uv run pytest -m "unit or fast"`
**Target Platform**: library/CLI shipped in the `spec-kitty-cli` wheel — OS independent
**Project Type**: single Python package tree (`src/charter`, `src/specify_cli`, `src/kernel`)
**Performance Goals**: no change — three extra optional pydantic fields on a model that is
constructed a handful of times per command
**Constraints**: no new module-level import from `schemas` into the activation writer/manager
layer (import cycle, see research.md); no change to any writer, ledger or migration
**Scale/Scope**: 1 source file (`src/charter/activation/schemas.py`), 2 test files, 1
changelog entry; no on-disk bytes change for any project

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — satisfied by construction: `ACTIVATION_YAML_KEYS` stays
  the only definition of the legal key set; the model restates names as typed fields and a
  parity gate pins the restatement. No third derivation is introduced (C-002).
- **Locality of change (DIRECTIVE_024 / smallest-viable-diff)** — one source file, additive
  fields; no writer, ledger, migration or docs-reference rewrite.
- **ATDD-first / red-first (DIRECTIVE_034)** — the failing test comes first, through the
  pre-existing writer entry point, before the model gains the fields.
- **Terminology** — "activation ledger", "flat activation keys", "legacy surface" are used
  as `docs/context` and #6496 define them; `activated_assets` is called out as not an
  activation key.
- **Ratchet discipline** — the parity gate is a shrink-only style invariant (no allowlist),
  consistent with `tests/architectural/test_charter_kind_vocabulary_single_authority.py`.
- **No heavy suites** — targeted `tests/charter` runs only (NO_FULL_HEAVY_SUITES_IN_MISSION).

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-yaml-activation-key-parity-01M67HRX/
├── plan.md              # This file
├── research.md          # Grounding, reproduction and import-cycle evidence
├── spec.md              # Requirements
├── tasks/               # Work package prompts (/spec-kitty.tasks)
└── traces/              # approach / design-decisions / tooling-friction tracers
```

### Source Code (repository root)

```
src/
└── charter/
    └── activation/
        ├── schemas.py          # CharterYaml — the only src/ file changed
        ├── pack_manager.py     # ACTIVATION_YAML_KEYS — the authority (unchanged)
        └── charter_yaml_io.py  # load/apply the writer path uses (unchanged)

tests/
├── charter/
│   ├── test_charter_yaml_model.py              # model behaviour + writer end-to-end repro
│   └── test_activation_vocabulary_setequal.py  # single-authority parity gate
└── architectural/
    └── test_charter_kind_vocabulary_single_authority.py  # style reference, unchanged
```

**Structure Decision**: the existing charter/activation layout is kept; the change is one
model definition in `src/charter/activation/schemas.py`, and the two test files that already
own "the shape of `charter.yaml`" and "the activation-key vocabulary" respectively.

## Design

### D1 — Declare the three missing names as typed fields (not a dynamic model)

`CharterYaml` gains:

```python
activated_glossary_packs: list[str] | None = None
activated_skills: list[str] | None = None
activated_anti_patterns: list[str] | None = None
```

They are grouped with the existing activation fields, keep the documented three-state
`None`/`[]`/non-empty contract (charter contract G3), and default to `None`, so an authored
charter without them validates exactly as before (C-003).

Rejected alternative: build the fields dynamically (`create_model`) inside `schemas.py`.
`charter.activation.schemas` is imported as part of `charter.activation.pack_manager`'s own
import chain, so a module-level import of the authority here is a circular import, and a
dynamic model would erase the per-field types, the per-field documentation and mypy/editor
visibility for a vocabulary that changes once or twice a year. Static fields plus a parity
gate give the same anti-drift property without either cost.

### D2 — Pin the parity with a test against the authority, both directions

New cases in `tests/charter/test_activation_vocabulary_setequal.py` (the file that already
guards the other three copies of this vocabulary):

- `test_charter_yaml_activation_fields_set_equal_to_authority` — the set of
  `activated_*`/`mission_type_activations` field names declared on `CharterYaml.model_fields`
  equals `frozenset(ACTIVATION_YAML_KEYS)`; the assertion message names the missing and the
  stray names so the maintainer is told exactly what to add or drop.
- `test_charter_yaml_has_no_activated_assets_field` — pins C-001 explicitly, so the stale
  part of the issue is not "fixed" by a future reader.

The existing `test_activation_field_is_flat_root_attribute` parametrization in
`tests/charter/test_charter_yaml_model.py` changes its hard-coded ten-name list into a
parametrization over `ACTIVATION_YAML_KEYS`, so "the model accepts every legal key" is a
behavioural assertion rather than a second mirror of the vocabulary.

### D3 — End-to-end regression through the pre-existing writer

A new test drives the real path the defect was reported on: a legacy (unmigrated) fixture
project (`charter.yaml` with `catalog`/`metadata`, `config.yaml` carrying the `charter:`
pointer and one legacy activation key), `prepare_activation_write` → `apply_yaml_write` for
each of the three previously-rejected keys, then `load_charter_yaml` →
`CharterYaml.model_validate`. This is the test that is red on `main` and green after the
fix, and it fails the same way the issue's reproduction does (`extra_forbidden`).

### D4 — Strictness stays

No change to `model_config` (`frozen=True, extra="forbid"`), to the `schema_version` pattern,
or to the nested-`activation:` structural guard. The existing strictness tests must pass
unmodified; one added case shows an unrelated unknown key (`activated_not_a_kind`) is still
rejected, so "accepts the authority" never degrades into "accepts anything `activated_*`".

## Implementation Concern Map

### IC-01 — Model/authority parity in `CharterYaml`

- **Purpose**: make the model of `charter.yaml` accept exactly the flat activation keys the
  authority defines, so a legitimate charter validates.
- **Relevant requirements**: FR-001, FR-002, NFR-002, NFR-003, C-001, C-002, C-003, SC-001
- **Affected surfaces**: `src/charter/activation/schemas.py` (`CharterYaml` class docstring
  and field block)
- **Sequencing/depends-on**: none
- **Risks**: the class docstring says "the ten `activated_*` fields"; it must be corrected in
  the same edit or it becomes a fresh false statement. `_OPTIONAL_EMPTY_OMIT_KEYS` and the
  serializers must not need changes (they are key-driven, not field-driven).

### IC-02 — Red-first proof and the anti-drift gates

- **Purpose**: prove the defect through the writer, then pin the vocabulary so it cannot
  drift again.
- **Relevant requirements**: FR-003, FR-004, NFR-001, SC-002, SC-003
- **Affected surfaces**: `tests/charter/test_charter_yaml_model.py`,
  `tests/charter/test_activation_vocabulary_setequal.py`
- **Sequencing/depends-on**: IC-01 (the end-to-end and parity tests go green only with the
  fields; the red run is captured before IC-01 lands)
- **Risks**: the parity test must derive its expectation from `ACTIVATION_YAML_KEYS`, never
  restate the names — otherwise it becomes another mirror of the thing it guards.

### IC-03 — User-facing notes

- **Purpose**: the model is now usable as the `charter.yaml` schema, which is what
  `charter synthesize`'s soundness check (#6555) wanted; say so for users and record the
  vocabulary rule for maintainers.
- **Relevant requirements**: FR-001 (user-visible effect), C-001 (the `activated_assets`
  trap)
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` under `[Unreleased]`;
  `docs/architecture/doctrine-kinds.md` only if a sentence there currently claims the model
  rejects these keys
- **Sequencing/depends-on**: IC-01
- **Risks**: keep the entry under 1,200 characters with the bold impact-first lead and
  `(#6556)`.

## Complexity Tracking

Not applicable — no charter violations.
