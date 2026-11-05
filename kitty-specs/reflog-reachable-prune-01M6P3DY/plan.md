# Implementation Plan: Prune keeps commits that only a reflog still reached

**Branch**: `issue-7211-reflog-reachable-prune` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/reflog-reachable-prune-01M6P3DY/spec.md`
**Input**: Mission specification from `kitty-specs/reflog-reachable-prune-01M6P3DY/spec.md`

## Summary

`prune_landed` removes a landed worktree and deletes its branch. Both actions destroy a reflog (`git worktree remove` deletes `.git/worktrees/<id>/logs/HEAD`; `git branch -D` deletes the branch reflog), so a commit that only a reflog still reached becomes unreachable and the next `git gc` may collect it. The fix reads both reflogs before anything is removed, computes which of those shas will be reachable from no ref afterwards, and records each such commit whose patch is not already on the primary ref under `refs/spec-kitty/discarded/reflog/<sha>` (create-only, before the removal). A record that cannot be written refuses the removal, exactly as the existing detached-tip record does. A rebase landing contributes nothing, because its pre-rebase commits are patch-equivalent to commits on the primary ref.

## Technical Context

**Language/Version**: Python 3.11 (the package targets 3.11+; `uv`-managed environment)
**Primary Dependencies**: Typer/rich CLI, in-repo `kernel.git` seam (`run_git`, `GitCommandError`), `specify_cli.git.destructive_guard` (guarded remove/delete + create-only bookkeeping refs). No new third-party dependency.
**Storage**: Git object database and refs only; no other store.
**Testing**: pytest, real scratch git repositories (the existing landed-worktree suites build them), with the CLI entry point exercised for the red-first proof.
**Target Platform**: POSIX and Windows git; no `/proc` dependency added (the process probe stays as it is).
**Project Type**: single Python package (`src/specify_cli`), CLI-first.
**Performance Goals**: one `rev-list` for reachability plus at most one `git cherry` per commit that is unreachable after the prune; a normal landed branch adds no kept ref.
**Constraints**: no network operation (the prune stays offline); create-only ref writes; the landing proof and every guard verdict unchanged; additive JSON only.
**Scale/Scope**: one module (`src/specify_cli/workspace/landed_worktrees.py`), one guard helper, one CLI renderer, two test modules, and the docs the prune already owns.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: the reachability rule lives in `prune_landed`; the create-only ref write lives in `destructive_guard` beside `keep_detached_tip`, not duplicated in the workspace module.
- **Locality of change**: edits stay in `landed_worktrees.py`, `destructive_guard.py`, `_landed_worktree_doctor.py` and their tests. No new module, no new command, no schema migration.
- **ATDD-first / red-first**: the failing test is written through the CLI entry point (`doctor workspaces --prune`) on the issue's reproduction before the fix.
- **Terminology**: "primary ref" means the local `refs/remotes/origin/<primary>` the assessment already proves against; "kept reflog ref" means `refs/spec-kitty/discarded/reflog/<sha>`. No bare "merge"/"primary".
- **Gate discipline**: no gate, allowlist or assertion is weakened; the new tests are additive.

## Project Structure

### Documentation (this mission)

```
kitty-specs/reflog-reachable-prune-01M6P3DY/
├── plan.md              # This file
├── research.md          # git behaviour the rule depends on
├── spec.md              # Requirements
└── tasks.md             # Created by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/
├── workspace/landed_worktrees.py      # reflog candidates, reachability, keep set, PruneOutcome.kept_commits
├── git/destructive_guard.py           # keep_reflog_tip: create-only refs/spec-kitty/discarded/reflog/<sha>
└── cli/commands/_landed_worktree_doctor.py   # text + JSON rendering of the kept refs

