# Mission Specification: Implement lane-allocation integrity

**Mission Branch**: `fix/implement-lane-recut-and-planning-commit-integrity`
**Created**: 2026-09-25
**Status**: Draft
**Input**: GitHub issues #4889 (P0) and #4905 (P1); operator steer via `/spk-mission-from-issue`.

## Intent Summary

**Primary actor**: an operator (or agent) running `spec-kitty implement` / `spec-kitty agent action implement` to prepare and drive a work package.

**What we are building**: two fail-closed / correctness fixes in the `implement` lane-allocation seam so the command never reports success while committed work is unreachable, and so every work package on a coordination-topology mission can be started.

**The two confirmed defects** (source-traced on current `main`, grounding squad):

1. **#4889 — silent empty re-cut (P0).** When a work package's lane worktree **and** lane branch are both gone while the WP is still `in_progress`, re-running `implement` falls through `allocate_lane_worktree`'s FRESH route (which consults no WP lane state), cuts a brand-new empty lane branch from the coordination tip, prints `✓ Lane worktree ready`, exits `0`, and overwrites the persisted lane metadata — stranding the committed WP work while canonical status still reads `in_progress`. A later `merge` then lands the empty lane.

2. **#4905 — WP file on the coordination branch (P1).** On `coord` / `lanes_with_coord` topologies, the agent-verb claim commit stages the PRIMARY-partition file `kitty-specs/<slug>/tasks/WP01-*.md` onto the **coordination branch**. Every later lane is cut from the coord tip and must absorb the recorded planning commit via FR-009; that merge then hits an add/add conflict on the WP file → `PlanningCommitMergeConflictError`, exit `1`, so `implement WP02` cannot start.

**Invariant that must always hold**: `implement` never prints `Lane worktree ready` / exits `0` when it did not actually place the WP's committed work reachable in the lane; a lane that once existed and was destroyed is distinguishable from a lane that never existed. This holds for **every** caller of the lane allocator, not just the CLI `spec-kitty implement` — the external orchestrator path (`agent action implement` / `start-implementation` / `transition --to claimed`, via `orchestrator_api` → `_resolve_start_workspace`) is the automation surface the P0 most exists to protect, so the guard must sit where both callers pass through. Lifecycle commits on the coordination branch never carry PRIMARY-partition work-package files, across **every** coord lifecycle staging site (claim, resume-refresh, review-claim), not just the first claim.

**Out of scope**: #4891 (`accept` skips the acceptance-matrix gate when `lanes.json` is absent) — same "exit-0 silent skip" archetype but a different command/module (`acceptance/gates_core.py`), and already covered by in-flight PR #5029. Automatic reflog/`fsck`-based recovery of the stranded commit is deferred; this mission fails closed with a diagnostic that names the recovery ref.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `implement` refuses to re-cut a destroyed lane (Priority: P1)

An operator (or a cleanup path) removes a WP's lane worktree and lane branch while the WP is still `in_progress` and has committed work on that branch. Re-running `spec-kitty implement WP##` must NOT silently create a new empty lane and report success — it must fail closed with a diagnostic that names the missing lane branch and where the stranded work can be recovered, and it must leave the persisted lane metadata intact.

**Why this priority**: P0 release blocker (milestone 11, MVP launch). Silent success plus loss of committed implementation state is the archetypal "Spec Kitty fights its own operator" defect; the next `merge` lands an empty WP with no error anywhere.

**Independent Test**: drive a `coord` mission to `implement WP01`, commit real work in the lane, delete the lane worktree + branch, re-run `implement WP01`, and assert exit non-zero, no `Lane worktree ready`, the persisted `WorkspaceContext` unchanged, and the diagnostic names the missing branch.

**Acceptance Scenarios**:

