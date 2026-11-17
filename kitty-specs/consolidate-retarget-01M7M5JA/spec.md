# Mission Specification: Consolidate retarget adopts the override target

**Mission Branch**: `kitty/mission-consolidate-retarget-01M7M5JA` (lands on `issue-7692-consolidate-retarget`)
**Created**: 2026-11-17
**Status**: Draft
**Input**: Issue #7692: "consolidate --target: adopt the override as the Mission's new recorded target (#5783 follow-up)".

## Intent Summary (confirmed)

- **Actor:** an operator consolidating a Mission with `spec-kitty consolidate`.
- **Trigger:** the Mission is recorded for one target branch (`meta.json` `target_branch`), and the operator wants it landed on another one.
- **Today:** since #5783 (PR #7688), every differing `--target` is refused with `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`, because part of the bookkeeping still commits to the recorded target. The operator's only route is to edit `meta.json` by hand, commit it and re-run.
- **Outcome:** an explicit, recorded retarget. The new target becomes the Mission's recorded target as the run's first change, and every write the run makes (the landing and all its bookkeeping) lands there. `--abort` and failures undo the retarget through the one rollback authority; `--resume` honours it.
- **Invariant:** a retarget never weakens a guard. A plain `--target` is refused exactly as today. A protected new target is refused exactly as a protected `--target` is today.

### Operator rulings (2026-11-17, relayed by the core triager)

| # | Question | Ruling |
|---|----------|--------|
| 1 | Opt-in | An explicit `--retarget` that requires `--target <branch>`. A plain `--target` keeps `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`, and that refusal's next step now also offers `--retarget`. |
| 2 | When the record is rewritten | Up front. The retarget is in effect before the run's pre-mutation snapshot, and the `meta.json` rewrite is committed as the run's first change, with provenance (from, to, actor, at, reason). `--retarget-reason` is optional with a default. |
| 3 | Resume, abort, rollback | The retarget is persisted in the run record and undone by the one rollback authority (ADR `2026-09-19-1`, amended). `--resume` honours it and never commits it twice. |
| 4 | Protection | No bypass: the #6464 and #5385 guards judge the new target before anything is written. |
| 5 | Parity | `--dry-run` forecasts the retarget with the same codes. `orchestrator-api consolidate-mission` refuses a retarget: it has no rollback door. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retarget a lanes or coordination Mission and land it in one place (Priority: P1)

An operator has a Mission recorded for `main` and decides that it must land on `develop`. With the root checkout on `develop`, they run `spec-kitty consolidate --mission <m> --target develop --retarget`. The run records `develop` as the Mission's target, lands the work there, and commits every piece of bookkeeping on `develop`. The run exits 0 with a clean tree, and `main` receives nothing.

**Why this priority**: this is the feature. Without it, the documented override is refuse-only.

**Independent Test**: the #5783 reproducer fixtures (lanes and coord, with `main` unprotected) run through the real CLI.

**Acceptance Scenarios**:

1. **Given** a lanes Mission recorded for `main` with the root checkout on `develop`, **When** the operator runs `consolidate --target develop --retarget`, **Then** the exit code is 0, the Mission's content is on `develop`, `develop`'s committed `meta.json` names `develop` as the target together with a retarget provenance record, every WP is `done` on the status surface, `kitty-specs/` is clean in the root checkout, and `main`'s tip and reflog are unchanged.
2. **Given** the same on a coord Mission, **When** the same command runs, **Then** the same holds, and the committed `meta.json` on `develop` does not name the deleted coordination branch.
3. **Given** either Mission, **When** the run completes, **Then** the retrospective, the mission-number bake and the teardown and gate-matrix projections are all committed on `develop` (no write is refused with a HEAD mismatch, and nothing is left dirty or untracked).

---

### User Story 2 - A plain `--target` keeps refusing (Priority: P1)

An operator who passes `--target develop` without `--retarget` is refused exactly as today, and the refusal now names `--retarget` as one way forward.

**Why this priority**: the #7688 protection must not weaken.

