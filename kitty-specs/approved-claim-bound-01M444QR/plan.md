# Implementation Plan: Approved claim bound

**Branch**: `issue-5668-approved-claim-bound` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/approved-claim-bound-01M444QR/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md) | **Decisions**: [research.md](research.md)

## Summary

`spec-kitty consolidate` builds an approved work package's claim from the live
lane tip, so a commit added after approval lands under a "verified" banner
(reproduced in all four topology and strategy combinations). The fix adds one
resolver that reads the approval stamp (`policy_metadata.lane_head` on the
`approved` transition) and refuses a lane that holds content commits beyond it.
The refusal runs in the claim builder, before any branch moves, and again at
the reconciliation gate against the lane tips at that moment. An approval with
no stamp refuses, and a new operator attestation lifts only that refusal.
`orchestrator-api consolidate-mission` runs the same check before its first
lane merge.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, `spec_kitty_events` (status transition contract, unchanged), git >= 2.38
**Storage**: the append-only status event log (`status.events.jsonl`); git refs
**Testing**: pytest. Red-first e2e in `tests/terminus/` driving `python -m specify_cli consolidate` as a subprocess; unit tests in `tests/consolidation/`; markers `integration`, `git_repo`, `regression`
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single (CLI package `src/specify_cli/`)
**Performance Goals**: one status event-log read per claim; existing canceled-content benchmark stays within its budget
**Constraints**: cyclomatic complexity <= 15; `ruff` and `mypy --strict` clean; no new restore path; status pipeline stays git-free; existing refusal codes and texts byte-identical
**Scale/Scope**: about 6 source modules and 8 to 10 test modules; one new module; one new CLI flag; one ADR

## Charter Check

| Gate | Status | Note |
|---|---|---|
| Single canonical authority | pass | One reader of the approval stamp; the bookkeeping-path definition and the lane-base anchors are reused, not copied |
| Architectural alignment (layer rule, status boundary) | pass | New code lives in `specify_cli.consolidation`; status is imported through the `specify_cli.status` facade, lazily where the module is import-light |
| ATDD-first / Standing Order 4 | pass | The red e2e is the first commit of the fix work package, after the tidy-first work package |
| Campsite cleaning (Standing Order 2, DIRECTIVE_025) | pass | Tidy-first enabler: public stamp readers, truthful approval fixtures |
| Gate discipline (Standing Order 5) | pass | No new allowlist, baseline or ratchet gate |
| Terminology canon | pass | Mission, work package; `--mission` only |
| Decision documentation (DIRECTIVE_003) | pass | New ADR in `docs/adr/4.x/` with a forward pointer from ADR `2026-09-29-1` |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | pass | Targeted files only; named architectural gate files, never the directory |

Conflict between the operator brief and the charter: none found.

## Project Structure

### Documentation (this mission)

```
kitty-specs/approved-claim-bound-01M444QR/
├── plan.md
├── research.md
├── research/code-grounding.md
├── data-model.md
├── quickstart.md
├── contracts/consolidate-refusals.md
├── tracers/{tooling-friction,approach,design-decisions}.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── approved_bound.py        # NEW: approval-stamp reader, lane check, attestation record
├── wp_attribution.py        # stamp readers made public (one reader)
├── canceled_attestation.py  # inline stamp read folds onto the public reader
├── reconciliation.py        # claim builder calls the lane check; new error codes
├── phase_claim.py           # refusal text when attestations were recorded
├── phase_gate.py            # gate re-check before "verified"
└── executor.py              # records the new attestation before the claim
src/specify_cli/cli/commands/consolidate.py     # --attest-approved-reviewed
src/specify_cli/orchestrator_api/consolidation.py  # check before the first lane merge

tests/terminus/              # red-first e2e, shared fixtures restamped
tests/consolidation/         # unit tests; tautological tests retired
docs/adr/4.x/                # new ADR
docs/api/cli-commands.md, docs/changelog/CHANGELOG.md, CLAUDE.md
```

**Structure Decision**: single project. One new module in the existing
`consolidation` package; no new package and no new layer edge.

## Design

### D-1 One reader of the approval stamp

`wp_attribution._stamp_of` and `_is_migration_event` become public
(`stamp_of`, `is_migration_event`). `canceled_attestation.attestation_stamps`
uses `stamp_of` instead of its inline read. `approved_bound.approval_stamp(events, wp_id)`
returns the stamp of the latest non-migration event that either has
`to_lane == approved` or is an approved-reviewed attestation (D-5). The `done`
restamp is never read.

### D-2 The lane check

`approved_bound.lane_refusals(...)` evaluates every code lane that has at least
one work package in the approved claim and is not fully canceled. Planning lanes
and `single_branch` missions are skipped (C-005).

