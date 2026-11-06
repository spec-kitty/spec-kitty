# Research: Lane and worktree model hardening

Phase 0 decisions for the plan. Every entry records a Decision, its Rationale and the Alternatives considered. The evidence lives in the six discovery briefs (A–F, session scratchpad) and the resolved Decision Moments (`decisions/`). Four planning questions (OQ-1 to OQ-4) and two follow-on points (`primary_partition_default`, `pr_bound_fallback`) went to the operator and are resolved as Decision Moments; each entry cites the decision it applies, and plan.md lists them under "Resolved planning decisions".

## R-1 Status read contract per topology (S1)

- **Decision**: one door, `resolve_status_read(repo_root, mission, *, owned=None) -> StatusReadSurface`, whose `source` is declared per topology.
  - **`single_branch`, `lanes`, provisional Missions**: `WRITE_CHECKOUT`, the repository root checkout's working tree or the validated owned checkout. Never a ref: these appends are uncommitted, so a ref read would drop rows.
  - **`coord` / `lanes_with_coord`, coordination worktree materialized**: `COORD_WORKTREE`. The transaction commits in the same unit of work. `status_surface_guard` stays the divergence backstop.
  - **`coord` / `lanes_with_coord`, worktree EMPTY or UNMATERIALIZED**: `COORD_BRANCH_REF`, a `git cat-file --batch` read of `refs/heads/<coord>:kitty-specs/<dir>/status.events.jsonl`.
  - **Coordination branch exists but carries no log yet** (the explicit-topology create window): a *declared* `WRITE_CHECKOUT` fallback, stamped on the surface so callers and tests can see it.
  - **Coordination branch deleted**: raise `CoordinationBranchDeleted` (unchanged).
  - **Consolidated Mission**: `CONSOLIDATED_TARGET`, the repository root checkout of the target.
  - **Every input root**: normalized first. A lane root re-anchors to the main repository root through the #6884 registry classifier.
  - The door never returns a lane path or a path that does not exist.
- **Rationale**: nine adapters give four answers for the UNMATERIALIZED state today (brief A, table A1). The write side (`status_transition._read_contract_from_transaction_target`) already reads the ref in that state, so the contract adopts the one adapter that is right. Short-lived checkouts (ruling 5) and the S9 write service make UNMATERIALIZED the normal state.
- **Alternatives**:
  - (a) Keep the loud repository-root fallback for EMPTY (coord-artifact-single-home FR-017/C-002). Rejected: it reads a stale copy as truth, which is the root cause of #6466/#7198. IC-01 reverses it explicitly.
  - (b) Materialize the coordination worktree on read. Rejected: it fights ruling 5 and S9, and it writes during a read.
  - (c) Raise on UNMATERIALIZED (`PlacementSeam` today). Rejected: a short-lived checkout would then break every reader.
- **Registry unreadable during normalization**: fail closed, as a typed error. Do not keep the input root as #6884 does (Rules and Invariants, rule 1). This tightens #6884's fail-open-to-unchanged choice and is recorded in the IC-01 ADR.

## R-2 Ref reader: absent file vs bad ref (S1, FR-004)

- **Decision**: the reader returns a typed result `RefRead.ABSENT | RefRead.PRESENT(bytes)` and raises `StatusSurfaceRefUnreadable` when the ref is missing, the object is unreadable or git fails. Callers map ABSENT to an empty history. A missing coordination ref keeps raising `CoordinationBranchDeleted` where the resolver already detects DEL.
- **Rationale**: `read_event_log(COORDINATION_BRANCH_REF)` returns `[]` on any `git show` failure (`status_service.py:172-200`), so a broken ref reads as genesis.
- **Alternatives**: return `None` for a bad ref, which is ambiguous at every call site. Rejected.

## R-3 for_review gate on the lane branch ref (S2)

- **Decision**: the shared gate counts `git -C <repo root> rev-list --count --end-of-options <base>..refs/heads/<lane>`. The branch comes from `lane_created_branch(manifest, lane)`, the same authority `wp_evidence.lane_evidence_window` uses. A missing `refs/heads/<lane>` refuses with a distinct reason (`reason_code=LANE_BRANCH_MISSING`). The no-commit refusal names the branch and base and never asks for a lane worktree. `move-task`'s checkout-present checks stay in `move-task` (C-006).
- **Rationale**: the gate's only checkout dependency is `worktree.exists() and lane_has_commit_beyond_base(worktree, ...)` (`for_review_gate.py:280`). With the checkout absent, `move-task` passes but `status emit` and `orchestrator-api transition` refuse, which invites `--force` (brief B).
- **Contract**: the orchestrator-api envelope stays `TRANSITION_REJECTED` with the same data keys. The distinct reason is carried in the message text plus an internal `GateDecision.reason_code`. No version bump (C-012, SC-012).
- **Alternatives**:
  - (a) A dirty-checkout refusal on the shared gate. Rejected by C-006: it is an unruled contract change.
  - (b) Expose `reason_code` in the orchestrator envelope. Deferred: it would need a second bump.
