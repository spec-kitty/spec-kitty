# Contracts — glossary-residue-three-senses-01M66977

This is a docs-only mission (issue #6759): it introduces no executable
behavior and defines no new external contract.

The contract surface it touches already exists and is only *cited*, not
changed:

- **Deliverable anchor**: `docs/context/orchestration.md#residue` — the
  disambiguation entry for the three "residue" senses (write-seam
  `is_kitty_specs_residue`, audit-engine `RESIDUE_DIRECTORY`, read-side
  `not is_selectable_mission_dir`). Backed by the structural test
  `tests/docs/test_glossary_residue_entry.py`, which pins the anchor, the
  sense names, the owning symbols, the "Do NOT use when" guards and the
  docstring links.
- **Generated projection**: `src/specify_cli/.contextive/orchestration.yml`
  regenerates from the entry (FR-004); `generate_contextive_glossaries.py
  check` gates it.
- **No runtime seam changes**: the diff touches only markdown, docstring
  comments, generated YAML, one test file and the changelog (NFR-002).
