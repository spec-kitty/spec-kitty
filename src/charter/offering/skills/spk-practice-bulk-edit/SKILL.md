---
name: spk-practice-bulk-edit
description: >-
  Recognize bulk-edit missions and drive the occurrence-classification
  guardrail on the user's behalf before modifying many matching instances.
  Triggers: user says any variant of "rename X to Y", "change the
  terminology", "migrate all occurrences", "replace across the codebase",
  "the X feature is now the Y feature", "sed everywhere", or any request
  that touches the same identifier/path/key in many files. Also triggers on
  gate errors mentioning "change_mode", "occurrence_map.yaml",
  "Bulk Edit Gate: BLOCKED", or "Bulk Edit Review: Diff Compliance".
  Does NOT handle: line-level semantic refactors inside one file, adding a new
  feature that creates new identifiers without changing existing ones, or
  reviewing finished missions for fidelity.
---

# spk-practice-bulk-edit

Use this skill when the user asks for a broad rename, replace, migration,
classification, or other multi-occurrence edit. The same token carries
different meaning depending on where it appears, so treating every occurrence
the same is how silent breakage happens (DIRECTIVE_035).

The user will not say "bulk edit". Recognize the shape, set
`change_mode: bulk_edit` in the mission's `meta.json`, and drive the
classification workflow before any code changes.

## Flow

1. Perform a manual pre-edit occurrence review before changing matches.
2. Align `kitty-specs/<mission>/occurrence_map.yaml` to the eight standard
   schema categories plus explicit exceptions and moves.
3. Treat runtime enforcement as a path-based review gate, not an AST-semantic
   classifier.
4. Confirm edit policy when the blast radius is unclear.
5. Execute the narrowest safe change and verify representative cases.
6. When the gate blocks at implement or review time, fix the occurrence map
   or the diff, never bypass the gate.

## References

- `references/bulk-edit-workflow.md` -- When to activate, the decision tree,
  what to do during specify and plan, valid actions and default postures,
  multi-path moves, and how to clear gate blocks.
- `docs/api/bulk-edit-gate.md` -- The `occurrence_map.yaml` schema and action
  vocabulary.
- `spk-charter-glossary` -- The canonical terms a migration moves to.