- **Known residual (out of scope)**: the count also includes dependency-fold and planning merges, and the local ref may be stale in multi-clone flows. Owned-file evidence and origin freshness for this gate are follow-ups.

## R-4 Restated ruling 3: lanes carry no live status (S6)

- **Decision**: the operator's restatement (DM `01M6QY3XQJ5…`). In practice:
  - No lane checkout shows `status.events.jsonl` / `status.json`: sparse exclusion is applied by the one lane-checkout helper, on every topology with code lanes.
  - No Spec Kitty write lands in a lane: the write seam classifies the target through the worktree registry, not by path shape, and lane auto-commits leave status unstaged.
  - No reader reads a lane copy (S1).
  - The fork-time blob stays in lane history, never deleted (C-008).
  - Existing lane worktrees are migrated by a clone-local migration: clean ones get the exclusion; dirty redundant copies are flagged and excluded; dirty copies holding event ids not on the surface are left untouched and reported; worktrees mid-merge or mid-rebase are skipped.
  - A doctor probe lists lane branches whose status files differ from their merge-base. That probe is the gate for a later retirement of the auto-rebase union merger.
- **Rationale**: deleting the files on lane branches would carry the deletion onto the Mission or coordination branch at consolidation. It would also trip `auto_rebase._refuse_preexisting_lane_status_deletions` and break ADR `2026-07-29-1` Assert A' (brief B R1).
- **Alternatives**:
  - (a) Literal deletion commits. Rejected: data loss.
  - (b) A git pre-commit hook. Rejected (A-9): it is not Spec Kitty-owned, and the doctor probe covers hand commits.
  - (c) Drop dirty lane copies in the migration. Rejected (C-009).
- **Migration placement**: `clone_local_effect=True`, because sparse configuration lives in the per-worktree git dir. `apply()` is idempotent (NFR-005). A `doctor` fix is not chosen as the only path, since upgrade must bring clones in line on its own.

## R-5 One lane-checkout helper (S3/S6)

- **Decision**: `lanes/lane_checkout.py::open_lane_checkout(...)` is the only lane `git worktree add`. It runs `worktree add` on an **attached** branch (so the `post-commit` lane-tip hook fires), installs the hook, adds the `.spec-kitty/` local exclude, and registers the sparse status exclusion. Routes: allocation FRESH, FRESH_LEGACY and CRASH_RECOVERY; the `lifecycle_sync` recreate; the review checkout; the printed recreate command. A non-vacuous gate forbids any other lane `worktree add`. The helper is also the future lease acquire (ADR `2026-04-03-1` amendment), but no lease state is built (C-007).
- **Rationale**: three routes skip the exclusion today even for coordination topologies (brief B §7), and `lanes` topology never registers it.
- **Alternatives**: patch each route. Rejected: that is how the routes drifted.

## R-6 S7: deferred materialization, provisional representation, decide-once, compensation

- **Decision (ruling)**: `create` without `--topology` mints exactly one Mission topic branch, `kitty/mission-<slug>-<mid8>` (A-1), whatever the target's protection. The first `finalize-tasks` settles the topology by size before its first status write and before any WP is claimed:
  - `single_branch` when there are ≤ 2 non-canceled WPs or ≤ 1 code lane;
  - otherwise `lanes_with_coord` on **every** target, protected or not, with the topic branch as the coordination branch (A-3; DM `01M6QZ02HDACM7A0VNYSAQ8MQB`, extended to unprotected targets by DM `01M6R0B954ZPQN5NV4R1ZRE7NY`).

  Plain `lanes` and `coord` are explicit-only. Settlement runs once. `--topology` and `--owned-checkout` are explicit and settled at create. Missions without `topology_source` are settled (legacy).
- **Decision (DM `01M6R0BDYC29D6XMDY72R22CP9`, OQ-3)**: a provisional Mission is stored as:
  - `topology: single_branch`
  - `mission_branch: <topic>`
  - `topology_source: default`
  - `topology_settled: false`
  - `create_return_branch: <the branch the write checkout was on before create switched it>` (new; read only by settlement)

  `create --json` reports `single_branch` with `topology_provisional: true` until finalize. The write checkout holds the topic branch until settlement (A-2, option "write checkout"). This reuses the minted `single_branch` routing (`single_branch_write_ref`, the one choke point for planning and status writes), so specify, plan and tasks land on the topic branch with no new placement code. Settlement then only ever grows: `single_branch` (no git step) or `lanes_with_coord`.
