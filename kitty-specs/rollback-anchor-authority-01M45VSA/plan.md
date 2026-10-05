# Implementation Plan: Rollback anchor authority (#5686, #5666)

**Branch**: `issue-5686-rollback-anchor` (lanes; local consolidate target) | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/rollback-anchor-authority-01M45VSA/spec.md`; grounding in [research/code-grounding.md](research/code-grounding.md).

Branch contract (from `setup-plan`): current branch `issue-5686-rollback-anchor`, planning/base `issue-5686-rollback-anchor`, merge target `issue-5686-rollback-anchor`. `branch_matches_target` is true. Publication is a PR from this branch to `main`.

## Summary

Make `consolidation/rollback.py` the only authority for the rollback anchor:

1. **Retire the second restore path (#5666).** Delete `phase_gate._rollback_target_after_failed_reconciliation`. A FAIL or REFUSE from the reconciliation gate already raises `typer.Exit(1)` inside the #5385 single door, so `_report_rollback` → `rollback_to_snapshot` CAS-restores against the *recorded* post tip and keeps a concurrent commit (`NOT_RESTORED`, moved by another actor). Widen the AST pin so that no `restore_branch_ref` call survives in the executor family outside `rollback.py`.
2. **Never re-anchor over an unexplained move (#5686).** The record gains per-branch *unsettled* marks. `begin_attempt` sets them; a RESTORED, ALREADY_AT_SNAPSHOT or KEPT_BY_OPERATOR rollback outcome clears them, and a reconciliation PASS clears the target's. An orderly exit is deliberately NOT settling. When an attempt starts, an unsettled branch whose live tip the record cannot explain keeps its recorded restore target and stays unrecorded. A read-only pre-check refuses with `UNEXPLAINED_BRANCH_MOVE` before the coord-strand heal, the attestations and the claim. The phase recorder also refuses to record a branch whose entry tip was not the expected one, which closes the between-phase foreign interleave (FR-011).
3. **Adopt a kill-left advance when provable.** `advance_branch_ref` and `advance_branch_ref_for_commit` report (branch, old, new) to an injected sink *before* the compare-and-swap write. The rollback module persists them fail-closed as a per-branch chain `[base, new1, ...]`. A live tip in the chain counts as this run's post tip only if the chain's base is the tip the record expected. The resync of a restore accepts a checkout already at the restore target's content, which covers a kill between `update-ref` and the resync (FR-012).
4. **Never deadlock.** `consolidate --abort --release-branch <b> --release-reason <text>` records an operator release bound to the live SHA. The authority reports the branch `KEPT_BY_OPERATOR`, an OK kind that never counts as restored, and the abort success line names it.
5. **Carry the restore target.** `_restore_target` derives from the previous restore target, not the snapshot, so an operator's move made between attempts survives later attempts.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git CLI (subprocess); `kernel.atomic.atomic_write`
**Storage**: `.kittify/runtime/merge/<mission_id>/state.json` (`ConsolidationState`, dataclass with `from_dict` known-field filter)
**Testing**: pytest with real temp git repos (no git mocking), `tests/consolidation`, `tests/terminus`, `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`, `tests/git`, `tests/architectural/test_single_rollback_authority.py` (lives in `tests/consolidation/`), specific architectural gate files
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single
**Performance Goals**: rollback NFR-001 bound unchanged (< 2 s); at most one extra atomic `state.json` write per `advance_branch_ref` inside an attempt
**Constraints**: C-001..C-005 from the spec (single authority, no destructive recipe, no edits to `reconciliation.py`, no edits to the coord status-write seam, no new size gates)
**Scale/Scope**: about 8 source files, about 10 test files

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | Removes the second restore path. All anchor logic lives in `rollback.py`. |
| ATDD / red-first (SO #4, C-011) | PASS | #5762's tests are the reds for FR-001 and FR-004. Each WP commits its new failing test before the fix. CLI-level reds for FR-005, FR-006 and FR-008. |
| Tidy-first enabler (SO #2, DIRECTIVE_025) | PASS | WP01 (atomic record write and recorder seam extraction) is behaviour-preserving and precedes the behaviour changes. |
| Architectural gate discipline (SO #5) | PASS | The AST pin is widened, with a self-mutation case, and starts empty (no allowlist). |
| No full heavy suites in mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | PASS | Targeted directories plus named gate files only. |
| Terminology canon | PASS | Mission and consolidate terms only. |
| Git discipline (PRs only, operator merges) | PASS | Draft PR to `main`; never merged by an agent. |

No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/rollback-anchor-authority-01M45VSA/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── data-model.md
├── quickstart.md
└── tasks.md / tasks/WP*.md   (tasks phase)
```