1. **Given** WP01 is `in_progress` with committed work on `kitty/mission-<slug>-lane-a`, **and** that lane's worktree and branch have both been removed, **When** the operator runs `spec-kitty implement WP01`, **Then** the command exits non-zero, prints a diagnostic naming the missing lane branch and a recovery ref (reflog/`fsck`), does not print `✓ Lane worktree ready`, and does not overwrite `.kittify/workspaces/<slug>-lane-a.json`.
2. **Given** the same destroyed-lane state as scenario 1, **When** the WP is claimed via the **orchestrator/agent surface** (`spec-kitty agent action implement WP01` / `start-implementation` / `transition --to claimed`), **Then** the same fail-closed refusal occurs (exit non-zero, diagnostic, no empty re-cut) — the guard is caller-independent, covering the `orchestrator_api` `_resolve_start_workspace` path as well as the CLI path.
3. **Given** WP01 is `in_progress` with its lane worktree **and** branch intact (nothing deleted), **When** the operator re-runs `spec-kitty implement WP01`, **Then** the command is a no-op resume: exit `0`, the lane tip is unchanged, and the committed work is present (the REUSE control arm is preserved).
4. **Given** WP01 is `in_progress`, its lane worktree is gone but the lane branch still exists, **When** the operator re-runs `spec-kitty implement WP01`, **Then** the command re-attaches the worktree to the surviving branch and resumes (the CRASH_RECOVERY control arm is preserved), exit `0`, committed work present.
5. **Given** a WP that was never allocated (genuinely fresh, no persisted lane context, WP `planned`), **When** the operator runs `spec-kitty implement`, **Then** a fresh lane is created normally (the fail-closed detector does not misfire on a legitimately new lane).
6. **Given** a WP in a **non-terminal, non-`in_progress`** lane (`blocked`, `for_review`, or `in_review`) whose lane worktree and branch have both been removed while committed work exists, **When** the WP is (re-)claimed, **Then** the same fail-closed refusal occurs — the guard keys on any non-terminal post-allocation state, not `in_progress` alone (the committed work is stranded identically).
7. **Given** a WP whose lane was legitimately consolidated-and-torn-down after approval (its tip is already reachable on the target branch) and was then force-moved back to `in_progress`, **When** the WP is claimed, **Then** the command resumes / re-creates normally rather than falsely refusing — because the persisted tip is an ancestor of the target (no work is stranded), the detector must not fail closed.

---

### User Story 2 - Second work package starts on a coord mission (Priority: P2)

An operator drives a multi-WP `coord` mission through the documented agent verb. Starting the second work package must succeed exactly as it does on the `lanes` topology, rather than failing with a planning-artifact merge conflict caused by the first WP's file having been committed onto the coordination branch.

**Why this priority**: P1 defect (milestone 12, CLI 4.x stable). On the create-time default topology a multi-WP mission can start exactly one work package through the agent verb; each remaining WP otherwise needs a hand-resolved git conflict inside a lane worktree that does not exist yet.

**Independent Test**: create a `coord` mission with WP01 and WP02 (WP02 depends on WP01), run `agent action implement WP01`, then `agent action implement WP02`, and assert WP02 starts (exit `0`, no `PlanningCommitMergeConflictError`); assert the coordination branch tree contains no `kitty-specs/<slug>/tasks/WP*.md` blob.

**Acceptance Scenarios**:

1. **Given** a `coord` mission where WP01 has been claimed via `agent action implement WP01`, **When** the coordination branch tree is inspected, **Then** it contains no `kitty-specs/<slug>/tasks/WP01-*.md` blob (the WP file stayed on the PRIMARY partition).
2. **Given** WP01 has been claimed on a `coord` mission, **When** the operator runs `agent action implement WP02`, **Then** the lane is allocated and the FR-009 planning-artifact merge completes without an add/add conflict, exit `0`.
3. **Given** WP01 has passed through a **review-claim** on a `coord` mission (`for_review → in_review` via `agent action review`), **When** the coordination branch tree is inspected, **Then** it still contains no `tasks/WP*.md` blob — the review-claim staging site does not re-pollute coord after the claim site was fixed (all coord lifecycle staging sites are covered by construction at the shared sink).
4. **Given** the same mission driven on the `lanes` topology (no coordination branch), **When** both WPs are claimed, **Then** behaviour is unchanged (no regression on the control topology).

---

### Edge Cases

