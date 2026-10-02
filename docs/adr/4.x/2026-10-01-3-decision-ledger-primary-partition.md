---
title: 'ADR: the decision ledger is a PRIMARY-partition kind (reverses the #3928 COORD intent)'
description: 'DECISION_LEDGER is classified PRIMARY for every topology; decision events stay COORD; the index gets a union merge driver and a doctor repair.'
status: Accepted
date: '2026-10-01'
updated: '2026-10-02'
---

**Status:** Accepted

**Date:** 2026-10-01

**Deciders:** Stijn Dejongh (owner), through the operator ruling
`decision-ledger-partition` (Decision Moment `DM-01M3V4BXG1EP7JX83TM5K6WSJ8`) and the
sibling ruling `legacy-ledger` of Mission `coord-artifact-single-home-01M3V4BE`.

**Technical Story:** [#5023](https://github.com/spec-kitty/spec-kitty/issues/5023), Mission
`coord-artifact-single-home-01M3V4BE` (FR-009, FR-009a, FR-009b, FR-009c). Reverses the
classification chosen under [#3928](https://github.com/spec-kitty/spec-kitty/issues/3928).

---

## Context and Problem Statement

The Decision Moment ledger is the pair `decisions/index.json` and `decisions/DM-<ulid>.md`
under a Mission's directory (`MissionArtifactKind.DECISION_LEDGER`). Two facts disagreed:

- **The taxonomy said COORD.** #3928 classified the kind as COORD-partition,
  "single-writer coordination bookkeeping", on the theory that the ledger's writer resolved
  its directory through the coordination status surface. No ADR recorded that intent; it
  lived in code comments.
- **The code said PRIMARY.** #4966 (AC-D2) had already moved the ledger's own reads and
  writes onto the PRIMARY partition: `decisions/service.py::_ledger_dir` resolves
  `PRIMARY_METADATA` through `placement_seam(...).read_dir(...)`. Only the decision
  **events** (`status.events.jsonl`, `decisions.events.jsonl`) were written to the
  coordination surface.

The disagreement is what #5023 reported. `spec-commit` classifies by the taxonomy, so it
routed the ledger's files onto the coordination branch, while the writer kept producing
them on the PRIMARY partition. The ledger then forked from the Mission's own history, and a
coordination teardown could destroy the only committed copy.

This ADR is the durable record the #3928 intent never had. It is narrower than, and
separate from, [ADR 2026-06-19-1](../3.x/2026-06-19-1-coord-empty-surface-fallback.md): that
ADR governs the empty coordination surface, and its 2026-10-01 amendment links here instead
of hosting the reversal.

## Decision Drivers

- The taxonomy must describe the write side that already exists, not the reverse
  (read/write symmetry, [ADR 2026-06-24-1](../3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md)).
- A committed ledger must travel with its Mission's branches and survive coordination
  teardown.
- No automatic log merge (C-003), and no silent loss of an index entry (FR-011).
- Fix forward (C-004): Missions created before this change must be repairable.

## Considered Options

1. **Classify the ledger PRIMARY (chosen).** The taxonomy moves to match where the ledger is
   read and written today.
2. **Move the ledger's reads and writes to the coordination surface.** The code would move
   to match the #3928 classification.

These are the two options the operator ruling weighed (Decision Moment
`DM-01M3V4BXG1EP7JX83TM5K6WSJ8`); its `Other` slot was not used.

## Decision Outcome

Chosen option 1, because it is the only option that changes the taxonomy rather than the
writer. The writer and every reader of the ledger content were already PRIMARY (#4966);
option 2 would have reversed that work and put the ledger on a branch that lanes do not
carry and that consolidation tears down.

- **Partition.** `DECISION_LEDGER` is in `_PRIMARY_ARTIFACT_KINDS`
  (`src/mission_runtime/artifacts.py`). `_COORD_RESIDUE_DIRS["decisions"]` still maps the
  directory to the same kind; only the partition membership moved. `kind_is_coordination_residue`
  is therefore false for it, so `decisions/` is never reset as coordination residue.
- **Events stay COORD.** Decision events in `status.events.jsonl` and
  `decisions.events.jsonl` (`DECISION_LOG`) are unchanged. `doctor decisions` joins the two
  surfaces; the ledger content is PRIMARY and the event log is COORD.
- **Committers.** The ledger is committed by `spec-commit` and `accept` only. The commit
  router routes the ledger to the target branch. `accept` classifies the current Mission's
  uncommitted ledger files through the artifact taxonomy
  (`acceptance/ledger_dirt.py::mission_decision_ledger_files`), commits them, and still
  fails closed on any other dirt, including another Mission's ledger. The consolidation
  dirty gate now refuses uncommitted ledger files instead of resetting them as residue;
  its message names `accept` or `spec-commit`.
- **Index merge driver.** The index travels with lane branches, so concurrent additions
  conflict on `decisions/index.json`. A `spec-kitty-decision-index` driver
  (`consolidation/drivers.py::union_decision_index`, run by `run_decision_index_driver`,
  command `spec-kitty merge-driver-decision-index`) takes the keyed union of `entries` by
  `decision_id`; a same-id collision resolves with the fold precedence in
  `decisions/index_fold.py`, so a terminal status beats `open`. `DM-*.md` needs no driver:
  each file is ULID-named and written once. The registration surfaces are `.gitattributes`
  (`kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index`), the `init` seed,
  and the migration `m_4_0_0rc5_decision_index_merge_driver` for already-initialised
  clones. The planning-recency resolver skips driver-covered paths so it cannot overwrite
  the union result. The `test_merge_reconciliation_class_guard.py` single-writer ruling for
  `decisions/` was amended to say so.
- **Fix-forward for pre-fix Missions.** A Mission whose ledger was committed only on the
  coordination branch is reported by `doctor decisions` as
  `DECISION_LEDGER_ONLY_ON_COORDINATION`. `doctor decisions --repair` copies the missing
  `DM-*.md` files and merges the index entries into the PRIMARY ledger additively (same
  `union_decision_index`, under the ledger's lock), and creates **no** commit; the operator
  commits with `spec-commit` or `accept`.
- **Teardown refusal.** The bookkeeping projection excludes PRIMARY kinds, so a
  coordination-only ledger would be destroyed with the coordination triple. Both
  `coordination/teardown.py::teardown_coordination_topology` and the consolidation
  preflight (`consolidation/executor.py::_pre_mutation_safety_preflight`) therefore refuse
  with `COORDINATION_LEDGER_UNREPAIRED` until the ledger is repaired. Nothing is mutated on
  refusal.
- **Fork posture.** `doctor decisions` and `agent decision verify` detect a forked decision
  event stream (`DECISION_LOG_FORKED`) from refs and worktrees through one detector,
  `decisions/fork.py::detect_decision_forks`. `--repair` never drops an entry whose events
  exist on either surface and never re-sequences a forked log (C-003); on a fork it prints
  the reconcile steps and exits 1.

### Consequences

#### Positive

- The taxonomy, the writer and the committers agree; `spec-commit` no longer forks the
  ledger onto the coordination branch.
- A committed ledger lands on the target branch and survives coordination teardown.
- Concurrent lane additions to the index merge without losing an entry.

#### Negative

- Behaviour change for coordination-routed Missions: an uncommitted ledger now blocks the
  consolidation dirty gate instead of being reset. That is intended; the message names the
  committers.
- Every reader that classified `decisions/` as residue flipped (commit router grouping,
  accept gate, retrospect, record-analysis, implement, move-task, auto-rebase, rollback,
  ordering, workspace teardown, bulk-edit diff check, and others). Non-coordination
  topologies (`lanes`, `single_branch`) keep today's verdicts (C-008).

#### Neutral

- Decision events and the status log are untouched; the single-writer posture still holds
  for them.

### Confirmation

- Focused reader tests for each flipped site, the red-first characterisation for the
  non-coordination topologies, and the merge-driver round-trip test.
- `tests/integration/test_coord_single_home_workflow.py`, whose accept leg lands an
  uncommitted ledger on the target branch tip.
- `tests/architectural/test_merge_reconciliation_class_guard.py` and the write-surface
  placement guard, both updated in the same Mission.

## Supersession

This ADR **reverses the classification half of #3928** for `DECISION_LEDGER` only. #3928's
other classifications stand. It does not supersede
[ADR 2026-09-24-2](../3.x/2026-09-24-2-coord-read-fail-closed.md), whose list of
coord-partition kinds carries a dated pointer to this ADR.

## Links

- Related: [ADR 2026-06-19-1](../3.x/2026-06-19-1-coord-empty-surface-fallback.md), its
  2026-10-01 amendment (the single-home write rule).
- Seam page: [The Artifact Placement Seam](../../architecture/artifact-placement-seam.md),
  "Worked example: `DECISION_LEDGER` moved COORD to PRIMARY (2026-10-01)".
- Research: `kitty-specs/coord-artifact-single-home-01M3V4BE/research.md` (D12 to D15).
- Contract: `kitty-specs/coord-artifact-single-home-01M3V4BE/contracts/doctor-decisions-fork-report.md`.
