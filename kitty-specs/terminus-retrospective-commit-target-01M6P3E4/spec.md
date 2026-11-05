# Mission Specification: Terminus retrospective commit target

**Mission Branch**: `issue-7201-terminus-retrospective-target`
**Created**: 2026-11-05
**Status**: Draft
**Input**: GitHub issue #7201 — "mission close refuses to commit the terminus retrospective when consolidate ran with --target"

## Context and the question this mission answers

Issue #7201 reports two symptoms after `spec-kitty consolidate --mission <m> --target <topic-branch>`:

1. `safe_commit` warns `HEAD is '<topic>', expected 'main'` and **refuses** to make the
   post-completion bookkeeping commit;
2. `retrospective.yaml` and `status.events.jsonl` are left **uncommitted** in the working tree.

The issue's proposer asks whether the refusal or the missing commit is the defect. This
mission settles that before changing either, because the two answers prescribe opposite fixes:

- if the **refusal** were the defect, the fix would relax `safe_commit`'s
  HEAD-must-match-destination guard;
- if the **missing commit** were the defect, the fix would be to make the terminus
  commit harder (retry, `--no-verify`, or a raw `git commit`).

**Neither is the defect, and neither is changed.** The guard is correct: it exists so a
commit can never be written to a branch the caller did not declare, and the branch the
caller declared (`main`, read from `meta.json`'s `target_branch` through the placement
port) is genuinely not the branch the checkout is on. Committing to `main` from a
`<topic-branch>` checkout would move a ref the operator is not on — and would be an
unauthorized write when `main` is protected. The missing commit is not a defect either: it
is the **deliberate fail-open** policy of the terminus (a retrospective failure must never
abort a merge or a close) reporting a refusal it could not resolve.

