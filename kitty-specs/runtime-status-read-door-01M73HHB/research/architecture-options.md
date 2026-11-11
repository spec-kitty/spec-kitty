# #7310 S5 follow-up: runtime/next status readers onto the door (architect lens)

Base: branch `refactor/7310-status-read-door-s5` (lanes precedent done, allowlist 42, `_LIVE_HIT_FLOOR = 43`, baseline 42).
In scope: 8 runtime/next entries (`test_status_read_single_door.py:207-214`) + `implement_support::_ensure_repo_root_checkout_available` (:238) after #7493.

## 0. Facts that shape the design

- **One log, read up to about 8 times per decision.** `_resolve_wp_board_action` (`runtime_bridge_decision_mapping.py:475-519`) calls `_wp_task_surface_error` (get_all_wp_lanes), `_compute_wp_progress` (get_all_wp_lanes + `materialize_snapshot`, `decision.py:251-315`), then `_finalized_task_board_override_step` (`:87-132`), which calls `preview_claimable_wp` (`discovery.py:196`, `_load_wp_states`), `_find_first_wp_by_lane` up to 4 times and `_count_wp_endings` (get_all_wp_snapshots). The implement and review arms then read the log again. Every read is `Path`-typed, and every one reduces the same events.
- **Reducer parity.** `get_all_wp_lanes`/`get_all_wp_snapshots` use `reduce(events)`. `materialize_snapshot` uses `reduce_shared_state(raw_events)` plus projections (`reducer.py:397`). The door's `materialize_status` uses `reduce(transitions, annotations)` (`read_surface.py:694`). `compute_weighted_progress` reads only `work_packages[*].lane` (`progress.py:120-175`), so only lane parity matters. CLAUDE.md says "one reducer, two parsers". *Speculative:* the lanes can differ only where the raw parser and the typed parser disagree, so a parity test should pin it.
- **The owned coordination arm today** (`resolution.py:1571-1660`) composes the coordination dir under `owned.repository_root` (R), the same as the door. The difference is not P vs R for the log. It is (i) where meta/PRIMARY is found: the owned arm uses `owned.mission_dir` (P), while `resolve_status_read(owned=…)` for coord calls `decide_status_read(owned.repository_root, mission)` (`read_surface.py:183-192`), which locates the Mission in R's `kitty-specs/`. If the owned Mission does not exist in R, that raises `FileNotFoundError`/`StatusReadPathNotFound`. (ii) the EMPTY/NONE/UNMATERIALIZED policy: the owned arm refuses with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, but `_dn_bootstrap`/query pass `tolerate_unmaterialized_coord=True` (`runtime_bridge.py:432-437`, `runtime_bridge_query.py:456-462`). So UNMATERIALIZED today yields a non-existent declared path and a silent **empty board**. The door reads `COORD_BRANCH_REF` for EMPTY/UNMATERIALIZED, and the ADR body already says "Owned checkouts of a coordination Mission follow the same rule instead of raising (FR-003)" (ADR :106-107).
- **`agent tasks status` already reads `resolve_status_read(…, owned=st.owned)`** (`tasks_status_cmd.py:388-405`). For an owned coordination Mission, the board and `next` can therefore disagree today, or one of them fails.

## 1. Design options for the Path-typed board consumers

| | (a) dual-typed `Path \| StatusReadSurface` | (b) read once, then a `BoardStatus` value into pure consumers | (c) owned-aware door entry |
|---|---|---|---|
| Single canonical authority | Weak: each consumer keeps its own read and branches on type | Strong: one door read and one reduction per decision, as in the #7335 precedent (`_st_reduce_surface`) | Required either way: fixes the door, not the consumers |
| Tiered rigour | Low-risk per function, but about 8 functions gain a second arm and twice the tests | Medium: signature change on private helpers; `preview_claimable_wp` is public, so keep its Path arm as a thin adapter | High: changes the door contract for owned coord, so it needs an ADR amendment |
| Diff size | Medium, spread out | Medium, concentrated in `decision.py`, `discovery.py`, `runtime_bridge_decision_mapping.py` | Small in the door, larger in tests |
| Reducer parity | Unchanged per call | One reduction. `weighted_percentage` must come from the same `work_packages` (pin it with a test against `materialize_snapshot` on a Path source) | n/a |
| Drops allowlist entries? | Yes, but the Path arms survive as a blind spot (they are not scanned) | Yes, and the consumers become door-only candidates | Unblocks the owned arm in `_dn_bootstrap`, `query_current_state` and `_build_finalized_override_query_decision`; without it those entries stay or regress |

