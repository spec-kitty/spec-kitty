# Directives

**Directives** are constraint-oriented governance rules that apply across flows or
phases. Each directive encodes a required or advisory expectation and can reference
lower-level tactics for execution.

## Schema

All directive files conform to `directive.schema.yaml` with fields:

- `schema_version` — Schema version string
- `id` — Unique identifier (e.g., `TEST_FIRST`)
- `title` — Human-readable name
- `intent` — What the directive enforces
- `enforcement` — `required` or `advisory`

Cross-artifact relationships (directive → tactic, directive → paradigm, etc.)
are expressed as typed edges in the per-kind DRG fragments — an edge lives in
the fragment for its *source* kind, so a directive's edges are in
`packs/built-in/directive.graph.yaml`. Inline `tactic_refs`
and `applies_to` fields were removed in Phase 1 excision (mission
`excise-doctrine-curation-and-inline-references-01KP54J6` WP02).

## Naming Convention

Numbered directives follow the pattern `NNN-kebab-title.directive.yaml` (e.g.,
`004-test-driven-implementation-standard.directive.yaml`). Non-numbered directives
use plain kebab-case (e.g., `test-first.directive.yaml`).

## Shipped Directives

Numbered shipped directives live in `directives/built-in/` and are referenced by
shipped agent profiles and the doctrine reference graph. A consistency test
verifies that every directive code referenced by a shipped profile resolves to a
file in this directory.

## Glossary Reference

See [Directive](../../../docs/context/charter.md#directive) in the charter
glossary context.
