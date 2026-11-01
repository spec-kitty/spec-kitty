---
work_package_id: WP03
title: Document the saving and the remaining wins
dependencies:
- WP02
requirement_refs:
- FR-007
planning_base_branch: issue-7001-universe-prestep-scope
merge_target_branch: issue-7001-universe-prestep-scope
branch_strategy: Planning artifacts for this mission were generated on issue-7001-universe-prestep-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7001-universe-prestep-scope unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
phase: Phase 3 - Documentation
history:
- at: '2026-11-01T15:25:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/development/reference/ci-gate-mechanics.md
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/development/reference/ci-gate-mechanics.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Document the saving and the remaining wins

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` with `/spk-charter-profile-load` before parsing the rest of this prompt.

---

## Objectives & Success Criteria

The reference page and the changelog state, for a reader who was not in this mission, what a
scope-only heavy leg now skips, with the measured cost and the caveats, and which cheap wins
remain for someone else to pick up.

Done when:

- `docs/development/reference/ci-gate-mechanics.md` documents the `--gates-file` input and its
  fail-closed rule in the command table, explains the intersection under "Where it runs", and
  stops claiming leg 2/2 holds no collecting test (both legs hold one today).
- The measured numbers are stated with their source and caveat (development host with heavy
  concurrent load; published CI range 89–233 s for a first collection) and the "further cheap
  wins" are named as notes, not as changes made here.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: a bold impact-first lead citing
  (#7001), then before/after, under 1,200 characters.

## Context & Constraints

- Spec FR-007 / SC-001..SC-003; plan IC-06.
- Measured evidence: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/research.md` (cold collect
  396.7 s, warm 0.82 s, `key` 0.57 s, consumers scan 1.5–1.8 s) and the PR body's tests section.
- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — edit the file under
  `docs/`, never the symlink.
- Follow the existing entry style in `[Unreleased]` (read three neighbouring entries first).

## Branch Strategy

- **Strategy**: mission branch `issue-7001-universe-prestep-scope`, merge target `main`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T008 – Rewrite the reference page's stored-universe section

- **Purpose**: The page is the operator's map of the pre-step; it must describe the new input
  and correct the stale partition claim.
- **Steps**:
  1. In the command table row for `consumers`, document `--gates-file <path>` (default
     `$SK_BATTERY_GATES_FILE`), the intersection, and the exit-1-with-no-answer behaviour for an
     unreadable file.
  2. In "Where it runs" (`ci-router.yml`, `architectural-heavy`), say that a leg asks only about
     the gates the diff selected, so a scope-only leg with no consumer skips every universe step
     (key, restore, collect, save, check), and that the collection itself is unchanged.
  3. Correct "leg 2/2 holds no collecting test and skips the step" — today each leg holds one
     (`test_fast_tier_marker_completeness.py` in 1/2, `test_same_tier_uniqueness.py` in 2/2).
  4. Add the measurement paragraph with the caveat and the "further cheap wins" notes (the store
     cache is keyed by `universe-<key>-<commit>`, so the second leg of a commit restores instead
     of collecting; checkout and `uv sync --frozen --all-extras` still run for a scoped leg).
- **Files**: `docs/development/reference/ci-gate-mechanics.md`
- **Notes**: Keep the page's existing voice and heading structure; no new page, no ADR (this is a
  behaviour refinement inside one job, not a structural boundary).

### Subtask T009 – `[Unreleased]` changelog entry citing (#7001)

- **Purpose**: The change is user-visible to anyone reading CI wall times.
- **Steps**:
  1. Add an entry under `[Unreleased]` in the "Fixed"/"Changed" list its neighbours use, with a
     bold impact-first lead, the (#7001) reference, before/after, and the measurement.
  2. Keep it under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: Do not touch released sections.

## Test Strategy

```bash
uv run --frozen python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
uv run --frozen pytest -q tests/docs -q
```

## Risks & Mitigations

- Docs-index drift: run the freshness check and fix only what this diff changed.
- Numbers that mislead: always give the host caveat with the local measurement and cite the
  published CI range separately.

## Review Guidance

- Confirm the claim "the collection itself is unchanged" is visible to a reader.
- Confirm the changelog entry leads with the impact, not with the mechanism.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change status**: `spec-kitty agent tasks move-task WP03 --to <status>`