**Recommendation: (b) + (c).**
- **(b) shape.** Add a frozen `BoardStatus` (or `WpBoardStatus`) next to `runtime/next/discovery.py`: `lanes: Mapping[str, Lane]`, `wp_states: Mapping[str, Mapping]`, `has_log: bool`, `weighted_percentage: float | None`. Build it once with `board_status_from(surface)`, which calls `read_status_stream` and `reduce` once. `_compute_wp_progress`, `_find_first_wp_by_lane`, `_count_wp_endings`, `_has_claimable_planned_wp`, `_wp_task_surface_error`, `_finalized_task_board_override_step` and `preview_claimable_wp` take `board=`. The `status_dir=` keyword stays only as an adapter that builds a `BoardStatus` from a Path, for external callers and tests, and is removed later.
- **What (b) fixes.** The "reads a Path that has no log" class (#4959) disappears, because a ref source yields real lanes.
- **(c) without option (a)'s risk.** Make `resolve_status_read(owned=…)` for a coordination topology take PRIMARY/meta from `owned.mission_dir` while it probes the coordination state under `owned.repository_root`. That is a `primary_dir` override threaded into `_decide`.
- **The policy question is a Decision Moment** (DM-1 below): should owned EMPTY/UNMATERIALIZED read the ref (as the ADR says) or refuse?
- **Rejected: (a) alone.** It keeps N readers and makes each one decide.

## 2. Non-reads: where each belongs

| Site | Current | Destination |
|---|---|---|
| `next_invocation_lifecycle.emit_mission_next_invoked` (:341) | A **write** of `mission-events.jsonl` through `read_dir` | The write seam: `.artifact(STATUS_STATE).write_dir` (or `placement_seam(...).write_dir`), which the gate exempts (`_WRITE_ATTRS`, test :68). Keep the best-effort `try`. **Check first:** readers of that file (`runtime_bridge_composition.py:352-394`) read `feature_dir/mission-events.jsonl`, so add a read-after-write test for coord MATERIALIZED, coord UNMATERIALIZED and landed. *Speculative:* `write_dir` raises on UNMATERIALIZED where `read_dir` tolerated it. Either way the event is dropped (feature_dir None), so behaviour is the same. |
| `_resolve_wp_board_action` `read_dir` probe (:476) | Called only for its `CoordinationWorktreeUnmaterialized`/`Deleted` raise | Through the door, UNMATERIALIZED is **readable** (`COORD_BRANCH_REF`), so the probe's premise goes away. Keep `CoordinationBranchDeleted` (the door raises it). Whether to still block on UNMATERIALIZED is DM-2. If DM-2 says block, add a small door-level classifier, `status_read_state(repo_root, mission, owned=None) -> CoordState`, or expose `surface.source` and block on `COORD_BRANCH_REF`. Do not keep a seam probe. |
| `decision._with_guard_failure_paths` (:450) and `runtime_bridge_io._artifact_presence_seam` (:1317, :1321) | Coupled. Bootstrap hands over the STATUS home as a **key**, and `_artifact_presence_seam` reverse-maps that dir back to a seam by comparing it with `read_dir(STATUS_STATE)`. Neither reads a log. | Thread the seam/context explicitly: `gather_artifact_presence(..., seam=...)` and `guard_failure_artifact_paths(..., seam=...)`. Callers: `runtime_bridge.py:275`, `runtime_bridge_composition.py:495`, `acceptance/non_wp_runtime.py:89`, `decision.py:452`. Then both STATUS_STATE identity reads disappear. Do **not** just swap in `PRIMARY_METADATA`: `_artifact_presence_seam` would then return None and COORD-kind artifacts would resolve in the primary dir (a regression). Fallback if out of scope: keep both entries and re-reason them to `_IDENTITY` (a reason change is allowed). |
| `_dn_bootstrap` (`runtime_bridge.py:446`) | `feature_dir = status_dir if is_dir() else primary` | `feature_dir` is a Mission-directory identity used for "not found", mission type and the presence key. After the seam threading above, bootstrap needs `PRIMARY_METADATA` plus a door surface for the board. The owned arm keeps its `ActionContextError` handling (:438-441) until DM-1 is settled. |

**Gate.** Teaching the gate a new "identity vs read" category is not worth it. Moving the sites removes the entries. Changing an entry's reason is fine, and no new gate is needed. One optional addition: put `runtime/next/discovery.py` (and later `decision.py`) in `DOOR_ONLY_MODULES` once they are pure. That module set is grow-only and is not a new gate, but `decision.py` keeps other path reads, so add only modules that are truly clean.

## 3. Behaviour changes (fix vs regression)

| # | Change | Class | Needs a DM? |
|---|---|---|---|
| B1 | Non-owned coord EMPTY/UNMATERIALIZED: `next`/query read the coord ref, a real board instead of an empty one (#4959 class) | fix | DM-2 (dispatch on UNMATERIALIZED) |
| B2 | Owned coord UNMATERIALIZED: today a silent empty board (tolerate flag); through the door, the ref | fix | DM-1 |
| B3 | Owned coord EMPTY/NONE: today `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` (a blocked decision); through the door, a ref read (EMPTY) | **regression by operator constraint**, though it matches the ADR | DM-1 |
| B4 | Owned Mission absent from R: today it resolves via P; through the door as it is now, `FileNotFoundError` | **regression**, fixed by option (c) | no, (c) is required |
| B5 | `_wp_task_surface_error` on a ref: real lanes, so it may now report missing task files it skipped before | fix (surfaces hidden inconsistency) | no |
| B6 | One reduction per decision (perf) | fix (NFR) | no |
| B7 | Landed Mission: door reads `CONSOLIDATED_TARGET`, where the legacy seam read the coord worktree or ref | fix, but `_merged_mission_short_circuit` runs first, so this is rarely reached | no |

**Candidate Decision Moments**
- **DM-1 Owned coordination with EMPTY/UNMATERIALIZED.**
  - (A) Read the committed ref, as the ADR's FR-003 says. Write-needing actions refuse later.
  - (B) Keep `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` for `next`. The door gains an `owned` refusal policy and the ADR is amended.
  - (C) Read the ref for query/progress, and refuse only on an advancing dispatch.
  - Recommendation: C. It meets the operator constraint and does not split the read authority.
- **DM-2 Non-owned UNMATERIALIZED on the advancing path.**
  - (A) Keep the "materialize it" block, decided from `surface.source`.
  - (B) Dispatch from the ref board, and let `implement` materialize.
  - Recommendation: A for this Mission (behaviour-preserving), with B filed as a follow-up.
- **DM-3 `_with_guard_failure_paths`/`_artifact_presence_seam`.**
  - (A) Thread the seam explicitly; both entries drop.
  - (B) Re-reason them as `_IDENTITY` and defer.

## 4. Proposed WP slicing

| WP | Content | Depends | Allowlist after |
|---|---|---|---|
| WP01 tidy-first | `BoardStatus` value plus a `board_status_from(surface)` builder. The consumers take `board=` and their Path kwargs become adapters. No call-site change, and a parity test (lanes and weighted % vs `materialize_snapshot`) | — | 42 |
| WP02 door | Option (c): owned-coord PRIMARY from `owned.mission_dir`, plus the DM-1 policy. Red first: owned Mission absent from R resolves; owned EMPTY behaves per DM-1. ADR amendment | — | 42 |
| WP03 board | `_resolve_wp_board_action` (both entries), `query_current_state`, `_build_finalized_override_query_decision`. Red first: non-owned UNMATERIALIZED query shows real lanes; owned arms keep the DM-1 outcome | WP01, WP02 | 38 |
| WP04 bootstrap/presence | Seam threading for `gather_artifact_presence`/`guard_failure_artifact_paths`; `_dn_bootstrap`, `_with_guard_failure_paths`, `_artifact_presence_seam` (DM-3 A) | WP02 | 35 |
| WP05 write + lanes | `emit_mission_next_invoked` onto `write_dir` (read-after-write test); `_ensure_repo_root_checkout_available` onto the door (after #7493) | #7493 merged | 33 |

Each WP lowers `_LIVE_HIT_FLOOR` and the `_baselines.yaml` entry in the same commit.
- **WP06 (optional):** add `runtime/next/discovery.py` to `DOOR_ONLY_MODULES`.

**Conflict risk**
- `runtime_bridge*`/`decision.py` are hot files. WP03 and WP04 touch them, so serialize those two.
- #7493 edits the same lines as `_ensure_repo_root_checkout_available`, hence WP05 waits.
- #7490 touches `coordination/status_transition.py`, which is outside this scope (no overlap).
- `_baselines.yaml` and the allowlist block conflict trivially between WPs, so rebase them in order.

## 5. Candidate FRs / acceptance

- **FR-A.** Every runtime/next board, progress and query decision reads status through exactly one `resolve_status_read` call and one reduction per decision. Test: patch the door, assert one call.
- **FR-B.** A non-owned coord Mission with an EMPTY/UNMATERIALIZED coordination worktree reports the lanes of the committed coordination ref in `next --json` query `progress`.
- **FR-C.** An owned coord Mission whose Mission dir exists only in the owned checkout resolves (no `FileNotFoundError`), and EMPTY/UNMATERIALIZED follows DM-1. `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` is still emitted wherever DM-1 keeps it.
- **FR-D.** `weighted_percentage` equals the legacy `materialize_snapshot` value for every Path source (parity test).
- **FR-E.** `MissionNextInvoked` is appended through the write seam, and a subsequent read of `mission-events.jsonl` sees it (coord materialized; single_branch).
- **FR-F.** `CoordinationBranchDeleted` still yields the flatten next_step. The UNMATERIALIZED blocked text follows DM-2.

**Gate success criterion.** 42 → **33**: the 8 runtime/next entries plus `_ensure_repo_root_checkout_available`. If DM-3 = B, the target is 35, with `_with_guard_failure_paths` and `_artifact_presence_seam` re-reasoned to `_IDENTITY`. `_LIVE_HIT_FLOOR` and the baseline move with it.

**Entries that remain** (about 33) are owned by other slices:
- `_PATH_CONSUMER`: acceptance, kanban, tasks.py ×2, accept, workspace/context, `reenter_lane_self_heal` (needs a shared `check_claim_ancestry` surface)
- `_DOCTOR` ×5 (decisions doctor, check_prerequisites, finalize_lanes, changelog): want the same door-level state classifier as DM-2 A
- `_WRITE_SIDE` ×4 (#7490/#6608)
- `_PARTITION` ×3
- `_PIN` ×2 (#5702)
- `_WORKPACKAGE` ×2
- `_DELEGATOR` ×2: last, after their callers
- `_SEAM_ARM` ×1
- `_FAIL_LOUD` (`_canonical_wp_lane_value`)
- `_AGGREGATE` (#3462)
- `_DRIFT`
- `_IDENTITY` (owned_charter)
- `_HANDED_REF`
- `_WRITES_THROUGH_READ` (tasks_materialization)