For one lane, with `tip` the lane branch head:

1. **Covered points.** The approval stamp of each approved work package, plus
   the latest non-migration stamp of each canceled work package on the lane
   (the existing closed world owns everything up to that point on a mixed lane).
2. **Missing stamp.** An approved work package with no approval stamp refuses
   with `APPROVAL_STAMP_MISSING`.
3. **Stamp not on lane.** A covered point that is not the tip or an ancestor of
   it refuses with `APPROVAL_STAMP_NOT_ON_LANE`.
4. **Beyond the bound.** Take the full range of commits reachable from `tip`
   and from no covered point and not from the claim base. Drop merge commits,
   commits reachable from an anchor, and commits that touch only bookkeeping
   paths. Anything left refuses with `LANE_MOVED_AFTER_APPROVAL`, naming up to
   three short SHAs, one path, the lane and its approved work packages.

Anchors are the existing lane-base anchors (`_closed_world_anchors`:
dependency-lane tips of lanes that are not fully canceled, and the target's
pre-consolidation tip) plus the mission branch, which only the tool advances.
`_lane_exempt_commits` and the gate's `_is_bookkeeping` are reused as they are.

Taking "reachable from no covered point" avoids choosing one bound when two
approvals sit on different sides of a merge.

### D-3 Where it runs

| Point | Code | Effect |
|---|---|---|
| Claim time | `build_approved_wp_set`, after the mixed-lane resolution (existing refusals keep precedence), before the collectors | sets `claim.refusal`; `claim_integrity_refusal` exits before the snapshot; nothing is rolled back |
| Gate time | `_phase_reconcile_before_teardown`, before `verify()`; skipped on the existing "already passed for this tip" resume path. It asks whether content arrived on a lane since the claim-time check: commits reachable from the live lane tip and from neither the tip validated at claim time, another lane's validated tip, nor the mission, target and coordination SHAs captured at claim time | a refusal becomes `VerifyResult.refused(...)` and takes the existing non-PASS branch, which exits through the executor's single `try` into `rollback_to_snapshot` |
| Orchestrator | `_execute_lane_merge`, after the merge gates and before the first `consolidate_lane_into_mission` | `PREFLIGHT_FAILED` envelope carrying the code |

The gate check never uses a live branch name as a reference: lanes are merged into the mission branch with a no-ff merge, so at gate time the live mission branch reaches every merged lane commit, and on a LANES mission the claim base is the mission branch itself.

The collectors keep reading the lane branch. With the check in front of them
the live tip can differ from the approved bound only by tool-made merges and
bookkeeping commits, which the physical merge needs in the claim.

The status event log is read once per claim through the existing
`_ClaimEventLog`, now also for missions with no mixed lane. An unreadable log
refuses with the existing `events_unreadable` wording.

### D-4 Refusal texts and codes

Three new module constants in `reconciliation.py`, rendered as a leading
`CODE: ` like `APPROVED_CONTENT_MISSING`. Full texts are in
[contracts/consolidate-refusals.md](contracts/consolidate-refusals.md). No
existing text changes. The recovery command named in each text is taken from
the live CLI and asserted by a test.

### D-5 Attestation

`consolidate --attest-approved-reviewed <WP>` (repeatable) shares
`--attest-reason`. It is validated before anything is recorded:

- the work package is in the approved claim (`approved` or `done`);
- it has no approval stamp. A stamped work package is refused: "already has a
  recorded approval; move it back for review instead".

The record is a forced operator self-transition to the work package's current
lane, with `reason_source = operator`, `policy_metadata.attestation =
"approved_reviewed"`, the evidence the transition contract requires, and the
`lane_head` the pipeline stamps itself. Because `approval_stamp` (D-1) reads
that event, the attestation's own lane head becomes the bound: a later commit
refuses, a later real approval replaces it, and the run's own `approved -> done`
does not affect it. It is recorded where `--attest-canceled-superseded` is
recorded today, before the claim.

### D-6 Tests

- **Red-first e2e** (`tests/terminus/test_post_approval_commit_refused.py`):
  lanes and coordination topologies x squash and merge strategies; each cell
  asserts non-zero exit, the code, the commit named, no banner, target tip
  unchanged, and the same fixture without the late commit consolidating with
  the banner (positive control).
- **Gate re-check**: a real `consolidate` run with a commit injected after the
  claim and before the lane merge at a named phase boundary; red with the
  claim-time check alone.
- **Unit**: `tests/consolidation/test_approved_bound.py` covers the stamp
  selection (latest approval, migration skipped, `done` restamp ignored,
  attestation), each refusal reason, and each FR-009 movement with a refusing
  control on the same fixture.
