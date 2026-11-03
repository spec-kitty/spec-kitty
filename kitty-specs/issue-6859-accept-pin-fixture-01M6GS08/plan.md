# Implementation Plan: Repair the #4891 accept pin's positive control fixture

**Branch**: `issue-6859-accept-pin-fixture` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/issue-6859-accept-pin-fixture-01M6GS08/spec.md`
**Input**: Mission specification from `kitty-specs/issue-6859-accept-pin-fixture-01M6GS08/spec.md`

## Summary

Repair one test fixture and nothing else. `test_issue_4891_accept_missing_lanes.py` builds both
its negative control (no `lanes.json`) and its positive control from the shared
`_create_test_feature` helper. That fixture predates #6715/#5939, so its approved work package
has no readable evidence window, no `owned_files` change inside it, and no approval by an
identity other than its implementer. The positive control is therefore red on `main` with
`IMPLEMENTATION_UNREADABLE`; the assertion it makes (accept succeeds when `lanes.json` and a
passing matrix are present) is correct.

The change moves the two controls onto one module-level fixture builder that states a
complete, accept-ready Mission — declared `owned_files`, a lane-branch implementation commit
in the evidence window, and a claim/approve/done history whose approving actor differs from
the implementer — and then adds `lanes.json` plus the passing matrix for the positive control
only. No product code, no assertion and no marker changes.

## Technical Context

**Language/Version**: Python 3.11 (repository standard)
**Primary Dependencies**: pytest, typer/click (`CliRunner`), real `git` subprocesses
**Storage**: N/A (a throwaway git repository per test under `tmp_path`)
**Testing**: `uv run pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q`
**Target Platform**: Linux CI and developer hosts (unchanged)
**Project Type**: single project (Python CLI under `src/specify_cli`, tests under `tests/`)
**Performance Goals**: the two-test file stays under 5 minutes locally (measured 107 s)
**Constraints**: tests-only diff; every existing assertion byte-identical; the real `accept`
CLI is the entry point; reuse the repository's existing fixture helpers
**Scale/Scope**: one test file, ~120 added fixture lines, zero production lines

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / ATDD-first** — satisfied: the red test is the authority for
  the defect and it stays the pin; no new surface is introduced. (charter, ATDD-First)
- **Test-first bug fixing (DIRECTIVE_034)** — satisfied: the failing CLI-level test existed on
  `main` before the change and stays as the regression pin; the fix does not add a test that
  only mirrors the implementation. (DIRECTIVE_034)
- **DIRECTIVE_041 (a test only where it guards real behaviour or a standing invariant)** —
  satisfied: no new test is added; the standing pin is repaired. No development-assist test
  needs retirement.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — satisfied: only the affected file is run locally; CI
  owns the wide sweep.
- **Locality of change (DIRECTIVE_024 / smallest-viable-diff)** — satisfied: one file; the
  shared `_create_test_feature` helper used by ~35 other call sites is deliberately *not*
  edited, so no other test's fixture changes.
- **Terminology canon** — satisfied: the new text says Mission/work package; no `feature*`
  alias is added to active surfaces (the module's existing identifiers are left alone).
- **Changelog fragments** — a tests-only change is non-user-facing: an
  `docs/changelog/unreleased/<pr>.internal.md` fragment per the repository rule.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6859-accept-pin-fixture-01M6GS08/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Task breakdown (/spec-kitty.tasks output)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/acceptance/, src/specify_cli/consolidation/   # read only, unchanged
tests/
└── specify_cli/cli/commands/
    └── test_issue_4891_accept_missing_lanes.py                 # the only edited file
```

## Approach

1. **Reproduce** the red positive control on a pristine `origin/main` clone (done before the
   mission: `1 failed, 1 passed`, `IMPLEMENTATION_UNREADABLE`).
2. **Read the gates, not guess.** The three axes `accept` applies to an approved work package
   live in `consolidation/wp_evidence.py`: `IMPLEMENTATION_UNREADABLE` (window cannot be
   diffed), `IMPLEMENTATION_MISSING` (no change to authored `owned_files` in the window), and
   `REVIEW_NOT_INDEPENDENT` (`consolidation/preflight.py` compares implementer of record with
   the approving actor). Establish empirically that each refuses this fixture, so the repair
   is provably complete rather than tuned to the first error message.
3. **One shared builder.** Add `_build_accept_ready_mission(tmp_path)` to the test module:
   - `_create_test_feature(..., omit_status_events=True)` for the repository skeleton;
   - rewrite `tasks/WP01-test.md` with `owned_files: [src/**]` — the evidence axis reads
     authored frontmatter only (`_owned_patterns_by_wp`);
   - branch `-M _WORK_BRANCH`, repoint `meta.json`'s `target_branch` (the fixture's existing
     protected-branch sidestep, kept as is);
   - seed `planned -> claimed` (implementer, with claim policy metadata), `claimed ->
     approved` (a distinct reviewer identity), `approved -> done`, then `materialize` — the
     shape `test_accept_clean_tree.py` already uses for the same gate;
   - commit, leaving the tree clean.
   Both controls call it and differ only by `lanes.json` + the passing matrix, exactly as the
   pin's docstring claims.
4. **Positive control adds its evidence.** After writing `lanes.json` (which pins
   `planning_commit_sha`) and the matrix, call
   `tests/lane_test_utils.commit_lane_implementation(..., path="src/wp01.py")` — the post-#6715
   pattern the other lane fixtures use — so the window holds WP01's change on its own lane
   branch.
5. **Prove non-vacuity half by half** (SC-002): drop each of the three fixture parts in turn and
   confirm the positive control turns red with the matching code; restore it and confirm green.
6. **Changelog fragment** `docs/changelog/unreleased/<pr>.internal.md` (tests-only, not
   user-facing), then PR as draft, `pr:pause-ci`, green, flip.

## Risks and Mitigations

- *Editing the shared `_create_test_feature` would move ~35 call sites' fixtures.* Mitigation:
  the builder is local to this module; the helper is only *called*, never modified.
- *Seeding a second status chain could duplicate or contradict the helper's one forced hop.*
  Mitigation: ask the helper to omit status events entirely (`omit_status_events=True`) and seed
  the whole lifecycle once.
- *Event-id alphabet* — the status store drops events whose `event_id` is not ULID-shaped.
  Mitigation: the seeded ids are Crockford base32 (ULID alphabet) and unique per event.
- *A green positive control that is green for the wrong reason.* Mitigation: SC-002's
  half-by-half reverts, plus the negative control still naming `lanes_manifest`.

## Complexity Tracking

No charter violation, so no entries. The change adds no abstraction: one local fixture builder
composed of existing test helpers, and one existing helper call.
