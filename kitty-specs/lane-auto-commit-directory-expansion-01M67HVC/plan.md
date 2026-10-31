# Implementation Plan: Lane auto-commit takes exact paths, never a collapsed directory

**Branch**: `issue-6750-lane-auto-commit-directory-expansion` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/lane-auto-commit-directory-expansion-01M67HVC/spec.md`
**Issue**: spec-kitty/spec-kitty#6750

## Summary

`move-task --to for_review`'s lane collector reads `git status` with untracked
directories collapsed, forwards the directory to `safe_commit`, and git expands
it: the children land, then the post-landing guard (correctly built to compare
exact file paths) reports a superset and blames a hook that does not exist, while
the collector reports "could not auto-commit" for a commit that landed.

The change is three small, single-owner edits:

1. the collector reads untracked **files** (`status_entries(..., untracked="all")`),
   so the requested set is the exact file set git stages — one canonical expansion
   rule, the same one the `safe-commit` CLI already uses;
2. `preflight_commit` refuses a directory argument **before** any HEAD/index
   mutation, so no future caller can re-open the class (the invariant the guard's
   docstring already claims);
3. the collector distinguishes a *landed* recovery-class failure from a
   pre-mutation one, and reports the landed SHA.

The post-landing guard and `SafeCommitUnrequestedPaths` stay exactly as they are
(type, code, message shape) — after (1) the only remaining cause of a genuine
extra path is an external stager, so its attribution becomes true again. A real
hook negative control pins that.

## Technical Context

**Language/Version**: Python 3.11 (the CLI's `requires-python`; `uv` workspace, `src/` layout)
**Primary Dependencies**: typer, rich, `kernel.git` (the single owner of git argv/parsing), `mission_runtime` (`CommitTarget`, `OwnedCheckout`)
**Storage**: git (worktrees, index, refs); no database
**Testing**: pytest — unit + integration under `tests/`, git-fixture tests driving the real entry points; `pytest -n auto` for the touched subsets, no full heavy suite in-mission
**Target Platform**: Linux/macOS/Windows developer machines (path handling must stay POSIX-normalized; #2836)
**Project Type**: single (Python CLI/library)
**Performance Goals**: unchanged git invocation count on the healthy auto-commit path (NFR-001): one status probe, no extra round trip; the refusal check is a `Path.is_dir()` stat
**Constraints**: refusal must precede every mutation (NFR-002); public `safe-commit` CLI expansion unchanged (C-001); `SafeCommitUnrequestedPaths` contract unchanged (C-002)
**Scale/Scope**: 2 source files (`tasks_move_task.py`, `commit_helpers.py`) + tests; ~40 changed source lines

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
| --- | --- |
| Single canonical authority (DIRECTIVE_044) | Pass — the expansion rule is `status_entries(untracked="all")`, the same rule the `safe-commit` CLI uses; no second expansion helper is introduced. The seam check lives in `preflight_commit`, which already owns path validation. |
| Architectural alignment / boundaries (DIRECTIVE_001) | Pass — `cli/commands/agent/*` keeps asking the commit seam; `git/commit_helpers.py` keeps owning git argv and the commit contract; no new cross-layer import. |
| ATDD-first / red-first (DIRECTIVE_034) | Pass — the regression test drives the real collector and fails on today's code; a hook negative control pins the guard. |
| Locality of change / smallest viable diff (DIRECTIVE_024, RECONCILE_CHANGE_SCOPE_TENSIONS) | Pass — three surgical edits at the sites that already own the behaviour; no refactor of the collector, no new module. |
| Test hygiene (DIRECTIVE_041) | Pass — each new test guards a standing invariant (exact requested paths; truthful landed/failed reporting); no test is added for coverage alone. |
| Terminology canon | Pass — "lane", "work package", "deliverable", "owned checkout" used as the codebase defines them. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Pass — only the touched test subsets run locally; CI owns the full sweep. |
| Issue matrix (charter, Tracker Ticket Assignment Rule) | Pass — #6750 is the only citing issue and it is claimed + assigned; one row will carry the terminal verdict. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/lane-auto-commit-directory-expansion-01M67HVC/
├── spec.md              # Mission specification
├── research.md          # Discovery findings / reproduction
├── plan.md              # This file
├── tasks.md             # Task decomposition (created by /spec-kitty.tasks)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/
├── kernel/git/listing.py                        # status_entries() — untracked="all" expansion (unchanged, reused)
├── specify_cli/
│   ├── git/commit_helpers.py                    # preflight_commit() refusal + _assert_committed_paths_requested()
│   └── cli/commands/
│       ├── agent/tasks_move_task.py             # _mt_commit_lane_deliverables() collector seam
│       └── safe_commit_cmd.py                   # public CLI expansion (unchanged; cited as the canonical rule)

tests/
├── specify_cli/cli/commands/agent/              # collector-level regression + hook negative control
└── specify_cli/git/                             # preflight refusal unit/integration
```

**Structure Decision**: single project, `src/` layout. Tests follow the existing
mirrors: collector behaviour next to the move-task tests
(`tests/specify_cli/cli/commands/agent/`), the commit-seam refusal next to the
existing `safe_commit` tests under `tests/specify_cli/git/` (or the existing
`tests/tasks/test_move_task_git_validation_unit.py`-style module where the
`git add`/index assertions already live).

## Complexity Tracking

No charter violations. The one deliberate asymmetry: the collector *expands*
while the seam *refuses*. Justified in the spec's Intent Summary — recovery of an
implementer's deliverables must keep working, while a raw directory request is a
caller bug that must not reach git. Both paths are pinned by tests.

## Implementation Concern Map

### IC-01 — Collector requests exact files

- **Purpose**: stop the collector from ever handing a directory pathspec to the commit seam, by reading untracked entries expanded to files.
- **Relevant requirements**: FR-001, NFR-001, SC-001
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_move_task.py::_mt_commit_lane_deliverables` (status read), `_lane_deliverable_paths` (unchanged contract: absolute paths), `tests/specify_cli/cli/commands/agent/`
- **Sequencing/depends-on**: none
- **Risks**: a lane with a very large untracked tree expands to many paths (already true for the CLI); the `.zig-cache/`-style sweep remains (C-003, deferred). `_lane_deliverable_paths` must keep handling renames with both sides.

### IC-02 — Preflight refuses a directory request before mutation

- **Purpose**: make "the requested set is exact files" a seam invariant any caller must satisfy, failing before HEAD/index move with a truthful files-only message.
- **Relevant requirements**: FR-002, NFR-002, C-002, SC-003
- **Affected surfaces**: `src/specify_cli/git/commit_helpers.py` — new `SafeCommitDirectoryArgument(SafeCommitError)` (`SAFE_COMMIT_DIRECTORY_ARGUMENT`) next to `SafeCommitPathPolicyError`, raised in `preflight_commit` after path normalization and before the `.worktrees/` policy / protection checks; `safe_commit` inherits it because every path already flows through `preflight_commit`.
- **Sequencing/depends-on**: none (independent of IC-01)
- **Risks**: must not fire for a symlinked directory (single `120000` entry), for a deleted tracked file, or for a path that merely shares a prefix with a directory. Must sit after absolute→relative normalization so the message names a repository-relative path.

### IC-03 — Truthful landed-vs-failed reporting

- **Purpose**: the collector must never describe a commit that landed as an untouched failed attempt, and must say what state the repository is in.
- **Relevant requirements**: FR-003, FR-004, SC-002
- **Affected surfaces**: `tasks_move_task.py` collector `except` arm — catch `SafeCommitRecoveryFailed` (parent of `SafeCommitUnrequestedPaths` / `SafeCommitIndexResidue`) first and render "commit <sha> landed on <ref>, but …"; keep the current advisory for every other exception. `commit_helpers.py` message text stays truthful for the genuine hook case (asserted, not restated).
- **Sequencing/depends-on**: IC-01 (the fixture that proves the silently-landed case)
- **Risks**: the collector is best-effort by design (the readiness guard stays authoritative) — do not turn a warning into a hard failure for a landed commit; do not swallow the SHA.