The defect is one layer up, in the **destination the terminus asks for**. The consolidate
run has already resolved the landing branch (`--target <topic-branch>`, persisted as
`ConsolidationState.target_branch`, the FR-007 single-persisted-merge-target authority) but
does not hand it to the terminus. The terminus therefore re-derives a destination from
`meta.json`, which is stale for this run, and asks `safe_commit` to commit to `main`. The
mechanism to hand it over already exists and is already used by the merge executor's own
bookkeeping commit (`commit_merge_bookkeeping(destination_ref_override=...)`, #4985/#4991)
— the terminus's two call sites simply do not use it.

So: **the refusal is right, the leftover is its consequence, and the wrong side is the
caller that withheld the resolved target.** This mission threads that target through and
leaves the guard untouched.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidate lands the retrospective on the branch it merged into (Priority: P1)

An operator consolidates a Mission into a topic branch (`spec-kitty consolidate --mission
<m> --target topic/x`) instead of straight to `main`. Today the retrospective capture
succeeds, the bookkeeping commit is refused, and the operator is left with two dirty files
and a warning to clean up by hand. After this mission the retrospective and its event-log
append are committed onto `topic/x` by the same run, with no manual step.

**Why this priority**: this is the reported defect and the only path that carries the
learning record automatically. Every other story here exists to make a refusal recoverable.

**Independent Test**: in a scratch git repo whose `kitty-specs/<slug>/meta.json` names
`target_branch: main` and whose HEAD is `topic/x`, run the terminus with the resolved target
supplied — the commit lands on `topic/x`, `main` is untouched, and the tree is clean.

**Acceptance Scenarios**:

1. **Given** a Mission whose `meta.json` target is `main` and a checkout on `topic/x`, **When**
   the terminus runs with the consolidate run's resolved target, **Then** `retrospective.yaml`
   and `status.events.jsonl` are committed onto `topic/x` and `main`'s tip is unchanged.
2. **Given** the same Mission consolidated *without* `--target`, **When** the terminus runs,
   **Then** the commit lands on `main` exactly as before (resolution still comes from
   `meta.json`; no destination is invented).

---

### User Story 2 - The recovery command can be aimed at the branch that was landed (Priority: P2)

The terminus's warning already names a recovery command, `spec-kitty mission close
--mission <m>`. Issue #7201 records that this recovery "has the same limit": it resolves the
same stale `meta.json` destination. An operator who has to heal a Mission consolidated onto a
topic branch needs the printed command to work as printed.

**Why this priority**: without it the fix is unrecoverable for Missions already consolidated
before this change, which is exactly the population that hit the bug.

**Independent Test**: run the terminus on a checkout where the commit is refused, and assert
the warning's command carries the target the terminus was given; then run `mission close
--mission <m> --target topic/x` and assert the recovered commit lands on `topic/x`.

**Acceptance Scenarios**:

1. **Given** a refused terminus commit whose resolved target was `topic/x`, **When** the
   warning is rendered, **Then** the recovery command it prints includes `--target topic/x`.
2. **Given** a merged Mission with dirty retrospective artifacts and a checkout on `topic/x`,
   **When** the operator runs `spec-kitty mission close --mission <m> --target topic/x`,
   **Then** the artifacts are committed onto `topic/x`.
3. **Given** `spec-kitty mission close` invoked without `--target`, **When** it closes a
   Mission, **Then** its behaviour is byte-identical to today (placement resolution from
   `meta.json`).

---

### User Story 3 - The commit guard is demonstrably not what changed (Priority: P3)

A reviewer of this change must be able to see that the fix did not buy green by weakening
`safe_commit`: a destination that disagrees with HEAD must still be refused, and the terminus
must still fail open (warn, never raise) when it is.

**Why this priority**: the whole mission's premise is that the refusal is correct. If the fix
made the guard permissive, the class of defect that produced #7201 would come back as
"committed onto a branch the operator never declared".

**Independent Test**: call the terminus on the same fixture without a resolved target and
assert the files stay uncommitted, the guard's message is still produced, and no exception
escapes.

**Acceptance Scenarios**:

1. **Given** a checkout on `topic/x` and a Mission whose `meta.json` target is `main`, **When**
   the terminus runs with no resolved target, **Then** the commit is still refused, no ref
   moves, and the refusal is reported as a warning (not raised).

### Edge Cases

- **Coord topology teardown**: the consolidate path persists the retrospective inside the
  shared teardown seam (`teardown_coordination_topology` → `_persist_retrospective`), before
  the coordination worktree is destroyed. That leg must carry the resolved target too, or the
  fix only reaches the post-merge call site and the reported warning still fires.
- **Target equal to the meta target** (the ordinary `--target main`, or no `--target`): the
  threaded value must produce a commit identical to today's.
- **A target that does not exist as a branch**: the existing destination-not-found refusal
  must still fail open in the terminus (warn, never abort the merge).
- **`mission close --discard`**: the abandonment leg persists a `runtime_abandoned`
  retrospective through the same seam; threading the target must not change its provenance
  stamping or its teardown ordering.
- **Unresolvable destination**: a legacy Mission with no usable identity must keep today's
  degrade behaviour (the `meta.json` target_branch degrade ref), not newly fail.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Terminus accepts a resolved destination | As an operator, I want the terminus retrospective commit to be told which branch this run landed on, so that the commit lands there instead of on a stale `meta.json` target. | High | Open | [build] | no |
| FR-002 | Consolidate threads its resolved target | As an operator running `consolidate --target <branch>`, I want the retrospective bookkeeping commit to land on `<branch>` without a manual step. | High | Open | [build] | no |
| FR-003 | Teardown seam carries the target | As an operator, I want the retrospective persisted before coordination teardown to land on the resolved target, so the fix is not limited to the post-merge call site. | High | Open | [build] | no |
| FR-004 | Recovery command can be aimed | As an operator healing a Mission consolidated onto a topic branch, I want `mission close` to accept `--target <branch>` so the printed recovery command works as printed. | Medium | Open | [build] | no |
| FR-005 | Warning names the aimable recovery | As an operator reading the refusal warning, I want the recovery command it prints to carry the resolved target, so copy-paste heals the Mission. | Medium | Open | [build] | no |
| FR-006 | Guard unchanged | As a maintainer, I want `safe_commit`'s HEAD/destination refusal and the terminus's fail-open policy to be unchanged, so the fix cannot hide wrong-branch commits. | High | Open | [ratchet] | no — paired with the same-fixture positive control in FR-002 (a resolved target must commit, an unresolved one must refuse) |
| FR-007 | Absent target is unchanged behaviour | As a maintainer, I want `mission close` without `--target` and consolidate without `--target` to behave exactly as today, so the change is additive. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new guard-capability call site | The fix routes only through the sanctioned `commit_merge_bookkeeping` surface; the architectural ratchet `tests/architectural/test_guard_capability_call_sites.py` stays green with no new entry. | Maintainability | High | Open |
| NFR-002 | No checkout-derived destination | Every destination the fix introduces is a caller-resolved value, never a HEAD read; `tests/architectural/test_no_write_side_rederivation.py` stays green with no new allow-list entry. | Architecture | High | Open |
| NFR-003 | Diff-coverable | Every new branch/helper introduced by the fix is executed by a test in this PR (CI diff-cover ≥90% on changed lines). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Additive optional parameter | The new destination parameter is keyword-only and defaults to `None` (today's behaviour), never a required argument. | Technical | High | Open |
| C-002 | Fail-open preserved | The terminus must keep warning and returning `None` on any commit failure; no path may newly raise into merge/close. | Technical | High | Open |
| C-003 | No gate weakening | No test may be skipped, xfailed or loosened to make this change pass. | Process | High | Open |

### Key Entities

- **Resolved merge target**: the branch a consolidate run lands on, resolved once as
  `--target` > persisted `ConsolidationState.target_branch` > `meta.json` > repo default, and
  carried in-memory as `lanes_manifest.target_branch`.
- **Terminus retrospective commit**: the single bookkeeping commit that persists
  `kitty-specs/<slug>/retrospective.yaml` and its `status.events.jsonl` append, reached from
  both `consolidate` and `mission close`.
- **`destination_ref_override`**: the existing `commit_merge_bookkeeping` parameter that lets
  a caller supply the authoritative resolved target in place of placement resolution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consolidate run with `--target <branch>` leaves `retrospective.yaml` and `status.events.jsonl` committed on `<branch>` and the working tree clean — 0 uncommitted terminus artifacts, asserted on a real git fixture. — [build] · no-op passable: no
- **SC-002**: `main`'s tip is unchanged by that run (0 ref movement on any branch other than the target). — [build] · no-op passable: no
- **SC-003**: The same fixture with no resolved target still refuses and leaves both files uncommitted — the guard's positive control (resolved target commits, unresolved refuses) is asserted in the same test file from one shared fixture. — [ratchet] · no-op passable: no
- **SC-004**: The warning emitted on refusal contains the exact aimable recovery command (`spec-kitty mission close --mission <slug> --target <branch>`) for the resolution that was attempted. — [build] · no-op passable: no
