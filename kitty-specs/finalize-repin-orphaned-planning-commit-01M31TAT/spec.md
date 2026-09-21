# Mission Specification: Finalize re-pins an orphaned planning_commit_sha after a rebase

**Mission Branch**: `fix/finalize-repin-orphaned-planning-commit`
**Created**: 2026-09-21
**Status**: Draft
**Input**: GitHub issue [#4827](https://github.com/spec-kitty/spec-kitty/issues/4827) — "finalize-tasks preserves an orphaned planning_commit_sha after a mid-mission rebase (lane-alloc wedge)" (P0, milestone MVP launch). Field report L1 (`docs/plans/engineering-notes/2026-09-21-full-mission-driving-tactical-workarounds-field-report.md`).

## Overview

When a mission uses lanes and its branch is rebased onto a moved base **mid-mission** (a routine event on a fast-moving `main`), the planning commit is rewritten to a new SHA. The SHA recorded in `lanes.json` (`planning_commit_sha`) is thereby **orphaned** — it is still present in the object store but is no longer reachable from the planning target-branch tip. Re-running `spec-kitty agent mission finalize-tasks` today either:

- **silently preserves** the orphaned SHA (default, no flag), or
- **refuses** to re-point it with `--refresh-planning-commit` (that flag is advance-only and treats any non-ancestor recorded SHA as a dangerous rewrite).

Downstream, `spec-kitty implement WP##` merges the recorded planning commit into each lane worktree; against an orphaned SHA that merge conflicts on the planning files (`tasks/WP*.md`) or fails allocation, and the operator sees a generic "merge conflicts — resolve manually" that misdescribes what is actually a stale pin. The same orphaned SHA silently corrupts the owned-review diff base and refuses the claim gate through other consumers. The only escape today is hand-editing `lanes.json` (proven by a trail of manual `chore(...): re-pin planning_commit_sha to HEAD` commits). This mission gives the operator a sanctioned, in-tool re-pin path and makes finalize and every recorded-pin consumer name the orphaned pin instead of silently preserving it, computing against a dead base, or reporting a false conflict.

## Terminology: the recorded-pin classification (used throughout)

The recorded `planning_commit_sha` is classified against **the planning target-branch tip** (NOT any lane worktree HEAD) using two git predicates — reachability (`git merge-base --is-ancestor <recorded> <tip>`) and object presence (`git cat-file -e <recorded>^{commit}`):

| Class | Reachable ancestor of target tip? | Object present? | Meaning |
|-------|-----------------------------------|-----------------|---------|
| **captured** | n/a (pre-execution) | n/a | Execution not begun; the tip is freshly captured (today's behavior). |
| **current/advanced** | yes | yes | The recorded pin is reachable from the tip (unchanged, or a legitimate amendment sits on top). |
| **orphaned** | no | yes | Present in the object store but unreachable — the shape a mid-mission rebase produces. |
| **foreign** | no | no | The object is absent from this repository (GC'd, or belongs elsewhere). |

Reachability against the **target-branch tip** is the mission's discriminator everywhere. This is deliberately distinct from the allocator's *existing* `is-ancestor <pin> <lane HEAD>` no-op gate, which is a different ref and a different question (see C-006).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-pin the planning commit after a mid-mission rebase (Priority: P1)

An operator driving a lanes mission rebases the mission branch onto an advanced upstream `main`. The rebase rewrites the planning commit to a new SHA, orphaning the one recorded in `lanes.json`. The operator re-runs finalize to heal the pin so subsequent lane allocation merges the live planning state.

**Why this priority**: This is the exact P0 wedge in the issue — without it the supported full-mission drive breaks whenever upstream moves mid-mission, and the only workaround is hand-editing `lanes.json`.

**Independent Test**: In a real git repo, finalize a lanes mission, begin execution, rebase the mission branch so the recorded planning SHA becomes present-but-unreachable-from-tip, then run finalize with the sanctioned re-pin flag and assert `lanes.json` now records the live planning-branch tip and the decision is reported as a re-pin.

**Acceptance Scenarios**:

1. **Given** a lanes mission whose execution has begun and whose recorded `planning_commit_sha` is **orphaned** (present, unreachable from the target-branch tip), **When** the operator runs `finalize-tasks --refresh-planning-commit --allow-orphaned`, **Then** `lanes.json`'s `planning_commit_sha` is re-pinned to the current target-branch tip, the run reports the decision as re-pinned (human + `--json`, distinct action value), and the recorded pin now classifies as current/advanced.
2. **Given** the same orphaned pin, **When** the operator runs a plain `finalize-tasks` (no flag), **Then** the run does **not** silently preserve the orphaned SHA; it fails closed with an orphan-specific diagnostic that names the `--refresh-planning-commit --allow-orphaned` recovery command and the recorded/tip SHAs.
3. **Given** the same orphaned pin, **When** the operator runs `finalize-tasks --refresh-planning-commit` (advance-only, without `--allow-orphaned`), **Then** the run is refused exactly as today, the refusal message still contains the substring "not an ancestor", and `lanes.json` is untouched (the #4141 contract is preserved).

### User Story 2 - Every recorded-pin consumer names a stale pin instead of a false conflict, a dead base, or a bare refusal (Priority: P1)

An operator whose `lanes.json` still holds an orphaned `planning_commit_sha` interacts with the pin through lane allocation, workspace reconcile, the claim gate, or an owned review. In every case the tool tells them the pin is stale and how to re-pin it, rather than dead-ending on a generic conflict, computing a review against a dead base, or refusing a claim without guidance.

**Why this priority**: The allocator and its sibling consumers are the detonation sites the operator actually hits; a misleading "resolve the conflict manually", a silently-wrong review diff, or an unexplained claim refusal all send them down the wrong path when the real problem is a single stale field.

**Independent Test**: With `lanes.json` recording an orphaned pin, exercise each consumer and assert it surfaces an orphan-specific, recovery-naming outcome — not the generic merge-conflict error, not a diff against the dead base, not a bare `missing_refs` refusal.

**Acceptance Scenarios**:

1. **Given** a lane allocation (fresh OR reuse) whose recorded `planning_commit_sha` is **orphaned** (unreachable from the target-branch tip, present), **When** `_merge_recorded_planning_commit` runs (any call site, including the `implement_support.py` reconcile path), **Then** it raises an orphaned-pin error whose next-step names the finalize re-pin command — not the generic `PlanningCommitMergeConflictError` "resolve manually".
2. **Given** a lane allocation whose recorded `planning_commit_sha` is **current/advanced** (reachable, healthy) but genuinely conflicts on overlapping content, **When** the allocator merges, **Then** the existing generic merge-conflict behavior is unchanged (this mission only reclassifies the orphan case, keyed off target-tip reachability — not lane-HEAD reachability).
3. **Given** the claim-ancestry gate (`check_claim_ancestry`) evaluating an **orphaned** recorded pin, **When** it runs, **Then** the diagnostic names the orphaned pin and the finalize re-pin recovery, rather than emitting the bare `"recorded planning commit <sha>"` into `missing_refs` with no guidance.
4. **Given** the owned-review base resolver (`_mt_resolve_owned_review_base`) resolving an **orphaned** recorded pin, **When** it runs, **Then** it does **not** silently compute the review diff against the dead base (an orphaned SHA passes `rev-parse --verify` because the object is still present); it detects the orphan and fails closed / names the re-pin recovery.

### User Story 3 - A re-pinned lane catches up to the live planning state; the advance/amendment and pre-execution paths are untouched (Priority: P2)

After a re-pin, an operator resuming `implement` on a lane that was allocated **before** the rebase sees that lane merge the re-pinned (live) planning state as a normal catch-up. On the pre-existing supported paths — a fresh pre-execution finalize, or a legitimate planning amendment advanced with `--refresh-planning-commit` — the operator sees exactly today's behavior.

**Why this priority**: The already-allocated-lane population is the one the operator is actually mid-flight on; the mission must be explicit that the re-pin makes such a lane catch up (a legitimate merge), not silently no-op. Backward compatibility with the closed #4141/#3311 contracts is a release-safety requirement.

**Independent Test**: Re-run the existing #4141 and #3311 finalize test suites and the `tests/lanes/` allocator suites; add a scenario for an already-allocated lane resuming after a re-pin.

**Acceptance Scenarios**:

1. **Given** a lane allocated before the rebase (its worktree merged the OLD pin) and a subsequent successful re-pin to the live tip, **When** the operator next runs `implement WP##` for that lane, **Then** the recorded pin is now current/advanced (reachable), the lane performs a legitimate catch-up merge of the live planning state, and — if that merge conflicts on genuinely overlapping content — the conflict is reported as a real content conflict (the base is live, not stale), which is the operator's to resolve.
2. **Given** execution has not begun, **When** finalize runs, **Then** the branch tip is captured (`action=captured`) exactly as today.
3. **Given** a legitimate amendment where the recorded SHA IS an ancestor of the tip, **When** finalize runs with `--refresh-planning-commit`, **Then** it advances to the tip (`action=refreshed`) exactly as today; and a plain run preserves-and-warns exactly as today (with the corrected guidance of FR-008).

### Edge Cases

- **Foreign / absent object**: the recorded SHA is not present in the object store. Not re-pinnable: even `--allow-orphaned` must refuse and direct the operator to investigate, because the tool cannot relate the pin to the current planning history.
- **Tip uncapturable / not a git repo**: the default (no-flag) path must **degrade to the historical preserve** (matching `_capture_target_branch_tip`'s graceful `None` return), NOT fail closed. Default fail-closed is restricted to the **proven-orphaned-against-a-capturable-tip** case only (see FR-002). This preserves the #3311 non-git preserve test.
- **Present-but-unreachable that is NOT our rebased planning commit** (a genuinely divergent side branch pin): topologically indistinguishable from a benign rebase orphan, which is precisely why the re-pin requires the explicit `--allow-orphaned` operator assertion rather than auto-repairing.
- **Already-allocated lane after re-pin**: covered by US3 AS1 — a legitimate catch-up merge, not a no-op (NFR-003 is scoped accordingly).
- **`doctor mission-state --fix` interplay**: the doctor rebuild already fresh-captures the tip; finalize's orphan re-pin uses the same tip-capture rule so the two escape hatches stay consistent (C-002).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Classify the recorded pin against the target tip | As an operator, I want finalize to classify the recorded `planning_commit_sha` as captured / current-advanced / orphaned / foreign using reachability from the **target-branch tip** plus object presence, so a rebase is recognised instead of collapsing orphaned and foreign into one refusal. | High | Open |
| FR-002 | No silent preserve of a proven orphan; degrade otherwise | As an operator, I want a plain `finalize-tasks` run against a **proven orphaned** pin (present, unreachable from a **capturable** tip) to fail closed with an orphan-specific diagnostic (naming the recorded SHA, the tip, and the `--refresh-planning-commit --allow-orphaned` recovery) instead of silently writing the dead SHA back. When the tip is uncapturable, the repo is non-git, or the object is absent (foreign), the default path **degrades to the historical preserve** rather than aborting. | High | Open |
| FR-003 | Sanctioned orphan re-pin | As an operator, I want `finalize-tasks --refresh-planning-commit --allow-orphaned` to re-pin `planning_commit_sha` to the current target-branch tip when the recorded SHA is orphaned, so subsequent lane allocation merges the live planning commit. `--allow-orphaned` defaults to False. | High | Open |
| FR-004 | Foreign object still refused | As an operator, I want the re-pin to refuse (even with `--allow-orphaned`) when the recorded SHA is absent from the object store, so the tool never guesses a pin it cannot relate to the current planning history. | High | Open |
| FR-005 | Preserve the advance-only contract | As an operator, I want bare `--refresh-planning-commit` (no `--allow-orphaned`) to keep refusing a non-ancestor recorded SHA exactly as #4141 does, with the refusal message still containing the substring "not an ancestor", so the amendment path's safety and its regression test are unchanged. | High | Open |
| FR-006 | Centralized orphan detection at every merge site | As an operator, I want orphan detection (keyed off target-tip reachability + object presence) centralized in the shared `_merge_recorded_planning_commit` helper so that **all** its call sites — `worktree_allocator.py` (fresh + reuse + dependency-lane) and `implement_support.py` reconcile — raise an orphaned-pin error naming the finalize re-pin recovery, instead of the generic "merge conflicts — resolve manually". A healthy (reachable) pin that conflicts on content keeps the existing generic behavior. | High | Open |
| FR-007 | Reconcile the claim-ancestry gate | As an operator, I want `check_claim_ancestry` (`implement_support.py`) to recognise an orphaned recorded pin and name the finalize re-pin recovery, instead of emitting a bare `"recorded planning commit <sha>"` into `missing_refs` with no guidance. | High | Open |
| FR-008 | Reconcile the owned-review base resolver | As an operator, I want `_mt_resolve_owned_review_base` (`tasks_move_task.py`) to detect an orphaned recorded pin (which passes `rev-parse --verify` because the object is present) and fail closed / name the re-pin recovery, instead of silently computing the review diff against a dead base. | High | Open |
| FR-009 | Report the re-pin decision | As an operator, I want the re-pin decision surfaced in both human output and the `--json` success payload (a distinct action value, e.g. `repinned`, carrying the previous and new SHA) so a machine consumer and a human both see what changed. | Medium | Open |
| FR-010 | Correct the misleading drift guidance | As an operator, I want the preserve-path drift message to stop pointing an orphaned pin at bare `--refresh-planning-commit` (which then refuses), stop firing as a false positive on the tool's own finalize bookkeeping commit (#4178), and print the decision **after** the `lanes.json` write, not before (#4178 print-before-write), so the guidance I am given actually works and reflects the committed state. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Backward compatibility | The pre-execution capture (#846/#3311), the #3311 preserve-when-valid path (including the non-git synthetic-SHA preserve test), and the #4141 advance-only refresh must remain behaviorally unchanged. The **named corrected-expectation surface** — tests that today assert the pre-fix silent-preserve-of-orphan or generic-conflict behavior and must gain corrected expectations in the same PR — is: `test_issue_3311_finalize_rewrites_active_lanes.py`, `test_issue_4141_refresh_planning_commit.py`, `tests/lanes/test_lane_base_common_ancestor.py`, `tests/lanes/test_worktree_allocator_atomicity.py`, and `test_mission_cli_golden_contract.py`. Every other existing finalize/lanes/allocator test passes unmodified. | Reliability | High | Open |
| NFR-002 | Fail-closed | On a proven-orphaned pin against a capturable tip, finalize aborts (no-flag) before writing any bytes to `lanes.json` and names a recovery command; it never silently preserves an orphan, guesses, or truthiness-coerces. Foreign/uncapturable states degrade to preserve per FR-002. | Correctness | High | Open |
| NFR-003 | Idempotent finalize; explicit lane catch-up | Re-running **finalize** after a successful re-pin performs no further mutation (the re-pinned SHA classifies as current/advanced). A **not-yet-allocated** lane then allocates cleanly. An **already-allocated** lane is NOT a no-op: its next `implement` performs a legitimate catch-up merge of the re-pinned live planning state into the lane worktree (an expected mutation), which conflicts only on genuinely overlapping content (a real conflict, the operator's to resolve — not the stale-pin dead-end). | Reliability | High | Open |
| NFR-004 | Partition invariants intact | The re-pin only rewrites the recorded planning ancestor the FR-009/ADR lane merge adds; it never changes a lane's primary/topology-derived parent. Coord/PRIMARY partition invariants are unchanged. | Correctness | High | Open |
| NFR-005 | Quality gates | New/changed code passes `ruff`, `ruff format --check`, and `mypy` with zero issues and no new suppressions; every new branch/helper carries focused tests in the same commit; touched functions stay at cyclomatic complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single write authority | finalize remains the sole writer that resolves the re-pin decision; every consumer (allocator, reconcile, claim gate, review-base resolver) only DETECTS and guides — none rewrites `planning_commit_sha`. | Technical | High | Open |
| C-002 | Writer/consumer consistency & blast radius | The recorded-pin writers (`lanes/compute_and_persist.py`, `mission_finalize.py`, `tasks_finalize.py`, `migration/mission_state.py`) must not diverge; the orphan re-pin uses the same tip-capture rule the fresh-capture/doctor paths use. The recorded-pin **consumers** in scope are `worktree_allocator.py` (`_merge_recorded_planning_commit` at :419/:482/:562 and dependency-lane merge), `implement_support.py` (`:352` reconcile merge and `:497` `check_claim_ancestry`), and `tasks_move_task.py` (`:697` owned-review base). Detection lives in the single shared helper so no call site is missed. | Technical | High | Open |
| C-003 | commit_router out of scope | `coordination/commit_router.py`'s `_planning_commit_worktree` is the unrelated commit-worktree-routing sense (an overloaded-name collision) and is NOT a writer of this field; excluded from the blast radius. | Technical | Medium | Open |
| C-004 | Re-pin target is the tip (do NOT flip to content-match) | The re-pin target is the current tip of the planning target branch — the same value fresh-capture and `doctor mission-state --fix` already use. This was adversarially confirmed safe on coord/lanes topology: WP-implementation commits are confined to lane branches (`execution-lanes.md` rule 5; `branch-target-routing.md`), so re-pin-to-tip cannot drag sibling-lane WP work into a lane's merge base; and the rebase already re-parents the planning commit onto the advanced base, so content-match would not avoid the base drag and would only *diverge* the re-pin path from the other three writers (violating C-002). Content-matched (patch-id) precision is explicitly deferred (context #2897). | Technical | High | Open |
| C-005 | Scope boundary | This mission does not build a first-class "rebase mission onto moved base" command (#2273) or guided dependency-lane conflict resolution (#3936); it is the precise finalize re-pin defect those only obliquely cover. Reduced false dependency-lane conflicts are a welcome side effect, noted in the PR, not a folded deliverable. | Business | High | Open |
| C-006 | Discriminator ref: target tip, not lane HEAD | Orphan classification keys off reachability from the **target-branch tip**. The allocator's pre-existing `is-ancestor <pin> <lane HEAD>` no-op gate is a different question (a fresh coord lane legitimately has no common ancestor with the primary-partition planning commit — #2993) and must be preserved; the new orphan check is layered before/around it, not substituted for it. `_merge_recorded_planning_commit` gains a target-branch ref argument so it can perform the classification. | Technical | High | Open |
| C-007 | Surface & contract updates in the same PR | Adding `--allow-orphaned` requires updating the golden-contract frozenset (`test_mission_cli_golden_contract.py`), the `--refresh-planning-commit` help text, the rendered CLI reference (`docs/api/agent-subcommands.md` via `scripts/docs/build_cli_reference.py`, gated by the doc-freshness check), and an additive bump of `orchestrator_api/envelope.py` `CONTRACT_VERSION` (1.5.0 → 1.6.0) for the new `repinned` action value. No command-skills-manifest regen is needed. | Technical | High | Open |

### Key Entities

- **`planning_commit_sha`**: the commit recorded in `lanes.json` that every lane worktree merges as its planning ancestor. Its lifecycle-frozen provenance (ADR 2026-07-29-1 / the FR-009-era invariant) is what a rebase breaks. Re-pinning is a fresh, equally-frozen snapshot — a sanctioned continuation of that ADR, not a mutation of the old snapshot.
- **Recorded-pin classification**: the {captured, current/advanced, orphaned, foreign} state derived from target-tip reachability + object presence.
- **Target-branch tip**: the live head of the planning target branch, the re-pin target.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a mid-mission rebase, an operator heals the planning pin with a single documented CLI command (`finalize-tasks --refresh-planning-commit --allow-orphaned`) — zero manual `lanes.json` edits required (down from the current 100%-manual escape).
- **SC-002**: A plain `finalize-tasks` run against a proven orphaned pin never silently preserves it: in 100% of proven-orphan cases it either re-pins (with the flag) or fails closed naming the recovery command; non-git/foreign/uncapturable states still preserve (no #3311 regression).
- **SC-003**: Every recorded-pin consumer (allocation fresh + reuse, reconcile, claim gate, owned-review base) surfaces an orphan-specific, recovery-naming outcome in 100% of orphan cases — never a generic "resolve manually", a diff against a dead base, or a bare claim refusal.
- **SC-004**: Zero regressions: the named corrected-expectation suites (NFR-001) pass with their corrected expectations, every other finalize/lanes test passes unmodified, and the new orphan-path regression tests (red-first against the pre-fix entry points) pass after the fix.
