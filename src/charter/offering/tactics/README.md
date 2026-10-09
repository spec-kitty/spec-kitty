# Tactics

**Tactics** are reusable behavioral execution patterns that define how work is
performed. They are operational, agent-consumable, and can be selected by directives
and mission context.

## Schema

Tactic files conform to `tactic.schema.yaml` with fields for step sequences (each
with title, description, examples) and reference objects.

## Naming Convention

Files use the pattern `kebab-id.tactic.yaml` (e.g., `zombies-tdd.tactic.yaml`).

## Shipped Tactics

| Tactic | Steps | Purpose |
|--------|-------|---------|
| `acceptance-test-first` | 6 | ATDD acceptance-first workflow |
| `tdd-red-green-refactor` | 6 | Classic Red/Green/Refactor loop with guardrails |
| `zombies-tdd` | 7 | Z/O/M/B/I/E/S progressive test complexity |
| `glossary-curation-interview` | 11 | Systematic glossary expansion with HiC curation rounds |
| `five-paradigm-parallel-debugging` | 6 | Parallel recurring-bug investigation across five independent debugging paradigms |

Tactics are referenced by directives and procedures via typed edges in
the per-kind DRG fragments (relation `requires`). An edge lives in the
fragment for its *source* kind, so those edges are in
`packs/built-in/directive.graph.yaml` and `packs/built-in/procedure.graph.yaml`.
Inline `tactic_refs` fields
were removed in Phase 1 excision (mission
`excise-doctrine-curation-and-inline-references-01KP54J6` WP02); the graph is
now the sole authority for cross-artifact relationships.

## Glossary Reference

See [Tactic](../../../docs/context/charter.md#tactic) in the charter glossary
context.
