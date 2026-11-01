---
work_package_id: WP02
title: The tooling that owns the landing basename
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- NFR-003
- C-003
- SC-004
planning_base_branch: issue-6939-rename-section-indexes-to-readme
merge_target_branch: issue-6939-rename-section-indexes-to-readme
branch_strategy: Planning artifacts for this mission were generated on issue-6939-rename-section-indexes-to-readme. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6939-rename-section-indexes-to-readme unless the human explicitly redirects the landing branch.
created_at: '2026-11-01T15:40:00+00:00'
subtasks:
- T006
- T007
- T008
phase: Phase 1 - The rename
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/freshen_adr_inventory.py
- scripts/docs/docs_index.py
- scripts/docs/inventory_lockfile.py
- scripts/docs/capture_baseline_urls.py
- scripts/docs/touched_set_gates.py
- scripts/ci/regen_docs_index.py
- scripts/ci/generated_docs_surfaces.py
- scripts/ci/check_generated_docs_untouched.py
- tests/ci/test_regen_docs_index.py
- tests/docs/test_freshen_adr_inventory.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6939'
---

# Work Package Prompt: WP02 – The tooling that owns the landing basename

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (implementer) as WP01.

## Objective

After WP01 no `index.md` exists under `docs/`, but two pieces of tooling still treat it
as the section landing page. Fix them so nothing re-creates the old name and nothing
silently maintains nothing.

## T006 — `freshen_adr_inventory` makes `README.md` canonical

`scripts/docs/freshen_adr_inventory.py` currently holds
`_INDEX_NAME = "index.md"` / `_README_NAME = "README.md"`, and both
`_canonical_index_target` and `_table_era_indexes` prefer `index.md` then fall back to
`README.md`. On the renamed tree the fallback masks the problem; the next change would
re-create `index.md`.

Make `README.md` the canonical landing basename: the era table is read from and written
to `docs/adr/<era>/README.md`, `indexed_era_adrs` excludes both basenames, and the
module docstring/comments say `README.md`. Keep behaviour for a tree that still holds a
legacy `index.md` only as far as the tests require; do not add a new compatibility
branch (ADR `2026-07-01-1`). If a legacy `index.md` and a `README.md` both exist, say
which wins and why in a one-line comment.

## T007 — The CI regen surface

- `scripts/ci/generated_docs_surfaces.py`: `ERA_INDEX_RE` already matches
  `docs/adr/<era>/(index|README).md`. Keep that dual awareness (the bot must still
  recognise an era page that predates the rename) and update the comment to name
  `README.md` as canonical.
- `scripts/ci/regen_docs_index.py`: the module docstring and the `GENERATED`/era wording
  name `docs/adr/<era>/index.md`; make it `README.md`.
- `scripts/ci/check_generated_docs_untouched.py`: same docstring wording.

## T008 — The `scripts/docs` readers

`grep -rn 'index\.md' scripts/docs scripts/ci` after T006–T007 must leave only (a)
legacy-recognition regexes with a comment saying why, and (b) prose that names a
historical path inside an immutable document. Update
`scripts/docs/touched_set_gates.py` (`_NAV_BASENAMES` already carries both — decide
whether `index.md` should stay recognised as a legacy nav basename and record the
reason), `scripts/docs/capture_baseline_urls.py` and `scripts/docs/docs_index.py` /
`inventory_lockfile.py` if they name the basename.

## Definition of Done

- [ ] `uv run python -m scripts.docs.freshen_adr_inventory --all --prune` (or its check
      mode) over the renamed tree reports no diff and no missing ADR row.
- [ ] `uv run pytest tests/docs/test_freshen_adr_inventory.py tests/ci/test_regen_docs_index.py
      tests/ci/test_check_generated_docs_untouched.py -q` is green.
- [ ] No generated surface is edited (NFR-003).
- [ ] Nothing under `packs/` is edited: the lint asset and its Spec Kitty config live in
      the external pack (C-003). Its `index.md` assumptions are reported in the PR body,
      not patched.

## Reviewer guidance

Check: (1) does the freshener still find all four eras' tables after the rename, and does
it write to the file it read? (2) is the regen classifier still able to recognise a
legacy era page (the bot runs on `main` where a stale page may predate the rename)?
(3) is a compatibility branch invented that ADR `2026-07-01-1` forbids?