- **Why the topic branch can be the coordination branch (corroborated 2026-11-06)**: `coordination_branch` is a `meta.json` key read through `COORDINATION_BRANCH_KEY` (about 32 readers), and its default name comes from `mission_branch_name`, the same grammar as the topic branch. The reconstruct-from-slug paths (`coordination/coord_seed.py:1155`, `coordination/workspace.py:300`) yield the same name. Nothing in the earlier rulings ties the coordination designation to a branch minted at create.
- **Settlement to `lanes_with_coord` (the one git-moving path; DM `01M6R0B954ZPQN5NV4R1ZRE7NY`)**:
  1. Commit the Mission dir on the topic branch in the write checkout.
  2. Move the repository root checkout off the topic branch, back to `create_return_branch`. Git forbids one branch checked out in two worktrees, so this step must precede step 4.
  3. Re-stamp `meta.json`: set `coordination_branch` to the topic ref name, keep `mission_branch` (the PRIMARY partition of a default Mission, FR-061; it now names the same ref as `coordination_branch`), set `topology: lanes_with_coord`, `topology_settled: true`, and write `topology_decision`.
  4. Materialize and seed the coordination worktree on the topic branch through `CoordinationWorkspace.resolve()`.
  5. Write `lanes.json`. Lane branches are cut from the topic (coordination) branch later, by the allocation path (A-7).

  No planning commit lands on the target at settlement, and there is no fast-forward or merge step. Lane consolidation lands into the coordination branch, and the coordination branch lands on the target at consolidate, as for an explicit `lanes_with_coord` Mission.