tests/specify_cli/
├── workspace/test_landed_worktrees.py        # prune-level tests on real repositories
└── cli/commands/test_doctor_workspaces_prune.py   # red-first CLI proof
```

**Structure Decision**: the behaviour belongs to the existing landed-worktree pruner; the ref-write primitive belongs next to the guard's other create-only discarded refs. Nothing is added to the `kernel` layer: `run_git` already provides what is needed.

## Design

**Candidate set.** Read `git reflog show --format=%H HEAD` in the worktree and `git reflog show --format=%H refs/heads/<branch>`, both before anything is removed, and union the shas. A missing reflog contributes nothing (exit code non-zero, not an error). The candidates are reflog *entry* shas, so their ancestors are covered transitively.

**Reachability after the prune.** `git rev-list <candidates> --not <every surviving ref>` where the surviving refs are `for-each-ref refs/` minus `refs/heads/<branch>` (the branch this prune is about to delete). The worktree's `HEAD` is not a ref. Any candidate returned is reachable from no ref afterwards.

**Patch narrowing.** For each such candidate, `git cherry <primary-ref> <sha>`. Every line printed with `-` means the commit's patch is already on the primary ref (the pre-rebase half of a rebase landing) and it is not kept. Empty output (a merge commit, or an error) and any `+` line mean "not provably on the primary", so it is kept. The check can only decide to *skip a duplicate*, never to drop something it cannot prove.

**Write before destroy.** Each kept commit gets `refs/spec-kitty/discarded/reflog/<sha>` through a new guard helper `keep_reflog_tip`, which uses the same create-only bookkeeping write as `keep_detached_tip` and raises `DestructiveOpRefused(DESTRUCTIVE_OP_ONLY_COPY)` when it cannot write. In `_prune_one` the order becomes: re-assess → keep the detached tip (existing) → record reflog-only commits → remove worktree → delete branch. A failure at either record step removes nothing.

**Reporting.** `PruneOutcome` gains `kept_commits: tuple[str, ...] = ()`, serialised as the additive JSON key `kept_commits`, and the text renderer prints one `reflog-only commit kept at <ref>` line per entry. `kept_ref` keeps its current meaning.

**Idempotence.** The ref name is the sha, so re-running the prune after a partial run re-writes the same ref (accepted, never moved).

## Implementation Concern Map

### IC-01 — Reachability computation (workspace module)

- **Purpose**: derive the set of reflog-only commits that must be kept, from both reflogs, before anything is destroyed.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-002
- **Affected surfaces**: `src/specify_cli/workspace/landed_worktrees.py`
- **Sequencing/depends-on**: none
- **Risks**: a reflog read on a worktree git cannot open must degrade to "no candidates", never to a prune failure; `rev-list` with a large argument list should go through stdin as the guard's `_unique_commits` already does.

### IC-02 — Create-only ref write and prune ordering

- **Purpose**: make the record step atomic in practice: write every kept ref before the first destructive action, and refuse the removal if a write fails.
- **Relevant requirements**: FR-001, FR-005, C-002
- **Affected surfaces**: `src/specify_cli/git/destructive_guard.py`, `_prune_one` in `src/specify_cli/workspace/landed_worktrees.py`
- **Sequencing/depends-on**: IC-01 (needs the keep set)
- **Risks**: the guard's routing allowlist pins which callers pass `LANDED_INTENT`; `keep_reflog_tip` must not widen that set — it is a plain bookkeeping write, not a delete.

### IC-03 — Outcome reporting and CLI rendering

- **Purpose**: name every kept ref in the text report and in `--json`, additively.
- **Relevant requirements**: FR-006, NFR-003
- **Affected surfaces**: `PruneOutcome.to_json`, `src/specify_cli/cli/commands/_landed_worktree_doctor.py`, `docs/api/cli-commands.md` (the `doctor workspaces --prune` entry), module docstrings
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the CLI reference is a generated/checked surface; regenerate only the section this diff changes and verify with `scripts.docs.check_docs_freshness --ci`.

### IC-04 — Red-first proof and regression coverage

- **Purpose**: reproduce the issue through the CLI entry point, then pin both reflog paths plus the rebase-landing non-churn case.
- **Relevant requirements**: SC-001..SC-005, FR-007
- **Affected surfaces**: `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py`, `tests/specify_cli/workspace/test_landed_worktrees.py`
- **Sequencing/depends-on**: the red test is written before IC-01..IC-03
- **Risks**: `git gc --prune=now` in a test must run with reflogs expired (`gc.reflogExpire=now`) so the assertion proves refs, not reflogs; a positive control on the same fixture proves the record step is what keeps the object.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A patch-id check (`git cherry`) in addition to "keep every unreachable commit" | This repository lands by rebase, so every landing's reflog holds pre-rebase commits; keeping a ref per superseded commit pins those objects forever and slows `for-each-ref` for everyone | Recording every unreachable commit is simpler but turns the common landing into permanent ref churn; recording nothing is the defect |