**Independent Test**: the existing #5783 override and dry-run arms stay green, and the remedy text names `--retarget`.

**Acceptance Scenarios**:

1. **Given** the #5783 override arm, **When** `consolidate --target develop` runs, **Then** it refuses with `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` before anything moves, and the next step mentions `--retarget`.
2. **Given** any Mission, **When** `--retarget` is passed without `--target`, **Then** the command exits with a usage error and moves nothing.

---

### User Story 3 - Abort, failure and resume of a retargeted run (Priority: P1)

A retargeted run that is aborted, or that fails after its first change, leaves the Mission recorded for its old target and the new target branch at its pre-run tip. An interrupted retargeted run resumes onto the new target without committing the retarget twice.

**Why this priority**: the retarget is a mutation of the record. It must be undoable by the same authority as every other mutation.

**Independent Test**: inject a failure after the retarget commit, then run `--abort` and assert the restore; separately, interrupt a run after the retarget commit and run `--resume`.

**Acceptance Scenarios**:

1. **Given** a retargeted run that failed after its retarget commit, **When** rollback runs (the failure itself, or `consolidate --abort`), **Then** `develop` is back at its pre-run tip, `develop`'s `meta.json` again names the old target, and the merge record is cleared or re-baselined as for any fully restored run.
2. **Given** a retargeted run interrupted after the retarget commit, **When** `consolidate --resume` runs, **Then** it lands on `develop`, creates no second retarget commit, and exits 0.
3. **Given** a persisted retarget to `develop`, **When** `consolidate --resume --target X --retarget` names a different `X`, **Then** it is refused with a named code and nothing moves.

---

### User Story 4 - Protection is never bypassed (Priority: P1)

