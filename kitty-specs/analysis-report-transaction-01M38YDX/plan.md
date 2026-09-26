# Implementation Plan: Safe analysis report transactions

**Branch**: `fix/analysis-report-transaction` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)
**Input**: Approved repair intake and committed specification. Audience: software engineers reviewing transaction safety.

## Summary

Add an explicit `record-analysis --report-only` mode. Resolve the existing PRIMARY artifact placement, check material inputs and branch state before writing, use the canonical path-scoped commit router, and verify the committed outcome. Keep the default broad dirty-tree guard. Reuse current upstream's charter YAML authority and `git commit --only` staging preservation instead of reintroducing stash or a separate commit-tree authorization path.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Typer, pathlib, subprocess Git, canonical mission placement and commit router  
**Storage**: Existing Git repository, index, analysis-report.md and its input manifest  
**Testing**: pytest, real temporary Git repositories, injected failure boundaries, focused coverage  
**Target Platform**: Linux, macOS, Windows supported by existing CLI  
**Project Type**: Existing single Python CLI project  
**Performance Goals**: Bounded reads of material mission/governance inputs and Git state; no whole application tree hashing or network access  
**Constraints**: No stash, guard weakening, global runtime install, extra checkout, or unrelated source edits  
**Scale/Scope**: Recorder, report freshness authority, and canonical commit-layer qualification

## Constitution Check

- Canonical authority: placement_seam owns report home; commit_for_mission/safe_commit own commit authorization and mechanics; analysis_report owns shared input freshness.
- ATDD: first commit a failing real CLI acceptance test for unrelated partial staging; add material-input and failure regressions before implementation.
- Reuse upstream #4888 path-scoped commit rather than duplicate its transaction mechanics.
- Tracer files record source divergence, missing owned CLI flags, and limits.
- Reviewer differs from implementer; root arranges independent review at committed pins.
- Planning uses canonical configured plan template resolved with validated owned root. Research/setup-plan lack owned CLI options; supported spec-commit and next maintain artifact commits and runtime state. No hand-authored state events.

## Project Structure

### Documentation (this mission)

`kitty-specs/analysis-report-transaction-01M38YDX/`: spec, plan, research, data-model, three tracer files, runtime-generated task artifacts.

### Source Code (repository root)

- `src/specify_cli/cli/commands/agent/mission_record_analysis.py`: opt-in boundary, default guard preserved, truthful outcome.
- `src/specify_cli/analysis_report.py`: shared material dependency manifest and freshness comparison.
- `src/specify_cli/git/`: reuse existing safe commit; extract narrowly scoped snapshot/verification helpers here only if canonical ownership requires it.
- Tests in owning recorder, report freshness, and Git test surfaces.

**Structure Decision**: Keep report semantics at the report owner and branch/index mechanics at the Git owner. No second placement resolver or authorization policy.

## Transaction Design

1. Resolve mission and existing PRIMARY report home; require its checked-out declared target. Use canonical preflight before any report write. Refuse active Git operations, conflicts, unsupported index modes, path escapes, and a dirty report.
2. Build one explicit dependency manifest used by both freshness and transaction checks: current spec/plan/status-normalized tasks, WP definition content, authoritative charter, selected project config/mission definition and effective governance dependencies. Include absent-file sentinels so newly introduced overrides invalidate a report. Do not hash unrelated application files or runtime status logs. Unsupported external mutable governance must refuse opt-in rather than be silently trusted.
3. Read NUL-delimited Git status including both rename endpoints. Reject changes overlapping material inputs. Snapshot HEAD, relevant input hashes, and unrelated index entries/content before rendering. Preserve malformed-input errors before writes.
4. Recheck snapshots immediately before the canonical path-scoped commit. Git's `commit --only` creates the path-scoped commit view and preserves unrelated staging; do not own a competing index-lock/commit-tree implementation.
5. Verify the resulting parent, changed-path set, report content, input hashes, and unrelated index entries. If a concurrent writer is observed after a commit, return an explicit unqualified-commit recovery outcome with its SHA. Never reset HEAD or restore unrelated state over concurrent changes.
6. Surface written-but-uncommitted failures instead of suppressing them in opt-in mode. Preserve the original broad default behavior and its compatibility tests.

## Validation

Real Git scenarios: unrelated tracked/untracked changes; partial staging and flags; dirty charter/config/selected mission definition/spec/plan/tasks/WP/report; rename endpoints and newline paths; protected/wrong/detached HEAD; active operation/conflict; symlink escape; input/index/HEAD changes at transaction seams; rejecting hooks; unchanged report; linked caller with PRIMARY report placement. Assert commit paths and parent, staged blobs, working bytes, outcome and exit code. Mutate one material definition after success to prove freshness invalidation. Run recorder/freshness/Git suites and required fast baseline; disposition pre-existing failures separately.

## Complexity Tracking

No new authorization or commit implementation. Git protects its own index/ref write operations but arbitrary external editors do not honor a project lock. The bounded promise is detection at checked seams and truthful post-commit failure, not universal filesystem serializability. Atomic snapshots of every external writer are outside scope.

## Parallel Work Analysis

Implementation remains sequential in one existing lane: manifest and safety regressions → report-only transaction → integration and independent review. Parent review may run independently against immutable commits; no shared file edits by reviewers.
