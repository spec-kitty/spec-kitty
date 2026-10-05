# Mission Specification: Frozen lanes for started work packages

**Mission Branch**: `issue-5573-frozen-started-lanes`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief: deliver #5573. Re-running finalize-tasks must never move a started work package to another lane. #5573 is a regression of #3311 in 4.0.0rc5. The aim is a structural bugfix.

**Grounding**: [`research/code-grounding.md`](research/code-grounding.md). This spec turns its decisions D1–D8 into requirements.

## Intent Summary (confirmed from the operator brief)

- **Primary actor**: an operator, or an agent acting for them, who amends the plan of a `lanes` (or
  `lanes_with_coord` / `coord`) mission after execution has started, and then re-runs `finalize-tasks`.
- **Trigger**: a routine planning amendment, for example widening a planned work package's owned files so that it
  overlaps a started one, followed by `spec-kitty agent mission finalize-tasks`.
- **Desired outcome**: every work package that has already started stays on the execution lane that holds its work.
  Unstarted work packages may still be regrouped. If a run cannot keep a started work package's lane, it refuses
  before it writes anything, names a stable error code, and gives a remedy that destroys nothing.
- **Invariant**: once a work package has started, its lane membership is a fact the lane manifest preserves. It is no
  longer the output of a grouping heuristic.
