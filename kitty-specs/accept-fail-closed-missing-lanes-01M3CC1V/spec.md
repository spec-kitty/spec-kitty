# Mission Specification: Accept fail-closed on absent lanes.json

**Mission Branch**: `issue-4891-accept-fail-closed-missing-lanes`
**Created**: 2026-09-25
**Status**: Draft
**Input**: GitHub issue #4891 — "accept silently skips the entire acceptance-matrix gate when lanes.json is absent — exit 0, acceptance recorded and committed with every criterion still pending" (P0, from:qa)

## Summary

`spec-kitty accept` is the gate that stands between an unverified mission and `merge`. When
`kitty-specs/<slug>/lanes.json` is **absent**, the lane-gate resolver
(`_resolve_lanes_manifest_or_stop`) returns a bare `None` and `_check_lane_gates` returns
**before** running the branch gate *and* the acceptance-matrix gates (presence / evidence /
negative-invariant / verdict). No diagnostic is recorded on either output channel:
`summary.ok` stays `True`, the command exits **0**, and `perform_acceptance` writes and commits
`accepted_at` / `accept_commit` / `acceptance_history` into `meta.json` while every acceptance
criterion is still `pending` (or the matrix does not exist at all).

The same mission with `lanes.json` **present** is correctly refused (exit 1,
`Acceptance matrix verdict is 'pending' …`). A **corrupt** `lanes.json` is also handled
correctly (blocked/skipped checks recorded, `ok` false). Only *genuine absence* fails open —
by the resolver's own docstring, a deliberate "silent no-op … matching the pre-extraction
behaviour exactly."

This mission makes absence **fail closed**, mirroring the existing corrupt-lanes branch and
consistent with `implement` / `review` / `merge`, which already refuse the same shape via
`MissingLanesError`.

## Grounding (verified against current `main`, HEAD `2864622117`)

- **Reproduced** with the issue's portable script on an isolated environment: control
  (lanes.json present) → `rc=1`, `ok=False`, no acceptance recorded; probe (lanes.json removed)
  → `rc=0`, `ok=True`, `accepted_at`/`accept_commit` written **and committed** on a fully-`pending`
  matrix.
- **Not superseded**: no later fix touches the None-handling; zero `4891` hits in
  `docs/changelog/CHANGELOG.md`.
