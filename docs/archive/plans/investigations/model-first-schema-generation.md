---
title: Model-First Schema Generation
description: 'Design note on model-first schema generation: deriving schemas from the data model rather than hand-authoring them, in a field-table record.'
doc_status: deprecated
updated: '2026-08-12'
---
> **RETIRED (shipped)** — the model-first design in this note shipped as the
> `scripts/generate_schemas.py` pipeline (Pydantic models as the single source of truth for the
> doctrine YAML schemas). Retained for historical reference; do not consult for current behavior.

# Model-First Schema Generation

| Field | Value |
|---|---|
| Date | 2026-03-29 |
| Scope | Pydantic models as single source of truth for all 10 doctrine YAML schemas |
| Related PRs | feature/agent-profile-implementation branch |
| Test result | 1067 passed, 0 failures |

## Purpose

Establish a model-first architecture where Pydantic models are the single
source of truth for every doctrine YAML schema.  Before this work, 6 of 10
schemas were hand-written YAML; the remaining 4 (mission, import-candidate,
model-to-task\_type, agent-profile) had no Pydantic models at all.  Drift
between models and schemas was already observable in the original 6.

---

## Architecture

```
Pydantic model  ──►  generate_schemas.py  ──►  *.schema.yaml
  (source of truth)     (post-processor)        (derived artifact)
```

`scripts/generate_schemas.py` calls `model_json_schema()` on each registered
model, then applies a deterministic post-processing pipeline:

1. **Inline enum refs** — StrEnum `$ref` entries are replaced with inline
   `type: string, enum: [...]`.  `ArtifactKind` gets a restricted subset;
   all other enums are inlined verbatim.
2. **Rename definitions** — `$defs/PascalCase` → `definitions/snake_case`.
3. **Clean Pydantic artifacts** — remove auto-generated `title` metadata,
   simplify `anyOf: [{type: X}, {type: null}]` to plain `type: X`, strip
   `default: []`/`default: null`.
4. **Add minLength** — required string fields without a `pattern` constraint
   get `minLength: 1`.
5. **Add metadata** — `$schema`, `$id`, `title`, `description`.
6. **Per-type fixups** — conditional rules (`allOf`), description annotations,
   format hints, `oneOf` conversions.
7. **Key ordering** — deterministic property ordering for clean diffs.

### CI integration

```bash
python scripts/generate_schemas.py --check   # exits 1 if any schema is stale
python scripts/generate_schemas.py           # regenerate all schemas
python scripts/generate_schemas.py mission   # regenerate a single schema
```

---

## Phase 1: Fix Doctrine Test Failures

Starting point: 13 test failures across tactics, procedures, styleguides,
agent profiles, and cycle detection.

All 13 failures were resolved by correcting schema-model drift:

- Tactic fixtures with extra properties that violated `additionalProperties:
  false` — folded content into step descriptions or a new `notes` field.
- Procedure model missing `anti_patterns`, `notes`, and `reason` on
  `ProcedureReference`.
- Styleguide/directive models missing `id`/`schema_version` pattern
  constraints.
- Cycle detection tests needed updated after cross-reference field additions.

Result: **1065 tests passing, 0 failures**.

---

## Phase 2: Schema Generation for Original 6 Schemas

Created `scripts/generate_schemas.py` and Pydantic model updates:

| Schema | Model location | Key changes |
|--------|----------------|-------------|
| paradigm | `doctrine.paradigms.models` | Added `tactic_refs`, `directive_refs`, `opposed_by` |
| tactic | `doctrine.tactics.models` | Added `notes`, `opposed_by`; pattern constraints on `id` |
| directive | `doctrine.directives.models` | Added `opposed_by`; pattern on `id`/`schema_version` |
| procedure | `doctrine.procedures.models` | Added `ProcedureAntiPattern`, `anti_patterns`, `notes` |
| styleguide | `doctrine.styleguides.models` | Pattern constraints on `id`/`schema_version` |
| toolguide | `doctrine.toolguides.models` | `extra='forbid'` added |

A shared `Contradiction` model was created in `doctrine.shared.models` and
imported by paradigm, tactic, and directive models to represent
`opposed_by` entries.

All models received `extra='forbid'` (matching `additionalProperties: false`
in schemas).

---

## Phase 3: Remaining 4 Schemas

