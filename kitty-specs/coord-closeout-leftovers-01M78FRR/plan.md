# Implementation Plan: Coordination closeout leftovers

**Branch**: `kitty/mission-coord-closeout-leftovers-01M78FRR` (lands on `fix/7598-coord-closeout-leftovers`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/coord-closeout-leftovers-01M78FRR/spec.md`

## Summary

Five closeout defects on the coordination path, each fixed red-first through the CLI entry
point the operator uses, plus three approved folds. Grounding: `research/code-grounding.md`
(section 7 supersedes earlier proposals). Operator rulings: `decisions/`.

1. **#7491**: persist the post-projection coordination tip with the reconciliation PASS anchor;
   a `--resume` whose landing is verified starts the late window there (when it is an
   ancestor of the live coordination tip), otherwise at today's pre-mutation snapshot.
2. **#4041**: a new `spec-kitty archive reclaim <mission>` command that removes the coordination
   worktree (through the existing teardown seam), deletes the coordination branch with a
   tip-bound `LANDED_INTENT` delete after an absorption proof, and flattens and commits the
   marker. One new named `operator_intent` caller in the routing-gate pin (ruled).
3. **#5867**: the squash projection proof returns `(path, reason)` per failing path; the gate
   renders a new error code, the paths (capped at 20) and a remedy per reason.
4. **#7599**: accept's local-mode "Next steps" keys on "lanes or a coordination branch still to
   consolidate" and names where the record went.
5. **#7600**: `RefAdvanceDirtyWorktreeError` text becomes neutral; consolidate (fresh/resume),
   `--abort`, and the review fast-forward each append their own remedy; the abort kept-record
   message varies by outcome.
6. **Folds**: #4380 item 2 (truthful marker-kept teardown text), stale squash-refusal rollback
   comment (`phase_gate.py:347-355`).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); git >= 2.38 for the absorption proof (fails closed below)
**Storage**: `.kittify/runtime/merge/<mission_id>/state.json` (one new optional field); `meta.json` marker; `.kittify/archive/archived-missions.jsonl` (read only)
**Testing**: pytest; red-first through `spec-kitty consolidate` / `--resume` / `--abort`, `accept`, `archive reclaim`; real tmp git repos via `tests/terminus/conftest.py` builders; targeted architectural gates (`research/code-grounding.md` §6)
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single (CLI)
**Performance Goals**: `archive reclaim` < 5 s for one Mission (NFR-005)
**Constraints**: one rollback authority (C-001), gates not weakened (C-002), destructive guard (C-003), placement untouched (C-004), complexity <= 15
**Scale/Scope**: ~10 source modules, 5 issues + 3 folds

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | PASS: reclaim reuses `teardown_coordination_topology`, `guarded_branch_delete`, `flatten_coordination_metadata`, `is_absorbed`; no second rollback path |
| Architectural alignment | PASS: `missions/_archive.py` stays record-only; reclaim lives in a CLI-layer service module |
| ATDD / red-first (SO 4, C-011) | PASS by construction: every WP's first commit is a failing test through the entry point |
| Gate discipline (SO 5) | PASS: no new gate; one ruled entry added to the existing named-intent pin |
| Tidy-first (SO 2) | PASS: WP01 is a behaviour-preserving enabler (PASS-anchor clearing helper) before the #7491 change |
| Tracers (SO 3) | Seeded in `traces/` |
| No version numbers in scope | PASS |
| Terminology | PASS: Mission; "primary" and "merge" senses named in new text |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS: targeted files only |

Post-design re-check: PASS. One recorded risk (below) may need a mid-mission escalation.

## Project Structure

### Documentation (this mission)

```
kitty-specs/coord-closeout-leftovers-01M78FRR/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/cli-refusals.md
├── research/ (code-grounding.md, foldable-issues.md, repro_7491.py.txt)
├── decisions/, traces/, checklists/
└── tasks.md, tasks/  (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── state.py               # +coord_tip_after_projection; clear helper for the PASS anchor pair
├── phase_gate.py          # persist tip with PASS; squash refusal paths + code; stale comment
├── phase_teardown.py      # _late_window_base resume arm; #4380 item 2 text
├── rollback.py            # use the clear helper; mode-aware remedies; outcome-aware abort text
├── executor.py            # restore the tip with anchor_before
├── bookkeeping_projection.py  # unlanded_projected_paths (reasons)
├── _constants.py          # SQUASH_PROJECTION_NOT_LANDED
src/specify_cli/cli/commands/consolidate.py   # abort kept-record message by outcome
src/specify_cli/cli/commands/archive.py       # `reclaim` subcommand; create prints pointer
src/specify_cli/missions/archive_reclaim.py   # NEW: reclaim service (CLI layer, not _archive.py)
src/specify_cli/git/ref_advance.py            # neutral RefAdvanceDirtyWorktreeError text
src/specify_cli/cli/commands/agent/workflow.py  # review fast-forward appends its own remedy
src/specify_cli/acceptance/__init__.py        # _build_acceptance_instructions local arm
tests/consolidation/, tests/coordination/, tests/specify_cli/..., tests/architectural/test_destructive_op_routing.py (pin)
docs/api/cli-commands.md, docs/changelog/unreleased/
```

**Structure Decision**: single CLI project; files above are the complete touch set.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New `operator_intent` caller in the routing-gate pin | A squash-landed coordination branch has commits on no other ref; a no-intent delete always refuses | Operator ruling (Decision 01M78G5TMBJWFRE1ZPVSS2ATKN); `LANDED_INTENT` + `expected_tip` keeps a keep-record of any unique commits, so nothing is lost |

## Risks

- **R1 (RESOLVED, Decisions 01M78HNKEQPPZMY24JZVJG2MNF and 01M78JC7ZBJM0CY442BKDGBP7V): measured, `is_absorbed` refuses every squash-landed case; reclaim uses the recorded landing instead: `merged_at` + live coordination tip at or behind `refs/spec-kitty/landed-coordination/<branch>`, written by consolidate (WP02) at PASS and advanced with proven late commits. Original note:** After a
  squash landing, the coordination branch may carry planning or `meta.json` bytes the target
  later changed, so `is_absorbed` (ancestor or merge-tree no-op) can say "not absorbed". WP04
  first measures this on a realistic fixture (a landed, archived coordination Mission). If the
  proof refuses the canonical case, implementation stops and escalates the proof choice before
  coding an alternative.
- **R2: `ref_advance.py` overlap with sub-epic C** (#7546 placement/safe-commit). Only the
  exception message changes; rebase conflicts resolved at closeout.
- **R3: `acceptance/__init__.py` overlap with C** (path-convention message). Only
  `_build_acceptance_instructions` and its caller's arguments change.

## Implementation Concern Map

### IC-01 — PASS-anchor pairing (tidy-first)

- **Purpose**: one place clears or restores the reconciliation PASS anchor, so a paired field
  cannot drift from it.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `consolidation/state.py`, `rollback.py` (830, 904, 969), `executor.py` (801-802)
- **Sequencing/depends-on**: none
- **Risks**: behaviour-preserving; AST rollback pin must stay green.

### IC-02 — Verified late-window base on resume (#7491)

- **Purpose**: the resume late window starts at the verified post-projection tip.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `state.py`, `phase_gate.py` (`_record_reconciliation_pass`), `phase_teardown.py` (`_late_window_base`, `_advance_approved_tip`), docstrings in `bookkeeping_projection.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: an unverified tip is unsound (challenger); guarded by `landing_verified_for_resume` and an ancestry check.

### IC-03 — Squash projection refusal names paths (#5867) + stale comment fold

- **Purpose**: the refusal carries a code, the paths and a remedy per reason.
- **Relevant requirements**: FR-009, FR-014
- **Affected surfaces**: `bookkeeping_projection.py`, `phase_gate.py`, `_constants.py`, `docs/api/cli-commands.md`, `tests/consolidation/test_executor_coverage.py`, `test_constants_seam.py`
- **Sequencing/depends-on**: none (touches `phase_gate.py` like IC-02: same lane)

### IC-04 — Archive reclaim (#4041)

- **Purpose**: reclaim an archived Mission's coordination triple through one command.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-008
- **Affected surfaces**: `cli/commands/archive.py`, new `missions/archive_reclaim.py`, `tests/architectural/test_destructive_op_routing.py`, `test_json_contract_enumeration.py`, `docs/api/cli-commands.md`
- **Sequencing/depends-on**: none
- **Risks**: R1.

### IC-05 — Honest abort and dirty-checkout remedies (#7600) + #4380 item 2

- **Purpose**: every abort refusal names its blocker and a remedy that completes the abort.
- **Relevant requirements**: FR-011, FR-012, FR-013
- **Affected surfaces**: `git/ref_advance.py`, `consolidation/rollback.py`, `cli/commands/consolidate.py`, `cli/commands/agent/workflow.py`, the consolidate surfaces that print `RefAdvanceError`, `phase_teardown.py:980-985`
- **Sequencing/depends-on**: IC-01 (shares `rollback.py`)

### IC-06 — Topology-aware accept "Next steps" (#7599)

- **Purpose**: accept never says "No merge needed" while lanes or a coordination branch remain.
- **Relevant requirements**: FR-010
- **Affected surfaces**: `acceptance/__init__.py`
- **Sequencing/depends-on**: none
- **Risks**: R3.
