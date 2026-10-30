---
work_package_id: WP02
title: Maintainer-facing changelog entry and gate sweep
dependencies:
- WP01
requirement_refs:
- SC-003
- NFR-002
planning_base_branch: issue-6728-reconcile-run-scope
merge_target_branch: issue-6728-reconcile-run-scope
branch_strategy: Planning artifacts for this mission were generated on issue-6728-reconcile-run-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6728-reconcile-run-scope unless the human explicitly redirects the landing branch.
created_at: '{{TIMESTAMP}}'
subtasks:
- T008
- T009
phase: Phase 2 - Record and verify
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: docs
tracker_refs:
- '#6728'
---

# Work Package Prompt: WP02 – Maintainer-facing changelog entry and gate sweep

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`) before parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Record the change where maintainers and changelog readers look, and confirm the gates the module
edit implicates. Done when:

- `docs/changelog/CHANGELOG.md` (`[Unreleased]` → the section a behaviour-preserving refactor
  belongs in) carries one entry with the bold impact-first lead and `(#6728)`, stating plainly that
  no product behaviour changes, naming before/after, and staying under 1,200 characters. The root
  `CHANGELOG.md` is a symlink — do not create a second file.
- No shipped docs page needs editing: `grep -rn "topic-scoped\|dead_edge_regenerated_urns" docs/`
  finds nothing descriptive (only archived plans may mention unrelated "run scope"). Confirm and
  record that; do not invent a docs page for an internal type.
- `tests/architectural/test_no_dead_symbols.py` and
  `tests/architectural/test_no_legacy_terminology.py` are green (the `__all__` edit and the module's
  prose are what implicate them).
- Every command you ran, with its result, is quoted in the WP history for the PR's `## Tests run`.

Requirements: SC-003, NFR-002.

## Context & Constraints

- This mission is a typing/API-shape change with **no** user-observable behaviour change. The
  changelog's own precedent for that is explicit: entries such as #6614 and #5695 say "No user-visible
  behavior changes" / "No product behavior changes" and list what moved. Follow that shape — the
  value for a reader is knowing the sentinel is gone and that nothing else moved.
- Honesty constraint: if any behaviour *did* change in WP01, do not paper over it with a "no
  behaviour change" sentence — report it instead (that would be a rejected WP01, not a changelog
  problem).
- Keep the diff to one file. No docs index regeneration is needed because no page is added or
  renamed (`scripts/docs/docs_index.py` would only be required for that); if you conclude otherwise,
  say so in the WP history with the command that proves it.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Execution worktrees are allocated per lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T008 – The `[Unreleased]` entry

- **Purpose**: a maintainer reading the changelog learns the sentinel is gone and that nothing
  user-visible moved.
- **Steps**: add one bullet to `docs/changelog/CHANGELOG.md` under `## [Unreleased] - 4.0.0rc8`, in
  the section the file already uses for internal/no-behaviour-change entries (check where the
  #6614 and #5695 entries live and match it; if those sit under `### Changed`, use that). Shape:

  > - **The charter reconciler's legacy-edge run scope is a named type, not an `Ellipsis` sentinel**
  >   (#6728). **Before:** `legacy_applies_edges` and `_is_legacy_applies` took
  >   `dead_edge_regenerated_urns: Collection[str] | None | EllipsisType = ...`, where only `None`
  >   and "the same set as the regenerated URNs" were ever passed, so the meaning of the default had
  >   to be read off the body. **After:** both take an explicit `run_scope: RunScope`
  >   (`FULL` / `TOPIC_SCOPED`), which owns the dead-edge filter; a full run still strips the dead
  >   `requires --> mission_type:*` edge wherever it sits, a topic-scoped run still strips it only
  >   on a directive it regenerated, and a legacy `applies` edge is still stripped only from a
  >   regenerated owner. No user-visible behaviour changes.

  Adjust wording to the file's voice (it uses "Before:"/"After:" with bold leads and one sentence of
  impact first). Count characters — the bullet must stay under 1,200.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Validation**: the entry renders as one list item; `git diff --stat` shows one file (plus the
  symlink untouched).

### Subtask T009 – Gate sweep

- **Purpose**: the `__all__` edit and the module prose implicate two named architectural gates; run
  exactly those, not the whole directory.
- **Steps**:
  - `uv run pytest tests/architectural/test_no_dead_symbols.py -q`
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  - `uv run pytest tests/charter/synthesizer/ tests/charter/test_project_registration.py -q` (re-run
    on the WP01 tip, to confirm nothing regressed between the two WPs)
  - `git diff --stat origin/main...HEAD -- src/ tests/ docs/` and read it once for anything you did
    not intend to change.
- **Files**: none (verification only).
- **Validation**: all green; if a gate fails for a reason outside this diff, reproduce it on
  pristine `origin/main` in a separate worktree before reporting it (charter Pre-existing Failure
  Reporting Rule), and never skip or xfail it.

## Test Strategy

Verification-only WP: the targeted gates above, never `tests/architectural/` wholesale, `make
test-full`, or any e2e/performance sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- One changelog bullet under `[Unreleased]`, `< 1,200` characters, with `(#6728)`, bold impact lead,
  before/after, and an explicit "no user-visible behaviour changes" (or an honest report if that is
  untrue).
- Both named architectural gates and the owning suites green on the WP tip.
- Confirmed (with the grep) that no shipped docs page describes the removed parameter.
- Commands and counts recorded for the PR body.

## Risks & Reviewer Guidance

- **Reviewer**: the entry must not claim a behaviour change it does not have, and must not omit the
  one thing that moved (the sentinel → `RunScope`). Check the character budget and that the root
  `CHANGELOG.md` symlink still points at `docs/changelog/CHANGELOG.md`.
- **Risk**: picking the wrong `[Unreleased]` subsection. The file groups by Keep-a-Changelog
  headings; match the neighbouring "no behaviour change" entries rather than inventing a heading.
- **Risk**: treating an unrelated red gate as yours. Reproduce on `origin/main` first, then cite or
  file an issue (the batch brief names #6798/#6801/#6816 as tracked pre-existing reds).
