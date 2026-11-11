# Implementation Plan: Coordination doctor scope and decisions runtime lock hygiene

**Branch**: `kitty/mission-doctor-scope-lock-hygiene-01M75NSF` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: [spec.md](spec.md), grounding [research/code-grounding.md](research/code-grounding.md)

## Summary

Two independent bug fixes behind one sub-epic (#7549):

1. **`doctor coordination` scope (#7552).** `--fix` refuses unless the operator names `--mission <handle>` or opts into
   `--all-missions`; `--mission` also scopes the stranded-revert check and fixer; discovery adds Missions held only by a
   coordination worktree and Missions present only on their own Mission branch (read from the ref, no checkout).
2. **Decisions runtime lock hygiene (#7498, #7540 item 5).** The lock owner (`decisions/lock.py`) ensures a clone-local
   exclusion in the common-dir `info/exclude` before acquiring, so no checkout role lists it; `safe_commit`'s path policy
   refuses to stage it (the one choke point every Spec Kitty commit goes through, and the reason an exclude alone is not
   enough: it stages with `git add --force`); reset-obstruction messages describe file state in words.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich; `kernel.git.listing` (`tree_paths`, `blob_at`), `core.git_ops.exclude_from_git_index`
**Storage**: git refs and files (`meta.json`, `info/exclude`)
**Testing**: pytest with real git repositories in `tmp_path`, `typer.testing.CliRunner` over the doctor app
**Target Platform**: Linux, macOS, Windows (paths via `pathlib`, git via `kernel.git`)
**Project Type**: single project (CLI)
**Performance Goals**: NFR-001 / NFR-002 (bounded git reads, one exclude write per clone)
**Constraints**: C-001..C-005 (no lock unlink, no rollback change, read-only without `--fix`, canonical selector, no new ratchet)
**Scale/Scope**: two source areas, ~5 files each

## Charter Check

- **Single canonical authority**: discovery stays on the placement seam (`missions/_read_path_resolver.py` gains the one
  branch-only reader, beside `coord_worktree_mission_names`); the lock predicate stays `coherence.is_decisions_runtime_lock`
  (reused, not copied); the lock filename stays `decisions/lock.LOCK_FILENAME`.
- **Architectural alignment**: `git/ref_advance.py` keeps zero `specify_cli` imports (C-003 of that module); the label fix
  uses `StatusEntry` state only. `safe_commit` already imports `specify_cli` helpers.
- **ATDD / red-first (Standing Order 4)**: each WP commits failing tests through the pre-existing entry points first
  (`doctor coordination` CLI, `spec-commit` CLI, a real decision write), then the fix.
- **Campsite (Standing Order 2)**: `_coordination_doctor._resolve_mission_dirs` leaves the walker-gate legacy allowlist
  if it stops walking `kitty-specs/` itself (drain, not a new gate).
- **No new gates (C-005)**: none added.
- No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-scope-lock-hygiene-01M75NSF/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
├── checklists/requirements.md
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/doctor.py                 # --all-missions option, help text
src/specify_cli/cli/commands/_coordination_doctor.py   # scope gate, scoped strand check, discovery records
src/specify_cli/missions/_read_path_resolver.py        # branch-only Mission reader (placement seam)
src/specify_cli/{coordination,consolidation,core,cli,runtime}/...   # remedy strings naming --mission
src/specify_cli/decisions/lock.py                      # ensure exclusion before acquire
src/specify_cli/git/commit_helpers.py                  # path policy refuses staging the lock
src/specify_cli/git/ref_advance.py                     # obstruction label in words
tests/specify_cli/cli/commands/test_doctor_coordination_scope_7552.py   (new)
tests/decisions/test_runtime_lock_hygiene_7498.py                      (new)
tests/git/... (safe_commit refusal)
```

**Structure Decision**: single project; the two areas share no file, so they become two independent work packages.

## Design decisions

- **D-1 `--fix` with no scope refuses** (`COORDINATION_FIX_SCOPE_REQUIRED`, exit 1, nothing mutated), not an interactive
  prompt: agents run the CLI non-interactively (Decision Moment `01M75NVX2D22SPCRPWBARSFHPQ`).
- **D-2 `--mission` + `--all-missions`** refuse as `COORDINATION_FIX_SCOPE_CONFLICT`, exit 1.
- **D-3 Scope filter on repo-level findings**: the stranded-revert findings carry `extra["mission_id"]`; under
  `--mission` keep only the resolved Mission's. Git-version and tracked-`.worktrees/` checks are read-only and stay.
- **D-4 Discovery records**: the per-Mission loop iterates `(meta, mission_dir | None)` records. Sources, in order, unique
  by directory name: the root checkout's `kitty-specs/*` (today's walk), coordination-worktree-held directories
  (`coord_worktree_mission_names`), then branch-only Missions. Only a root-checkout directory gets `meta_path` (the
  `NEVER_CREATED` flatten edits that file); no other record is ever flattened.
- **D-5 Branch-only reader** (`_read_path_resolver.branch_only_mission_metas`): for each local `refs/heads/kitty/mission-*`
  that is not a lane branch, list `kitty-specs/*/meta.json` on that ref, skip names already present on disk, read the
  blob, and keep it only when its `mission_branch` or `coordination_branch` equals that branch (FR-007). Unreadable or
  malformed entries become a warning finding (`COORDINATION_BRANCH_META_UNREADABLE`), never a crash. Read-only.
- **D-6 `--mission` on a branch-only Mission**: the canonical resolver is asked first; only on `MissionNotFoundError`
  are branch-only records matched by exact `mission_id`, mid8 or `mission_slug`; more than one match is
  `AMBIGUOUS_HANDLE`. Same ladder, one extra source, no fallback to "all".
- **D-7 Remedy strings** that tell the operator to run `doctor coordination --fix` name `--mission <handle>` when the
  Mission is known, else `--mission <handle>` as a placeholder.
- **D-8 Lock exclusion** is the pattern `**/kitty-specs/*/decisions/index.json.lock` (matches any monorepo depth, like the
  predicate's `(?:^|/)` anchor), appended once to the common-dir `info/exclude` by `decisions_lock` before the OS lock is
  taken. Best-effort (`exclude_from_git_index` already swallows `OSError`).
- **D-9 Commit backstop**: `preflight_commit` step 6a refuses any requested path for which
  `coherence.is_decisions_runtime_lock` holds, with `SafeCommitPathPolicyError` (new reason text, same code
  `SAFE_COMMIT_PATH_POLICY`), before any index mutation. The owned index-only removal is exempt: `safe_commit` passes its
  validated `index_only_removals` through.
- **D-10 No automatic reclaim of a stale lock**: deleting or replacing the lock file breaks mutual exclusion for any
  process that already opened it (kernel G3). Prevention (D-8, D-9) removes the cause of the landing obstruction (a branch
  that tracks the lock). Recorded as an interpretation the operator may overturn.
- **D-11 Obstruction label**: `ref_advance` renders an obstructing entry as `<path> (untracked, …)` / `<path> (ignored by
  git, …)` instead of the porcelain `?? `/`!! ` prefix.

## Implementation Concern Map

### IC-01 — Coordination doctor scope and discovery

- **Purpose**: `--fix` touches only named Missions and can find Missions held only by a branch or a coordination worktree.
- **Relevant requirements**: FR-001..FR-007, NFR-001, C-003, C-004
- **Affected surfaces**: `cli/commands/doctor.py`, `cli/commands/_coordination_doctor.py`, `missions/_read_path_resolver.py`,
  remedy strings across `src/`, `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py`
- **Sequencing/depends-on**: none
- **Risks**: existing tests that call `--fix` without a scope must add `--all-missions` (behaviour-preserving update);
  remedy-string tests pin exact text.

### IC-02 — Decisions runtime lock hygiene

- **Purpose**: the lock is never visible as dirt in any checkout role and never staged.
- **Relevant requirements**: FR-008..FR-011, NFR-002, C-001, C-002
- **Affected surfaces**: `decisions/lock.py`, `git/commit_helpers.py`, `git/ref_advance.py`, tests under `tests/decisions/`, `tests/git/`
- **Sequencing/depends-on**: none
- **Risks**: `test_lock_primitive_ban.py` (no raw locks added); a test fixture repo without `info/exclude`.
