---
work_package_id: WP03
title: Port the in-repo Divio readers to kind
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- SC-005
planning_base_branch: issue-6931-frontmatter-contract
merge_target_branch: issue-6931-frontmatter-contract
branch_strategy: Planning artifacts for this mission were generated on issue-6931-frontmatter-contract. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6931-frontmatter-contract unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 3 - Readers
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Authored via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/inventory_lockfile.py
- scripts/docs/docs_index.py
- scripts/docs/frontmatter_backfill.py
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Port the in-repo Divio readers to `kind`

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objective

The Divio axis is currently read from the frontmatter `type` key. WP04 removes the
Divio `type` (it names the *section* in doc-kitty's vocabulary, ADR-0009), so every
reader must move to `kind` **in the same change** — otherwise the retrieval index
and the page inventory silently degrade to `none` for 198 pages.

Port exactly these, and nothing else:

1. `scripts/docs/inventory_lockfile.py` — `entry_for_page` derives `divio_type`
   from `kind` via a total `KIND → DivioType` map (`Tutorial`, `How-To`,
   `Reference`, `Explanation` map to their Divio values; every other kind → `none`).
   Keep `DivioType` as the axis enum: it is the *reading* of the page, which is what
   `kind` carries.
2. `scripts/docs/docs_index.py` — the same substitution where it resolves the Divio
   axis for `docs/development/docs-retrieval-index.yaml`.
3. `scripts/docs/frontmatter_backfill.py` — its writer currently emits `type` from
   `divio_type`; it must emit `kind` instead, or a future backfill run would
   re-introduce the Divio `type` and put the corpus back into violation.

The map itself belongs in `scripts/docs/frontmatter_contract.py` so there is one
copy (import it down; do not retype it in three places).

## Definition of done

- `uv run python -m scripts.docs.inventory_lockfile --check` (or the repo's
  equivalent generate-and-compare) reports no drift; regenerate the lockfile only if
  it genuinely changes, and say so in the PR if it does.
- `uv run python -m scripts.docs.docs_index` regeneration produces no drift for
  `docs/development/docs-retrieval-index.yaml`.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.
- `spec-kitty docs query` answers (SC-005): cite the exact command and output in the
  PR's "Tests run".
- `uv run pytest tests/docs -q` still passes for the three touched modules.
