# Implementation Plan: `consolidate --skip-lanes` records an evidence window it can judge

**Branch**: `issue-7209-skip-lanes-planning-commit` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/issue-7209-skip-lanes-planning-commit-01M6P3JR/spec.md`
**Branch contract**: planning artifacts and the fix land on `issue-7209-skip-lanes-planning-commit`; the PR targets `spec-kitty/spec-kitty` `main`, which only the operator merges.

## Summary

Give the `--skip-lanes` synthesized `LanesManifest` the evidence-window base it never had.
`entry_preflight._synthesize_no_lane_manifest` resolves, from the target branch's own history,
the commit immediately before the Mission's planning artifacts appeared
(`kitty-specs/<slug>/`), and records it as `planning_commit_sha`. `wp_evidence.lane_evidence_window`
then computes `base..target` for the synthesized planning lane, so the #6715 evidence axis
judges the work packages it already knows how to judge instead of refusing
`EVIDENCE_WINDOW_UNCOMPUTABLE` on every direct-on-target Mission. When no base is resolvable
(history unreadable, or the Mission directory is not on the target), the existing refusal stands
and its recovery line names the remedy that works in this topology — commit the Mission's
planning artifacts on the target — alongside the existing `finalize-tasks` advice for a recorded
but unpinned `lanes.json` (#7210).

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`)
**Primary Dependencies**: `typer` (CLI surface), `rich` (console rendering); the git seam is
`kernel.git.run_git` plus `specify_cli.consolidation.git_probes.commit_parents`; no new dependency.
**Storage**: files only — `lanes.json`, `meta.json`, `status.events.jsonl`; this change writes no
new file and no new field (the synthesized manifest exists in memory only).
**Testing**: pytest; `pytest.mark.integration`, `pytest.mark.git_repo`, `pytest.mark.non_sandbox`
for real-git fixtures; the pre-existing CLI test drives a real Typer command through `CliRunner`.
**Target Platform**: Linux/macOS developer and CI checkouts (POSIX git).
**Project Type**: single project — CLI library under `src/specify_cli/`.
**Performance Goals**: at most two extra git invocations per `consolidate --skip-lanes` run, and
none when `lanes.json` is present (`git log` over one pathspec plus one parent read).
**Constraints**: no `lanes.json` schema change; no new configuration key; no attestation; no
behavior change on any Mission that has a `lanes.json`.
**Scale/Scope**: one resolver (~30 lines) plus a refusal-text change (~6 lines); 2 product files,
1 pre-existing test fixture, 1 new test module, 1 doc page, 1 changelog fragment.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority | PASS — `wp_evidence.lane_evidence_window` stays the one window authority; the fix feeds it, it is not duplicated. |
| Smallest viable diff / locality of change | PASS — product edits stay in the two consolidation modules that own the seam (#7198/#7199 teardown untouched). |
| ATDD-first / test-first bug fix | PASS — the pre-existing CLI test is the red-first proof; new tests precede the implementation commit. |
| Canonical terminology | PASS — "Mission", "work package", "lane", "evidence window"; no legacy "feature" prose introduced. |
| No new hosted surface / contract change | PASS — in-memory manifest only; no API or schema change. |
| Gates not weakened | PASS — FR-004 pins the evidence/independence refusals through the synthesized window with same-fixture paired tests. |
| No full heavy suite in-mission | PASS — targeted suites plus the touched-module neighbours only. |
| Docs & changelog | PASS — `--skip-lanes` doc note plus a per-PR changelog fragment. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-7209-skip-lanes-planning-commit-01M6P3JR/
├── spec.md              # Mission specification
├── research.md          # Discovery findings and decisions
├── reasons-canvas.md    # SPDD canvas
├── plan.md              # This file
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── entry_preflight.py   # _synthesize_no_lane_manifest: resolve and record the base
├── wp_evidence.py       # EVIDENCE_WINDOW_UNCOMPUTABLE line + recovery text
└── (untouched: reconciliation.py, phase_claim.py, phase_teardown.py, bookkeeping_projection.py)

tests/
├── specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py  # red-first entry point (fixture)
└── consolidation/test_skip_lanes_evidence_window.py              # new focused module
```

**Structure Decision**: single project. The product change lives in the consolidation package
that owns the synthesized manifest and the evidence axis; the tests split along the same seam
(one CLI-level proof through the real `consolidate` command, one unit-level module for the
resolver, the fail-closed case and the refusal text).

## Design

### D-1: where the base comes from

`_resolve_planning_base_commit(main_repo, mission_slug, target_branch) -> str | None`, private to
`entry_preflight`:

1. `git log --format=%H <target_branch> -- kitty-specs/<slug>` (newest-first). Empty output → `None`.
2. The last line is the earliest commit on the target that touched this Mission's directory — the
   commit that introduced its planning artifacts.
3. `commit_parents(main_repo, that_sha)[0]` — the target tip immediately *before* the Mission's
   artifacts appeared. A root commit has no parent and is its own base.
4. Any `GitCommandError` / `GitProbeError` → `None`. Nothing is fabricated, no timestamp is used,
   and no fallback window is invented.

Why the parent rather than the introducing commit: a Mission whose first commit carries planning
artifacts *and* a work-package change together (the shape of the #2745 fixture, and of a squashed
history) would otherwise get an empty window and a false `IMPLEMENTATION_MISSING`. The parent is
the boundary of "before this Mission".

### D-2: where the base is recorded

`_synthesize_no_lane_manifest` sets `planning_commit_sha=_resolve_planning_base_commit(...)` on the
manifest it already builds, using the same resolved `target_branch` the manifest's
`mission_branch` uses (so `--target` is honored). The field is the existing recorded field; the
synthesized manifest's `computed_from` line already documents that this manifest is synthesized.
No new field, no persistence.

### D-3: the refusal when nothing is resolvable

`wp_evidence._scan_lane` stops claiming "lanes.json records no planning commit" when there need be
no `lanes.json`; it says no planning commit is *recorded or resolvable*, keeping
`EVIDENCE_WINDOW_UNCOMPUTABLE` as the line-leading code. `_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]`
keeps the `finalize-tasks` advice for a recorded-but-unpinned manifest (#7210) and adds: for a
Mission with no `lanes.json` (the `--skip-lanes` direct-on-target topology), commit the Mission's
planning artifacts (`kitty-specs/<slug>/`) on the target branch so its start is in history, then
re-run. Both are remedies an operator can perform; the code and the refusal are unchanged.

### D-4: what is deliberately not done

- No attestation or `--skip-evidence` flag; `EVIDENCE_WINDOW_UNCOMPUTABLE` stays unliftable.
- No change to `tasks_move_task`'s evidence gate: it already returns early when `lanes.json` is
  absent, and its refusal text stays the lanes.json-shaped one it documents.
- No change to the `single_branch` leg's own recovery line (that path always has a stored
  topology and, with a resolved base, now windows correctly through the synthesized manifest).
- No change to `lanes.json` persistence, `finalize-tasks`, or the coordination-teardown seam.

## Test plan

**Red first (must fail before the fix):**

1. `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` — its `WP01-work.md` gains
   the `owned_files` a real Mission declares; the three nodes must still fail with
   `EVIDENCE_WINDOW_UNCOMPUTABLE` on the pre-fix tree (they do today on `origin/main`).
2. `tests/consolidation/test_skip_lanes_evidence_window.py` (new):
   - `test_synthesized_manifest_records_the_mission_start_boundary` — real repo: planning commit,
     then implementation commit; the synthesized manifest's `planning_commit_sha` is the commit
     before the Mission's artifacts, and `lane_evidence_window` diffs to include the
     implementation path. Positive control for the whole axis.
   - `test_synthesized_window_passes_a_work_package_that_owns_the_change` — `evaluate_evidence`
     returns no refusal on that fixture (the row FR-001 non-vacuity partner).
   - `test_synthesized_window_still_refuses_a_work_package_with_no_owned_change` — same fixture,
     WP owns an untouched path → `IMPLEMENTATION_MISSING` (FR-004 / SC-003).
   - `test_synthesized_window_still_refuses_a_self_reviewed_work_package` — same fixture, approval
     by the implementer identity → `REVIEW_NOT_INDEPENDENT` (FR-004).
   - `test_unresolvable_base_keeps_the_refusal_and_names_a_working_remedy` — Mission directory not
     committed on the target: `planning_commit_sha` is `None`, the refusal leads with
     `EVIDENCE_WINDOW_UNCOMPUTABLE`, and the recovery text names committing the Mission's planning
     artifacts on the target branch (FR-003 / SC-004; pairs with the first positive row).
   - `test_resolved_base_is_deterministic` — two builds on one repo yield the same SHA (NFR-002).
3. Post-fix: the three CLI nodes go green (SC-001, SC-002).

**Suites to run:**

- `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`
- `tests/consolidation/test_skip_lanes_evidence_window.py`
- `tests/consolidation/test_wp_evidence.py`, `tests/consolidation/test_lane_evidence_axis.py`,
  `tests/consolidation/test_single_branch_evidence_axis.py` (refusal text and codes)
- `tests/specify_cli/cli/commands/test_consolidate_*.py` and `tests/consolidation/` on the touched
  modules' neighbours (`-n 4 --dist loadfile` where the suite allows)
- `uv run --frozen ruff check` and `ruff format --check` on the changed files
- `uv run --frozen python -m scripts.docs.check_changelog_style`

## Complexity Tracking

No charter violations. The only structural question — whether the base belongs on the manifest or
in the axis — is settled by the single-authority rule (D-1/D-2).

## Implementation Concern Map

### IC-01 — Synthesized-manifest evidence base

- **Purpose**: make the `--skip-lanes` manifest carry a real, deterministic evidence-window base
  resolved from target history, or none at all.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, NFR-003, C-001, C-002.
- **Affected surfaces**: `src/specify_cli/consolidation/entry_preflight.py`
  (`_synthesize_no_lane_manifest`, new private resolver), `wp_evidence.lane_evidence_window`
  (consumer, unchanged).
- **Sequencing/depends-on**: none.
- **Risks**: a too-loose pathspec would attribute another Mission's work; the resolver reads only
  `kitty-specs/<slug>/`. A git failure must not degrade into an empty window.

### IC-02 — Refusal text for an unresolvable window

- **Purpose**: keep the refusal and make its recovery honest for a Mission with no `lanes.json`,
  without losing the recorded-but-unpinned advice.
- **Relevant requirements**: FR-003, C-003.
- **Affected surfaces**: `src/specify_cli/consolidation/wp_evidence.py` (`_scan_lane` line,
  `_RECOVERY`), the module docstring's first verdict.
- **Sequencing/depends-on**: IC-01 (the recovery must not claim a shape the resolver just handled).
- **Risks**: pinned-text tests elsewhere read only the line-leading code; verify with the evidence
  suites listed above.

### IC-03 — Proof and docs

- **Purpose**: the pre-existing CLI nodes go green, the new module pins the behavior and its
  non-vacuity pairs, and the operator-facing docs and changelog match.
- **Relevant requirements**: SC-001..SC-004.
- **Affected surfaces**: `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`,
  `tests/consolidation/test_skip_lanes_evidence_window.py`,
  `docs/guides/how-to/missions/merge-mission.md`, `docs/changelog/unreleased/<pr>.fixed.md`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: the fixture change must stay a fixture-realism change (declare `owned_files`), not an
  assertion relaxation; the doc note must not promise completion where the evidence axis still
  (correctly) refuses.
