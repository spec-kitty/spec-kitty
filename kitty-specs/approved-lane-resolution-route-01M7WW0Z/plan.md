# Implementation Plan: Approved-lane conflict resolution route

**Branch**: `kitty/mission-approved-lane-resolution-route-01M7WW0Z`, which lands on `fix/approved-lane-resolution-route`
**Date**: 2026-11-20
**Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md`

## Summary

Consolidate's stale-lane remedy and its reconciliation gate disagree about a conflict between approved lanes. The remedy prescribes a hand merge. The gate drops that merge as unreviewed and refuses its bytes late, after every lane has landed and the run has rolled back.

This plan makes the remedy print the one sanctioned route:
1. send the WP back;
2. incorporate the sibling lane at its approval stamp;
3. resolve;
4. independent review and approval;
5. re-run.

The route is reachable after a rollback, and the run refuses an unreviewed resolution merge by name before anything moves. The review context points at the resolution bytes. The rollback undoes the run's own auto-rebase merges. Two soundness holes are closed:
- merge probes that follow clone-local attributes and drivers;
- canceled content riding a re-approved dependency lane.

The ADR amendments record the model. Approach C, attributing a conflict resolution mechanically, stays rejected.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor; CI also runs newer interpreters)
**Primary Dependencies**: typer and rich (CLI), git ≥ 2.38 for `merge-tree --write-tree` and ≥ 2.36 for `show --remerge-diff` (both already required); git ≥ 2.40 for `check-attr --source`, needed only to honour a committed attribute (older git refuses it). The first two are already required by the consolidation probes. No new dependency.
**Storage**: git refs and objects in the repository; the consolidation run record (`.kittify/runtime/merge/<mission_id>/state.json`); the append-only status event log. One new ref namespace: `refs/spec-kitty/auto-rebase/` (see research R-03).
**Testing**: pytest. Unit tests at the probe and helper level. Real-git integration tests via the existing fixture builders (`tests/consolidation/*_support.py`). End to end through the real CLI via `tests/terminus/conftest.py::run_terminus`. Red first for every behaviour change. `make test-fast` plus the blast radius; no full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION).
**Target Platform**: Linux, macOS and Windows CLI. The new git invocations use only porcelain and plumbing available on all three.
**Project Type**: single project (`src/specify_cli`, `src/kernel`, `tests/`)
**Performance Goals**: NFR-001. FR-004 adds at most one own-content probe per approved-lane merge that no own stamp reaches. FR-010 adds one batched `check-attr` per probed merge. The git-version check runs once per run.
**Constraints**:
- Fail closed (NFR-002).
- Complexity ≤ 15 (NFR-003).
- No new verdict-lifting attestation (C-002).
- One rollback authority, one refusal renderer, one merge-probe layer, one review-range owner (C-006).
- The orchestrator-api contract version is bumped (C-007).
**Scale/Scope**: 14 work packages (tasks.md is authoritative for the WP structure and ownership; the source tree below is an overview) over consolidation, lanes, review, orchestrator-api and docs. No migration: the new ref namespace is created on demand, and an absent namespace is the legacy state.

## Charter Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter rule | Status | How the plan meets it |
|---|---|---|
| Single canonical authority | PASS | FR-004 reuses the gate's unreviewed-merge predicate (shared function, R-04). FR-009 lives in `consolidation/rollback.py`, which keeps the AST pin. FR-010 goes in the probe layer, shared by both callers. FR-001 reuses `approved_bound.move_back_command`. FR-007 extends `review/wp_range.py`. |
| Architectural alignment (layers) | PASS | All changes stay in `specify_cli` and `kernel` (the kernel git helpers, if a check-attr helper belongs there). No new cross-layer import. |
| ATDD-first / red-first (Standing Order 4) | PASS | Every work package opens with its red acceptance or attack test (see the IC risks). FR-009 and FR-011 are red-first on the observed harm, with a stated route if they are green at the base. |
| Architectural gate discipline (Standing Order 5) | PASS | No new allowlist. The `test_single_rollback_authority.py` pin stays empty. Two report-only lane tests are re-pinned narrowly (R-05), not deleted. |
| Campsite cleaning (Standing Order 2) | PASS | `stale_check._stale_remediation`, `approved_bound.check_lane` and `reconciliation_verifier._with_attribution_hint` are tidied first where they are touched (extract helpers, keep complexity ≤ 15). |
| Mission tracer files (Standing Order 3) | PASS | Seeded at tasks: `traces/tooling-friction.md`, `traces/approach.md`, `traces/design-decisions.md`. |
| Mission hygiene (Standing Order 8) | PASS | Issue-matrix rows for #5604, #7754, #7755, #7767, #5721 and #7497. Cross-reference-only rows are marked `not-applicable` or context. The reviewer is a separate session. |
| No full heavy suites | PASS | The test plan names files, not directories (quickstart.md). |
| Terminology canon | PASS | Mission, consolidate (lane consolidation), "incorporate"; never "sync" or "feature". |
| Supply chain (DIRECTIVE_051) | N/A | No dependency is added, upgraded or removed. |

Post-design re-check: PASS. The incorporate step is a new `lanes/incorporate.py` behind the existing `implement` command; `lanes/lifecycle_sync.py` is unchanged. Research R-01 to R-10 introduce no second authority. The operator ruling on R-01 (option b) keeps the authority map: the incorporate step extends the existing lane sync point.

## Project Structure

### Documentation (this Mission)

```
kitty-specs/approved-lane-resolution-route-01M7WW0Z/
├── spec.md
├── plan.md                 # this file
├── research.md             # Phase 0 decisions R-01..R-10
├── data-model.md           # entities, records, refusal codes, state transitions
├── quickstart.md           # operator walkthrough + targeted test commands
├── contracts/
│   ├── refusal-codes.md            # new codes, envelopes, remedy text shape
│   ├── stale-remedy.md             # approved-lane stale remedy contract
│   ├── auto-rebase-record.md       # refs/spec-kitty/auto-rebase/ contract
│   └── review-context-merges.md    # review-context merge lines (amends C-001)
├── squads/                 # adversarial squad records and dispositions
└── tasks.md                # produced by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/
├── lanes/
│   ├── stale_check.py           # FR-001/002/003: approved-lane remedy, halt reason, siblings
│   ├── consolidation.py         # consolidate_lane_into_mission: approved_wp_ids + halt report plumbing
│   ├── auto_rebase.py           # FR-005: write the auto-rebase record on every merge it makes
│   └── incorporate.py           # FR-001 (R-01 option b): sibling incorporation (new), called from the implement command
├── consolidation/
│   ├── approved_bound.py        # FR-004: unreviewed_resolution_merges + RESOLUTION_MERGE_UNREVIEWED
│   ├── reconciliation_authorship.py  # shared unreviewed-merge predicate (extract; C-003)
│   ├── reconciliation_claim.py  # claim field: unreviewed_merges (FR-006)
│   ├── reconciliation_verifier.py    # FR-006 hint branch
│   ├── reconciliation_canceled.py    # FR-011 anchor fix (if red)
│   ├── git_probes.py            # FR-010 effective-attribute guard for both probes
│   ├── phase_advance.py         # pass approved WPs + sibling map to the stale check; record moves always
│   ├── rollback.py              # FR-009 lane restore from recorded move (CAS) + new outcome
│   └── state.py                 # lane_rebase_moves lifetime across re-baseline (FR-009)
├── review/
│   ├── wp_range.py              # FR-007: list merges in range (no history simplification)
│   └── context_block.py         # FR-007: labelled remerge-diff command per merge
├── orchestrator_api/
│   ├── consolidation.py         # new code reaches preflight_error_codes; stale remedy stance
│   └── envelope.py              # CONTRACT_VERSION bump (C-007)
└── cli/commands/agent/workflow.py   # FR-001 option b: `implement --incorporate <lane>` flag
src/kernel/git/                  # check-attr helper only if no kernel helper exists (R-06)

tests/
├── lanes/                       # stale remedy, auto-rebase record, incorporate
├── consolidation/               # bound, verifier, rollback, probes, canceled, #7307 tightening
├── review/                      # wp_range merges, context block lines
├── orchestrator_api/            # envelope/contract version, preflight codes
└── terminus/                    # FR-008 end-to-end route (squash, merge, N1-N3, three lanes)

docs/adr/4.x/2026-10-04-5-*.md, docs/adr/3.x/2026-09-29-1-*.md,
docs/adr/3.x/2026-09-19-1-*.md, docs/adr/4.x/2026-11-08-2-*.md, CLAUDE.md residual line   # FR-013
docs/changelog/unreleased/<id>.<section>.md                                                   # changelog fragment
```

**Structure Decision**: single project. Changes extend the existing seams named above. No new package.

## Complexity Tracking

No charter violations. Nothing to justify.

## Implementation Concern Map

> Implementation concerns are not work packages. `/spec-kitty.tasks` translates them.

### IC-01: Merge probes fail closed on effective merge attributes and drivers

- **Purpose**: neither the clean-fold recognizer nor the own-content remerge probe may be steered by clone-local or uncommitted merge settings.
- **Relevant requirements**: FR-010, NFR-001, NFR-002
- **Affected surfaces**:
  - `consolidation/git_probes.py`: `n_way_merge_blob`, `merge_own_changed_paths`, the kernel remerge helper they call;
  - `lanes/consolidation.py`: read-only use of the `_MERGE_DRIVERS` registry;
  - tests in `tests/consolidation/`.
- **Sequencing/depends-on**: none. FR-004 (IC-03) must build on this.
- **Risks**:
  - The tool installs its own drivers locally. The guard must allow exactly the registered (driver name, command, pattern) triples and nothing else, including a redefined command under a registered name and `merge.default`.
  - A Mission that edits another Mission's `kitty-specs/**` files matches a registered pattern; allow it, because it is still the registered driver.

### IC-02: Auto-rebase record and rollback of the run's own lane merges

- **Purpose**:
  - every auto-rebase merge leaves a durable tool record;
  - the rollback undoes this run's own recorded lane moves under compare-and-swap;
  - a lane that moved since is a distinct, kept outcome.
- **Relevant requirements**: FR-005 (record), FR-009, NFR-002
- **Affected surfaces**:
  - `lanes/auto_rebase.py`: write `refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`;
  - `consolidation/phase_advance.py`: record the move on every auto-rebase merge, not only on success;
  - `consolidation/rollback.py`: lane restore and the new outcome `LANE_MOVED_SINCE_AUTO_REBASE`, which is not re-baselineable;
  - `consolidation/state.py`;
  - `lanes/lane_tip.py`: reset the lane work-tip record;
  - `git/ref_advance.resync_checkouts_to_tip`.
- **Sequencing/depends-on**: none.
- **Risks**:
  - The ADR 2026-09-19-1 A2 reversal is narrow: only `[before, after]` from this run's record.
  - Two pinned tests in `test_rollback_authority.py` are re-pinned, not deleted.
  - A dirty lane checkout refuses the resync and is reported (#5638 posture).
  - The red-first test reproduces the actual harm at the base: a left-over merge on the next run.

### IC-03: Claim-time named refusal for an unreviewed resolution merge

- **Purpose**: refuse before any mutation when a merge on an approved code lane carries its own non-bookkeeping content and none of that lane's own approval stamps reaches it. A recorded tool merge is exempt from this refusal only.
- **Relevant requirements**: FR-004, FR-005 (consumer), FR-012, C-003, C-007
- **Affected surfaces**:
  - `consolidation/approved_bound.py`: new function and code, `render_refusals` text, `_compound_refusal` order;
  - `consolidation/reconciliation_authorship.py`: extract the shared "own stamps reach this merge" predicate from `_drop_unreviewed_merges`;
  - `orchestrator_api/consolidation.py` and `envelope.py`: codes and contract bump;
  - the forecast cell;
  - `tests/consolidation/test_approved_bound_residuals.py` (convert the strict xfail);
  - `tests/consolidation/test_dependency_merge_attribution_7307.py` (FR-012).
- **Sequencing/depends-on**: IC-01 (probe guard) and IC-02 (record).
- **Risks**:
  - Do not change `content_commits`: tier 2 and the gate re-check share it.
  - Add a predicate-agreement test between the claim and the gate.
  - The three-lane control is required.

### IC-04: Approved-lane stale remedy and sibling incorporation

- **Purpose**:
  - the stale refusal on approved code lanes names exactly the conflicting sibling lane or lanes, the halt reason and paths, and the runnable re-review route;
  - the route's incorporate step exists as a canonical command.
- **Relevant requirements**: FR-001, FR-002, FR-003
- **Affected surfaces**:
  - `lanes/stale_check.py`: new fields and the approved-lane remedy branch; pure;
  - `lanes/consolidation.py`: plumb `approved_wp_ids`, the halt report and the sibling map; return the report;
  - `consolidation/phase_advance.py`: sibling mapping from pre-run lane tips;
  - new `lanes/incorporate.py` and `cli/commands/agent/workflow.py` (`lanes/lifecycle_sync.py` unchanged): `--incorporate <lane>` (R-01 option b, ruled by the operator in DM-01M7WX8AX56E23AXBZRWGNX4EM);
  - orchestrator-api stale stance: same renderer;
  - `tests/lanes/test_stale_remediation_cli_command.py`: re-pinned per the ruling.
- **Sequencing/depends-on**: none for the remedy text. The incorporate command needs the approval-stamp reader that already exists in `approved_bound`.
- **Risks**:
  - The A-10 rule (#7285) must hold under option b.
  - The sibling must be named at its approval-stamp SHA (#7630 trust).
  - Exact-set naming: a three-lane control rules out over-inclusion.

### IC-05: Reconciliation hint for the dropped-merge shape

- **Purpose**: when an un-attributable blob comes from a dropped post-approval merge, the gate refusal names the re-review route instead of `--dependency-ref`.
- **Relevant requirements**: FR-006
- **Affected surfaces**:
  - `consolidation/reconciliation_claim.py` and `reconciliation_claim_types.py`: additive claim field `unreviewed_merges`;
  - `reconciliation_authorship.py`: populate it;
  - `reconciliation_verifier._with_attribution_hint`.
- **Sequencing/depends-on**: the shared predicate and claim field (IC-03's WP04 part) and the probe guard (IC-01).
- **Risks**:
  - `Divergence.describe()` stays unchanged.
  - Mixed or canceled divergences show no re-review hint (N4).
  - Renderer-level tests.

### IC-06: Review context points at merge resolutions

- **Purpose**: the reviewer sees a labelled `git show --remerge-diff <sha>` command for each merge in the WP review range.
- **Relevant requirements**: FR-007
- **Affected surfaces**:
  - `review/wp_range.py`: list merges, without history simplification;
  - `review/context_block.py`: one line per merge, commands only;
  - review-context contract C-001 text.
- **Sequencing/depends-on**: none. The availability check uses the existing `remerge_diff_available`.
- **Risks**:
  - Keep the renderer pure.
  - The byte budget.
  - Git without remerge-diff support prints a "cannot show" note.

### IC-07: Canceled content via a re-approved dependency lane (#7497)

- **Purpose**: prove, red first, whether a fully canceled lane merged into a re-approved dependency lane lands, and close it if so.
- **Relevant requirements**: FR-011
- **Affected surfaces**:
  - `tests/consolidation/resume_frozen_anchors_support.py` (builder reuse);
  - a new test file;
  - if red, `consolidation/reconciliation_canceled.py` / `reconciliation_kernel.py`: anchor C on A as of C's cut, not A's live tip.
- **Sequencing/depends-on**: none.
- **Risks**:
  - The fixture must assert its preconditions.
  - If the test is green at the base: ratchet pin and close #7497 with evidence.

### IC-08: End-to-end proof of the route

- **Purpose**: drive the whole route through the real CLI. Covers:
  - squash and merge strategies;
  - N1–N3;
  - the three-lane variant;
  - unforced transitions by distinct actors.
- **Relevant requirements**: FR-008, SC-001 to SC-004
- **Affected surfaces**: `tests/terminus/` (new support module with adjacent-hunk lanes on one shared file).
- **Sequencing/depends-on**: IC-02, IC-03, IC-04, IC-06 (the red test is written first; it goes green when they land).
- **Risks**:
  - The lane checkout's sparse status exclusion may interact with the hand merge (#5965). Record any CLI gap as an issue.

### IC-09: ADR, contract and doc amendments

- **Purpose**: record the model. Covers:
  - re-review as the sanctioned exit;
  - the #7630 trust model;
  - FR-004 / FR-005;
  - FR-009's narrow A2 reversal;
  - FR-010's fail-closed rule;
  - the FR-007 contract change;
  - the stale-remedy rule;
  - the CLAUDE.md residual line;
  - the changelog fragment.
- **Relevant requirements**: FR-013
- **Affected surfaces**:
  - `docs/adr/4.x/2026-10-04-5-*`;
  - ADR 2026-09-29-1;
  - `docs/adr/3.x/2026-09-19-1-*`;
  - `docs/adr/4.x/2026-11-08-2-*`;
  - `CLAUDE.md`;
  - `docs/changelog/unreleased/`.
- **Sequencing/depends-on**: IC-01 to IC-07 (documents what landed).
- **Risks**: run the terminology guard (`tests/architectural/test_no_legacy_terminology.py`).