- **Explicit non-goal**: retiring a canceled work package by clearing its scope (the #3432 residual). It is deferred to
  the #3550 epic; decision `01M444ZPVGXPXZY365PGJ7K68P` records why.

## Domain Language

| Term | Meaning in this mission | Avoid |
|---|---|---|
| **Started work package** | A work package whose status history has ever recorded a move into a working state: any lane other than `planned`, `blocked` or `canceled` (that is `claimed`, `in_progress`, `for_review`, `in_review`, `approved`, `done`, including forced or `blocked → in_progress` moves that skip `claimed`). Being reset to `planned` or canceled afterwards does not make it unstarted. | "active WP", "in-flight WP" (ambiguous about resets) |
| **Execution lane** | A group of work packages that share one lane branch and one worktree, identified by a lane id (`lane-a`, …), recorded in the lane manifest (`lanes.json`). | "lane" alone, when it could mean a status lane such as `in_progress` |
| **Recorded lane** | The execution lane a work package belongs to in the lane manifest as it stood before this finalize run. | |
| **Re-finalize** | Any `finalize-tasks` run on a mission that already has a lane manifest. | "re-plan" |
| **Lane work tip** | The recorded tip of a lane branch (`refs/spec-kitty/lane-tip/<branch>`), as defined in CLAUDE.md "Lane work tips". | |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An amendment that overlaps a started work package keeps it on its lane (Priority: P1)

WP02 is in progress and has committed work on lane-b. The operator amends WP01, which is still planned, so that it
also owns WP02's file and depends on WP02. They re-run `finalize-tasks`. Both work packages now belong to one lane.
That lane is **lane-b**, the one holding WP02's work, and WP01 runs after WP02 within it. The next `implement WP02`
reuses the lane-b worktree with the committed work visible.

**Why this priority**: this is the reported defect (#5573). Today `finalize-tasks` exits 0 and moves WP02 to lane-a.
`implement WP02` then fails with `LaneWorkTipUnknownError` until someone repairs it by hand in git.

**Independent Test**: reproduce the issue's steps through the `agent mission finalize-tasks` entry point. Assert that
WP02's lane id is unchanged, that the run succeeds, and that the next allocation of WP02 resolves to the worktree
holding its committed work.

**Acceptance Scenarios**:

1. **Given** lane-a = [WP01 (planned)] and lane-b = [WP02 (in_progress, committed work)], **When** WP01 is amended to
   overlap and depend on WP02 and `finalize-tasks` re-runs, **Then** it succeeds, the manifest has one lane `lane-b`
   holding [WP02, WP01], and allocating WP02 again returns the original lane-b worktree with its committed work.
2. **Given** the same mission with WP02 only `claimed` (no commits yet), **When** the same amendment is re-finalized,
   **Then** WP02 still stays on lane-b.
3. **Given** the mirror case, where WP01 is started on lane-a and WP02 is planned, **When** WP02 is amended to overlap
   WP01, **Then** the merged lane is lane-a. The outcome follows the started work package, not lane-id order.

---

### User Story 2 — An amendment that cannot keep every started work package in place is refused before anything is written (Priority: P1)

WP01 is started on lane-a and WP02 is started on lane-b. An amendment makes them overlap, which would force both into
one lane. One lane cannot be two branches, so `finalize-tasks` refuses. It names a stable error code, the work
packages and lanes involved, and a non-destructive remedy. The lane manifest, the status log, the work package files
and git history are all left exactly as they were.

**Why this priority**: a silent success that moves a started work package is the defect class. When moving cannot be
avoided, a loud, early refusal is the only safe outcome (this was #3311's stated expectation).

**Independent Test**: seed two started work packages on different lanes, amend them to overlap, re-finalize through the
CLI in JSON mode, and assert all of the following:
- the exit code is non-zero;
- the error code is the named one;
- the conflict lists both work packages and their recorded lanes;
- the remedy is present;
- the lane manifest and status log are byte-identical to before.

**Acceptance Scenarios**:

1. **Given** two started work packages on different recorded lanes, **When** an amendment forces them into one lane and
   `finalize-tasks --json` runs, **Then** it exits non-zero with error code `LANE_MEMBERSHIP_FROZEN`, a conflict entry
   naming both work packages and their recorded lanes, and a remedy, and nothing is written.
2. **Given** the same mission, **When** `finalize-tasks --validate-only` runs, **Then** it reports the same refusal.
3. **Given** a started work package whose task file has been removed from the plan, **When** `finalize-tasks` runs,
   **Then** it refuses with `LANE_MEMBERSHIP_FROZEN`, naming that work package. The remedy is to restore the file and
   cancel the work package instead.
4. **Given** a started work package whose kind changed between code change and planning artifact (crossing the
   planning lane), **When** `finalize-tasks` runs, **Then** it refuses with `LANE_MEMBERSHIP_FROZEN`.
5. **Given** a mission with an existing lane manifest whose status log exists but is malformed (or whose status
   surface cannot be resolved), **When** `finalize-tasks` runs, **Then** it refuses with `LANE_MEMBERSHIP_FROZEN`
   instead of assuming nothing has started.
6. **Given** a mission with an existing lane manifest and **no** status log at all (for example, a legacy finalize that
   wrote the manifest before seeding status), **When** `finalize-tasks` runs, **Then** it proceeds. No history means
   nothing has started (lane work tips still count). This is the positive control for scenario 5.
7. **Given** a refusal for started work packages from two lanes forced together, **When** the operator applies the
   remedy the refusal names (removing the overlap between them), **Then** the next re-finalize succeeds. Each refusal
   reason names a remedy that resolves it.

---

### User Story 3 — Unstarted work packages can still be regrouped, deterministically (Priority: P2)

Before any work package starts, or for the work packages that have not started yet, the operator can still amend
ownership and dependencies and re-finalize. The resulting lane grouping and lane ids are deterministic: the same
inputs always give the same manifest. Lane ids follow a documented rule: lanes keep the id of the prior lane they share
the most work packages with, ties go to the lowest prior lane id, and new lanes get the next free id. A lane id that
held started work is never handed to a different group.

**Why this priority**: amending unstarted work is a supported, routine operation (#4141, ADR 3.x `2026-07-29-1`). The
fix must not freeze the whole manifest.

**Independent Test**: re-finalize missions with no started work packages through permutations of merge, split, add and
remove amendments. Assert that the output equals the documented rule and is identical across repeated runs.

**Acceptance Scenarios**:

1. **Given** a mission where nothing has started, **When** an amendment merges two lanes, **Then** re-finalize
   succeeds and regroups them, and the merged lane takes the lowest tied prior lane id (unchanged behaviour).
2. **Given** a started work package on lane-b and a planned lane-mate, **When** an amendment moves the planned
   lane-mate into its own new lane, **Then** re-finalize succeeds, the started work package keeps lane-b, and the new
   lane gets a fresh id that never held started work.
3. **Given** any amendment and any set of started work packages (the property sweep), **When** re-finalize runs,
   **Then** every started work package either keeps its recorded lane id or the run refuses. Never anything in
   between.

### Edge Cases

- Two started work packages share a recorded lane, and an amendment removes the overlap that grouped them. They stay
  together on their lane: the lane branch already holds both work packages' commits.
- A started work package was rejected back to `planned`. It is still started: its lane branch holds its work.
- A work package went straight from `planned` to `canceled` or `blocked`, without ever being claimed. It is not
  started.
- A started work package gains a dependency on a planned lane-mate. Both stay in the started work package's lane, and
  the lane orders them by dependency.
- Cancellation handling is unchanged.
  - A work package canceled through the status log stays a member of its recorded lane, as it does today.
    Consolidation's canceled-content checks rely on it staying listed.
  - A work package excluded from lane computation by the existing cancellation projection (#3713) is leaving through
    cancellation, not being moved. This holds whether it counts as started through its history or through the
    lane-work-tip fallback. It is not refused under FR-005, and its recorded lane id stays reserved (FR-004).
- A recorded lane has a lane work tip, but no work package in it shows a started history (for example, work committed
  before the claim was recorded). All of that lane's recorded members are treated as started. A tip is recorded as
  soon as a lane is allocated, even before any commit, so this can freeze a lane that was allocated but never worked
  on. Freezing too much is the safe direction: the cost is a refusal, never stranded work.
- First finalize (no lane manifest yet): behaviour is unchanged. Lane ids are minted positionally.
- `single_branch` missions have one repository-root lane and nothing to move. Behaviour is unchanged.
- The planning lane (`lane-planning`) keeps its fixed id. A started work package can never be moved into or out of it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Started work packages keep their recorded lane | As an operator, I want every started work package to keep its recorded lane id on re-finalize so that its committed work stays reachable by the next implement. | High | Open | [build] | no — #5573's reproduction moves WP02 to lane-a today |
| FR-002 | Lane follows the started member | As an operator, I want a regrouped lane that contains exactly one recorded lane's started work packages to take that lane's id, regardless of lane-id order or the order groups are processed in, so that tie-breaks and group order can never move started work. | High | Open | [build] | no — the mirror case (WP02 started) fails today while WP01-started passes by luck |
| FR-003 | Started lane-mates stay together | As an operator, I want started work packages that share a recorded lane to remain in one lane after re-finalize so that neither is split away from the branch holding its commits. | High | Open | [build] | no — a split amendment re-letters one of them today |
| FR-004 | Lane ids that held started work are never re-minted | As an operator, I want a recorded lane id that held a started work package never minted for a new lane. A regrouped lane that still shares members with that recorded lane may continue under its id. The point is that new work never lands on a branch carrying someone else's commits. | Medium | Open | [build] | no — today an orphaned id is re-minted for a new group |
| FR-005 | Refuse unsatisfiable re-finalizes before any write | As an operator, I want finalize-tasks to refuse when an amendment would force started work packages from different recorded lanes into one lane, would drop a started work package from the plan, or would move it across the planning lane. The refusal comes before any status or manifest write, and finalize's existing restore leaves every mission file byte-identical, so a broken manifest is never committed. Refusing the removal of a started work package's task file is an intentional behaviour change: today it succeeds and strands the work. | High | Open | [build] | no — two-started-lanes collapse exits 0 today |
| FR-006 | Named refusal with a non-destructive remedy | As an operator, I want each refusal to carry the stable error code `LANE_MEMBERSHIP_FROZEN`, a machine-readable reason, the conflicting work packages and recorded lanes, and a remedy specific to that reason that resolves it, so that I can recover safely. The remedies are: remove the overlap that forces started lanes together, for example by moving the shared path into a new work package; restore a removed task file and retire the work package by canceling it **without** clearing its owned files; restore a changed execution mode; repair the status log. No remedy suggests deleting the manifest, forcing, or resetting or restoring git trees. | High | Open | [build] | no — no such code exists today |
| FR-007 | Fail closed on unreadable status | As an operator, I want finalize-tasks to refuse with `LANE_MEMBERSHIP_FROZEN` when a lane manifest exists but the status log is malformed or its surface cannot be resolved, so that an unreadable log is never mistaken for "nothing started". A log that is simply absent means no history-started work package, and finalize proceeds. Where an earlier finalize step already rejects a malformed log line before lanes are considered (with its existing message), that earlier fail-closed refusal satisfies this requirement. `LANE_MEMBERSHIP_FROZEN` with reason `status_unreadable` covers the cases that reach lane computation, such as a coordination status surface that cannot be read or resolved. | Medium | Open | [build] | no — the existing execution-begun probe fails open on a malformed log |
| FR-008 | Started means "ever worked" | As an operator, I want a work package counted as started when its status history ever entered a lane other than planned, blocked or canceled, or when its recorded lane has a lane work tip but no member with such history, so that a reset, a forced move or an unrecorded claim cannot unfreeze committed work. | High | Open | [build] | no — reset-to-planned work packages are treated as unstarted today |
| FR-009 | Validate-only reports the refusal | As an operator, I want `finalize-tasks --validate-only` to report the same refusal a real run would make so that I can check an amendment before applying it. | Medium | Open | [build] | no — validate-only computes lanes without the prior manifest today |
| FR-010 | Unstarted regrouping stays supported and deterministic | As an operator, I want amendments of unstarted work packages to keep regrouping lanes, with the documented lane-id rule (most shared members, then lowest prior lane id, then next free id), so that routine planning amendments keep working. | Medium | Open | [ratchet] | yes — paired with FR-001/FR-005 on the same fixtures (the property sweep asserts both halves) |
| FR-011 | Existing re-finalize guarantees hold | As an operator, I want the #4945 lane-id read-back, the #3311 planning-commit preservation, the recorded mission branch (FR-011 of ADR 3.x 2026-09-26-2), and finalize atomicity (#5641) to keep holding so that this fix regresses none of them. | High | Open | [ratchet] | yes — pinned by the existing regression tests, which stay green |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added latency | A re-finalize of a mission with 30 work packages takes at most 200 ms longer than on the base commit (median of 5 runs on the same machine). The extra work is one status read and lane-tip lookups. | Performance | Medium | Open |
| NFR-002 | Deterministic output | Re-running finalize-tasks on unchanged inputs produces a byte-identical lane manifest (apart from `computed_at`) in 10 of 10 runs, across all permutation fixtures. | Reliability | High | Open |
| NFR-003 | Quality gates | All new and changed code passes `ruff check`, `ruff format --check`, and `mypy` with zero findings and no new suppressions. Every touched function stays at cyclomatic complexity ≤ 15. New code has ≥ 90% line coverage (diff-cover). | Maintainability | High | Open |
| NFR-004 | Fast compute-level tests | The compute-level invariant tests (including the permutation sweep) run in under 2 s in total and carry the `fast` marker. The end-to-end CLI tests run in under 30 s in total on a warm environment. | Testability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Red-first through the entry point | A failing test that reproduces #5573 through `agent mission finalize-tasks` is committed before the fix (charter Standing Order 4, ATDD-first). | Process | High | Open |
| C-002 | Lane computation stays pure | The lane-computation and compute-and-persist core keep reading no git and no `meta.json`. Status and lane-tip evidence is gathered by the finalize shell and passed in already resolved. | Technical | High | Open |
| C-003 | Existing refusal texts unchanged | Existing finalize error codes and messages stay byte-identical. Only the new `LANE_MEMBERSHIP_FROZEN` refusal is added. | Technical | High | Open |
| C-004 | No new gates or allowlists | No new size, ratchet or allowlist gates are introduced (ADR 4.x `2026-09-30-1`). Issue priorities are not changed. | Process | Medium | Open |
| C-005 | Sibling missions' files untouched | `src/specify_cli/cli/commands/implement.py` and `src/specify_cli/core/mission_creation.py` (in-flight sibling missions #5635 and #5634) are not modified. | Process | High | Open |
| C-006 | No new third-party dependency | The property-style sweep uses the standard library and pytest only. `hypothesis` is not added. | Technical | Medium | Open |
| C-007 | Tidy-first ordering | Behaviour-preserving enabler commits that make the fix testable come before the red test (DIRECTIVE_025). | Process | Medium | Open |
| C-008 | Terminology | Prose uses Mission / work package canon. `feature` is not introduced. Error remedies reference `--mission`. | Process | Medium | Open |

### Key Entities

- **Lane manifest**: the per-mission record of execution lanes (id, member work packages, write scope, dependencies),
  rewritten by each finalize. It is the single authority for which lane a work package executes on. It has four write
  paths:
  - `agent mission finalize-tasks`: can rewrite an existing manifest, and is the path this mission guards.
  - The legacy `agent tasks finalize-tasks`: writes only when no manifest exists.
  - The `doctor mission-state --fix` rebuild: writes only when no manifest exists.
  - The planning-commit refresh: rewrites only the recorded planning commit, never membership.

  Only the first can move a started work package. All three membership-computing paths share the one
  compute-and-persist core, which enforces the invariant.
- **Started work package set**: the work packages whose lane membership the next manifest must preserve. It is derived
  from the status history (and lane work tips) for each finalize run.
- **Frozen membership**: the mapping from started work package to recorded lane id. Lane computation honours it as a
  constraint.
- **Membership conflict**: one reason that frozen membership cannot be honoured (two recorded lanes in one group,
  removed work package, kind change, unreadable status). It carries the work packages and lanes involved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5573 reproduction, the re-finalize succeeds and the next `implement WP02` resumes on the worktree
  holding WP02's committed work, in 3 of 3 runs. — [build] · no-op passable: no
- **SC-002**: Across the permutation sweep (all subsets of started work packages × merge/split/add/remove amendments ×
  both lane-id orders), 0 cases move a started work package to a different lane while reporting success. —
  [build] · no-op passable: no
- **SC-003**: Every refusal leaves the lane manifest, the status log, `tasks.md`, `meta.json` and the work package
  files byte-identical (100% of refusal cases checked). — [build] · no-op passable: no
- **SC-004**: All pre-existing re-finalize regression tests for #3311, #4945, #4141 and #5641 still pass, and missions
  with no started work packages and no lane work tips get the same manifest as on the base commit, apart from the
  documented FR-004 id reservation, which never applies when nothing has started. — [ratchet] · no-op passable: yes
  (paired with SC-001/SC-002 on the same fixtures)

## Assumptions

- Status events are the sole authority for work package lifecycle (frontmatter `lane` is retired). The started set is
  read from the same status surface the planning-commit guard already reads (coordination-aware).
- Lane branch and worktree names are keyed only on the lane id, so preserving the lane id preserves access to the work.
- A lane work tip is evidence that its lane holds work, even when the status history is silent.

## Out of Scope (follow-ups filed)

- The #3432 residual: retiring a canceled work package by clearing its scope. Follow-up: #5701 (under #3550).
  Rationale: decision `01M444ZPVGXPXZY365PGJ7K68P`, grounding D7.
- Moving the planning-commit "execution has begun" probe, and its doctor twin, onto the history-based started
  predicate. Follow-up: #5702.
- The `doctor mission-state --fix` lane-manifest rebuild, which re-mints lane ids with no prior manifest. Follow-up:
  #5703.
- The wording of the allocator's `LaneWorkTipUnknownError` remedy (its text is frozen by C-003), and per-work-package
  lane-change reporting in the finalize JSON. Deferred: once started work packages can no longer move, neither is
  needed to close this defect.
- Stale cached `lane_wp_ids` in workspace contexts after a re-finalize: see #5539, cross-referenced only.

## References

- #5573 (this defect); #3311 and #3432 (originals); #4945 / PR #5020 (lane-id read-back); #5080 (sibling lane-identity
  invariant); #5115 (lane work-tip guard); #5641 / PR #5662 (finalize atomicity); epics #1795, #3550, #1676.
- ADR 3.x `2026-07-29-1` (finalize-tasks is the single `lanes.json` writer), ADR 3.x `2026-09-26-2` (lane naming;
  refuse, never rescue), terminus-merge-integrity FR-010 (lane id bound to its branch).
