---
title: 'ADR: a default Mission topology is settled once, by size, at the first finalize'
description: 'Create without --topology mints one topic branch; the first finalize-tasks settles single_branch or lanes_with_coord by size, once, and only then materializes it.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
updated: '2026-11-13T00:00:00Z'
---

# A default Mission topology is settled once, by size, at the first finalize

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it.

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator). The rulings are recorded as resolved Decision Moments in Mission `lane-worktree-model-hardening-01M6QY1M` (`spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M`).

**Technical Story:**

- [#7282](https://github.com/spec-kitty/spec-kitty/issues/7282) (S7): small Missions stay small; the topology is chosen once, at finalize. Epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276).
- **Supersedes** [#5100](https://github.com/spec-kitty/spec-kitty/issues/5100) item 2, the "explicit-only topology" decision ([issue comment 5870360497](https://github.com/spec-kitty/spec-kitty/issues/5100#issuecomment-5870360497)). No ADR file held that decision; this record replaces it.
- **Amends** [ADR 2026-06-22-1](../3.x/2026-06-22-1-mission-topology-ssot.md) Decision 2 ("stored at create, read thereafter"), by an appended amendment on that file.
- **Depends on** the S8 bound ([#7283](https://github.com/spec-kitty/spec-kitty/issues/7283)), recorded as the 2026-11-06 amendment of [ADR 2026-10-04-5](2026-10-04-5-approval-stamp-bounds-the-approved-claim.md). Constraint C-010: S8 ships before or with this decision.
- **Read side:** [ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) (one status read contract, S1) carries the reads that this record's placement rule changes.

**Reader:** a maintainer who needs to know why `agent mission create` without `--topology` mints only a branch, when and how `finalize-tasks` turns that into `single_branch` or `lanes_with_coord`, and where a default Mission's planning artifacts live meanwhile.

**Terms.** "PRIMARY partition" is the artifact partition (spec, plan, tasks, WP files, `lanes.json`, `meta.json`; `_PRIMARY_ARTIFACT_KINDS` in `src/mission_runtime/artifacts.py`), never the primary branch; "repository root checkout" is the main working tree; "target branch" is the branch the Mission lands on at `consolidate`. "Lane consolidation" is the landing of lane branches into the Mission or coordination branch; the landing on the target is named as such. See [`docs/context/orchestration.md`](../../context/orchestration.md#primary-partition).

---

## Context and Problem Statement

Today `create` chooses the topology before any work package exists. On a protected target it mints a coordination branch and its worktree, so a Mission that later turns out to be two work packages carries a coordination topology it never needed. The Mission tracer files record operators hand-removing those scaffolds after `specify` chose a coordination topology on a protected branch.

The transitions are not symmetric. Shrinking a `lanes` or coordination topology into `single_branch` needs a worktree removal and a branch hand-over; growing from one topic branch needs neither a projection nor a deletion. The operator's rationale (ruling 1 and the S7 escalation answer, DM `01M6QY2SJ9ND1SKMH2230FS7JA` and `01M6QY46RJGFZN6WBVQQXCZSY6`): build nothing that may have to be torn down, and decide the shape when the work packages are known.

#5100 item 2 made the topology explicit-only; ADR 2026-06-22-1 Decision 2 stores it at create and reads it thereafter. Both have to change for a size-based default to be decided at finalize, and the change has to stay a stored, read-once value, not a re-inference.

## Decision Drivers

- Build nothing that might be torn down: a Mission is created with the least structure that can carry its planning work.
- One stored topology value (ADR 2026-06-22-1): settlement writes it once; nothing re-infers it from disk.
- No WP is ever re-homed: the topology is fixed before any WP is claimed.
- A failed settlement costs nothing (NFR-003): `meta.json`, branch tips and the repository root checkout come back byte for byte.
- No planning artifact reaches the target before `consolidate`.
- No user-reachable size default without the S8 bound (C-010), because the default sends most small Missions to `single_branch`.

## Considered Options

1. **Deferred materialization: one topic branch at create, settled by size at the first finalize, one settlement path on every target** (chosen).
2. Keep `lanes` or `coord` as the provisional default and re-stamp it to `single_branch` at finalize.
3. Store a new `topology: provisional` enum value.
4. Write pre-settlement artifacts by commit, with no checkout.
5. Keep the write checkout on the topic branch for a `lanes` Mission's whole life.
6. On an unprotected target, land the topic branch's planning commits on the target at settlement (fast-forward, else a git merge commit) and settle to plain `lanes`.

## Decision Outcome

**Chosen option:** Option 1, because it builds only what the settled size needs, keeps one stored topology value, and has one settlement path that never lands anything on the target.

### Decision 1: create without `--topology` mints one topic branch and nothing else

- `create` without `--topology` mints exactly one Mission topic branch, `kitty/mission-<slug>-<mid8>` (assumption A-1), whatever the target's protection. It creates no lane, no lane or coordination worktree, and no coordination branch (FR-051).
- The topic branch name is the existing Mission and coordination branch grammar (`mission_branch_name` / `coordination_branch_name`). Settlement assigns it a role; it never renames or re-mints it.
- `--topology <X>` records `topology_source: explicit`, and `--owned-checkout` records `topology_source: owned_checkout`. Both are settled at create and materialize exactly as today (FR-052). An explicit topology always wins, at create and at finalize.

### Decision 2: the size rule

At the first `finalize-tasks`, a provisional Mission settles to:

- **`single_branch`** when it has at most 2 non-canceled WPs, or at most 1 code lane. Planning-artifact WPs count toward the WP count; canceled WPs do not. `lane-planning` is not a code lane; 0 code lanes settles to `single_branch` (A-6).
- **`lanes_with_coord`** otherwise, on **every** target, protected or not, with the topic branch as the coordination branch under the same name (A-3; DM `01M6QZ02HDACM7A0VNYSAQ8MQB` for protected targets, extended to every target by DM `01M6R0B954ZPQN5NV4R1ZRE7NY`).

A tie (exactly 2 WPs in 2 code lanes) settles to `single_branch`: the WP-count arm wins. Plain `lanes` (no coordination) and `coord` (coordination, no lanes) are never default outcomes; both stay available through `--topology`. The recorded rule names are `wp_count_le_2`, `code_lanes_le_1` and `lanes_with_coord`.

Why `lanes_with_coord` on every target: create no longer mints a coordination branch, and a `lanes` Mission whose status lives on a protected target is refused at `consolidate` (`PROTECTED_BRANCH_REFUSED`). `coordination_branch` is a `meta.json` key (read through `COORDINATION_BRANCH_KEY` by about 32 readers) whose default name already uses the Mission branch grammar, and the reconstruct-from-slug paths (`coordination/coord_seed.py`, `coordination/workspace.py`) yield the same name, so the topic branch can carry the coordination designation unchanged (corroborated 2026-11-06). One settlement path removes the protection-dependent arm and its landing step.

### Decision 3: deferred materialization

- Settlement writes the lane manifest (`lanes.json`). Lane branches and lane checkouts appear only through the existing implement-time allocation (A-7); nothing is pre-allocated at finalize.
- Lanes are cut from the topic branch. Lane consolidation lands into it. It lands on the target branch at `consolidate`, as for an explicit `lanes_with_coord` Mission.
- Nothing lands on the target at settlement. There is no fast-forward or git merge step.

**Settlement to `single_branch`** has no git step: it writes `topology_settled: true` and `topology_decision`; the topic branch stays the Mission branch and stays checked out in the write checkout.

**Settlement to `lanes_with_coord`** is the one git-moving path:

1. Commit the Mission directory on the topic branch in the write checkout.
2. Move the repository root checkout off the topic branch, back to `create_return_branch`. Git forbids one branch checked out in two worktrees, so this precedes step 4.
3. Re-stamp `meta.json`: `coordination_branch` = the topic ref name, `mission_branch` kept (it now names the same ref), `topology: lanes_with_coord`, `topology_settled: true`, `topology_decision` written.
4. Materialize and seed the coordination worktree on the topic branch through `CoordinationWorkspace.resolve()`.
5. Write `lanes.json`.

### Decision 4: the provisional representation and `topology_source`

A provisional Mission is stored as (DM `01M6R0BDYC29D6XMDY72R22CP9`):

| `meta.json` key | Provisional value | Notes |
|---|---|---|
| `topology` | `single_branch` | Reuses the minted `single_branch` write path (`single_branch_write_ref`), so specify, plan and tasks land on the topic branch with no new placement code. |
| `mission_branch` | the topic branch | Kept at promotion to `lanes_with_coord`. |
| `topology_source` | `default` | New, additive. `explicit` / `owned_checkout` for explicit creates. **Absent means legacy, and legacy means settled** (FR-057). |
| `topology_settled` | `false` | New. Written only when `topology_source == default`; settlement sets `true`. Absent with `topology_source == default` is invalid and refuses. |
| `create_return_branch` | the branch the write checkout was on before create switched it | New. Read only by settlement to `lanes_with_coord`; kept afterwards for audit, never read once settled. |
| `topology_decision` | absent | Written once at settlement: `{rule, wp_count, code_lane_count, from, to, target_protected, decided_at}`. `target_protected` is informational. Write-once. |

`create --json` reports `topology: single_branch` with `topology_provisional: true` until finalize; `finalize-tasks --json` reports the decision and `--validate-only` previews it without writing (FR-058). These fields reach `orchestrator-api` in one additive contract bump, 1.24.0 to 1.25.0 (main took 1.24.0 for #7210 meanwhile), together with the S5 cleanup report (DM `01M6R0BJQ6Q1MV6492EH6HB66H`); no release ships 1.25.0 without all of them.

### Decision 5: the PRIMARY partition of a default Mission lives on the topic branch until `consolidate`

For `topology_source: default`, the PRIMARY partition resolves to the Mission topic branch (`meta.mission_branch`, which after a multi-lane settlement is also the coordination branch), before and after settlement, until `consolidate` lands it on `target_branch` (FR-061, DM `01M6R0QJVPVZG2QT8MWQD4NXJR`, which supersedes the mirror-an-explicit-create rule of DM `01M6R0B3YX291STRVVQ0HQCJD5`). `target_branch` stays the landing branch. Explicit `--topology` Missions keep today's placement: the PRIMARY partition on `target_branch`.

- **One "landed" signal, owned by the placement seam.** Before the landing, the seam resolves a default Mission's PRIMARY partition to `meta.mission_branch`; once `consolidate` records that the topic branch has landed on the target, it resolves to `target_branch`. `consolidate` does not decide placement itself: after the landing it re-reads the seam (analysis H1).
- **Readers go through the seam or the read door.** Settlement moves the repository root checkout back to `create_return_branch`, so the root checkout does not show the planning files of a settled `lanes_with_coord` default Mission. `agent context resolve` and `check-prerequisites --paths-only` return the PRIMARY-partition location from the resolver, never a fixed root path. The status read side is ADR 2026-11-06-2.
- **Landing.** The mission-to-target phase (`_phase_mission_to_target` through `integrate_mission_into_target`) already carries the topic branch's tip. FR-062 covers the PRIMARY commits after the consolidation checkpoint that that landing does not carry; the default-Mission landing decision is its own predicate, and `lands_mission_branch` keeps its `single_branch` meaning.

### Decision 6: decided once, before any WP starts

The topology is settled only at the first `finalize-tasks`, before finalize's first status write and before any WP is claimed (FR-054, C-011). Re-finalize, the legacy `tasks-finalize` repair path and doctor rebuilds never re-decide. Growth after settlement keeps the settled topology. A finalize that finds any WP with a lifecycle event past `planned`, or any recorded lane branch or worktree, does not settle; the topology stays.

### Decision 7: settlement is compensated

Settlement is a planned list of reversible steps executed in order, with an undo stack. Any failure restores `meta.json` byte for byte, every branch tip, the absence of a coordination worktree, and the repository root checkout on the topic branch (FR-056, NFR-003; fault-injected at every git step). Preconditions, each a refusal with nothing changed:

- the write checkout is not occupied by another in-progress WP (`WRITE_CHECKOUT_OCCUPIED`) and is clean (`WRITE_CHECKOUT_DIRTY`, #5676);
- `create_return_branch` exists and is not checked out in another worktree, the coordination worktree can be materialized, and no git step failed (`TOPOLOGY_SETTLEMENT_REFUSED`, new; its remedy names the branch).

### Decision 8: `--pr-bound` and `--commit-to-target`

- The `--pr-bound` coordination-unreachable fallback to plain `lanes` is dropped for default Missions (A-5, DM `01M6R0QQM5FCPY736008AD4W6V`). Multi-lane settlement always yields `lanes_with_coord`. The #2533 stranded-branch hazard the fallback guarded does not apply once the topic branch is the coordination branch.
- `--commit-to-target` still requires an explicit `--topology single_branch` (FR-060). A provisional Mission never writes straight to its target.

### Decision 9: S8 before or with S7 (C-010)

No user-reachable settlement ships in a release without the per-WP approval windows of the ADR 2026-10-04-5 amendment of 2026-11-06. A default `single_branch` Mission always consolidates its minted topic branch (A-4), so every size-default `single_branch` Mission falls inside that bound; only an explicit `--commit-to-target` Mission stays in the unbounded residual.

### Consequences

#### Positive

- A small Mission is created and finalized with one branch and no worktree; nothing is built only to be torn down.
- One settlement path for every target: no protection-dependent arm, no landing step at settlement, no conflict handling.
- The topology stays one stored value; settlement writes it once and records why (`topology_decision`).
- Pre-settlement placement needs no new code: the provisional Mission uses the existing minted `single_branch` write path.

#### Negative

- Every size-default multi-lane Mission carries a coordination worktree, also on unprotected targets where it would have been `lanes` before. This is the accepted cost of one settlement path.
- The `single_branch` population grows, which is why C-010 ties this decision to the S8 bound.
- Every no-topology `create` moves the repository root checkout onto the topic branch until settlement. A second `create` run from there could record the first Mission's topic branch as its target. Mitigation: target resolution never picks a branch recorded as another Mission's `mission_branch` or `coordination_branch`, and resolves the primary branch (the repository's default branch) instead. A refusal instead would be a new code, to be raised in review.
- After a `lanes_with_coord` settlement the repository root checkout no longer shows the planning files; any reader that reads a root-checkout path for a default Mission is wrong and must use the seam.
- `create_return_branch` may be deleted or checked out elsewhere by settlement time; settlement then refuses until the operator restores it.

#### Neutral

- Legacy Missions (no `topology_source`) are settled and never re-decided, so upgrading changes no in-flight Mission's shape.
- Plain `lanes` and `coord` remain available, explicitly.

### Confirmation

- `tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py` (WP13): create without `--topology` mints one branch and records the provisional keys; the explicit `--topology coord` control still creates its coordination branch.
- `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py` (WP14): the size rule, the tie, canceled and planning-artifact WP counting, decide-once on re-finalize, legacy Missions untouched, `--validate-only` and `--json`.
- `tests/lanes/test_topology_settlement_compensation.py` (WP14): fault injection at every git step leaves `meta.json` byte-identical, branch tips unchanged and the root checkout on the topic branch.
- `tests/integration/test_default_mission_primary_placement.py` (WP14): the PRIMARY partition of a default Mission resolves to the topic branch before and after settlement and to the target after `consolidate`; the explicit control keeps `target_branch`.
- `tests/integration/test_default_mission_consolidate_lands_primary.py` (WP20): `consolidate` leaves no PRIMARY change of the topic branch off the target.
- The S8 confirmation tests are named in the ADR 2026-10-04-5 amendment of 2026-11-06.

## Pros and Cons of the Options

### Option 1: deferred materialization, one settlement path

**Pros:** builds only what the size needs; growth only, never a shrink; one path on every target; reuses the minted `single_branch` write path before settlement.

**Cons:** a coordination worktree on every multi-lane default Mission; the root checkout move needs a recorded return branch and compensation.

### Option 2: provisional `lanes`/`coord`, re-stamped to `single_branch`

**Pros:** no change at create.

**Cons:** the most expensive transition (a worktree removal and a branch hand-over) becomes the common one. Rejected by the escalation ruling (DM `01M6QY46RJGFZN6WBVQQXCZSY6`).

### Option 3: a `topology: provisional` enum value

**Pros:** the provisional state is explicit in the type.

**Cons:** about 55 stored-topology readers would need a new arm; the `single_branch` representation needs none. Rejected.

### Option 4: pre-settlement writes by commit, no checkout

**Pros:** the repository root checkout never moves.

**Cons:** agents author spec, plan and tasks in a working tree. Rejected.

### Option 5: the write checkout holds the topic branch for a `lanes` Mission's life

**Pros:** no coordination worktree.

**Cons:** it occupies the repository root checkout for the whole Mission (#5550, #5676). Rejected (A-3).

### Option 6: land planning commits on an unprotected target at settlement and settle to `lanes`

**Pros:** today's `lanes` shape on unprotected targets.

**Cons:** planning artifacts reach the target before `consolidate`; a conflict path and a protection-dependent arm. This was the plan's original recommendation for OQ-2; rejected by the operator (DM `01M6R0B954ZPQN5NV4R1ZRE7NY`).

## More Information

- Mission artifacts: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/spec.md` (User Story 3, FR-050 to FR-062, A-1 to A-7), `research.md` R-6, `data-model.md` §1, `contracts/finalize-tasks-json.md`, `contracts/mission-create-json.md`, `contracts/error-codes.yaml`.
- Decision Moments: `01M6QY2SJ9ND1SKMH2230FS7JA` (ruling 1), `01M6QY46RJGFZN6WBVQQXCZSY6` (deferred materialization), `01M6QZ02HDACM7A0VNYSAQ8MQB` and `01M6R0B954ZPQN5NV4R1ZRE7NY` (the "lanes otherwise" mapping), `01M6R0BDYC29D6XMDY72R22CP9` (provisional representation), `01M6R0BJQ6Q1MV6492EH6HB66H` (contract bump), `01M6R0QJVPVZG2QT8MWQD4NXJR` (PRIMARY placement), `01M6R0QQM5FCPY736008AD4W6V` (`--pr-bound`).
- Related: [ADR 2026-06-22-1](../3.x/2026-06-22-1-mission-topology-ssot.md) (stored topology, amended), [ADR 2026-10-04-5](2026-10-04-5-approval-stamp-bounds-the-approved-claim.md) (approval bound, amended for S8), [ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) (status read contract), [`docs/context/topology.md`](../../context/topology.md).

## Amendment 2026-11-13: an explicit `lanes` create on a protected target is refused

Operator ruling Q2 (2026-11-13), [#7632](https://github.com/spec-kitty/spec-kitty/issues/7632).

- **The gap.** `lanes` is explicit-only (Decision 1) and mints neither a Mission branch nor a coordination branch. On a protected target, `agent mission create --topology lanes` was admitted, its scaffold commit was skipped, and every later status write was refused with `PROTECTED_BRANCH_REFUSED`.
- **Decision.** Create refuses that shape before any write, with `LANES_PROTECTED_TARGET_REFUSED` (`LanesProtectedTargetError`, exit 1, the code in the `--json` payload). The message names two remedies: an unprotected target branch (`--target-branch`), or `--topology lanes_with_coord`. Create does not mint a branch for a `lanes` Mission; that would be Option 5, which stays rejected.
- **Predicate.** The refusal asks the predicate the later status write asks, `ProtectionPolicy.is_protected` with the operator hatch, over the repository root's configuration and, for an owned create, the owned checkout's as well. It does not ask the #5100 mint rule (`is_protected_target`, primary branch plus configured branches). A primary branch the project un-protects (`protection.protected_branches: []`) still admits `lanes`, because its status writes succeed there.
- **Scope.** Only create changes. A stored `lanes` Mission, the migrations that stamp or restamp `lanes`, and finalize (which never settles to `lanes`) are unchanged. The scaffold commit's `ProtectedBranchRefused` bootstrap skip is no longer reached by a `lanes` create; it stays for the other skip causes.

Nothing else in this record changes.
