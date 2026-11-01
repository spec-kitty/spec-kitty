# Implementation Plan: Rename the 60 `index.md` section indexes to `README.md`

**Branch**: `issue-6939-rename-section-indexes-to-readme` | **Date**: 2026-11-01
**Spec**: `kitty-specs/rename-section-indexes-to-readme-01M6BVMP/spec.md`
**Issue**: #6939 (part of #6100; ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-1, D-7; plan step S-13)

## Summary

Rename every `docs/**/index.md` (60 files) to `README.md`, reconcile the four
directories that already hold a `README.md`, and rewrite every in-repo *reference*
that names a renamed file: in-docs relative link targets, the 8 `toc.yml` files,
frontmatter `related:` paths, and the tooling whose constants or docstrings treat
`index.md` as the section landing basename (`scripts/docs/freshen_adr_inventory.py`,
`scripts/ci/regen_docs_index.py`, `scripts/ci/generated_docs_surfaces.py`, the
`scripts/docs` readers). Add a ratchet test that no `index.md` can reappear under
`docs/`, and update the docs suites whose live-tree floors are keyed on `index.md`.

## Technical Context

**Language/Version**: Python 3.11/3.12 (repo toolchain), YAML for `toc.yml`/frontmatter
**Primary Dependencies**: standard library only for the rewrite; existing
`scripts/docs` + `scripts/ci` modules; pytest for the gates
**Storage**: the `docs/` tree (Markdown + YAML), no database
**Testing**: `tests/docs`, `tests/ci/test_regen_docs_index.py`,
`tests/ci/test_check_generated_docs_untouched.py`, `tests/contract/test_terminology_guards.py`,
plus `scripts.docs.check_docs_freshness --ci`
**Target Platform**: repository content, rendered by DocFX today / doc-kitty after the chain lands
**Project Type**: single repository, documentation corpus + docs tooling
**Performance Goals**: n/a (one-off content change; the rewrite script is seconds-class)
**Constraints**: no gate weakened or skipped; generated surfaces not edited by the PR;
only link *targets* change inside immutable/historical pages (ADR D-7)
**Scale/Scope**: 60 renames, 8 `toc.yml` files, 194 Markdown files with 542 link
occurrences, 128 files with 183 `related:` paths, 2 tooling modules + 1 CI module,
~10 test modules

## Charter Check

- **Single canonical authority**: the rename map (60 pairs) is the only source for the
  rewrite; the script resolves each link against its own file's directory, never by a
  global string substitution.
- **Locality of change / smallest viable diff**: bodies change only where a link
  target must; no prose rewriting, no reformatting, no reordering.
- **ATDD-first**: the invariant test (`no index.md under docs/`) is written first and
  shown red against `main` with a fixture that adds an `index.md`, then kept as a
  ratchet; the docs suites that floor on `index.md` are updated, not deleted.
- **Generated-surface boundary**: `docs/development/docs-retrieval-index.yaml` and
  `docs/development/page-inventory.yaml` stay untouched
  (`scripts/ci/check_generated_docs_untouched.py`); the ADR era table rows move with
  their file and are otherwise not hand-edited.
- **No fake green**: where a gate cannot pass because the doc-kitty chain is unlanded,
  the PR body names it; nothing is xfailed, skipped or disabled.

## Project Structure

### Documentation (this mission)

```
kitty-specs/rename-section-indexes-to-readme-01M6BVMP/
├── plan.md          # this file
├── spec.md          # mission spec
├── tasks.md         # work packages
└── traces/          # running logs (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
docs/
├── index.md → README.md                      # root landing page
├── toc.yml                                   # 19 hrefs
├── adr/{index.md → README.md, <era>/index.md → README.md}
├── architecture/{index.md merged into README.md}
├── context/, api/, guides/, development/, plans/, ...  # 56 rename-only sections
scripts/
├── docs/freshen_adr_inventory.py             # _INDEX_NAME / _README_NAME
├── docs/{docs_index,inventory_lockfile,capture_baseline_urls,touched_set_gates}.py
├── ci/{regen_docs_index,generated_docs_surfaces,check_generated_docs_untouched}.py
└── ci/regen_docs_index.py                    # era-table docstring + classifier consumption
tests/
├── docs/{test_docs_structural_lint,test_rulers_blocking,test_publish_manifest_coherence,...}.py
└── ci/{test_regen_docs_index,test_check_generated_docs_untouched}.py
```

**Structure Decision**: single project. The change is content plus the docs tooling
that names the content; it introduces no new module, package or surface.

## Implementation Concern Map

### IC-01 — The rename map and the mechanical rewrite

- **Purpose**: Produce the 60-pair rename map and rewrite every in-docs reference that
  resolves to a renamed file, deterministically and without touching prose.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001
- **Affected surfaces**: `docs/**` (60 renames, ~194 Markdown files, 8 `toc.yml`)
- **Sequencing/depends-on**: none
- **Risks**: the 4 collisions must merge rather than overwrite; link rewriting must
  resolve relative paths per file (not string-substitute), and must not touch fenced
  code, prose or immutable rationale.

### IC-02 — The tooling that owns the landing basename

- **Purpose**: Make the docs tooling and CI modules name `README.md` as the section
  landing page so nothing re-creates `index.md` and nothing silently maintains the
  wrong file.
- **Relevant requirements**: FR-006, FR-007, SC-004
- **Affected surfaces**: `scripts/docs/freshen_adr_inventory.py`,
  `scripts/ci/regen_docs_index.py`, `scripts/ci/generated_docs_surfaces.py`
  (already dual-aware), `scripts/docs/*` docstrings/readers
- **Sequencing/depends-on**: IC-01 (the renamed tree is what the tooling is tested against)
- **Risks**: the generated-surface geometry (`ERA_INDEX_RE`) already accepts both
  basenames; narrowing it wrongly would make the bot stop recognising the era pages.
  Its dual-awareness is kept, with `README.md` made canonical.

### IC-03 — The guards

- **Purpose**: Add a ratchet that no `index.md` reappears under `docs/`, and update the
  docs suites whose live-tree assertions are keyed on `index.md` (floors, curated-index
  fixtures, publish-manifest expectations) so the gate is refreshed, not weakened.
- **Relevant requirements**: FR-008, FR-009, SC-003
- **Affected surfaces**: `tests/docs/**`, new `tests/docs/test_section_index_basename.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the docs-structural-lint asset and its Spec Kitty config live in the
  external pack; its `curated_complete_sections` and `frontmatter_in_scope_exclusions`
  assumptions about `index.md`/`README.md` cannot be changed here and are reported, not
  patched.

## Complexity Tracking

No charter violation. The mission touches one concern (a docs naming convention) across
three surfaces (content, tooling, tests); no new abstraction, dependency or gate is
introduced.
