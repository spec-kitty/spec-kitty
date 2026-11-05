---
work_package_id: WP02
title: Operator surface and regression sweep
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-009
- NFR-003
- C-001
- SC-004
planning_base_branch: issue-7198-late-window-accounting
merge_target_branch: issue-7198-late-window-accounting
branch_strategy: Planning artifacts for this mission were generated on issue-7198-late-window-accounting. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7198-late-window-accounting unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 2 - Operator surface
history:
- timestamp: '2026-11-05T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/phase_teardown.py
- tests/consolidation/test_late_teardown_projection.py
- docs/guides/how-to/recovery/recover-from-interrupted-merge.md
- docs/changelog/unreleased/**
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Operator surface and regression sweep

## Objective

WP01 makes two new refusal kinds reachable. Every refusal must name the repair that actually clears
it (#6791's lesson: a remedy that repeats the refusal is worse than no remedy), the docs must state
what the widened guarantee proves, the changelog fragment must exist, and the existing suites must
pass without a weakened assertion.

## Context

- `src/specify_cli/consolidation/phase_teardown.py`:
  - `_late_projection_remedy` — one branch per `LateProjectionRefusalKind`, the last one
    (`RECORD_NOT_LANDED`) is the fall-through; add yours **before** it.
  - `_late_projection_refusal` — the envelope: branch, target, triple kept, exit 1, `--abort` ruled
    out, ends with `spec-kitty consolidate --resume` again plus the error-code suffix. Do not change
    its shape; it already satisfies NFR-003.
  - `_land_late_coordination_commits` — the caller. **Do not touch the approved-tip advance
    condition** (`if not run.is_resume and projected_tip and ...`): it is #7199's seam, owned by
    another agent in this batch.
- `tests/consolidation/test_late_teardown_projection.py`: `_REMEDY_PHRASES` (per-kind required and
  forbidden phrases) and the two invariant tests that iterate `tuple(LateProjectionRefusalKind)`.
- `docs/guides/how-to/recovery/recover-from-interrupted-merge.md` — "What a first run lands before it
  tears down" and the per-kind remedy list above it.

## Subtasks

### T001 — Remedies

Add two branches to `_late_projection_remedy`:

- `STATUS_EVENTS_NOT_LANDED` — the union stage folds the coordination **worktree's working-tree**
  `status.events.jsonl`, not the branch's commits, so the repair is to make that copy hold the events
  (`git -C <coordination worktree> checkout <branch> -- kitty-specs/<slug>/status.events.jsonl`) and
  re-run, or to land them on the target yourself. Say which copy the union reads: an operator who
  copies onto the target and re-runs must not be surprised.
- `NON_COORDINATION_RECORD_NOT_LANDED` — a primary artifact is never projected (#5460) and the
  target authors its own copy, so the repair is to land the file on the target from the coordination
  branch (`git checkout <branch> -- <path>` in the target checkout, then commit) or to revert the
  coordination commit that changed it.

Neither may use the phrase "Land the file on <target> yourself" verbatim (the test forbids the old
generic instruction), and neither may advise copying `status.events.jsonl` bytes over the target's
log without saying the union stage will rematerialize `status.json` from it.

### T002 — Remedies pinned by test

Extend `_REMEDY_PHRASES` for both kinds with required phrases (the copy the union reads / the
projection cannot carry primary artifacts, and the recovery command) and forbidden phrases (the other
kind's repair). Keep `test_no_two_refusal_kinds_share_a_remedy` green — if two remedies collide,
the wording is wrong, not the test.

### T003 — Re-pin the gate-CAS fixture (no weakened assertion)

`test_first_run_does_not_approve_a_tip_that_moved_during_the_projection` injects a `meta.json` commit
during the projection *because* the assertion used to exempt `meta.json`, so the refusal it wanted to
exercise was the gate's compare-and-swap. `meta.json` is judged now. Re-pin the injection to
`status.json` (still excluded, by the derived-snapshot rule) and update the docstring to say why:
the case still proves "a tip that moved during the projection is never stamped approved", now with a
path the assertion legitimately skips. Keep every assertion in the test (the branch survives, the
anchor does not advance, the late record landed, the message names the compare-and-swap).

### T004 — Docs

In `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`, the late-window section: state
that the proof covers **every** change in the window (not only coordination records), with the four
dispositions in one short paragraph, and add the two new refusals to the per-kind remedy list. Keep
the existing paragraphs' voice; do not restructure the page. If the docs index row for a heading you
touch goes stale, regenerate only that surface and say so in the PR body.

### T005 — Changelog fragment

`docs/changelog/unreleased/<issue-or-pr>.fixed.md` in the shape `docs/changelog/unreleased/README.md`
requires: one bold impact-first lead with `(#7198)`, then before/after, under 1,200 characters. Name
the file with the issue number first and rename it to the PR number once the PR exists.

### T006 — Regression sweep

Run and record in the PR body:

```
uv run --frozen pytest tests/coordination/test_projection_teardown.py \
  tests/consolidation/test_late_teardown_projection.py \
  tests/consolidation/test_teardown_refusal_resume.py \
  tests/terminus/test_coord_teardown_cas_branch_delete.py \
  tests/consolidation/test_wp_evidence.py -q -p no:randomly -n 4
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed py files>
make format-check-files FILES="<changed py files>"
uv run --frozen mypy src/specify_cli/consolidation/bookkeeping_projection.py src/specify_cli/consolidation/phase_teardown.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
```

A failure you cannot attribute to this diff: reproduce on pristine `origin/main` in a clean
worktree, cite or file an issue, and name it in the PR's `## Deferred`. Never skip or xfail a gate.

## Definition of Done

- Both new kinds have a remedy that names a command and ends in `--resume`; the bijection and
  phrase tests pass.
- The re-pinned CAS test passes with all its original assertions.
- The docs and changelog fragment are written and the changelog-style check is clean.
- The five focused suites, ruff, format, mypy and the terminology test are green, with the exact
  commands and results recorded for the PR body.

## Risks & Mitigations

- **A remedy that repeats the refusal.** Word each remedy against the machinery that actually runs
  next: for status events that is the union stage reading the worktree copy; for primary artifacts it
  is the projection's deliberate exclusion.
- **Losing the gate-CAS coverage** while re-pinning T003. Keep the injection seam and every
  assertion; only the injected path changes.
- **Touching #7199's condition.** Do not edit the anchor-advance `if`; if a docstring sentence above
  it needs correcting for this Mission, keep the diff to the sentence and say so in the PR body.
