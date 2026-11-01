# Tasks: Rename the 60 `index.md` section indexes to `README.md`

**Mission**: `rename-section-indexes-to-readme-01M6BVMP` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6939-rename-section-indexes-to-readme`
**Tracker**: closes #6939

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first ratchet: no `index.md` under `docs/` (fails on the planning base) | WP01 | |
| T002 | The 60-file rename, including the four existing-`README.md` collisions | WP01 | |
| T003 | Rewrite in-docs link targets through the rename map | WP01 | |
| T004 | Rewrite the 8 `toc.yml` `href`s | WP01 | |
| T005 | Rewrite frontmatter `related:` paths | WP01 | |
| T006 | `freshen_adr_inventory._INDEX_NAME` → `README.md`, era tables read/written there | WP02 | |
| T007 | `scripts/ci` regen surface + era-table docstrings | WP02 | |
| T008 | `scripts/docs` readers that name `index.md` | WP02 | |
| T009 | Docs suites whose live-tree floors/expectations are keyed on `index.md` | WP03 | |
| T010 | `[Unreleased]` changelog entry | WP03 | |
| T011 | Docs freshness + related-validator sweep, PR body input | WP03 | |

## Phase 1 — The rename

### WP01 — Rename and reconcile every reference

- **Prompt**: [tasks/WP01-rename-and-reconcile.md](tasks/WP01-rename-and-reconcile.md)
- **Goal**: No `index.md` remains under `docs/`; the 60 pages are `README.md` with their
  old content; the four collided directories keep one landing page each with no content
  lost; every in-docs link target, `toc.yml` `href` and frontmatter `related:` path that
  named a renamed page now names the new page (FR-001 … FR-005, NFR-001, NFR-002, C-001).
- **Priority**: P1 (MVP). **Dependencies**: none.
- **Independent test**: `find docs -name index.md` is empty; the resolution sweep in T003
  reports 0 dangling targets; `git diff -M --stat` shows 60 renames and no body change
  beyond link targets.

### WP02 — The tooling that owns the landing basename

- **Prompt**: [tasks/WP02-tooling-basename.md](tasks/WP02-tooling-basename.md)
- **Goal**: `freshen_adr_inventory` treats `README.md` as the era landing page and
  maintains the ADR era tables there; the regen classifier and the `scripts/docs`
  readers name `README.md` as the canonical landing basename without losing the
  ability to recognise the one they replaced (FR-006, FR-007, SC-004, C-003).
- **Priority**: P1. **Dependencies**: WP01 (runs against the renamed tree).
- **Independent test**: `freshen_adr_inventory --all --prune --check` over the renamed
  tree reports no diff and no missing file; the era-table regen classifier still
  classifies `docs/adr/<era>/README.md` as a generated surface.

### WP03 — Refresh the guards and record the change

- **Prompt**: [tasks/WP03-guards-and-changelog.md](tasks/WP03-guards-and-changelog.md)
- **Goal**: the docs suites that floor on `index.md` assert the new convention instead
  of being deleted (FR-009, SC-003); the `[Unreleased]` changelog entry names the
  user-facing change (SC-006); the freshness and related-path sweeps are green and every
  red attributable to the unlanded doc-kitty chain is written down for the PR body
  (FR-008 ratchet already added by WP01, C-002, C-004).
- **Priority**: P2. **Dependencies**: WP01, WP02.
- **Independent test**: `uv run pytest tests/docs tests/ci/test_regen_docs_index.py
  tests/ci/test_check_generated_docs_untouched.py -q` green;
  `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`.

## Requirement coverage

| Requirement | Work package |
|---|---|
| FR-001, FR-002, FR-003, FR-004, FR-005 | WP01 |
| FR-006, FR-007 | WP02 |
| FR-008, FR-009 | WP01 (ratchet), WP03 (existing suites) |
| NFR-001, NFR-002, C-001 | WP01 |
| NFR-003 | WP01, WP02, WP03 (the generated index/inventory are never staged) |
| C-002, C-003, C-004 | WP02 (C-003), WP03 (C-002, C-004) |
| SC-001, SC-002 | WP01 |
| SC-003 | WP03 |
| SC-004 | WP02 |
| SC-005 | WP03 |
| SC-006 | WP03 |

## Deferred to the doc-kitty chain (reported, not fixed here)

- `site/moves.yaml` (#6927) does not exist, so links are rewritten through the mission's
  own rename map instead of the moves ledger.
- DocFX is still the live deployer, so `dir/index.html` is not yet the renamed pages'
  output URL; the docs-pages deploy stays a post-merge concern the PR cannot exercise.
- The docs-structural-lint asset and its Spec Kitty config live in the external pack:
  its `curated_complete_sections` index and `**/README.md` frontmatter exclusion now see
  the renamed pages differently. Reported in the PR, never patched here (C-003).