- **Fixtures**: `tests/terminus/conftest.py` and
  `tests/consolidation/test_reconciliation.py::_build_mission` write approvals
  after the lane commits with the real tip as the stamp.
  `strip_lane_head_stamps` stays the one way to build an unstamped mission.
- **Retired or rewritten**: in `test_reconciliation.py` the self-comparison test is
  deleted and the "non-mixed lane never reads events" test is rewritten as the
  read-count pin. The "claim equals the lane tips" test stays (the collectors
  still read the tips) and `approved_shas_from_lane_tips` keeps its behaviour
  with a corrected docstring.
- **Residual**: content inside a merge commit, pinned as strict `xfail`.
- The #5330 strict xfails keep their state; a flip is accepted only with the
  reason recorded in the test and the PR.

### D-7 Corrections made during implementation

The sections above are the plan as written. Implementation and review changed
four points; the decision record (`docs/adr/4.x/2026-10-04-2-*`) is authoritative.

- **Claim base and anchors.** The check measures from the target tip as it was
  before the run mutated anything (persisted on a resume), not from the
  coordination base, and the mission branch is not an anchor. Every bounded
  lane's approval stamps are anchors. A post-approval commit already merged into
  the mission branch passed the first version on a resume.
- **Gate re-check.** A plain commit added during a run was already failed by the
  existing content checks; the re-check adds the named refusal and closes the
  duplicate-blob case on a mission with no coordination branch.
- **Attestation.** A repeat attestation is accepted only while the lane has not
  moved past the earlier one. The hollow-review check ignores attestation events.
- **Empty lanes.** A lane with no commit beyond the claim base is not checked.

## Complexity Tracking

No charter violation to justify.

## Implementation Concern Map

### IC-01 — Tidy-first enablers

- **Purpose**: make the stamp readers public and make the shared approval fixtures truthful, with no product behaviour change, so the red test can express "after approval".
- **Relevant requirements**: FR-001, FR-014, C-007
- **Affected surfaces**: `consolidation/wp_attribution.py`, `consolidation/canceled_attestation.py`, `tests/terminus/conftest.py`, `tests/terminus/lanes_fixture.py`, `tests/consolidation/test_reconciliation.py`
- **Sequencing/depends-on**: none
- **Risks**: the fixture reorder touches builders used by about 35 test files; the whole of `tests/terminus/` and `tests/consolidation/` must stay green before and after.

### IC-02 — Approved bound: reproduction, resolver, claim-time and gate-time refusal

- **Purpose**: refuse a lane with content beyond its approved bound, an unstamped approval and a rewritten lane, before mutation and again at the gate.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, FR-009, FR-010, FR-012, FR-013, NFR-001, NFR-004, C-001, C-002, C-003, C-005
- **Affected surfaces**: `consolidation/approved_bound.py` (new), `consolidation/reconciliation.py`, `consolidation/phase_gate.py`, `tests/terminus/`, `tests/consolidation/test_approved_bound.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: false refusals from tool-made lane movement on `--resume`; precedence against the mixed-lane closed world; the #5330 xfail at `test_canceled_content_residuals.py:513`.

### IC-03 — Attestation for an unstamped approval

- **Purpose**: let an operator land a mission approved before the stamp existed, without ever lifting a post-approval commit refusal.
- **Relevant requirements**: FR-006, FR-007
- **Affected surfaces**: `consolidation/approved_bound.py`, `consolidation/executor.py`, `consolidation/phase_claim.py`, `cli/commands/consolidate.py`, `docs/api/cli-commands.md`, CLI golden test
- **Sequencing/depends-on**: IC-02
- **Risks**: the transition contract requires evidence for `approved` and `done`; `--attest-reason` is shared by two flags.

### IC-04 — Orchestrator entry point

- **Purpose**: `orchestrator-api consolidate-mission` refuses before its first lane merge on the code-lane path.
- **Relevant requirements**: FR-011
- **Affected surfaces**: `orchestrator_api/consolidation.py`, its tests
- **Sequencing/depends-on**: IC-02
- **Risks**: that path has no rollback door, so the check must run before any merge.

### IC-05 — Suite honesty and documentation

- **Purpose**: retire the tests that assert the live-tip claim, record the decision and document the operator-facing change.
- **Relevant requirements**: FR-014, FR-015
- **Affected surfaces**: `tests/consolidation/test_reconciliation.py`, `tests/terminus/conftest.py` (oracle), `docs/adr/4.x/`, `docs/adr/3.x/2026-09-29-1-*.md` (pointer), `docs/changelog/CHANGELOG.md`, `CLAUDE.md`
- **Sequencing/depends-on**: IC-02, IC-03, IC-04
- **Risks**: docs retrieval index and freshness checks after adding an ADR.
