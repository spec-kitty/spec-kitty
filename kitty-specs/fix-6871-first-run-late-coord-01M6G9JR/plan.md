# Implementation Plan: Keep a coordination commit that lands before a first-run teardown

**Branch**: `issue-6871-first-run-late-coord` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/spec.md`

## Summary

The teardown phase already owns a proven mechanism for "a coordination commit the target never
received": `_land_late_coordination_commits` projects the window, commits it onto the target and
then refuses unless every coordination record the window carried is byte-identical on the target
(`assert_late_window_landed`, #6791/#6857). It is gated behind `if not run.is_resume: return`,
so the first run — the one with no second chance — has neither the projection nor the assertion.

The change turns that early return into a base-selection problem instead of a resume-only gate:

- `--resume` keeps `state.pre_mutation_coord_sha` as the window base and its behaviour byte for
  byte;
- a first run uses `coord_tip_after_projection` (the merge's own last verified write to the
  coordination ref, captured at the end of the bookkeeping phase) as the window base.

Everything after base selection is the existing code path: same seams, same commit, same
assertion, same refusal builder. A clean first run has tip == base, so the existing
`_post_checkpoint_commit_shas` early return makes it a provable no-op. A first run with a late
commit either lands it or refuses with the triple intact.

## Technical Context

**Language/Version**: Python 3.12 (`uv run`, `src/specify_cli/`)
**Primary Dependencies**: typer CLI, pytest, real-git fixtures under `tests/`
**Storage**: git refs + `kitty-specs/<slug>/` (status log, meta.json), `ConsolidationState` JSON
**Testing**: `uv run pytest` on the focused suites; real-git fixture helpers, no git mocking
**Target Platform**: developer CLI (`spec-kitty consolidate`)
**Project Type**: single Python package + CLI
**Constraints**: no new CLI flag, no config key, no exit-code change; the `--resume` assertion
and window must not be weakened; teardown is post-landing, so a refusal must never roll back the
verified landing
**Scale/Scope**: one phase module (`consolidation/phase_teardown.py`), its tests, one changelog
fragment, and the docs that describe the teardown guarantee

## Charter Check

- **Single canonical authority**: the projection, the assertion and the refusal builder keep
  their single homes (`bookkeeping_projection`, `_late_projection_refusal`); the new code selects
  a window base and calls them. No second copy of the record selector or of a refusal text.
- **ATDD-first / red-first**: the failing test lands before the fix, through the pre-existing
  entry point `_teardown_coordination_triple` (the phase the CLI drives), and a CLI-level case
  proves the operator-visible behaviour.
- **No weakening of a gate**: the `--resume` window base, the post-projection assertion, the
  projection teardown gate CAS and the compare-and-swap branch delete are untouched; the first
  run is added to them.
- **Mission tracers**: `traces/{approach,design-decisions,tooling-friction}.md`.
- **Tidy-first**: the new base-selection logic is one small, documented helper, not a second
  copy of `_land_late_coordination_commits`.

## Implementation Concern Map

- **IC-01 — Window base selection.** A first run and a resume disagree on where the late window
  starts, and the disagreement is the whole defect. One helper
  (`_late_window_base`) expresses it so no caller re-derives it.
- **IC-02 — Approved-tip bookkeeping.** After a proven landing the run may advance the tip
  teardown approves; before a proven landing it may not. The advance must be a compare-and-swap
  on the tip the assertion just proved, never a fresh read (the same discipline as
  `_carry_pass_anchor_over_own_commit`).
- **IC-03 — Refusal routing.** A first-run refusal must reach the operator as a
  `CoordinationTeardownError` naming branch, target, marker and `--resume` — reusing
  `_late_projection_refusal` so the per-kind remedies (#6791) stay the single source.
- **IC-04 — The unprovable corner.** A first run with no anchor keeps today's behaviour and is
  reported; it must not acquire a refusal that no resume can clear.

## Project Structure

### Documentation (this mission)

```
kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/
├── spec.md
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── issue-matrix.json    # one row: #6871
└── traces/{approach,design-decisions,tooling-friction}.md
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── phase_teardown.py            # EDIT: window base selection, first-run projection + assertion
└── bookkeeping_projection.py    # READ ONLY: the projection + assertion seams (no change)
tests/coordination/
├── test_projection_teardown.py  # EDIT: first-run red cases next to the resume ones
tests/consolidation/
└── test_late_teardown_projection.py  # READ/pass unchanged: the #6857 resume suite
docs/
├── changelog/unreleased/<pr>.fixed.md
└── reference/…                  # only if a doc page states the resume-only guarantee
```

## Design

`_land_late_coordination_commits` becomes:

1. `base = _late_window_base(run)`:
   - resume → `run.state.pre_mutation_coord_sha`; when that or the checkpoint is missing, keep the
     existing `_refuse_unbuildable_late_window` refusal (unchanged);
   - first run → `run.coord_tip_after_projection`; when it is missing, return (no window; residual
     documented, IC-04).
2. The existing ref/window checks stay: the checkpoint must exist and name the branch being
   deleted, otherwise nothing is projected.
3. The existing body runs: stranded-paths refusal, status projection, mission-record projection,
   guarded gate-matrix projection, one bookkeeping commit, `assert_late_window_landed`.
4. **New**: on a first run only, when the projection and the assertion succeeded, record the
   projected tip as `run.coord_tip_after_projection` — and only if the ref is still at the tip the
   assertion was made over. Anything else leaves the anchor alone, so the projection teardown
   gate and the branch-delete CAS refuse (fail-closed).
5. The console line distinguishes the first-run case ("landed between the gate and teardown") from
   the resume case ("landed during teardown") only in wording; the commit message stays the one
   #5570 introduced, so history and tests that count projection commits are unchanged.

Ordering inside `_teardown_coordination_triple` is unchanged: project → fold status → read the
pre-teardown tip → gated coord worktree teardown → CAS branch delete → flatten. The first-run
projection necessarily runs before the gate, which is what makes the gate's anchor provable.

## Risks

- **Re-walking the merge.** Using `pre_mutation_coord_sha` on a first run would project stale
  primary artifacts and manufacture refusals. Avoided by anchoring on
  `coord_tip_after_projection` (spec, Scope decisions).
- **Approving a tip without proving it.** The anchor advance is gated on the assertion plus a
  compare-and-swap against the ref; a commit landing mid-projection keeps the older anchor and the
  gate refuses.
- **Double commit.** The window is `base..tip`, and `_paths_have_status_changes` gates the commit,
  so a re-run (resume after a refusal) does not add a second projection commit for the same
  content.
- **Test-fragility in existing suites.** `test_fresh_run_without_a_window_is_covered_by_the_teardown_gate`
  documents the old no-op for a run with no anchor; it must stay true (the no-anchor path keeps
  returning) — it is re-checked, not rewritten.

## Out of Scope (reported, not changed)

The single-agent / empty-lane-window evidence refusals from #7082
(`REVIEW_NOT_INDEPENDENT`, `IMPLEMENTATION_MISSING`) live on the approval-evidence axis. Changing
who may review an approval is a governance decision, and both refusals already name their
recoveries (`_RECOVERY` in `consolidation/wp_evidence.py`, `--attest-no-implementation`). Named in
the PR's `## Deferred` with that reason.

## Verification

- `uv run pytest tests/coordination/test_projection_teardown.py -q`
- `uv run pytest tests/consolidation/test_late_teardown_projection.py -q`
- `uv run pytest tests/consolidation/test_teardown_refusal_resume.py tests/terminus/test_coord_teardown_cas_branch_delete.py -q`
- `uv run pytest tests/ -q -k "teardown or consolidation" --timeout=600` (bounded, not a full suite)
- `uv run --frozen python -m scripts.docs.check_changelog_style` after the fragment