- A destroyed lane whose branch survives only as a stale `origin/<lane>` remote ref (the #4969 origin-preference path): the #4889 detector must key on WP lane **state** (non-terminal post-allocation status + persisted `WorkspaceContext`), not on ref existence, so origin-preference cannot resurrect a stale ref and disguise an empty re-cut as non-empty.
- The persisted `WorkspaceContext` exists but canonical status is a terminal lane (`done`/`canceled`): not the #4889 trigger — treat per normal routing, do not fail closed.
- **Re-open after a legitimate merge-and-teardown**: a WP force-moved terminal → `in_progress` after its lane was consolidated and deleted has a persisted context + non-terminal status + no branch/worktree, but its tip is already reachable on the target. Before failing closed, the detector must confirm the persisted tip is **not** an ancestor of the target branch; if it is reachable there, no work is stranded → resume/recreate normally (avoids a false refusal).
- **Caller bypass**: `allocate_lane_worktree` is reached by both `create_lane_workspace` (CLI) and `orchestrator_api` `_resolve_start_workspace` (agent/orchestrator surface). A guard placed only in the CLI wrapper is bypassed by the orchestrator path — the detector must sit inside the shared allocator (or a helper both callers pass through) so it is caller-independent.
- A coord mission where the WP file was already committed onto coord by a pre-fix run (existing corpus): the fix targets the write path; already-polluted coord branches are a migration/recovery concern noted for the plan, not silently "fixed" by the merge.
- The FR-009 planning-artifact merge is invoked on all three allocation routes (REUSE, CRASH_RECOVERY, FRESH); the #4905 staging fix must not leave any route or any of the three coord lifecycle staging sites (claim, resume-refresh, review-claim) still committing the WP file onto coord.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Detect destroyed-lane state | As an operator, I want the lane allocator to distinguish "this lane never existed" from "this lane existed and its branch/worktree were destroyed" using WP lane state (any **non-terminal post-allocation** status — `in_progress`, `blocked`, `for_review`, `in_review` — plus a persisted `WorkspaceContext`), so a silent empty re-cut is impossible. | High | Open |
| FR-002 | Fail closed on destroyed lane | As an operator, when the destroyed-lane condition holds, I want the command to exit non-zero with a diagnostic naming the missing lane branch and a recovery ref, and to never print `Lane worktree ready`. | High | Open |
| FR-003 | Preserve the recovery pointer | As an operator, I want the fail-closed path to leave the persisted lane metadata (`.kittify/workspaces/<slug>-lane-<id>.json`) unmodified, so the last on-disk pointer to the stranded tip survives. | High | Open |
| FR-004 | Preserve REUSE / CRASH_RECOVERY resume | As an operator, I want the intact-lane control arms (worktree present → REUSE; branch present, worktree gone → CRASH_RECOVERY re-attach) to remain no-op / re-attach resumes exactly as today. | High | Open |
| FR-005 | Keep WP files off the coordination branch | As an operator, I want **every** coord/`lanes_with_coord` lifecycle staging site (claim, resume-refresh, review-claim) to route the PRIMARY-partition `tasks/WP*.md` file to the PRIMARY partition — fixed at the shared coordination-commit sink by partitioning staged paths by artifact kind — never staging it onto the coordination branch. | High | Open |
| FR-006 | Second WP starts on coord | As an operator, I want `agent action implement WP02` on a `coord` mission to allocate its lane and complete the FR-009 planning merge without a `PlanningCommitMergeConflictError`, and this must hold after WP01 has passed through review-claim as well as claim. | High | Open |
| FR-007 | Red-first reproductions | As a maintainer, I want each defect to land an issue-pinned `@pytest.mark.regression` reproduction that is RED through the real `implement` entry point before its fix. | Medium | Open |
| FR-008 | Caller-independent guard | As an operator, I want the destroyed-lane guard to fire for **every** caller of the lane allocator — the CLI `spec-kitty implement` AND the orchestrator/agent surface (`agent action implement` / `start-implementation` / `transition --to claimed`, via `_resolve_start_workspace`) — so the automation path cannot bypass the P0 fix. | High | Open |
| FR-009 | No false refusal on reachable tip | As an operator, I want the detector to resume/recreate normally (not fail closed) when the persisted lane tip is already an ancestor of the target branch — a re-open after a legitimate merge-and-teardown strands no work and must not be refused. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No false positives | The destroyed-lane detector produces zero false refusals on a genuinely fresh lane (WP never allocated, no persisted context): 100% of the "genuinely fresh" acceptance runs create a lane normally. | Reliability | High | Open |
| NFR-002 | Topology- and caller-independent | The #4889 fail-closed behaviour holds on all coordination topologies (`coord`, `lanes_with_coord`) AND for every allocator caller (CLI `implement` + orchestrator-api `start-implementation`/`transition`), and does not alter `single_branch`/`lanes` behaviour beyond the stated fix. | Reliability | High | Open |
| NFR-003 | Complexity ceiling | Every function added or modified stays at cyclomatic complexity ≤ 15 (Ruff C901 / Sonar S3776) with new branches/helpers covered by focused tests in the same change. | Maintainability | Medium | Open |
| NFR-004 | Diagnostic quality | The #4889 diagnostic is actionable: it names the specific missing lane branch and a concrete recovery ref/command; no generic "workspace error". | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical status is the authority | The detector reads WP lane state from the resolved coordination status surface (`status.events.jsonl` via the reducer), never from the lane worktree tree (sparse-checkout excludes status files there — reading them there would silently no-op). | Technical | High | Open |
| C-002 | No new authority | Reuse the existing `WorkspaceContext` persistence (`workspace/context.py`) and status reducer; do not introduce a second lane-state authority. | Technical | High | Open |
| C-003 | Write-scope-disjoint work packages | The #4889 detector and the #4905 staging fix are separate work packages with disjoint write scopes so they can proceed in parallel; a shared regression WP proves both across all three allocation routes. | Technical | Medium | Open |
| C-004 | Smallest viable diff | Fix the two write sites; do not migrate already-polluted coord branches or add a new recovery subcommand in this mission (note as future work). | Technical | Medium | Open |

### Key Entities

- **Lane allocation route**: the REUSE / CRASH_RECOVERY / FRESH decision `allocate_lane_worktree` takes; #4889 adds a fail-closed pre-flight before the FRESH routes, inside the shared allocator so both callers (`create_lane_workspace` and `orchestrator_api` `_resolve_start_workspace`) are covered.
- **Persisted `WorkspaceContext`**: the `.kittify/workspaces/<slug>-lane-<id>.json` record of a prior allocation (`branch_name`, `base_commit`, `created_at`); the recovery pointer FR-003 preserves.
- **WP lane state**: the canonical `status.events.jsonl` lane reduced for the WP; the authority FR-001 keys on (non-terminal post-allocation states, read from the resolved coordination status surface).
- **Coordination-commit sink**: the shared `_commit_via_coordination_transaction` through which all three coord lifecycle staging sites funnel; FR-005 partitions its staged paths by artifact kind so PRIMARY-partition WP files never reach coord.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #4889 trigger scenario (lane worktree + branch both removed while the WP is in a non-terminal post-allocation state), the command exits non-zero 100% of the time — via **both** the CLI and the orchestrator/agent caller — and never prints `Lane worktree ready`; the stranded commit remains reachable via the ref named in the diagnostic.
- **SC-002**: In the #4889 control arms (worktree intact; branch intact + worktree gone; genuinely fresh lane; re-open with tip reachable on target), the command resumes / creates normally with exit `0` and no false refusal — zero regressions.
- **SC-003**: On a `coord` mission with WP01→WP02, both work packages start through `agent action implement` with exit `0` and no `PlanningCommitMergeConflictError`; the coordination branch tree contains zero `tasks/WP*.md` blobs — verified after claim **and** after a review-claim.
- **SC-004**: Both defects have an issue-pinned regression test that is RED on the pre-fix entry point and GREEN after the fix, exercised across all three allocation routes and both allocator callers.

## Assumptions

- The operator's `/spk-mission-from-issue` invocation authorizes PR-bound feature-branch work landing on `main` via a PR to the upstream repo; no separate branch-strategy confirmation was required.
- Fail-closed (not automatic recovery) is the correct #4889 posture — the issue's own *Regression expectation* specifies exit non-zero with a diagnostic; automatic reflog/`fsck` recovery is out of scope.
- The #4889 guard belongs **inside `allocate_lane_worktree`** (a pre-flight before the FRESH routes) or a helper both callers pass through — not in the CLI-only `create_lane_workspace` wrapper, which the orchestrator-api caller (`_resolve_start_workspace`, `orchestrator_api/commands.py:1375`) bypasses (post-spec architecture lens).
- The root fix for #4905 is at the shared coordination-commit sink (`_commit_via_coordination_transaction`), partitioning staged paths by artifact kind via `mission_runtime.is_primary_artifact_kind`, so all three lifecycle staging sites (claim / resume-refresh / review-claim) are covered by construction — not a per-site patch and not a new merge driver. This matches the existing `commit_to_primary_target` partition mechanism the native planning-commit path already uses.
- The orchestrator status commit (`coordination/status_transition.py`) is already partitioned (stages only status artifacts to coord), so #4905 is confined to the CLI `workflow_executor.py`/`workflow.py` path and does not touch WP01's files — the WP01∥WP02 write scopes are disjoint (post-spec lens confirmed).