A retarget onto a protected branch is refused exactly as a protected `--target` is today (#6464). A retarget onto a branch whose done bookkeeping the status-write policy would refuse is refused before anything moves (#5385).

**Acceptance Scenarios**:

1. **Given** a Mission recorded for an unprotected branch and a protected `main` as the new target, **When** `consolidate --target main --retarget` runs, **Then** it refuses with `PROTECTED_BRANCH_REFUSED` before anything moves, and the Mission's `meta.json` is unchanged.

---

### User Story 5 - Forecast and external-orchestrator parity (Priority: P2)

`consolidate --dry-run --target develop --retarget` forecasts the retarget: the same refusals and codes as the real run, and the planned retarget in its JSON. `orchestrator-api consolidate-mission` cannot retarget, and a differing target there keeps its current refusal.

**Acceptance Scenarios**:

1. **Given** the #5783 fixtures, **When** `--dry-run --json --target develop --retarget` runs, **Then** it reports no refusal and includes a `retarget` object naming `main` → `develop`, and moves nothing.
2. **Given** a protected new target, **When** the same forecast runs, **Then** it reports `PROTECTED_BRANCH_REFUSED` exactly as the real run does.
3. **Given** `orchestrator-api consolidate-mission` with a target differing from the record, **Then** it still refuses with `PREFLIGHT_FAILED` / `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`, and the orchestrator-api contract version does not change.

### Edge Cases

- `--target` equal to the recorded target together with `--retarget`: not a retarget. The run proceeds exactly as without the flag and makes no retarget commit.
- The root checkout is not on the new target: refused by the existing off-target preflight, before anything moves.
- `meta.json` on the new target is dirty, untracked, or missing the Mission directory: refused before anything moves, with a named code.
- The new target's `meta.json` names a target that is neither the old one nor the new one (the record drifted between branches): the retarget records the value it actually replaced.
- `--resume` with no `--target` after a retarget: honours the persisted retarget.
- `--retarget` on a `single_branch` Mission with no lanes (the planning-artifact-only path): see C-006.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Explicit opt-in | As an operator, I want `consolidate --target <b> --retarget` to retarget the Mission, and `--retarget` without `--target` to be a usage error that moves nothing, so that a retarget is always deliberate. | High | Open | [build] | no |
| FR-002 | Plain override unchanged | As an operator, I want a plain `--target <b>` (no `--retarget`) on a Mission recorded for another branch to keep refusing with `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` before anything moves, with a next step that now also names `--retarget`, so that #7688's protection holds. | High | Open | [ratchet] | yes — paired with FR-003 on the same fixture |
| FR-003 | Retarget lands everything on the new target | As an operator, I want a retargeted run on a lanes or coord Mission to exit 0 with the landing and every write in #7688's S4 table (per-WP done, coord flatten, landed mission-branch clear, retrospective, mission-number bake, teardown and gate-matrix projections, lane-context tombstones, merge bookkeeping) committed on the new target and a clean tree, so that the result, the status log and git agree. | High | Open | [build] | no |
| FR-004 | Recorded with provenance | As an operator, I want the new target's committed `meta.json` to name the new target and carry a retarget record (from, to, actor, at, reason), written as its own commit before the landing, so that the record shows who changed the target and why. | High | Open | [build] | no |
| FR-005 | Reason flag | As an operator, I want an optional `--retarget-reason "<why>"` that goes into the provenance (a fixed default is recorded when it is omitted), and passing it without `--retarget` to be a usage error, so that the reason is captured when I give one. | Medium | Open | [build] | no |
| FR-006 | Rollback restores the retarget | As an operator, I want a failure after the retarget commit, and `consolidate --abort`, to restore the new target branch to its pre-run tip through the one rollback authority (the old record returns with it), so that an undone run leaves no trace of the retarget. | High | Open | [build] | no |
| FR-007 | Resume honours a persisted retarget | As an operator, I want `consolidate --resume` after an interrupted retargeted run to land on the persisted new target without a second retarget commit, and to refuse a `--resume --target X --retarget` that names a different `X`, so that a resume finishes the run that was started. | High | Open | [build] | no |
| FR-008 | No protection bypass | As an operator, I want a retarget onto a protected branch refused with `PROTECTED_BRANCH_REFUSED` (#6464), and a retarget whose done bookkeeping the status-write policy would refuse on the new target refused with that policy's code (#5385, its probe re-pointed at the new target, never skipped), both before anything is written, so that `--retarget` launders no guard. | High | Open | [ratchet] | yes — paired with FR-003 on the same fixture with an unprotected target, and a protected-old-target arm that is admitted |
| FR-009 | Dry-run parity | As an operator, I want `--dry-run --target <b> --retarget` to report the same refusals and codes as the real run, include a `retarget` object (from, to) in its JSON, and move nothing, so that the forecast never promises what the run refuses. | Medium | Open | [build] | no |
| FR-010 | orchestrator-api refuses retargets | As an external orchestrator, I want `consolidate-mission` with a target differing from the record to keep refusing with `PREFLIGHT_FAILED` / `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`, with a message that points at the CLI's `--retarget`, and no contract-version change, so that a path with no rollback door never retargets. | Medium | Open | [ratchet] | yes — the existing #7688 orchestrator test is the control |
| FR-011 | Unwritable new target refused up front | As an operator, I want a retarget whose new target cannot take the retarget commit (root checkout off the new target, `meta.json` dirty, untracked or absent there) refused with a named code before anything moves, so that the first change cannot half-happen. | High | Open | [build] | no |
| FR-012 | Restating the record is not a retarget | As an operator, I want `--target <recorded> --retarget` to run exactly like a run with no override (no retarget commit, no retarget record), so that the flag is harmless when nothing changes. | Low | Open | [build] | yes — asserts the absence of a commit; paired with FR-003 |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Refusals move nothing | Every refusal this Mission adds or changes leaves 0 branch-tip changes, 0 reflog entries on the old and new targets, 0 merge records and 0 changed paths under `kitty-specs/` in the root checkout. | Reliability | High | Open |
| NFR-002 | Exactly one retarget record | A retargeted run, including one `--resume` or a re-run after a rolled-back failure, leaves exactly 1 `retarget_history` entry on the new target and writes nothing to the old target. Where the new target already carries the record (explicit layouts), it also gains exactly 1 retarget commit; on a default-topology Mission the record commit is folded into the squash landing. | Reliability | High | Open |
| NFR-003 | Test cost | The new end-to-end tests add at most 60 s of wall time to the targeted terminus and consolidation suites on a developer machine (`-n 6 --dist loadfile`). | Maintainability | Medium | Open |
| NFR-004 | Quality gates | New and changed code passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with 0 new findings, and keeps every touched function at cyclomatic complexity 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | #6464 semantics unchanged | The protected-override semantics and the operator hatch of #6464 are not changed. | Technical | High | Open |
| C-002 | #7688 refusal kept | `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` is not weakened for a plain `--target`. | Technical | High | Open |
| C-003 | One rollback authority | The retarget is undone only through the consolidation rollback authority (ADR `2026-09-19-1`); no second restore path is added. | Technical | High | Open |
| C-004 | No new architectural gate | No new architectural gate is added without operator approval. | Process | High | Open |
| C-005 | Existing seams | The bookkeeping writes reach the new target by reading the rewritten record through the existing seams. The override is not threaded through each write. | Technical | High | Open |
| C-006 | Topologies in scope | Explicit lanes and coord Missions, and default-topology Missions (`topology_source: default`) settled to `lanes_with_coord` or `single_branch`, are in scope (operator ruling 2026-11-17: no follow-up). `RETARGET_RECORD_UNWRITABLE` is kept only for a shape where no branch the landing reads carries the Mission's record. Each remaining refused shape is named in the PR with evidence. | Technical | High | Open |
| C-007 | ADR amendment | The rollback-record change is recorded as an amendment to ADR `2026-09-19-1`. | Process | High | Open |

### Key Entities

- **Recorded target**: the branch the Mission's `meta.json` names as `target_branch`; every bookkeeping write resolves it.
- **Retarget record**: the provenance of a retarget in `meta.json` (from, to, actor, at, reason).
- **Run record**: the consolidation's persisted state; it gains the retarget (from, to, commit) so `--abort` and `--resume` can act on it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On both the lanes and the coord #5783 fixtures, a retargeted run exits 0, and 100% of the S4 writes those fixtures produce (done, flatten, retrospective, mission-number, the record itself) are on the new target with a clean `kitty-specs/`. The S4 rows they do not produce (gate-matrix projection, lane-context tombstones) are shown by seam-level tests to resolve the rewritten record — [build] · no-op passable: no
- **SC-002**: On the same fixtures, a plain `--target` run is still refused, with 0 branch movement — [ratchet] · no-op passable: yes (paired with SC-001)
- **SC-003**: After an injected failure or `--abort` following the retarget commit, the new target's tip equals its pre-run tip in 100% of the tested arms — [build] · no-op passable: no
- **SC-004**: `--dry-run` and the real run agree on the refusal code, or on its absence, in 100% of the tested arms (retarget, protected retarget, plain override, `RETARGET_RECORD_UNWRITABLE` arms) — [build] · no-op passable: no

## Assumptions

- The root checkout is on the new target for a retarget (the existing off-target preflight already requires this).
- The record is written on every branch the landing reads it from: the Mission branch when it carries `meta.json` (always for default-topology Missions, whose record lives on their topic branch), and the new target when it carries it. A Mission whose record is on neither is refused (FR-011).
- The old recorded target's own copy of `meta.json` is left as it is; it never receives the Mission.

## Out of Scope

- Making the coord flatten fail closed (#7688 deferred it).
- The bookkeeping projection's write-before-validate order (#7301): recorded as a residual that a retarget does not widen.
- Retargeting through `orchestrator-api` (#7361 owns adding a rollback door there).
- Lane freshness against a new target during review (#7329).

## References

Refs #5783, PR #7688 (S4 table), #7651, #6464, #7360, #7301, #7361. Research: `research/discovery-tracked-issues.md`, `research/discovery-similar-surfaces.md`.
