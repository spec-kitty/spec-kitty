# Implementation Plan: a stray `.git` that is not a repository is not an anchor

**Branch**: `issue-7093-stray-git-anchor-not-a-repository` (planning base and merge target: the same branch; it reaches `main` through a PR) | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/stray-git-anchor-not-a-repository-01M6G9VN/spec.md`

**Branch contract (repeated per the plan prompt):** planning artifacts are on
`issue-7093-stray-git-anchor-not-a-repository`, this mission's planning base branch
and merge target are `issue-7093-stray-git-anchor-not-a-repository`, and completed
work merges into that branch — never into `main`.

## Summary

`specify_cli.mission_metadata._has_no_git_anchor` answers "is there a repository at or
above this folder?" by checking whether *any* `.git` entry exists there. A `.git`
*directory* that holds no `HEAD` is not a repository — git itself says `fatal: not a
git repository` for every path below it — but the check counts it, so `read_tracked_meta`
converts git's "no repository here" into the refusal signal `TrackedMeta(None,
unavailable=True)`, whose meaning is "git tracks this path but cannot give it back".
`build_baseline_feature_meta` then returns `None`, and the `2.0.6` sweep reports writing a
baseline it never writes.

The fix narrows the anchor to the two shapes that can hold history: a `.git` *pointer
file* (a worktree, submodule or separate-git-dir marker — still a repository the caller may
be unable to read, so it still refuses), or a `.git` *directory that holds `HEAD`* (git's
own marker of a repository). Any other `.git` entry is a name, not an anchor: the walk
continues upward, and when no repository anchor exists the answer is "nothing is tracked
here", which is what `read_tracked_meta` already documents and what the shared repair
needs. Nothing else changes: the tracked-copy seed, the index-only / corrupt /
staged-differs refusals and the dubious-ownership refusal all keep working.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib only (`os`, `stat`, `pathlib`); the existing git
subprocess in `read_tracked_meta` is untouched
**Storage**: files — `kitty-specs/<mission>/meta.json` and the `.git` anchors above it
**Testing**: pytest. Red-first at two levels: a unit test that builds the stray
non-repository `.git` above a Mission folder (fresh, environment-independent fixture) and
the pre-existing sweep test that must pass unchanged
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single
**Performance Goals**: one `stat` per ancestor, no directory listing, no extra git
subprocess (NFR-001, NFR-002)
**Constraints**: no edit to any module under `src/specify_cli/upgrade/migrations/`
(C-001, DIRECTIVE_044); no existing assertion touched (C-002); one owner for
"what does git hold" (C-003); ruff and mypy clean, diff-cover ≥ 90 % on changed lines
**Scale/Scope**: 1 production function in 1 file, 2 test files (additions only), 1
changelog fragment

Supply chain: no dependency decision, so DIRECTIVE_051 controls are not triggered.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority.** `mission_metadata` stays the ONE answer to "what does
  git hold" and keeps the ONE refusal signal; the fix narrows its anchor test instead of
  adding a second repository detector in a caller. The frozen sweep and its successor
  both consume the same answer unchanged. Status: pass.
- **Architectural alignment / archive freeze (DIRECTIVE_044).** No migration module is
  edited; the module whose bytes are its `content_hash` is not the fix site, and
  `SUPERSEDED_MIGRATIONS` remains the only way a shipped migration changes behaviour.
  Status: pass.
- **ATDD-first (ATDD-First Discipline, DIRECTIVE_034).** The defect gets its failing test
  through the production entry point (`read_tracked_meta` → `build_baseline_feature_meta`,
  and the frozen sweep's own `apply`) before the fix, committed red first. Status: pass.
- **Locality of change (DIRECTIVE_024).** One function in
  `src/specify_cli/mission_metadata.py`, plus tests and the changelog fragment. No caller,
  signature, return type or notice text changes. Status: pass.
- **Terminology.** Mission, `.git` anchor, tracked `meta.json`, refusal, baseline meta. No
  "feature". Status: pass.
- **No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION).** Targeted suites only:
  `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` and
  `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`, plus the migration and
  upgrade seams that consume `read_tracked_meta`. Status: pass.
- **Pre-existing Failure Reporting Rule.** Any red on the PR not attributable to this diff
  is reproduced on pristine `origin/main` and cited or filed. Status: to be applied at CI
  time.

## Project Structure

### Documentation (this mission)

```
kitty-specs/stray-git-anchor-not-a-repository-01M6G9VN/
├── spec.md
├── plan.md            # this file
├── traces/            # approach, design-decisions, tooling-friction
└── tasks.md / tasks/  # from the tasks step
```

### Source Code (repository root)

```
src/specify_cli/mission_metadata.py                              # _has_no_git_anchor: anchor = pointer file or .git dir with HEAD
tests/specify_cli/upgrade/test_read_tracked_meta_6673.py         # NEW test: stray non-repository .git is not an anchor (+ pointer-file control on the same fixture)
tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py       # NEW test: the frozen sweep repairs meta.json under a stray non-repository .git
docs/changelog/unreleased/<pr>.fixed.md                          # per-PR fragment
```

**Structure Decision**: single project; the change is one private helper in one module
that the upgrade seams already share, so no new module, package or seam is introduced.

## Implementation Concern Map

### IC-01 — The anchor test distinguishes a repository from a name

- **Purpose**: Stop a non-repository `.git` directory from turning "nothing is tracked
  here" into a refusal, without weakening the refusal for a repository git cannot read.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001,
  C-002, C-003
- **Affected surfaces**: `src/specify_cli/mission_metadata.py` (`_has_no_git_anchor`),
  `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`,
  `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py`
- **Sequencing/depends-on**: none
- **Risks**: (a) a symlinked `.git` or a `.git` file must stay an anchor, or the refusal
  tests regress; (b) an unreadable anchor must fail closed, not read as absent; (c) a
  `.git` directory with `HEAD` must still anchor even when the walk continues past a
  stray `.git` below it — covered by the walk order (first anchor wins).

## Complexity Tracking

No charter violations; the diff is one helper, two test additions and one changelog
fragment.