Four schemas had no Pydantic models.  Each required a different generation
strategy due to schema complexity:

### Mission (`doctrine.missions.models`)

Straightforward model with one complication: the `states` array accepts both
bare strings and objects (`{id, agent-profile}`).  Pydantic emits `anyOf` for
this union; the hand-written schema uses `oneOf`.  A fixup converts
`anyOf → oneOf` in the generated schema.

The `MissionTransition.from` field uses `alias="from"` since `from` is a
Python keyword.  The `by_alias=True` flag ensures the schema emits `from`
instead of `from_state`.

### Import Candidate (`doctrine.import_candidates.models`)

The most complex schema — uses a top-level `oneOf` with two independent
object schemas:

- **LegacyImportCandidate** (WP01 baseline): `schema_version`, `id` with
  uppercase pattern, `source.title + source.reference`, `target`, status
  enum `[proposed, accepted, rejected]`.
- **CurationImportCandidate** (WP03 scaffold): richer `source` with
  `type`/`publisher`/`url`/`accessed_on`, `classification.target_concepts`,
  `adaptation`, status enum `[proposed, reviewing, adopted, rejected]`,
  plus conditional: if `status == adopted` then `resulting_artifacts` is
  required with `minItems: 1`.

A top-level `oneOf` cannot be expressed by a single Pydantic model, so
`generate_schemas.py` has a `register_custom()` path: it generates each
variant independently, fully inlines all `$ref` definitions (each variant
must be self-contained), and wraps them in the outer `oneOf`.

### Model-to-Task Type (`doctrine.model_task_routing.models`)

The largest schema (251 lines) with 17 `$defs` entries including 7 StrEnums.
The standard pipeline handles this with `_inline_all_enum_refs()` — a
generalisation of the `ArtifactKind`-only inliner that replaces all StrEnum
`$ref` entries.  Format annotations (`date-time`, `uri`) and `default: USD`
are added in the fixup phase.

### Agent Profile (`doctrine.agent_profiles.schema_models`)

A new `schema_models.py` was created **separate from** the domain model in
`profile.py`.  The two models serve different purposes:

| Concern | `profile.py` (domain) | `schema_models.py` (schema) |
|---------|----------------------|----------------------------|
| Purpose | Runtime object hydration, weighted matching, inheritance | Schema generation |
| Draft | N/A (Pydantic only) | Draft 2020-12 (was Draft-07) |
| Extra fields | `sentinel`, `excluding` | `tactic-references`, `toolguide-references`, `styleguide-references`, `self-review-protocol` |
| Role field | `Role` StrEnum + `BeforeValidator` coercion | Plain `str` |
| Context sources | 3 fields | 6 fields (adds `tactics`, `toolguides`, `styleguides`) |

The schema model uses `by_alias=True` to emit kebab-case property names
matching the YAML convention (`profile-id`, `context-sources`, etc.).

---

## New Infrastructure in generate\_schemas.py

| Feature | Purpose |
|---------|---------|
| `by_alias` flag | Emit alias names in schema (mission, agent-profile) |
| `register_custom()` | Fully custom generators for non-standard schemas |
| `_inline_all_enum_refs()` | Inline all StrEnum `$ref` entries, not just ArtifactKind |
| `_inline_all_refs()` | Fully inline all `$ref` for self-contained oneOf variants |
| `_deep_order_variant()` | Key ordering inside `oneOf` entries |

---

## DDD Paradigm Artifact

As part of Phase 2, a Domain-Driven Design paradigm was authored:

- **File:** `src/doctrine/paradigms/shipped/domain-driven-design.paradigm.yaml`
- **Coverage:** Strategic DDD (Bounded Contexts, Context Mapping, Ubiquitous
  Language) and Tactical DDD (Aggregates, Entities, Value Objects, Domain
  Events, Repositories, Services).
- **References:** 7 existing tactics, 3 existing directives.
- **Opposed by:** Big Ball of Mud, CRUD-Everywhere, Anemic Domain Model.

Gaps (10+ missing tactics) are tracked in `work/ddd-tactic-gaps.md`.

---

## Final State

| Metric | Value |
|--------|-------|
| Total schemas | 10 (all generated from models) |
| Hand-written schemas | 0 |
| Tests passing | 1067 |
| Tests failing | 0 |
| `--check` mode | All 10 OK |
