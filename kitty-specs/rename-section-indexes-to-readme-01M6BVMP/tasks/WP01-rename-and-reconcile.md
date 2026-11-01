---
work_package_id: WP01
title: Rename and reconcile every reference
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- SC-001
- SC-002
planning_base_branch: issue-6939-rename-section-indexes-to-readme
merge_target_branch: issue-6939-rename-section-indexes-to-readme
branch_strategy: Planning artifacts for this mission were generated on issue-6939-rename-section-indexes-to-readme. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6939-rename-section-indexes-to-readme unless the human explicitly redirects the landing branch.
created_at: '2026-11-01T15:40:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - The rename
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- tests/docs/test_section_index_basename.py
execution_mode: code_change
model: ''
owned_files:
- docs/
- tests/docs/test_section_index_basename.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6939'
---

# Work Package Prompt: WP01 – Rename and reconcile every reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (`python-pedro`, role `implementer`) and behave according to its guidance.

## Objective

Issue #6939. Rename all 60 `docs/**/index.md` to `README.md` and reconcile every
in-repo reference that names a renamed file. Prop: ADR `2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`
D-1 (the site landing basename is `README`), D-7 (in an immutable page, rewriting a link
target is the one allowed body change).

**Grounding (2026-11-01, `origin/main` `287a226cfe`):** 60 `index.md` under `docs/`;
8 `toc.yml` files with 46 `index.md` hrefs; 194 Markdown files with 542 `index.md` link
occurrences; 128 files with 183 frontmatter `related:` paths ending in `index.md`.
Four target directories already hold a `README.md`: `docs/adr/{1.x,2.x,3.x}` (redirect
stubs pointing at the sibling `index.md`) and `docs/architecture` (a second landing
page carrying the boundary rule, while `index.md` carries the page enumeration).

## T001 — Red-first: the ratchet

Write `tests/docs/test_section_index_basename.py`:

```python
def test_no_index_md_remains_under_docs() -> None: ...
def test_the_guard_catches_a_reintroduced_index_md(tmp_path) -> None: ...   # positive control
```

The live-tree assertion walks `docs/` and fails listing every `index.md` it finds; the
positive control builds a synthetic tree containing an `index.md` and asserts the guard
function reports it (so the guard cannot pass vacuously). Expose the walk as a helper so
the control calls the same code the live assertion does.

Run it on the unmodified tree, quote the 60-path failure in your completion note, and
commit the test alone (`test(6939): no index.md under docs (red)`).

## T002 — The 60 renames

`git mv` each `docs/**/index.md` to `README.md`, except the four collisions:

| Directory | Action |
|---|---|
| `docs/adr/1.x`, `docs/adr/2.x`, `docs/adr/3.x` | `git rm` the redirect-stub `README.md`, `git mv index.md README.md` |
| `docs/architecture` | merge: the merged `README.md` keeps the boundary rule, layout, ADR-location, C4 and creation sections from the old `README.md` **and** the page-enumeration sections from `index.md`; drop the now-self-referential cross-links between the two; `git rm` `index.md` |

Keep each page's frontmatter; where two pages merged, keep the surviving page's
frontmatter and fold in any `related:`/`description` content that would otherwise be
lost. No prose rewrite beyond that (C-001): no reflow, no reordering, no typo fixes.

## T003 — In-docs link targets

Rewrite every Markdown link/image target that resolves (relative to its own file) to one
of the 60 old paths, to the same target under the new name, preserving the original
relative style (`../adr/index.md` → `../adr/README.md`, `index.md` → `README.md`).
Do **not** string-replace `index.md` inside prose, fenced code blocks, or an ADR's
rationale: only link targets. Then verify with a sweep that every rewritten target
exists on disk and print the count of occurrences changed.

## T004 — `toc.yml` hrefs

All 8 `toc.yml` files (`docs/toc.yml` 19, `docs/guides/toc.yml` 11,
`docs/api/toc.yml` 5, `docs/development/toc.yml` 5, `docs/operations/toc.yml` 2,
`docs/changelog/{,1x,2x}/toc.yml` 1 each): rewrite `href`s that resolve to a renamed
page, same relative style.

## T005 — Frontmatter `related:` paths

Every `related:` list entry is repo-relative (`docs/...`). Rewrite each entry that names
one of the 60 old paths to its new path (183 entries in 128 files).

## Definition of Done

- [ ] `find docs -name index.md` prints nothing; the ratchet test is green and its
      positive control fails if the walk stops reporting.
- [ ] `git diff -M --stat` shows 60 renames (3 with stub deletion, 1 merged).
- [ ] The link sweep reports 0 dangling targets, and the number of rewritten targets is
      recorded in the completion note.
- [ ] No prose, code-block or rationale text was changed (C-001).
- [ ] `docs/development/docs-retrieval-index.yaml` and
      `docs/development/page-inventory.yaml` are **not** in the diff (NFR-003).

## Reviewer guidance

Check: (1) the four collisions — is any unique section or link lost? (2) are the link
rewrites resolution-based rather than a global substitution (grep the diff for a
`docs/index.md` in prose that should have survived)? (3) do any `related:` paths still
point at a `README.md` that does not exist? (4) was a generated surface touched?
