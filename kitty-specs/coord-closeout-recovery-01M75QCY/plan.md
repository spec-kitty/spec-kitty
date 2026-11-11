# Implementation Plan: Coordination closeout recovers from its own commits

**Branch**: `kitty/mission-coord-closeout-recovery-01M75QCY` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/coord-closeout-recovery-01M75QCY/spec.md`

Planning questions answered: scope is the four slices of #7544's prompt (#7550; #5931 with #7540
item 2; #5406 with #7540 item 3; the end-to-end test). Items 4-6 of #7540 belong to other runs.
Priority raised to P0 by the grounding probe (`research/code-grounding.md` §1).

## Summary

Three defects make a settled `lanes_with_coord` closeout fail, each at a single authority:

1. accept's record commit bypasses the placement seam when the root checkout is on an unprotected
   branch (#7550);
2. the destructive guards' residue context reads the stored topology from a raw root path, which a
   settled Mission does not have, and in-span `safe_commit` commits move the coordination branch
   with no advance intent (#5931, #7540 item 2);
3. the run after `--abort` resolves placement before the coordination worktree exists and prints a
   `single_branch` remedy (#5406, #7540 item 3).

Each is fixed at its authority, red first through the CLI, with an end-to-end test of the #7544
Done-when.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git (CLI)
**Storage**: git refs and worktrees; `meta.json`; `.kittify/runtime/merge/<id>/state.json`
**Testing**: pytest with real git in `tmp_path`; CLI driven through `CliRunner` / subprocess for the red tests; one slow end-to-end module
**Target Platform**: Linux, macOS, Windows (no new platform-specific code)
**Project Type**: single
**Performance Goals**: no extra git calls outside a consolidate span (NFR-002)
**Constraints**: C-001..C-006 of the spec
**Scale/Scope**: 5 WPs, about 10 source files, mostly small diffs

## Charter Check

- Single canonical authority: each fix lands at the existing authority (placement seam / commit
  router, `ResidueContext.for_mission`, `safe_commit` + advance-intent sink, the materializer).
  No second rollback path (C-001). PASS.
- Architectural alignment: `git/ref_advance.py` gains only a plumbing-level predicate (no
  `specify_cli` import). PASS.
- ATDD-first / Standing Order 4: every WP opens with a red test through `spec-kitty accept` /
  `spec-kitty consolidate`, committed before the fix; P0 marker on the repro, removed by the fix.
- Standing Order 5: no new gates (C-005); existing gates re-run, not loosened.
- NO_FULL_HEAVY_SUITES_IN_MISSION: targeted modules + named gate files only.

## Implementation Concern Map

| IC | Concern | Authority | WP |
|----|---------|-----------|----|
| IC-01 | Acceptance record commit placement + provenance + refusal | `acceptance/__init__.py::_commit_acceptance_meta` | WP01 |
| IC-02 | Residue context reads the stored topology through the placement seam | `coordination/coherence.py::ResidueContext.for_mission` | WP02 |
| IC-03 | In-span `safe_commit` persists its advance intent before the ref moves | `git/commit_helpers.py::safe_commit`, `git/ref_advance.py` sink predicate | WP03 |
| IC-04 | Rematerialize the coordination worktree before the run resolves placement; topology-aware missing-manifest remedy | `consolidation/executor.py` pre-phase, `consolidation/entry_preflight.py` | WP04 |
| IC-05 | End-to-end closeout test | `tests/integration/` | WP05 |

### IC-01 design

`_commit_acceptance_meta` always commits through `_commit_acceptance_meta_via_router`
(`commit_for_mission`, `PRIMARY_METADATA`), which resolves the write home through the placement
seam: the coordination worktree's Mission branch for a settled default Mission, the root checkout's
branch for a `single_branch` Mission on its own branch, the coordination worktree on a protected
primary. The raw `run_git(["add"...])` path is deleted (single path; `test_commit_scope_owner` shrinks).
`parent_commit` becomes `rev-parse HEAD` in the checkout that holds `summary.feature_dir` (the branch
the record is written on). Router or git failures raise `AcceptanceError` with a code
`ACCEPT_RECORD_COMMIT_FAILED`; the CLI's existing `AcceptanceError` rendering prints it (no
traceback). `status_phase` is untouched (DD-1).

### IC-02 design

`ResidueContext.for_mission` resolves the Mission's `PRIMARY_METADATA` directory through
`mission_runtime.placement_seam(repo_root, slug).read_dir(...)` and reads `read_topology` there;
when the seam cannot resolve (any resolution error), it falls back to the current raw join, so a
legacy or unresolvable Mission keeps today's behaviour (strictest when absent). Rollback's
`_RunResidue` is unchanged: the Mission's own status log/snapshot in its coordination checkout were
already residue by rule; they were refused only because the context could not be built.

### IC-03 design

`git/ref_advance.py` gains `advance_intents_reported() -> bool` (a sink is installed). `safe_commit`
with no `expected_parent_sha` and no `index_deletions`, while intents are reported, reads the
destination tip and commits through the existing `_safe_commit_with_expected_parent` mode, which
reports the intent (sink) before its CAS `update-ref` and syncs the real index for the committed
paths. Outside a span nothing changes (NFR-002). A concurrent move between the read and the CAS
fails closed (C-002). The rollback's `_effective_post` then explains the run's own done commits.

### IC-04 design

At the top of `run_lane_based_consolidation`, before the origin gate and the status-dir
resolution: when the seam's `PRIMARY_METADATA` dir has no `meta.json`, find the branch holding
`kitty-specs/<slug>/meta.json` (`branch_holding_path`), read that `meta.json` from the branch, and
when its stored topology is a coordination topology whose `coordination_branch` is that branch, call
`materialize_coord_surface_for_write(main_repo, slug, coordination_branch=..., mid8=resolve_declared_mid8(meta, slug))`
and rebuild the seam. `_require_lanes_json_naming_mission_branch` keeps the `git checkout` remedy only
for a `single_branch` holder; for a coordination holder it names
`spec-kitty doctor coordination --fix --mission <slug>`-free wording: re-run `spec-kitty consolidate`
once the coordination branch is local (the materializer's own refusal text is printed when it refuses).

### IC-05 design

`tests/integration/test_coord_closeout_recovery_7544.py`, marked slow + e2e: builds a 6-WP default
Mission once per module (CLI subprocesses, as the grounding probe), snapshots it, then runs accept,
consolidate with an injected failure (a `sitecustomize`-free injection: a tiny runner script that
patches one phase and calls the CLI `main`), `--abort`, and `consolidate`, asserting each exit code
and the landed content. A second test kills consolidate at the WP02 done commit (git wrapper on
`PATH`) and asserts `--abort` + `consolidate` recover (SC-002).

## Project Structure

### Documentation (this mission)

```
kitty-specs/coord-closeout-recovery-01M75QCY/
├── spec.md
├── plan.md
├── research.md                      # points at research/code-grounding.md
├── research/code-grounding.md
├── contracts/refusal-codes.md       # the one new refusal code
├── traces/{tooling-friction,approach,design-decisions}.md
└── tasks.md + tasks/WP0*.md
```

### Source Code (repository root)

```
src/specify_cli/acceptance/__init__.py           # WP01
src/specify_cli/coordination/coherence.py        # WP02
src/specify_cli/git/ref_advance.py               # WP03 (predicate only)
src/specify_cli/git/commit_helpers.py            # WP03
src/specify_cli/consolidation/executor.py        # WP04 (pre-phase only)
src/specify_cli/consolidation/entry_preflight.py # WP04
tests/specify_cli/acceptance/                    # WP01
tests/coordination/                              # WP02
tests/consolidation/, tests/specify_cli/git/      # WP03, WP04
tests/integration/test_coord_closeout_recovery_7544.py  # WP05
docs/changelog/unreleased/7544-*.fixed.md        # each WP its own fragment
```

## Test strategy

Red first through the CLI entry point for each WP (WP01 `accept`, WP02/WP03 `consolidate --abort`
after a kill/failure, WP04 `consolidate` after `--abort`), using a lightweight `lanes_with_coord`
fixture built by the existing consolidation test helpers where they exist, else by real CLI calls.
Then unit pins at each authority with a negative control (foreign commit stays unexplained, foreign
edit still refuses, single_branch remedy unchanged, `safe_commit` outside a span unchanged).

Blast radius per WP: the module's tests + `tests/consolidation/` (WP02-WP04) +
`tests/coordination/` (WP02) + `tests/specify_cli/acceptance/` (WP01) + named gates
`tests/consolidation/test_single_rollback_authority.py`, `tests/architectural/test_commit_scope_owner.py`,
`tests/architectural/test_no_write_side_rederivation.py`, `tests/architectural/test_layer_rules.py`,
`tests/architectural/test_merge_pipeline_ratchets.py`, `tests/architectural/test_no_legacy_terminology.py`.

## Complexity Tracking

No charter violation to justify.
