# Tasks: Glossary entry for the three "residue" senses

**Mission**: `glossary-residue-three-senses-01M66977` · **Issue**: #6759 · **Topology**: `single_branch`
**Planning/base branch**: `issue-6759-glossary-residue` · **Merge target**: `issue-6759-glossary-residue`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first structural test `tests/docs/test_glossary_residue_entry.py` (entry presence, three sense names, guards, three docstring links, canon bullet) | WP01 | |
| T002 | `### Residue` entry in `docs/context/orchestration.md` after `### The drain`, per the glossary-conventions schema and `styleguide:kitty-glossary-writing` | WP01 | |
| T003 | Docstring links: `is_kitty_specs_residue` and `is_selectable_mission_dir` (`src/specify_cli/context/mission_resolver.py`), `RESIDUE_DIRECTORY` (`src/specify_cli/audit/models.py`) | WP01 | |
| T004 | AGENTS.md Terminology Canon bullet for the residue footgun, linking the entry | WP01 | |
| T005 | Regenerate `src/specify_cli/.contextive/orchestration.yml`; run the docs gates (`docs_index --write` if needed, `freshen_adr_inventory`, `check_docs_freshness --ci`, `test_no_legacy_terminology.py`) | WP01 | |
| T006 | `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` | WP01 | [P] |

## WP01 — Residue glossary entry, docstring links and structural test (P1)

**Goal**: one `docs/context/` entry names the three live "residue" senses with "do NOT use when" guards, linked from the three owning docstrings and flagged in the Terminology Canon, pinned by a red-first structural test (FR-001–FR-004, NFR-001, NFR-002, C-001–C-003, SC-001–SC-004).
**Independent test**: `pytest tests/docs/test_glossary_residue_entry.py` is red on the planning base and green after the change; `scripts/generate_contextive_glossaries.py check` exits 0.
**Prompt**: [tasks/WP01-glossary-entry.md](tasks/WP01-glossary-entry.md)

T001 Red-first structural test (WP01)
T002 `### Residue` entry in `docs/context/orchestration.md` (WP01)
T003 Three docstring links (WP01)
T004 AGENTS.md Terminology Canon bullet (WP01)
T005 Contextive regeneration + docs gates (WP01)
T006 Changelog entry (WP01)

**Dependencies**: none. **Risks**: prose drift from the code rules (mitigated: definitions quoted from the live docstrings; the test pins sense names, not wording); Contextive staleness (mitigated: generator `check` mode).
