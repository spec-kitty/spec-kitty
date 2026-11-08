---
title: 'ADR: the upgrade worktree pass is plan-then-apply, and every registered migration must converge'
description: 'The upgrade worktree pass becomes a read-only plan step plus an apply step, and a run-twice check holds every migration and every upgrade to converge.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-08'
updated: '2026-11-08T00:00:00Z'
---

# The upgrade worktree pass is plan-then-apply, and every registered migration must converge

**Status:** Proposed (2026-11-08). The operator accepts or amends it on the pull request.

**Date:** 2026-11-08

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #7405: slice S2 of epic #3347, "extract `_upgrade_worktrees` and prove migrations convergent".
- #3347: upgrade/migration atomicity and recoverability (epic).
- #6549: a migration that is not needed on pass 1 and applied on pass 2 (the defect class).
- #7429: a non-convergent migration this check found (#6549 is the earlier, separately reported one).
- Related: #5934, #5712, #5472, #5470.

**Reader:** a maintainer who changes `spec-kitty upgrade` or writes a migration, and an agent doing
either. It assumes you know the migration ledger (ADR `2026-10-17-1`) and the worktree selection
rule (#5457, #7173).

## Context and Problem Statement

`src/specify_cli/upgrade/runner.py` is the most-fixed file in the upgrade surface: 51 changes in
three months, 35 of them fixes. Most of its control flow sat in one method,
`MigrationRunner._upgrade_worktrees` (radon F, 43). One loop decided which worktrees to touch,
synthesized metadata, ran each migration's `detect` / `can_apply` / `apply` with four exception
paths, tracked five per-worktree flags (dirty, held, errored, failed, migrated), recorded ledger
results, and then saved, stamped and committed each worktree. Every fix in that area had to reason
about the whole loop at once, and there was no unit to test below the runner.

Separately, nothing checked that a migration converges. ADR `2026-10-17-1` makes the ledger the
execution authority, and `detect()` is the guard that keeps a re-run safe (C-003). A record does
not always settle a migration, though: a clone-local record never travels, `skipped` and `failed`
do not settle, a structural reselection re-runs a recorded `runs_first` migration, and a
residue-safe successor stays unsettled until its predecessor records `success` (#6688). So
`detect()` is what stops a second run, and a migration whose verdict depends on state the run
itself moves (the version stamp, a fold an earlier migration performs) behaves differently on the
next run. #6549 is one such case. This change found another, #7429: on a 2.1.0 project, the second
`upgrade` deletes every generated `.claude/commands` file the first run installed, exit 0.

## Decision Drivers

* Each branch of the worktree loop should be testable on its own, without driving git.
* The preview and the run already share one selection rule (`worktree_dispositions`). The split
  must keep that.
* Behaviour preservation must be provable. Existing patch points (`runner.VersionDetector`,
  `MigrationRunner._record_migration_result`) and the dict `_upgrade_worktrees` returns are used
  by callers and tests.
* A shipped migration's bytes are its `content_hash` (DIRECTIVE_044). A convergence check may pin
  a defect but never fixes it by editing the shipped module.
* An allowlist is priced debt: each entry needs an issue and must fail once its defect is fixed.

## Considered Options

* **A.** Decompose `_upgrade_worktrees` into more private methods on `MigrationRunner`.
* **B.** Move the pass into its own module as a read-only plan step and an apply step, with the
  runner supplying what it owns as hooks.
* **C.** Move the pass and everything it calls (record, settle, schema stamp, commit) into its own
  module.

For convergence:

* **D.** Rely on per-migration tests that each migration's authors write.
* **E.** One generated check: every registered migration, run twice on representative fixtures,
  plus the whole upgrade run twice.

## Decision Outcome

**Chosen options:** "B" and "E".

1. **The worktree pass is two steps in `specify_cli.upgrade.worktree_pass`.**
   `plan_worktree_pass` reads only. It returns a `WorktreePassPlan`: the migrations that run on
   worktrees, the result each directory under `.worktrees/` reports when the pass writes nothing
   there, and the target worktrees (selected, with upgradeable state, in name order). It reads
   selection through `worktree_dispositions`, the rule the preview also reads. `WorktreePass`
   applies a plan and returns a `WorktreePassReport`. Per-worktree state is a `WorktreeRun`, and
   each per-migration branch (`detect`, `apply`, result handling, record) is its own method.
2. **The runner keeps what it owns and passes it as hooks.** These are the ledger and metadata
   record (`_record_migration_result`), metadata synthesis for a worktree without one (which still
   looks up `VersionDetector` in `runner`), and `_settle_worktree` (save, schema stamp, commit).
   `_upgrade_worktrees` and `upgrade_worktrees_only` keep their signatures and their returned dict.
3. **Every registered migration must converge, and so must the whole upgrade.**
   `tests/upgrade/test_migration_convergence.py` runs every registered migration twice, the way the
   runner runs it, on its own copy of each fixture (a fresh `init` project and a legacy 2.1.0
   project). The second run must change nothing in the tree, including `.git/config`, `.git/info`
   and `.git/hooks`. It also runs `MigrationRunner.upgrade` twice on each fixture and on an
   older-version lanes project, and the second run must apply nothing and change nothing.
   A floor on how many migrations each fixture selects as needed (`detect()` returns True, which leads to `apply()`), together with a check that
   `detect()` writes nothing, keeps the check non-vacuous.
4. **A non-convergent migration is pinned, never patched in place.** Per migration, the entry goes
   in `NOT_CONVERGENT` as a strict `xfail`. Per run, `KNOWN_EXTRA_PASS` names exactly the
   migrations the second run still applies, and the third run must then change nothing. Each entry
   names its follow-up issue. Both pins fail once the migration converges, so the entry is removed
   with its fix, which ships as a superseding migration (ADR `2026-10-17-1`, Amendment 2026-10-25).
   Today `NOT_CONVERGENT` is empty and `KNOWN_EXTRA_PASS` holds one entry, #7429.

### Consequences

#### Positive

* `_upgrade_worktrees` drops from radon F (43) to A. Every function in the new module is at most B
  (9). `_upgrade` drops from D (21) to C (15).
* Each worktree-loop rule has a unit test with fake hooks (`test_worktree_pass_unit.py`), and the
  end-to-end behaviour is pinned by a characterization net (`test_worktree_pass_characterization.py`)
  that was written before the move and did not change across it.
* A new migration is covered by the convergence check the moment it is registered, with no test of
  its own. A new #6549-class defect on the fixtures fails CI instead of reaching a user.

#### Negative

* The convergence check runs 285 cases, about 30 seconds on one worker. It is an integration
  test, not part of the fast tier.
* The check proves convergence only on its fixtures. A migration whose old state none of them
  carries runs as "not needed" twice and proves nothing. The floor guards the total, not each
  migration.
* `_settle_worktree` changed signature (it takes the `WorktreeRun` and the pass context). It is
  private and has no other caller.

#### Neutral

* `append_warnings`, `metadata_bytes` and `skip_as_applied` moved to `worktree_pass`, because both
  the pass and the main-checkout loop use them.
* The pass stays not sequenced-view aware (#6552, C-004), as before.

### Confirmation

The characterization net stays green across the split. The convergence check is green with its pins
in place, and it reproduced #7429 independently through `spec-kitty upgrade --yes`. Adding a fixture
for a migration family the current fixtures do not reach widens the proof without changing this
decision.

## Pros and Cons of the Options

### A. Private methods on `MigrationRunner`

**Pros:**

* The smallest diff, and no hook wiring.

**Cons:**

* The loop's state still lives in local variables threaded through methods, or on the runner
  instance, and there is still no unit below the runner to test.

### B. Plan and apply module, runner hooks

**Pros:**

* The plan is pure apart from reads, and the apply step tests with fakes.
* The runner keeps its persistence and commit rules in one place.

**Cons:**

* Three hooks to wire, and one more module.

### C. Move everything

**Pros:**

* The pass is fully self-contained.

**Cons:**

* It moves the schema stamp and commit code that the main checkout also uses, and it breaks the
  runner's patch points. That doubles the diff for no behavioural gain.

### D. Per-migration authored tests

**Pros:**

* Each test knows its migration's real legacy state.

**Cons:**

* Coverage depends on each author remembering, and nothing tests the whole-run interaction that
  #6549 and #7429 come from.

### E. Generated run-twice check

**Pros:**

* It covers every registered migration and the whole run, with no per-migration work.

**Cons:**

* Its proof is only as wide as its fixtures.
