---
work_package_id: WP03
title: Refresh the guards and record the change
dependencies:
- WP01
- WP02
requirement_refs:
- FR-009
- C-002
- C-004
- SC-003
- SC-005
- SC-006
planning_base_branch: issue-6939-rename-section-indexes-to-readme
merge_target_branch: issue-6939-rename-section-indexes-to-readme
branch_strategy: Planning artifacts for this mission were generated on issue-6939-rename-section-indexes-to-readme. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6939-rename-section-indexes-to-readme unless the human explicitly redirects the landing branch.
created_at: '2026-11-01T15:40:00+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Guards and record
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/docs/
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6939'
---

# Work Package Prompt: WP03 – Refresh the guards and record the change

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (implementer) as WP01.

## Objective

The docs suites contain live-tree assertions keyed on `index.md`. Refresh them to the
new convention — never delete or weaken them — and record the user-facing change.

## T009 — The docs suites

Start from the failing set after WP01/WP02 (`uv run pytest tests/docs -q`) and fix each:

- `tests/docs/test_docs_structural_lint.py`: the live-tree non-vacuity floors
  (`index_count >= 40`) and the `shadow_tree` assertions must key on the basename the
  tree now carries. Keep a floor that is still non-vacuous and keep the
  `README.md`-not-flagged assertion; the point of the floor is to prove the cohort is
  not empty, so set it below today's actual count and say so in the comment.
- Any suite that expects a published page set, a publish manifest, a versioned-docs
  entry, a relayed/`related:` path or a redirect-stub target for an `index.md` page.
- `tests/docs/test_rulers_blocking.py`, `test_publish_manifest_coherence.py`,
  `test_versioned_docs_integrity.py`, `test_published_pages.py`, `test_capture_baseline_urls.py`,
  `test_docs_index_regenerates_cleanly.py`, `test_relative_link_fixer.py`: fix fixtures
  that now point at a renamed path, and leave fixture-only `index.md` names alone where
  they test the tool's generality.

Never xfail, skip or delete a live-tree assertion to get green: if an assertion cannot
hold under the new convention, restate it for the new convention.

## T010 — Changelog

`docs/changelog/CHANGELOG.md`, under `[Unreleased]`: bold impact-first lead with
`(#6939)`, then before/after, under 1,200 characters. `python -m
scripts.docs.check_changelog_style` must pass.

## T011 — Sweeps and the honest red list

Run and record:

```bash
uv run pytest tests/docs -q
uv run pytest tests/ci/test_regen_docs_index.py tests/ci/test_check_generated_docs_untouched.py -q
uv run python -m scripts.docs.check_docs_freshness --ci
uv run python -m scripts.docs.check_spelling
uv run python -m scripts.docs.check_changelog_style
uv run python -m scripts.ci.check_generated_docs_untouched
```

For anything red, classify it: caused by this diff (fix it) or caused by the unlanded
doc-kitty chain / pre-existing on `main` (reproduce on pristine `origin/main` in a
scratch worktree, cite or file an issue, and write it into the PR `## Deferred` section).
No red may be hidden (C-002).

## Definition of Done

- [ ] `tests/docs` green, with every refreshed assertion still non-vacuous.
- [ ] Freshness `errors=0`, spelling and changelog-style clean, generated-surface guard
      clean (nothing regenerated in the PR).
- [ ] The changelog entry exists and is under the style limit.
- [ ] Every remaining red is written down with its cause and its unblocking issue.

## Reviewer guidance

Check: (1) was any assertion deleted rather than restated? (2) are the new floors still
meaningful (a floor of 0 is not)? (3) does the changelog claim anything the diff does not
do — e.g. that `dir/index.html` is already live?