- **Settlement to `single_branch`**: no git step. `topology_settled: true` and `topology_decision` are written; the topic branch stays the Mission branch and stays checked out in the write checkout.
- **PRIMARY placement of a default Mission (DM `01M6R0QJVPVZG2QT8MWQD4NXJR`, supersedes DM `01M6R0B3YX291STRVVQ0HQCJD5`; FR-061)**: for `topology_source: default` the PRIMARY partition (`_PRIMARY_ARTIFACT_KINDS`, `src/mission_runtime/artifacts.py:180`: spec, plan, research, data-model, contracts, tasks, WP files, `lanes.json`, `meta.json`) resolves to the Mission topic branch (`meta.mission_branch`, which after a multi-lane settlement is also the coordination branch) until `consolidate` lands it on the target. `target_branch` stays the landing branch. Explicit `--topology` Missions keep today's placement (PRIMARY to `target_branch`). This is a placement contract change, recorded by the IC-01 and IC-02 ADRs and carried by the S1 read door (IC-05) and the placement seam as one change. IC-14 pins, rather than escalates, that a default Mission's PRIMARY reads and writes go to the topic branch before and after settlement and that `consolidate` lands them. **Consequence**: settlement moves the repository root checkout back to `create_return_branch`, so the root checkout no longer shows the planning files; readers must go through the read door or placement seam, never a root-checkout path.
- **Compensation**: settlement is a planned list of reversible steps executed in order, with an undo stack. Any failure restores `meta.json` byte for byte, every branch tip, the absence of a coordination worktree and the repository root checkout on the topic branch (NFR-003, fault-injected at every git step). Preconditions:
  - the write checkout is clean and not occupied (`in_progress_wps_in_write_checkout`; #5676 is fixed in the extracted mint core first);
  - `create_return_branch` exists and is not checked out in another worktree;
  - no WP has a lifecycle event past `planned`;
  - no lane branch or worktree is recorded.
- **Rationale**: the operator's rationale is that shrinking a lane or coordination topology into `single_branch` is the most expensive transition and growing is cheap. Brief C showed `coord → single_branch` needs a worktree removal and a branch hand-over, while growth from a held topic branch needs neither projection nor deletion. Reusing the minted `single_branch` routing keeps placement code unchanged before settlement. One settlement path for every target removes the protection-dependent branch of the transition and the landing step with its conflict handling.
- **Alternatives**:
  - (a) Keep `lanes`/`coord` as the provisional default and re-stamp to `single_branch` (brief C WP1/WP2). Rejected by the escalation ruling.
  - (b) Store a new `topology: provisional` enum value. Rejected: about 55 stored-topology readers would need a new arm; the `single_branch` representation needs none.
  - (c) Write pre-settlement artifacts by commit with no checkout. Rejected: agents author spec, plan and tasks in a working tree.
  - (d) Keep the write checkout on the topic branch for a `lanes` Mission's life. Rejected: it occupies the repository root checkout (#5550, #5676), the same reason A-3 rejected it on protected targets.
  - (e) On an unprotected target, land the topic branch's planning commits on the target (fast-forward, else a merge commit) and settle to `lanes`. This was the plan's original recommendation for OQ-2. Rejected by the operator (DM `01M6R0B954ZPQN5NV4R1ZRE7NY`): lanes are cut from the topic branch, which carries the coordination designation.
- **Risks**:
  - Every no-topology `create` moves the repository root checkout onto the topic branch. A second `create` run from there would record the first Mission's topic branch as its target. Mitigation in IC-13: target resolution never picks a branch recorded as another Mission's `mission_branch` or `coordination_branch`, and resolves the primary branch instead, with a test. If the operator prefers a refusal, that is a new code (raise in review).
  - `create_return_branch` may be deleted or checked out elsewhere by settlement time. Settlement refuses `TOPOLOGY_SETTLEMENT_REFUSED` with nothing changed; the remedy names the branch.
  - The `single_branch` population grows. C-010 requires S8 (IC-11/IC-12) to ship with or before IC-13/IC-14.
  - Every size-default multi-lane Mission now carries a coordination worktree, also on unprotected targets where it would have been `lanes` before. That is the accepted cost of one settlement path.
- **`--pr-bound` (A-5, DM `01M6R0QQM5FCPY736008AD4W6V`)**: the coordination-unreachable fallback to plain `lanes` is dropped for default Missions. Multi-lane settlement always yields `lanes_with_coord`; plain `lanes` stays explicit-only. The #2533 stranded-branch hazard does not apply once the topic branch is the coordination branch. **`--commit-to-target` (FR-060)**: still requires an explicit `--topology single_branch`.

## R-7 S8 stamp and tier-1/tier-2 windows

- **Decision**:
  - **Stamp**: for every lifecycle transition of a WP in a Mission whose *stored* topology is `single_branch`, the stamp is the head of the Mission write branch (`write_branch_for`). It is never keyed on `is_planning_lane` or `execution_mode: direct_repo`. A `lanes` planning lane stays unstamped.
  - **Tier 1** (claim time): `check_lane` runs unchanged on the Mission branch, so content committed after the newest approval refuses `LANE_MOVED_AFTER_APPROVAL`.
  - **Tier 2** (claim time): every content commit in `claim_base..mission_branch` (merges and bookkeeping excluded) must be reachable from some approved WP's `S_k` and not from its `O_k`. `O_k` is the first governed claim stamp (`wp_attribution.first_governed_open_stamp`); `S_k` is the newest approval stamp. Otherwise consolidate refuses `LANE_MOVED_AFTER_APPROVAL`, naming the commit and the preceding WP. Overlapping windows are accepted.
  - **Gate re-check**: the Mission branch is read through the claim's `lane_id -> branch` map, never `_lane_branch_for("lane-planning")`, which resolves to the target.
  - **No stamp**: missing `S_k` refuses `APPROVAL_STAMP_MISSING`; `S_k` not on the branch refuses `APPROVAL_STAMP_NOT_ON_LANE`. A missing `O_k` degrades to `(claim_base, S_k]` and is logged (A-8).
  - **Scope**: the bound applies only when `lands_mission_branch`. `--commit-to-target` stays unbounded, pinned by a strict xfail (FR-078).
- **Rationale**: tier 1 alone misses a commit slipped between two approvals, which is the common case on one shared branch. The window is cumulative from the first claim because the reviewer's diff runs from `wp-base` (brief D). Reusing codes keeps the orchestrator-api `preflight_error_codes` contract unchanged (FR-076).
- **Alternatives**:
  - (a) Extend the #5046 canceled-WP resolver (`_windows`). Rejected: it is first-parent-only and canceled-scoped, and ADR Option 5 already rejected it.
  - (b) A new refusal code. Rejected (C-012).
  - (c) Exact per-commit attribution. Deferred: it is heavier and the reviewer's cumulative diff makes any-window sound.

## R-8 S8 backward compatibility: refuse plus attest

- **Decision (ruling)**: every unstamped approval on an in-flight `single_branch` Mission refuses `APPROVAL_STAMP_MISSING` after upgrade. `--attest-approved-reviewed <WP> --attest-reason "..."` lifts it per WP. **No `approval_bound` marker key** is written (brief D's marker proposal was not adopted).
- **Rationale**: this follows the lanes precedent of ADR `2026-10-04-5` ("Upgrade impact"; Option 7 rejected exempting old approvals).
- **Alternative**: a Mission-level marker scoping the bound to newly stamped Missions. Rejected by the operator.

## R-9 S5 lane-cleanup module and remover port

- **Decision**:
  - One module, `consolidation/lane_cleanup.py`: a pure plan builder plus `apply(items, remover)`.
  - `LaneRemover` is a Protocol port, bound today to the current guarded primitives exactly as they behave, and to `guarded_landed_removal` with an O3-local landing proof once #7275 merges.
  - Order: the coordination triple first (S10's codes and exits unchanged), then the lane legs, then the record clear.
  - Each lane yields `removed`, `kept(code, remedy, command)` or `retained_by_policy`; the lane legs never raise after a verified landing (exit 0).
  - `clear_tip` runs only after a confirmed branch delete.
  - A `cleanup_started` marker in `ConsolidationState` makes `--resume` after a kill skip straight to cleanup, but only if the red-first test shows the crash window is real (FR-035).
  - `orchestrator-api consolidate-mission` and `mission close --discard` call the same module. The envelope gains per-lane outcomes in contract 1.24.0, the same bump that carries the topology fields (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).
  - Once bound, `accept --mode pr` removes the lanes the pushed PR head absorbs.
  - The prune backstop treats consolidated or PR-accepted Mission lanes as candidates when no consolidation record is active and no retention is declared.
- **Rationale**:
  - There are three teardown copies with branch-name drift.
  - A `DestructiveOpRefused` after landing surfaces as a traceback today.
  - No step owns removal after a PR landing.
  - #7275 binds only the prune, and its O3 needs a named remote ref (brief E).
- **Alternatives**:
  - (a) Stack on #7275. Rejected: it is a 2.7k-line PR still taking fold commits, with a shared routing test.
  - (b) Leave the lane legs first. Rejected: a coordination refusal would then strand evidence (R6 of brief E).
- **`ConsolidationState` field**: an additive field read with a default. ADR `2026-09-19-1` is amended only if the field is persisted across `--abort` (it is not).

## R-10 S9 ADR split

- **Decision**: five records plus one amendment (brief F):
  - core **C-1**: the coordination branch is written by commit, not through a worktree; every coordination-partition kind is covered, `status.json` handling, retired codes, the drain-and-remove migration;
  - core **C-2**: gates over a worktree-less coordination branch; it cites the #7265 pass and does not re-decide it; the write fence options;
  - core **C-3**: the committed ledger is the coordination-branch blob; read API pull and the `events tail` cursor source;
  - spec-kitty-events **ADR 0007**: the write service commits a unit to a branch ref with compare-and-swap, plus the `mission-write` 1.0.0 contract deltas;
  - spec-kitty-events **ADR 0008**: the read service reads git objects;
  - an amendment to core ADR `2026-10-22-1` D-6 naming the records and adding step 4a.

  All are Proposed. Choices the rulings leave open stay as options with a recommendation (A-12). The events ADRs are drafted by a sibling session in that repository's conventions (`NNNN-title.md`); core IC-03 cross-links them.
- **Rationale**: the placement rule of ADR `2026-10-29-1` D-1/D-7 puts Java service internals and the `mission-write` contract in spec-kitty-events, and CLI placement, gates and the cursor in core. Writing to the object store is a new `EventLogPort` adapter, so D-6's "own ADR first" applies.
- **Alternatives**: one omnibus ADR. Rejected: it crosses repository ownership and mixes three decision owners.

## R-11 S11 text-follows-behaviour

- **Decision**: core skill and CLI text changes land in IC-17, after the slices they describe. The stale-lane CLI remedy prints a `spec-kitty` re-entry command, once the A-10 re-entry path (`agent action implement <WP>` → auto-rebase) is verified by a test. Pack doctrine ships as a patch file for `spec-kitty-open-packs` with hand-off steps (pin bump, `make sync-packs`, `charter pack regenerate-graph`). No lease text is written (FR-093). A grep guard with planted strings fails on `spec-kitty merge`, manual stale-lane recipes, hand status-commit advice and lease text.
- **Alternative**: a `consolidate` mission-step prompt. Out of scope (spec "Out of Scope").

## R-12 Supply chain

- **Decision**: no dependency is added, removed or re-pinned. `uv.lock`, `pyproject.toml` dependency ranges and `packs/*.source.yaml` pins are not changed by this Mission. The open-packs pin bump happens after the operator lands the patch upstream. Git batched reads use the existing `git` binary (`cat-file --batch`), and no Python git library is introduced.
