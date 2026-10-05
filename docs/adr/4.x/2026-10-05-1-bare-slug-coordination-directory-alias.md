---
title: 'ADR: a bare-slug coordination Mission has one exact directory alias set, and one directory on the target'
description: 'A coordination Mission with a bare primary directory owns two directory names; one resolver pairs them from recorded identity, and consolidate folds them into one directory.'
status: Accepted
date: '2026-10-05'
updated: '2026-10-05'
---

**Status:** Accepted

**Date:** 2026-10-05

**Deciders:** Stijn Dejongh (owner). Operator rulings of 2026-10-05 on the alias authority and on the end state (one directory on the target).

**Technical Story:** [#5651](https://github.com/spec-kitty/spec-kitty/issues/5651) (regression), [#5611](https://github.com/spec-kitty/spec-kitty/issues/5611) (nightly red), Mission `nightly-suites-green-01M44FEP` (Track A, WP01 to WP04; FR-001 to FR-006, FR-017).

**Readers:** maintainers of the consolidation and coordination code, and whoever lands this Mission's pull request.

---

## Context and Problem Statement

A coordination Mission whose directory under `kitty-specs/` is the bare slug (no `-<mid8>` suffix) is a genuine shape, documented in `coordination/transaction.py::_canonical_coord_mission_slug`. Its coordination branch still carries a canonical `<slug>-<mid8>` name. Such a Mission has **two directory names**: the primary directory `kitty-specs/<slug>/` and the composed coordination directory `kitty-specs/<slug>-<mid8>/`.

Commit `5b5699e500` ("give coordination artifacts one durable home") made `spec-kitty consolidate` seed the composed directory (`coordination/coord_seed.py::_run_merge_and_commit` writes `status.events.jsonl` and `status.json` there). Three places in the code still keyed on one name, so consolidation onto a protected target broke (#5651, the red of the nightly integration job, #5611). The failure has three layers; each hid the next:

1. **Commit routing.** The seed commit goes through the commit router, whose partition classifier compared the path's directory name with the bare slug. It did not recognise the composed directory's status files, grouped them with the PRIMARY partition, and the protected-branch refusal returned `no_op_wrong_surface`. The seed logged a warning and consolidate carried on with uncommitted files, ending in `MERGE_UNSAFE_WORKTREE_DIRTY`.
2. **Gate.** With the seed committed, the reconciliation gate's `_is_bookkeeping` (`consolidation/reconciliation.py`) did not treat the composed directory's status files as bookkeeping, so the gate failed and rolled the target back.
3. **Teardown.** `consolidation/phase_teardown.py` read the Mission's `mid8` from the coordination status directory, which holds no `meta.json`. The `mid8` was empty and the coordination worktree was never destroyed.

A fourth effect was visible only in the measurement: the squash carries the composed directory onto the target, so a Mission could end with two directories there (the primary one with all six files and the composed one with a strict subset of the event log). The composed directory holds more than the status pair: the seed carries every file of the Mission directory whose kind is not a primary-partition kind (`coordination/coord_seed.py`), that is the status pair, `decisions.events.jsonl`, `acceptance-matrix.json`, `issue-matrix.json` and `issue-matrix.md`, everything under `traces/`, and `tasks/<wp>/review-cycle-*.md`. The same Mission directory in the #2709 reproduction (`traces/mission-trace.md`) failed the gate for that reason.

Evidence: the regression bisects to `5b5699e500` (the sibling test passes at its parent). In this repository 0 of 50 coordination Missions have a bare primary directory, and 48 of 50 have the coordination branch equal to the Mission branch, so a composed directory rides to the target by default. The shape exists in hand-built fixtures; whether older Missions carry it is not measured (#2463 discusses them). Before this change the reproduction mocked `commit_merge_bookkeeping` and so never ran the real bookkeeping door; it now runs the real consolidation under both strategies with no mock of in-repository code.

## Decision

### 1. One exact alias set, from recorded identity, resolved in one place

`missions/_read_path_resolver.py::mission_dir_aliases(repo_root, mission_slug)` returns a `frozenset` of directory names: the slug as passed, plus the composed `<slug>-<mid8>` name when the literal primary directory's `meta.json` records a `mid8` or a `mission_id`. The composed name is built by the same composer the seed uses (verbatim, no stripping, no case folding), so the alias is byte for byte what the seed writes.

- **Exact, never inferred.** There is no prefix or suffix matching and no guess from the shape of the slug. A slug that already ends in its `mid8` yields a one-element set, so a canonical Mission's bare stem is never an alias.
- **Safe segment only.** An unsafe slug, or a recorded identity whose composed name is not one safe path segment (a separator, traversal, padding, a newline), yields the one-element set. Absent, malformed or unreadable metadata also yields the one-element set; the function never raises.
- **Why in this module.** It already owns the directory composers and the primary metadata read. Resolving identity inside `mission_runtime` would grow that module's shrink-only outbound ledger in a gate file that is out of scope. A new module would be a sixth composer.
- **Resolve once, classify purely.** The commit router resolves the set once per commit (`coordination/commit_router.py::_group_files_by_partition`, one `meta.json` read per commit that has files) and passes the names to the pure classifiers in `coordination/coherence.py` (`kind_across_mission_dir_names`, `is_coord_residue_churn`). `mission_runtime/artifacts.py` is unchanged.

### 2. The target ends with one directory

Every coordination-kind file of the composed directory rides the squash onto the target. The existing bookkeeping commit removes them: `consolidation/phase_bookkeeping.py::_phase_commit_and_assert` calls `_fold_alias_directory`, which uses `coordination_alias_files`, `assert_alias_events_preserved`, `assert_alias_files_preserved` and `remove_alias_files` in `consolidation/bookkeeping_projection.py`.

- **One predicate for "coordination-kind".** `coordination/coherence.py::is_coordination_kind_file` (a file the kind authority classifies to a kind that is not a primary-partition kind) is the predicate the seed uses to decide what to carry, the fold uses to decide what it may remove, and the gate leg uses to decide what is bookkeeping. The list is stated once, in the kind table.
- **Proof per file, all or nothing, before anything is deleted.** The status event log: every event id of the composed log is in the unioned primary log. `status.json`: a derived snapshot, rematerialised into the primary directory, no proof. Any other coordination-kind file: its bytes equal the primary directory's file at the same relative path, in the target checkout now, or at the run's pre-mutation target tip (`ConsolidationState.pre_mutation_refs`). The second leg is the one the product's own seed makes true: the seed copies a root-checkout file into the composed directory when the coordination branch lacks it, so an untouched seed copy equals the primary file as the run found it, even if the primary file has since changed. A symbolic link is never proven. A file that is not proven raises `AliasFileNotPreserved` (code `ALIAS_FILE_NOT_PRESERVED`, all unproven files named at once); an unprovable event raises `AliasStatusEventsNotPreserved`. Both are `AliasFoldRefusal`s, rendered by `spec-kitty consolidate` with exit 1 after the rollback, with nothing deleted.
- **What it removes.** Tracked coordination-kind files under the composed name that exist on disk, then the directories that unlinking emptied (`rmdir`, never recursive), up to and including the composed directory. Untracked files and every file that is not a coordination kind stay.
- It adds no git command and no run-state field: the door stages a tracked-but-missing path as a deletion in the same commit, and the rollback authority already covers that commit. It returns nothing for a Mission whose status directory is its primary directory.
- Measured through the real door: one directory on the target, the complete event set including the `done` event, the coordination branch and worktree gone, a clean root checkout. The `done` event lands in the primary directory's log.

### 3. The reconciliation gate exempts only coordination-kind files

`_is_bookkeeping` gains one leg, `_is_nested_alias_coordination_file`. It applies only when the claim's `planning_prefix` is a nested coordination-worktree path whose last segment (the composed name, read from the prefix, not rebuilt from the slug) differs from the Mission slug. It then accepts only a root-anchored path `kitty-specs/<that name>/<file>`, at any depth below the directory, whose file satisfies `is_coordination_kind_file`. No signature or call site changes.

This leg matters for `--strategy merge`, where the per-commit axis flags the seed, fold and `done` status commits, and for any squash run that does not go through the fold.

**Why the alias cannot let foreign content through (the closed-world argument).** The gate refuses any path it cannot attribute to an approved lane, so an exemption is a hole unless it is exact. Three rules close it, and each has a negative control:

- *The name is exact.* It is the composed directory the claim itself names. A different `mid8` on the same slug (`<slug>-01KX0001`) and another Mission's name (`other-mission-01KX0000`, `other-mission`) are content and fail the gate (`tests/consolidation/test_reconciliation.py`, `test_gate_fails_status_files_of_a_different_mission_directory`, `test_is_bookkeeping_keeps_non_coordination_kinds_and_foreign_names_as_content`). A slug with no recorded identity has no alias (`tests/specify_cli/missions/test_mission_dir_aliases.py`).
- *The record kind is restricted.* Existing code exempts a whole `kitty-specs/<slug>/` subtree for the primary name, so a plain alias would exempt `spec.md` and source under the composed name. Only coordination-kind files are exempt. `spec.md`, `plan.md`, `tasks/WP01.md`, `notes/plan.md` and `src/x.py` under the composed name fail the gate, and an integration test commits a planning file there and shows the target rolled back and nothing torn down, under both strategies (`tests/integration/test_merge_lane_planning_data_loss.py`).
- *The prefix must be nested and the path root-anchored.* A missing, root-form or malformed prefix leaves every verdict as before.

### 4. Teardown reads identity from the primary metadata

`phase_teardown.py` loads `meta.json` from `run.target_feature_dir`, as the neighbouring code does, not from the status directory. No alias is needed there.

### 5. A refused coordination seed commit stops consolidate

`SeedReport` (`mission_runtime/write_location.py`) gains a defaulted field `commit_refused`, set in `coord_seed.py` when the seed commit is not applied. `consolidation/entry_preflight.py::_resolve_run_status_dir` reads it and raises `_refuse_on_unapplied_seed_commit`: exit 1, error code `COORD_SEED_COMMIT_REFUSED` (`consolidation/_constants.py`), before the lock, the snapshots and any teardown. The message names the uncommitted files and says they are kept. A re-run retries the commit. The "no branch moved" wording reuses `_protected_refusal_footer`, so it is scoped to this run when an earlier merge record exists. The files are not deleted, which keeps the seed-retry design (I-SEED-10) intact. The reviewer measured that the old behaviour lost no status events; the change replaces a misleading dirty-worktree remedy with the real cause.

## Considered Options

1. **Alias set plus fold (chosen).** Keeps the composed coordination directory, fixes the three layers with one rule and restores the pre-regression end state of one directory.
2. **One directory name keyed on the primary directory.** No classifier change, but every Mission seeded since 2 October needs a read fallback to find its composed directory. Rejected.
3. **Alias without the fold.** Leaves a split status log on the target (two directories). Rejected.
4. **Refuse the bare-slug shape.** Changes a documented contract, and the shape is genuine. Rejected.
5. **A deletion commit before the squash.** Removes the coordination home mid-run and forces a re-seed. Rejected.
6. **Seed only when the coordination branch differs from the Mission branch.** 48 of 50 Missions would have no status home. Rejected.
7. **Filter the squash.** The squash is in `lanes/consolidation.py`, which another running Mission owns. Rejected.
8. **Thread the alias set through the claim object.** Edits outside the one function this Mission may change in `reconciliation.py`. Rejected in favour of deriving the name from `planning_prefix`.

## Consequences

- A bare-slug coordination Mission consolidates onto a protected target and lands one directory. The reproduction runs the real consolidation under both strategies.
- The gate leg and the fold are two mechanisms for one end state, and both use the seed's predicate for what a coordination file is. Under `--strategy merge` both are needed; under squash only the fold is.
- `reconciliation.py` gains one adjacent private helper next to the code mission #5668 works in. Flag it for the rebase.

### Residuals and follow-ups

Each is a known gap, not a hidden one.

| Residual | Follow-up |
|---|---|
| A coordination write made under the composed name AFTER the seed (a trace written, a matrix or review cycle updated during the Mission) is a file the primary directory does not hold, so the fold refuses with `ALIAS_FILE_NOT_PRESERVED` instead of carrying it into the primary directory. This is safe (nothing is deleted) but not complete: the post-checkpoint projection is keyed on the bare slug and never carries composed-name files. Carrying them forward, instead of refusing, is a product decision. | [#5751](https://github.com/spec-kitty/spec-kitty/issues/5751) |
| Resume after an interruption inside the fold still refuses for a bare-slug Mission. The refusal now says what recovers (`consolidate --abort`, then a fresh run), for deletions of any coordination-kind file under the composed name; making the resume itself work remains. | [#5748](https://github.com/spec-kitty/spec-kitty/issues/5748) |
| With the gate leg in place, the gate no longer backstops a skipped fold under squash. | [#5751](https://github.com/spec-kitty/spec-kitty/issues/5751) |
| Single-name anchors remain: the post-merge porcelain invariant in `phase_bookkeeping.py` (pinned by a test), the second classifier caller in the acceptance package, and the dead `planning_prefix` leg under coordination topology. | [#5751](https://github.com/spec-kitty/spec-kitty/issues/5751) |
| The fold's preservation refusals (`ALIAS_STATUS_EVENTS_NOT_PRESERVED`, `ALIAS_FILE_NOT_PRESERVED`) and the refusal for an uncomposed `coordination_branch` (`COORDINATION_WORKTREE_BRANCH_MISMATCH`) are rendered by `spec-kitty consolidate`, with exit 1. The second prints no recovery command: renaming the branch and correcting `coordination_branch` in `meta.json` and `mission_branch` in `lanes.json` recovers only once both corrected files are committed on the target, which was not proven safe to print blind. The shape cannot be minted (`coordination_branch_name` always composes, and 0 of 51 coordination Missions in this repository declare it), and a coordination status write already refused it before this Mission. Remaining: the code-lane path of `orchestrator-api consolidate-mission` has no seed backstop (only its planning-only path reaches it, as a `PREFLIGHT_FAILED` envelope without the cause text), and none of these refusals is rendered there. | [#5750](https://github.com/spec-kitty/spec-kitty/issues/5750) |
| Several tests build Missions with a shared over-mocked helper. | [#5749](https://github.com/spec-kitty/spec-kitty/issues/5749) |

Related, different mechanism (cross-reference only): #5638 (the rollback's byte-restore leaves tracked status files dirty) and #5644 (the guard that detects committed events lost from the worktree).
