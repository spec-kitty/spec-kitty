---
description: "Work packages for the README rename and docs audit"
---

# Work Packages: Rename section indexes to README.md; docs staleness inventory and retired-surface gate

**Inputs**: `kitty-specs/readme-rename-and-docs-audit-01M78WZM/` (spec.md, plan.md)

**Organization**: subtasks (`Txxx`) roll up into two work packages. WP02 depends on WP01: the inventory is built on the final paths.

## Subtask Format: `[Txxx] [P?] Description`

---

## Work Package WP01: Rename the section indexes to README.md (Priority: P1)

**Goal**: every `docs/**/index.md` is `README.md`, the moves ledger records each rename, every link and reader follows, `indexBasename` is `README`, and every legacy URL still resolves (#6939).
**Independent Test**: `tests/docs/test_section_index_basename.py` green (red on the base), `site_redirects --check` clean with an unchanged map, `dockitty-check-links --strict` clean.
**Prompt**: `/tasks/WP01-rename-section-indexes.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-015, NFR-003, NFR-004, NFR-005, C-001, C-002, C-005

### Included Subtasks

T001 Red-first tests: the basename ratchet with its planted control (reused from #7040), the ledger return rule, the index-rename predicate, the narrowed basename
T002 `git mv` the 59 `docs/**/index.md` to `README.md`
T003 Append the 59 `#6939` moves to `site/moves.yaml`; `moves_ledger.collapse` reads a return as superseding the earlier move away; `is_index_rename` for the baseline test and `rename_reconcile`
T004 Narrow `INDEX_BASENAMES` to `('README',)`, regenerate `site/dockitty-contract.json`; `site_redirects` legacy fold and rule 3; prove the redirect map unchanged
T005 Rewrite links from the ledger's `#6939` pairs (link targets only in immutable pages); verify immutable diffs
T006 Update every reader: `freshen_adr_inventory.py` (reused basename switch), `regen_docs_index.py`, `generated_docs_surfaces.py`, `check_generated_docs_untouched.py` (era rows keyed by era folder), `touched_set_gates.py`, `site_built_check.py`, `dockitty_frontmatter_migration.py`, the docs-index workflow comment, templates, and the tests that read real index paths
T007 ADR amendment `## Amendment 2026-11-12 (section indexes renamed)`

### Dependencies

- None.

### Risks & Mitigations

- Return moves read as cycles: the collapse rule and its test.
- Immutable prose rewritten: link-target-only rule plus the diff verifier.

---

## Work Package WP02: Staleness inventory and retired-surface gate (Priority: P1)

**Goal**: one command generates the inventory of every published living page; one retired-surface authority; a gate in `docs-lint` that fails on a new retired-surface mention, with a shrink-only burn-down tied to #7522–#7528; per-section page lists (#7520).
**Independent Test**: the gate is green on the tree and red on a planted mention and on a stale entry; the inventory regenerates byte for byte; the size ratchet holds.
**Prompt**: `/tasks/WP02-audit-inventory-and-gate.md`
**Requirement Refs**: FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, NFR-001, NFR-002, NFR-004, NFR-005, C-003, C-004

### Included Subtasks

T008 Red-first tests for the gate (planted mention, stale entry, live identifiers not hit) and the inventory (frontmatter-only commit ignored, missing path and command, reader, diagram, Divio)
T009 Move the retired code paths and CLI prefixes to `scripts/retired_surfaces.py`, add the documentation-level retirements; the arch gate imports them
T010 `scripts/docs/staleness_audit.py`: the inventory and the per-section page lists
T011 `scripts/docs/retired_surface_gate.py` and `scripts/docs/retired_surface_burndown.yaml`; the size ratchet in `_baselines.yaml`; the gate's findings in `check_docs_freshness.py`
T012 Wire the gate into `docs-lint` in `ci-router.yml`; update the job pins and the scrub record
T013 Generate the inventory snapshot and page lists into the Mission's `audit/`; changelog fragment

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- False hits on live identifiers: boundary rules and negative tests.
- Git-history cost of the inventory: one `git log` walk per page, run on demand, never in the gate.
