# Research: Implement lane-allocation integrity

Phase 0 output. No `[NEEDS CLARIFICATION]` markers remain; this is a decision log for a source-traced bug-fix mission.

## Supply-chain install safety (DIRECTIVE_051)

**N/A — recorded, not skipped.** This mission adds, upgrades, and removes **zero** dependencies (no `pyproject.toml` / `uv.lock` change planned). Registry authenticity, package freshness, lifecycle-script discipline, and Node-LTS awareness therefore have no decision surface here. If implementation discovers a needed dependency, this record must be revisited before adding it.

## Adversarial evidence (post-spec architecture lens)

Contested findings and dispositions (per `contracts/adversarial-evidence-contract.md`); none silently dropped:

| Finding | Disposition | Where folded |
|---------|-------------|--------------|
| #4889 detector placed in `create_lane_workspace` is bypassed by the orchestrator-api caller (`_resolve_start_workspace`, `orchestrator_api/commands.py:1375`) | **changed** | Detector moved into `allocate_lane_worktree` (both callers); FR-008, US1-S2 added |
| FR-001 keying on `in_progress` alone under-reaches (`blocked`/`for_review`/`in_review` strand work identically) | **changed** | FR-001 broadened to non-terminal post-allocation; US1-S6 added |
| Real false-positive: re-open after legitimate merge-and-teardown (tip already on target) | **changed** | FR-009 added (resume if persisted tip is ancestor of target); US1-S7 + edge case added |
| #4905 fix at claim site only leaves review-claim (`workflow_executor.py:1741`) re-polluting coord | **changed** | FR-005 broadened to the shared sink covering all three staging sites; US2-S3 + SC-003 review-claim assertion added |
| C-003 write-scope disjointness of WP01∥WP02 | **accepted** (confirmed real: orchestrator status commit already partitioned) | plan Parallel Work Analysis |

## Decisions

### D1 — Detector seam: inside `allocate_lane_worktree`
- **Decision**: place the fail-closed destroyed-lane pre-flight inside `allocate_lane_worktree`, between the CRASH_RECOVERY gate (~L634) and the FRESH routes (~L636), so both callers (`create_lane_workspace` and `_resolve_start_workspace`) are covered.
- **Rationale**: `allocate_lane_worktree` is the single choke point both callers pass through; a wrapper-level guard is caller-dependent and the orchestrator path (the automation surface the P0 defends) would bypass it — "fixed and green but bypassed" is worse than a known-open P0.
- **Alternatives**: (a) guard in `create_lane_workspace` only — rejected (orchestrator bypass); (b) a shared helper both wrappers call — viable but adds a second call site to keep in sync; the allocator-internal placement is DRY and cannot be forgotten by a future caller.

### D2 — Detection signal: lane state, not ref existence
- **Decision**: the trigger is `persisted WorkspaceContext exists` AND `canonical status is non-terminal post-allocation` AND `neither the local lane branch nor its worktree exists` AND `the persisted lane tip is NOT an ancestor of the target branch`.
- **Rationale**: ref existence is defeated by #4969 origin-preference (a stale `origin/<lane>` can resurrect and disguise an empty re-cut). The persisted tip / status pair is the honest signal that committed work existed. The ancestor-of-target check (FR-009) removes the one real false-positive (re-open after legitimate merge).
- **Alternatives**: reflog scan for a stranded tip — rejected (fragile, gc-dependent; the persisted `base_commit`/branch tip is a stable pointer). Content probe of the lane worktree — impossible (it's gone).

### D3 — Status read surface
- **Decision**: read WP lane state from the resolved coordination status surface via the reducer, never from the lane worktree tree.
- **Rationale**: C-001 — on coord topology the lane worktree sparse-excludes `status.events.jsonl`/`status.json` (#2514), so reading there returns nothing and the guard silently no-ops (a fresh whack-a-field of the same class the mission fixes).

### D4 — #4905 fix at the shared coord-commit sink
- **Decision**: partition staged paths by artifact kind inside `_commit_via_coordination_transaction` (`agent/workflow.py`) — route `WORK_PACKAGE_TASK` (PRIMARY-partition) paths to the primary target via the existing `commit_to_primary_target` mechanism; keep only `STATUS_STATE` on coord — using `mission_runtime.is_primary_artifact_kind` (the write-side twin already cited at `commands.py:685`).
- **Rationale**: all three staging sites (claim `workflow_executor.py:881`, resume-refresh `:1066`, review-claim `:1741`) funnel through this one sink; fixing by construction here closes the class, versus a per-site patch that leaves re-pollution vectors. Reuses the canonical partition authority rather than inventing a merge driver for the WP file.
- **Alternatives**: teach FR-009 `_merge_recorded_planning_commit` to auto-resolve the add/add — rejected (papers over a partition leak; the WP file simply should not be on coord). Per-site path filtering — rejected (three sites to keep in sync; the sink is the single authority).

### D5 — Fail-closed, not auto-recovery
- **Decision**: #4889 exits non-zero with a diagnostic naming the missing lane branch + a concrete recovery ref (reflog / `git fsck --lost-found`); it does not attempt automatic recovery.
- **Rationale**: the issue's own *Regression expectation* specifies exit non-zero + diagnostic; auto-recovery is riskier and out of scope for a P0. The persisted metadata is left intact (FR-003) so the recovery pointer survives.

### D6 — Out of scope (noted, not ticketed here)
- Migrating already-polluted coord branches from pre-fix runs (a `doctor`-style recovery); a first-class `implement` recovery subcommand; automatic reflog recovery. These are genuine future work; record in the PR body per the steer, do not fold.
