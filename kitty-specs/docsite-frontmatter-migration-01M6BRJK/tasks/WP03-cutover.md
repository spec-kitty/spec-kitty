---
work_package_id: WP03
title: 'Cutover: related reader, corpus shape, apply'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-007
- FR-009
- NFR-002
- C-001
- C-003
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6929-docsite-frontmatter-migration
merge_target_branch: issue-6929-docsite-frontmatter-migration
branch_strategy: Planning artifacts for this mission were generated on issue-6929-docsite-frontmatter-migration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6929-docsite-frontmatter-migration unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - Cutover
history:
- at: '2026-11-01T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- tests/docs/test_dockitty_frontmatter_shape.py
execution_mode: code_change
owned_files:
- docs/**/*.md
- scripts/docs/related_validator.py
- tests/docs/test_related_validator.py
- tests/docs/test_rulers_blocking.py
- tests/docs/test_dockitty_frontmatter_shape.py
- tests/glossary/test_canonical_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Cutover: related reader, corpus shape, apply

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- A corpus-shape test over `docs/` (FR-009) is red on the unmigrated tree and green after.
- `related_validator.py` reads slugs (string or `{ref, note}`), resolves them with `_dockitty_contract.page_for_slug`, and reports a published page's entry naming an unpublished page (FR-007).
- The migration is applied to `docs/` (FR-002, FR-005, FR-006, FR-008); the diff is frontmatter-only (NFR-001); the generated surfaces and #6927/#6928 files are untouched (C-003).

## Context & Constraints

- `tests/glossary/test_canonical_promotion.py::test_wp02_owned_referrers_have_zero_dangling_related_edges` runs `validate_related` over the real tree — the reader port and the corpus migration land together here so no commit is red.
- Do **not** regenerate `docs/development/docs-retrieval-index.yaml` or `page-inventory.yaml` (the bot does that after merge; `check_generated_docs_untouched.py` refuses a PR that edits them).

## Branch Strategy

- **Strategy**: `single_branch` on `issue-6929-docsite-frontmatter-migration`.
- Implement with `spec-kitty agent action implement WP03 --agent claude --mission docsite-frontmatter-migration-01M6BRJK`.

## Subtasks

### T011 — Corpus-shape test (commit first, red)
`tests/docs/test_dockitty_frontmatter_shape.py`, over `iter_docs_pages(docs/)` minus the skip set the migration uses:
- no `audience` that is a string or contains a string;
- every `audience` entry has non-empty `profile` and `guidance_text`;
- every `related` entry is a slug (no `/` prefix, no `.md`, no `docs/`) that `page_for_slug` resolves to a **published** page — for published source pages; for unpublished source pages, resolves to any page;
- every `external_references` entry has `url` and `title`;
- every dated ADR has `kind: ADR` and `doc_status` equal to the mapping of its `status`.
Each check names offending files; floor: ≥ 300 audience pages, ≥ 200 ADRs, ≥ 300 related pages examined.
Also a negative control per rule on a `tmp_path` fixture (one old-shape page → named offender).

### T012 — Port `related_validator.py`
- Rewrite fixtures first (T013), then port: an edge dangles when `page_for_slug` finds nothing; add `unpublished_edges` (published source → excluded/draft target) as a separate report list; `--strict` fails on either. Keep `checked_count`, the floor and `--changed-from`.
- `DanglingEdge.to_path` carries the slug as written.

### T013 — Fixtures
- `tests/docs/test_related_validator.py`, `tests/docs/test_rulers_blocking.py` (the R2 cases): slug form.
- `tests/glossary/test_canonical_promotion.py`: the historical-glossary-path comparison uses the slug (`_OLD_GLOSSARY_PATH` without `.md`), so the assertion keeps its meaning.

### T014 — Apply
`python -m scripts.docs.dockitty_frontmatter_migration --apply --json` → save the report (counts, dropped refs) for the PR. Then `--check` must report zero changes.

### T015 — Verify
- `python -m scripts.docs.dockitty_frontmatter_migration --verify-against origin/main` → exit 0.
- `python -m scripts.docs.audience_resolver --strict` and `python -m scripts.docs.related_validator --strict` → 0 dangling.
- `git diff --name-only origin/main -- docs | python scripts/ci/check_generated_docs_untouched.py`-equivalent: confirm no generated surface is in the diff.
- `pytest tests/docs/ tests/specify_cli/docs/ tests/glossary/test_canonical_promotion.py`.

## Definition of Done

- Shape test red-first then green; all listed tests green; verify-against clean; counts recorded in a WP history note.

## Reviewer guidance

- Sample 10 migrated files across classes by eye (audience, ADR, related with external refs, an archive page).
- Confirm `docs/adr/*/README.md`, `docs/architecture/README.md`, era `index.md` files and the generated YAML files are unchanged.