- **Partition authority** (`src/mission_runtime/artifacts.py:158-186`): `LANE_STATE`
  (`lanes.json`) is a **PRIMARY-partition** artifact ("travels with tasks.md → PRIMARY",
  read+write symmetric for every topology). Therefore reading it off the primary
  `read_feature_dir` is correct for **all** topologies; an absent-on-primary `lanes.json` is
  *genuinely absent*, not "on the coord surface." (This is #4891's explicit distinction from the
  closed #3439 coord-husk surface-read bug.)
- **Single chokepoint**: `merge` does **not** independently re-verify the acceptance matrix
  (`policy/merge_gates.py`, `merge/executor.py`) — it trusts `accept`. So fixing `accept` closes
  the release risk; `merge`'s `--skip-lanes`/`--no-lanes` is a deliberate operator opt-in, not a
  silent bypass, and is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator cannot accept a mission whose acceptance was never verified (Priority: P1)

As an operator (or a CI gate) running `spec-kitty accept`, when a mission's `lanes.json` is
absent, I want the command to **refuse** — exit non-zero, tell me which acceptance-matrix checks
did not run, and **not** record or commit acceptance — so that an unverified mission can never be
silently marked accepted and passed on to `merge`.

**Why this priority**: This is the entire mission. It is a P0 false-success on the release gate.

**Independent Test**: Drive a `single_branch` mission to `done` with no acceptance verdicts
(matrix all `pending`), remove `lanes.json`, run `spec-kitty accept --mission <slug> --json`, and
assert `rc != 0`, `summary.ok == False`, the skipped/blocked matrix checks are listed, and no
`accepted_at`/`accept_commit` is written or committed.

**Acceptance Scenarios**:

1. **Given** a finalized mission driven to `done` with an all-`pending` acceptance matrix and
   `lanes.json` removed, **When** `spec-kitty accept --mission <slug> --json` runs, **Then** it
   exits non-zero, `summary.ok` is `False`, `activity_issues` names the absent manifest, and
   `accepted_at`/`accept_commit` are **not** written to `meta.json`.
2. **Given** the same mission with `lanes.json` removed, **When** accept runs, **Then**
   `blocked_checks` contains a `lanes_manifest` diagnostic and `skipped_checks` lists every
   acceptance-matrix gate that did not run (presence, evidence, negative-invariants, verdict).
3. **Given** the same mission with `lanes.json` **present** and an all-`pending` matrix, **When**
   accept runs, **Then** the pre-existing refusal is unchanged (exit 1,
   `Acceptance matrix verdict is 'pending' …`) — no regression.
4. **Given** a mission with a **corrupt** `lanes.json`, **When** accept runs, **Then** the
   pre-existing corrupt-lanes handling is unchanged (blocked/skipped recorded, `ok` false).

### Edge Cases

- **Absent matrix AND absent lanes.json**: still fail closed (the skipped-checks include the
  matrix *presence* check, mirroring the corrupt path's `include_matrix_presence=True`).
- **Genuine no-lane / flat legacy shapes**: there is **no** legitimate mission shape on 4.0 that
  reaches `accept` without `lanes.json` (`is_planning_artifact_only` requires lanes present;
  every finalized mission writes it; implement/review/merge/move-task already fail closed). So
  failing closed breaks no legitimate mission.
- **Remediation**: the diagnostic must point the operator at the recovery
  (`spec-kitty agent mission finalize-tasks` / `spec-kitty doctor mission-state --fix`), matching
  `MissingLanesError`'s wording — a gate that did not run must be distinguishable from one that
  passed.
- **Coordination / orchestrator readiness surfaces**: `collect_feature_summary` also backs
  `orchestrator_api/commands.py`; the single-seam fix propagates there for free — verify it is not
  broken.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Absent lanes.json fails closed | As an operator, I want `accept` to exit non-zero and set `summary.ok=False` when `lanes.json` is absent, so acceptance is never falsely recorded. | High | Open |
| FR-002 | Skipped/blocked checks recorded | As an operator, I want every acceptance-matrix gate that did not run recorded in `skipped_checks`, plus a `lanes_manifest` `blocked_checks` diagnostic, so a gate that did not run is distinguishable from one that passed. | High | Open |
| FR-003 | No acceptance recorded on absence | As an operator, I want `accepted_at`/`accept_commit`/`acceptance_history` to remain unwritten and uncommitted when `lanes.json` is absent. | High | Open |
| FR-004 | Actionable remediation | As an operator, I want the diagnostic to name the recovery command (finalize-tasks / doctor mission-state --fix), matching `MissingLanesError`. | Medium | Open |
| FR-005 | No regression to present/corrupt paths | As a maintainer, I want the present-lanes and corrupt-lanes behaviours unchanged. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single canonical authority | The fix extends the existing `_resolve_lanes_manifest_or_stop` seam; no second lanes-resolution authority and no coord-aware read is introduced (`lanes.json` is PRIMARY-partition per `artifacts.py`). | Reliability | High | Open |
| NFR-002 | Type + lint clean | `ruff check`, `ruff format --check`, and `mypy --strict` pass with zero new issues; no new suppressions. | Maintainability | High | Open |
| NFR-003 | Complexity ceiling | Touched functions remain ≤15 cyclomatic complexity (Ruff C901 / Sonar S3776). | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | ATDD / red-first | An issue-pinned `@pytest.mark.regression` repro driven through the real `spec-kitty accept` entry point (or `collect_feature_summary`) must be RED on the base and GREEN after the fix (ADR 2026-07-17-1). | Technical | High | Open |
| C-002 | Invert the codified-bug test | The existing `tests/characterization/test_trio_pure_cores.py::test_missing_lanes_manifest_is_a_silent_noop` codifies the defect and must be inverted to assert fail-closed diagnostics. | Technical | High | Open |
| C-003 | Scope: accept only | Do not touch `merge`'s `--skip-lanes` opt-in; the optional defense-in-depth (merge independently re-asserting acceptance) is noted as future architecture in the PR body, not implemented here. | Technical | High | Open |

### Key Entities

- **`lanes.json` (LANE_STATE)**: the finalize-tasks output manifest; PRIMARY-partition artifact.
  Its presence gates lane-based acceptance evaluation.
- **`AcceptanceSummary`**: the accept-time verdict object; `.ok` currently consults
  `activity_issues` (and others) but **not** `skipped_checks`/`blocked_checks` — so the fix must
  land an `activity_issue` to flip `ok`.
- **`AcceptanceCheckDiagnostic`**: the `{check, detail}` record used for skipped/blocked checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue #4891 probe (lanes.json removed) makes `spec-kitty accept` exit non-zero
  with `summary.ok=False`, down from the current exit 0 / `ok=True`.
- **SC-002**: No `accepted_at`/`accept_commit` is written or committed to `meta.json` in the
  absent-lanes case (was: written and committed).
- **SC-003**: The absent-lanes case reports ≥4 skipped acceptance-matrix checks and a
  `lanes_manifest` blocked check (was: empty).
- **SC-004**: The present-lanes and corrupt-lanes cases are byte-for-byte unchanged in behaviour
  (regression suite green).
