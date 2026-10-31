# Implementation Plan: Glossary entry for the three "residue" senses

**Branch**: `issue-6759-glossary-residue` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/glossary-residue-three-senses-01M66977/spec.md` (issue #6759)

## Summary

Add a `### Residue` term entry to `docs/context/orchestration.md` that names the
three live senses of "residue" — a `kitty-specs/` child that is not a Mission —
each with its owning code symbol, its rule, and a "do NOT use when" guard:
write-seam residue (`is_kitty_specs_residue`), audit-engine residue
(`RESIDUE_DIRECTORY` / `not is_mission_dir`), and read-side / `doctor identity`
residue (`not is_selectable_mission_dir`). Link the entry from the three owning
docstrings, flag it in AGENTS.md's Terminology Canon (the sibling `primary` /
`merge` / `routing` footgun pattern), regenerate the committed Contextive YAML
for the `orchestration` context, and pin the whole contract with a red-first
structural test modeled on the Routing disambiguation test in
`tests/docs/test_artifact_placement_seam_page.py`. No runtime behavior changes.

## Technical Context

**Language/Version**: Python 3.11 (test); Markdown docs (primary change surface)
**Primary Dependencies**: none added or changed
**Storage**: N/A (markdown + generated Contextive YAML)
**Testing**: `pytest tests/docs/test_glossary_residue_entry.py` (new, unit
marker, structural assertions only — no prose pinning);
`python scripts/generate_contextive_glossaries.py check`; docs gates
(`docs_index --write`, `freshen_adr_inventory`, `check_docs_freshness --ci`,
`tests/architectural/test_no_legacy_terminology.py`); `ruff format --check` on
touched Python files.
**Target Platform**: repo docs + `src/` docstring comments
**Project Type**: single (repository docs)
**Performance Goals**: N/A
**Constraints**: docs mirror shipped behavior (code is the source of truth);
entry follows `docs/context/glossary-conventions.md` schema and
`styleguide:kitty-glossary-writing`; smallest viable diff (C-003)
**Scale/Scope**: 1 glossary entry, 3 docstring links, 1 canon bullet, 1
regenerated YAML, 1 test file (~100 lines), 1 changelog entry

## Charter Check

- Single canonical authority: the entry documents and links the owning code
  symbols; it does not create a second authority for any residue rule (C-001).
- Terminology canon: the change *is* terminology governance (AGENTS.md canon
  bullet + glossary entry).
- ATDD-first: the structural test is written first and is red on the planning
  base (the entry and links do not exist there).
- Smallest viable diff: no unrelated doc rewrites; no `src/` logic changes
  (docstring comments only).
- Docs gates: `check_docs_freshness --ci` errors=0 (the edited page keeps a
  fresh `updated:` date), `test_no_legacy_terminology.py` green.

## Project Structure

### Documentation (this mission)

```
kitty-specs/glossary-residue-three-senses-01M66977/
├── plan.md              # This file
├── research.md          # Grounding findings
├── spec.md              # Requirements
└── tasks/               # WP task files (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
docs/context/orchestration.md                     # + ### Residue entry (after "### The drain")
AGENTS.md                                          # + Terminology Canon residue bullet
docs/changelog/CHANGELOG.md                        # + [Unreleased] entry
src/specify_cli/context/mission_resolver.py        # docstring links (2 senses)
src/specify_cli/audit/models.py                    # docstring link (RESIDUE_DIRECTORY)
src/specify_cli/.contextive/orchestration.yml      # regenerated (generated file)
tests/docs/test_glossary_residue_entry.py          # new structural test (red-first)
```

**Structure Decision**: single-repository docs change; the disambiguation
cluster at the tail of `docs/context/orchestration.md` (`PRIMARY partition` →
`Routing` → `The drain`) gains `### Residue` as its next entry.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

Single concern; no IC decomposition needed for a one-WP docs mission.

### IC-01 — Residue disambiguation surface

- **Purpose**: One glossary entry + links + test that together make the three
  senses distinguishable from every reading position (glossary, code, dev
  guidelines).
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `docs/context/orchestration.md`, `AGENTS.md`,
  `src/specify_cli/context/mission_resolver.py`, `src/specify_cli/audit/models.py`,
  `src/specify_cli/.contextive/orchestration.yml`,
  `tests/docs/test_glossary_residue_entry.py`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none
- **Risks**: entry drift from code (mitigated: cite owning symbols and issue
  provenance, test pins sense names); Contextive regeneration staleness
  (mitigated: generator `check` mode must exit 0).

## Planning Interrogation (Engineering Alignment)

Operator brief fixes the scope and directs defaults (non-interactive run;
findings in `research.md`). Alignment: the mission is a Simple Feature (one doc
entry + links + test). Invariant: zero behavior change — only markdown,
docstring comments, generated glossary YAML, a test and a changelog entry
change. The three sense definitions are quoted from the live code on
`main`@512567ee, not reinvented. The test asserts structure (presence, sense
names, guards, links), never prose wording. Decisions from the spec flow
unchanged: entry home `docs/context/orchestration.md#residue`; docstring link
form ``docs/context/orchestration.md#residue`` (matches
`src/specify_cli/state/contract.py` precedent).
