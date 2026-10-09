# Paradigms

**Paradigms** are worldview-level framings for how work is approached in a domain.
They influence the selection and interpretation of directives and tactics but are
not executable step recipes themselves.

## Schema

Paradigm files conform to the doctrine YAML conventions with fields:

- `schema_version` — Schema version string (currently `1.0`)
- `id` — Unique identifier (e.g., `test-first`)
- `name` — Human-readable name
- `summary` — Brief description of the worldview stance

## Naming Convention

Files use the pattern `kebab-id.paradigm.yaml` (e.g., `test-first.paradigm.yaml`).

Shipped paradigms live under:

- `packs/built-in/paradigms/*.paradigm.yaml`

## Glossary Reference

See [Paradigm](../../../docs/context/charter.md#paradigm) in the charter
glossary context.
