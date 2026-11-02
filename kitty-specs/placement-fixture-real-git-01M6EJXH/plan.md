# Implementation Plan: Placement fixture must be a real git repo (#7055)

**Branch**: `issue-7055-placement-fixture-real-git` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/placement-fixture-real-git-01M6EJXH/spec.md`
**Input**: Mission specification from `kitty-specs/placement-fixture-real-git-01M6EJXH/spec.md`

## Summary

Fix the deterministic red in
`tests/specify_cli/migration/test_runtime_state_cutover_placement.py` by replacing the
module-local bare `.git` directory marker with a real `git init` repository, so
`cutover_mission`'s #6673 tracked-`meta.json` seam classifies the fixture as "a repository
that tracks nothing for this path" instead of "git refused to answer", and the mismatch test
reaches `PlacementMismatchError` again. Add one seam-level regression test pinning the
deliberate refusal for an unusable anchor (skip with `TRACKED_META_UNAVAILABLE`, nothing
written, no raise), so the two fail-safe paths stay distinguishable.

No `src/` change is expected: the product behaviour is already pinned by
`tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`. If implementation proves a product
defect instead, stop and report rather than widening the diff.

## Technical Context

**Language/Version**: Python 3.11 (repo floor; `.venv` from `uv sync --frozen --all-extras`)
**Primary Dependencies**: pytest (`pytestmark = pytest.mark.fast`), the repo's own
`specify_cli.migration.runtime_state_cutover` / `specify_cli.upgrade.tracked_meta_notice`.
No new dependency.
**Storage**: N/A (test fixtures on `tmp_path`)
**Testing**: targeted pytest of the affected module plus the #6673 tracked-meta suite it
leans on; no full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: Linux CI and developer hosts (git 2.4x)
**Project Type**: single Python package (`src/specify_cli`, `tests/`)
**Performance Goals**: module runtime roughly unchanged (a `git init` per repo-building test,
no commit, no network)
**Constraints**: `GIT_CEILING_DIRECTORIES` stays pinned to the test's `tmp_path`; the fixture
must also hold at an unborn `HEAD`; no weakening/skip/xfail of the existing assertion
**Scale/Scope**: one test module (5 fixture call sites + 1 new test); zero production files

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan complies |
| --- | --- |
| ATDD-first / DIRECTIVE_034 (test-first bug fixing) | The red already exists on `main` and is reproduced before any edit; the fix is proven by the module going green without changing the assertion. The new regression test is written red-first against the current (marker) fixture shape: it asserts the skip seam, which the real-repo fixture would not satisfy for the wrong reason — see Phase 1 red-first proof. |
| DIRECTIVE_024 locality of change | Edits stay inside the single test module; no `src/` change. |
| DIRECTIVE_041 (test value) | One new test, guarding a standing invariant (two fail-safe seams must not be confused); no speculative tests. |
| Single canonical authority | The tracked-meta classification stays owned by `tracked_meta_notice.py`; the test consumes it, never reimplements it. |
| Pre-existing Failure Reporting Rule | #7055 is the report; this mission closes it and cites the pin test that proves product intent. |
| Test-remediation red-first discipline | Red evidence recorded in `research.md` D1/D2 and re-run before/after the edit. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only the module and the #6673 suite run. |
| Proof Trail | Decision Moments resolved; tracer files; PR `Tests run` block carries the commands and results. |

No violations; `## Complexity Tracking` is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/placement-fixture-real-git-01M6EJXH/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings (created in `discovery`)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

`data-model.md`, `quickstart.md` and `contracts/` are not produced: this is a test-remediation
mission with no entities, no interfaces and no runnable surface. `meta.json` records
`"contracts": "none"` with a rationale so strict `spec-kitty accept` waives the directory.

### Source Code (repository root)

```
src/specify_cli/migration/runtime_state_cutover.py   # read-only reference: seam ordering
src/specify_cli/upgrade/tracked_meta_notice.py       # read-only reference: classification
tests/specify_cli/migration/test_runtime_state_cutover_placement.py   # THE edit
tests/specify_cli/upgrade/test_read_tracked_meta_6673.py              # read-only pin (regression)
tests/unit/migration/_backfill_fixture.py                             # read-only: build_mission helper
```

**Structure Decision**: single-project layout already in place; the mission edits exactly one
test module and reads two neighbouring test/product files to keep its fixtures honest.

## Phase 0 — Outline & Research