Contracts: none. This mission changes no HTTP/API interface; the CLI change is a new `--abort` option, documented in data-model.md and the PR. `meta.json` records `"contracts": "none"`.

### Source Code (repository root)

```
src/specify_cli/
├── git/ref_advance.py                 # advance-intent sink (ContextVar), reported before the CAS write; restore resync accepts a checkout already at the target
├── consolidation/
│   ├── state.py                       # new fields; atomic save_state
│   ├── rollback.py                    # unsettled marks, intent chains, effective post, carried restore target, release outcome
│   ├── phase_claim.py                 # begin_attempt with this process's pre-claim tips
│   ├── executor.py                    # early UNEXPLAINED_BRANCH_MOVE pre-check; intent sink installed around the door span
│   ├── run_state.py                   # recorder: entry-expected taint check, per-branch intent clearing
│   └── phase_gate.py                  # retire _rollback_target_after_failed_reconciliation
└── cli/commands/consolidate.py        # --release-branch / --reason on --abort; truthful success line
tests/
├── consolidation/                     # repro (markers dropped), rollback authority, wiring, refuse-restores, AST pin
├── terminus/test_rollback_door.py     # door FAIL with concurrent commit
├── git/                               # advance intent sink
└── specify_cli/cli/commands/test_consolidate_abort_rollback.py  # release, kill-left adoption/refusal
docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md  # dated follow-up 2026-10-05
CLAUDE.md                              # remaining-second-restore-paths sentence
```

**Structure Decision**: single project, existing module layout. No new modules.

## Implementation Concern Map

### IC-01 — Atomic record and recorder seam (tidy-first)

- **Purpose**: make `save_state` atomic, since the new marker and intent writes land inside the kill window, so a torn `state.json` can never make `--abort` unreadable. Expose the attempt hooks without behaviour change.
- **Relevant requirements**: NFR-001, NFR-004
- **Affected surfaces**: `consolidation/state.py`
- **Sequencing/depends-on**: none
- **Risks**: Windows rename semantics; `atomic_write` is already used repo-wide.

### IC-02 — Retire the FAIL-path restore (#5666)

- **Purpose**: one restore path. FAIL/REFUSE rolls back only through the door.
- **Relevant requirements**: FR-001, FR-002, FR-010 (5666 half)
- **Affected surfaces**: `consolidation/phase_gate.py`; `tests/consolidation/test_single_rollback_authority.py`, `test_refuse_restores_target.py`, `test_merge_state_authority.py`, `test_rollback_anchor_p0_repro.py`, `tests/terminus/test_rollback_door.py`
- **Sequencing/depends-on**: none
- **Risks**: gate tests that call `_phase_reconcile_before_teardown` outside the door must be re-pinned to the door (stale → re-pin), not deleted wholesale.

### IC-03 — Unsettled marks, advance intents, recorder taint, no re-anchoring (#5686, #5666 between-phase)

- **Purpose**: the restore target and CAS expectation always come from the record. A kill-left move is adopted on proof or refused, and a foreign interleave is never recorded as this run's.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-010 (5686 half), FR-011, FR-012
- **Affected surfaces**: `consolidation/rollback.py`, `consolidation/state.py`, `git/ref_advance.py`, `consolidation/phase_claim.py`, `consolidation/executor.py`; tests in `tests/consolidation/test_rollback_authority.py`, `test_executor_rollback_wiring.py`, `tests/git/`, the repro file
- **Sequencing/depends-on**: IC-01 (atomic writes). It follows IC-02 in the same lane because both touch the repro file and the AST pin.
- **Risks**: the AST door pin (`test_single_rollback_authority.py` rule 3) must still find every span phase inside the one door `try` once the door is wrapped in the attempt scope. `ref_advance` must not import consolidation (layering), hence the injected sink.

### IC-04 — Operator release and truthful `--abort` (#5687 deadlock)

- **Purpose**: `--abort` never deadlocks and never says "restored" for a kept branch.
- **Relevant requirements**: FR-008, FR-009
- **Affected surfaces**: `cli/commands/consolidate.py`, `consolidation/rollback.py`, `consolidation/state.py`; `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`
- **Sequencing/depends-on**: IC-03
- **Risks**: option validation (`--release-branch` only with `--abort`; `--release-reason` required); help text; terminology.

### IC-05 — Docs and ADR

- **Purpose**: record the decision and keep the CLAUDE.md residual list honest.
- **Relevant requirements**: C-001 (documentation of the removed path)
- **Affected surfaces**: ADR `2026-09-19-1` (dated follow-up), `CLAUDE.md` consolidation section, `CHANGELOG.md` / `docs/changelog/4.0.0.md` if that is the convention
- **Sequencing/depends-on**: IC-02..IC-04
- **Risks**: none