All unknowns were resolved in `discovery` (`research.md` D1–D4) and no `[NEEDS CLARIFICATION]`
marker remains:

- **Decision**: real `git init` fixture, classifier untouched — rationale and probe evidence in
  `research.md` D2.
- **Decision**: no commit in the fixture — unborn `HEAD` is a supported shape (`read_tracked_meta`
  → `_committed_meta_bytes` returns `None`, `_index_tracks_meta` is false) — `research.md` D2/Q2.
- **Decision**: add the seam-level regression pin — `research.md` D3.
- **Alternatives considered**: (a) patch `_tracked_meta_notice` to skip the classifier when the
  directory is not a canonical `kitty-specs/<slug>` home — rejected: it would weaken the #6673
  refusal on the strength of a path shape the seam does not own; (b) `xfail`/skip the mismatch
  test — rejected: it is a real contract with a real defect in the fixture, and the charter
  forbids weakening a gate; (c) change `cutover_mission` to run the placement check before the
  tracked-meta skip — rejected: the skip must precede seeding (#6673), and both orders are
  equally fail-safe, so sequencing is not this issue's defect.

## Phase 1 — Design & Contracts

- **Contracts**: none (`meta.json`: `"contracts": "none"`, rationale recorded).
- **Data model**: none — the only "entities" are test fixtures (`repo_root`, `canonical_dir`,
  `divergent_dir`, `status_dir`), already documented in the module's docstrings.
- **Design of the edit**:

  1. `_init_bare_git_marker(repo_root)` → `_init_git_repo(repo_root)`:
     `subprocess.run(["git", "init", "-q", str(repo_root)], check=True)` with
     `capture_output=True`; docstring explains why a real repo is required (the cutover shells
     out to git for the tracked-meta seam; a bare marker makes git refuse and the seam skip
     before the placement check). Keep a module-level note that no commit is needed.
  2. Update the 5 call sites' comments where they say "bare marker".
  3. Rename the now-misleading anti-scaffold wording only if it references the marker.
  4. New test `test_unusable_git_anchor_refuses_with_tracked_meta_notice_without_writing`:
     build the bare-marker shape explicitly (a local helper or an inline `(root / ".git").mkdir()`),
     call `cutover_mission(divergent_dir, status_feature_dir=status_dir)`, assert
     `flipped is False`, `skipped_notice` endswith `[TRACKED_META_UNAVAILABLE]`, no
     `meta.json` at either candidate location, and no exception escapes.

- **Red-first proof for the new test**: against the *pre-fix* tree (marker fixture), the new
  test already passes — it pins behaviour that exists. That is correct for a regression pin
  (it does not drive a product change), and its value is proven by mutation: swapping the
  assertion to a real-repo expectation makes it fail. The module's actual red-first evidence is
  the pre-existing failing mismatch test (`research.md` D1) going green after the fixture fix,
  with the assertion byte-identical.
- **Charter re-check post-design**: unchanged; still no violations, no new surfaces.

## Complexity Tracking

*No Charter Check violations.*

## Implementation Concern Map

### IC-01 — Real-repo fixture and call-site truthfulness

- **Purpose**: make the module's enclosing-repo fixture the shape every live Mission has, so the
  cutover's tracked-meta seam resolves "nothing tracked" and the placement check is reached.
- **Relevant requirements**: FR-001, FR-002, FR-004, NFR-001, NFR-002, C-003
- **Affected surfaces**: `tests/specify_cli/migration/test_runtime_state_cutover_placement.py`
  (helper + 5 call sites)
- **Sequencing/depends-on**: none
- **Risks**: leaving a call site on the marker would silently keep a test on the wrong seam;
  the two action-context tests call `_flip_phase`/`_resolve_primary_home_or_degrade` directly and
  must keep passing under a real repo.

### IC-02 — Seam-distinction regression pin

- **Purpose**: pin that an unusable `.git` anchor yields the #6673 refusal skip (not a
  `PlacementMismatchError`, not a write), so the two fail-safe paths remain deliberate and the
  fixture choice is explainable from the tests alone.
- **Relevant requirements**: FR-003, NFR-003, SC-003
- **Affected surfaces**: same module (one new test)
- **Sequencing/depends-on**: IC-01 (the module helper vocabulary should be settled first)
- **Risks**: over-pinning notice text; assert the stable code suffix and the outcome
  (`flipped`, `skipped_notice` presence, no file), not the full sentence.
