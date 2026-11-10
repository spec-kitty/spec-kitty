# #7310 runtime/next status readers -> the read door: code grounding (debrief)

HEAD `757d70d2` on `refactor/7310-status-read-door-s5` (7 commits over origin/main). Read only; no repo file edited.
**The clone is shallow** (`git rev-parse --is-shallow-repository` = true), so churn and blame data are unreliable and were not used.
Experiment scripts: `repro/reducer_exp.py` and `repro/repro_cells.py` beside this file (the edge and pre-seed probes were throwaway).

Gate state: `LEGACY_READ_ALLOWLIST` has 42 keys (`tests/architectural/test_status_read_single_door.py:206-248`), `_LIVE_HIT_FLOOR = 43` (:270), the baseline is 42 (`tests/architectural/_baselines.yaml:28`), and `ALLOWLIST_DRAIN_BY = "2026-12-31"` (:51).
In-scope keys: 8 in runtime/next (:207-214), plus `implement_support.py::_ensure_repo_root_checkout_available` (:238).

Precedent pattern (`git log origin/main..HEAD`): each reader moved in two commits, a red test first and then a fix commit.
- Example: `e817c9fe` replaces `_read_events(placement_seam(...).read_dir(STATUS_STATE))` with `read_status_events(resolve_status_read(repo_root, slug))` and keeps `status.reduce`.
- The fix commit deletes one allowlist key in the same commit.
- `b84f5621` then lowers the floor and the baseline together.

## 0. The sites at HEAD (where each Path comes from)

| Allowlist key | Line | What it feeds |
|---|---|---|
| decision.py `_with_guard_failure_paths` artifact | decision.py:450 | owned only. `feature_dir = status_dir if is_dir() else PRIMARY_METADATA` (:451) -> `guard_failure_artifact_paths` + `get_mission_type`. Directory identity, not a log read. |
| next_invocation_lifecycle `emit_mission_next_invoked` | :341 (`tolerate_unmaterialized_coord=True`) | `emit_event(... feature_dir)` -> `_write_event` appends `mission-events.jsonl` (`mission_v1/events.py:62-66`, `append_event_log_lines` with `create_parents=False`). A **write**; `emit_event` swallows the failure (:56-59). |
| runtime_bridge `_dn_bootstrap` artifact | runtime_bridge.py:446 | owned only. `feature_dir = status_dir if is_dir() else primary_metadata_dir` (:448). The value becomes `ctx.feature_dir`, which reaches `_compute_wp_progress(feature_dir)` (:539), `runtime_emitter_for_mission` (:486), `_guards._should_advance_wp_step` (:771), `_state_to_action`, `gather_artifact_presence` -> `get_wp_lane` (runtime_bridge_io.py:1619) and `committed_authority.wp_ending`. The non-owned arm uses `_resolve_runtime_feature_dir` (runtime_bridge_identity.py:137-163), which is not an allowlist key. |
| decision_mapping `_resolve_wp_board_action` read_dir | :476 | probe only, for `CoordinationWorktreeUnmaterialized` / `CoordinationBranchDeleted` (:477-500); `ActionContextError` -> `_WP_BOARD_DECLINE` (:501-506). |
| decision_mapping `_resolve_wp_board_action` artifact | :506 | `status_dir` -> `_wp_task_surface_error` (:507), `_compute_wp_progress` (:511), `_finalized_task_board_override_step` (:512), implement/review resolvers (:402, :426). |
| runtime_bridge_io `_artifact_presence_seam` read_dir | :1317, :1321 | equality of the seam's STATUS dir with `feature_dir` (seam identity), not a log read. |
| runtime_bridge_query `_build_finalized_override_query_decision` | :182 | `preview_claimable_wp(task_dir, status_dir=...)` (:180). |
| runtime_bridge_query `query_current_state` | :364 | `status_state.read_dir` -> `_wp_task_surface_error` (:376), `_compute_wp_progress` (:393), `_finalized_task_board_override_step` (:537-541). |
| implement_support `_ensure_repo_root_checkout_available` | :274 | `has_event_log` + `get_wp_lane(..) == IN_PROGRESS` (:280). Applies to single_branch only (:228). PR #7499 (for #7493) is open. |

What the legacy resolvers return for STATUS_STATE:
- **Non-owned `mission_context_for` (resolution.py:1474-1492).** Returns `status_surface.status_read_dir` = `_resolve_status_surface_dir` (:1658-1710) = `resolve_status_surface(...).parent` = parent of the door decision's `legacy_path` (surface_resolver.py:1247-1297).
  - COORD_BRANCH_REF: the composed coordination dir (`read_surface.py:521-531`), which does not exist for EMPTY or UNMATERIALIZED.
  - MISSION_BRANCH_REF: the root checkout's primary dir (:456-464).
  - Pre-seed: the primary dir when the worktree is EMPTY, the composed coordination dir when it is UNMATERIALIZED (:504-519).
  - Unreadable ref: re-decided with `for_write=True` (surface_resolver.py:1290-1296).
- **`placement_seam(...).read_dir`** (resolution.py:2496-2564 -> `resolve_artifact_surface` :2979 -> `_classify_artifact_surface` :2832-2916).
  - No landed check before the coordination probe. `translate_surface` picks the consolidated directory only after classification.
  - EMPTY/NONE -> PRIMARY; UNMATERIALIZED raises `CoordinationWorktreeUnmaterialized`; DELETED raises `CoordinationBranchDeleted`.

## 1. Path-typed status consumers downstream, and their call sites in src/

Definitions:
- `has_event_log` lane_reader.py:32; `get_wp_lane` :52; `get_all_wp_lanes` :80; `get_all_wp_snapshots` :103.
- `read_events` store.py:742; `materialize_snapshot` reducer.py:397 (reduces through `reduce_shared_state`, :18/:401).
- `_load_wp_states` discovery.py:97 (`_read_events` + `_reduce_events`, best-effort `except Exception -> {}`).
- `preview_claimable_wp` discovery.py:196.
- `_get_wp_lanes` decision.py:236 (swallows only `CanonicalStatusNotFoundError`); `_compute_wp_progress` :251; `_find_first_wp_by_lane` :318.
- `_count_wp_endings` decision_mapping.py:142; `_wp_task_surface_error` :352; `_has_claimable_planned_wp` :74; `_finalized_task_board_override_step` :87.
- `committed_authority._require_event_log` / `has_event_log` committed_authority.py:114, :246.

Call sites in the runtime chain (every one takes a Path):

| Consumer | Callers (file:line) |
|---|---|
| `get_all_wp_lanes` | decision.py:246; decision_mapping.py:366 |
| `get_all_wp_snapshots` | decision_mapping.py:154 |
| `materialize_snapshot` | decision.py:309 |
| `_get_wp_lanes` | decision.py:266, :337 |
| `_compute_wp_progress` | runtime_bridge.py:539; decision_mapping.py:511; runtime_bridge_query.py:393 |
| `_find_first_wp_by_lane` | decision.py:502, 504, 511, 533; decision_mapping.py:117, 119, 121, 123, 426 |
| `preview_claimable_wp` | decision.py:500; decision_mapping.py:84, 402; runtime_bridge_query.py:180; **workflow.py:1261** (`_preview_claimable_wp_for_mission`, status_dir from `_resolve_workflow_read_dir(STATUS_STATE)` :1255) |
| `_load_wp_states` | discovery.py:254 |
| `_wp_task_surface_error` | decision_mapping.py:507; runtime_bridge_query.py:376; **runtime_bridge_guards.py:102** (`_should_advance_wp_step`, fed `ctx.feature_dir`) |
| `_count_wp_endings` | decision_mapping.py:126 |
| `get_wp_lane` | runtime_bridge_io.py:1619 (`gather_artifact_presence`, fed `ctx.feature_dir`) |
| `has_event_log` | committed_authority.py:114 (`wp_ending`, fed `ctx.feature_dir` via guards), :246 (`_committed_surface`, landed PRIMARY) |

Repo-wide call counts, for scale (most are outside runtime/next):
- `get_all_wp_lanes`: 4 (also workspace/context.py, release/changelog.py).
- `materialize_snapshot`: 23 in 19 modules.
- `read_events` (status): about 50 in 38 modules.
- `get_wp_lane`: 13 in 10 modules.
- `has_event_log`: 8 in 6 modules.
- `preview_claimable_wp`: 5 in 4 modules.

**Paths that come from an owned checkout.** These are the only owned-derived Paths in the chain:
- `_dn_bootstrap` owned arm (runtime_bridge.py:446-448) -> `ctx.feature_dir`, and from there every `ctx.feature_dir` consumer above:
  - `_compute_wp_progress` :539;
  - `_should_advance_wp_step` / `_wp_task_surface_error` (runtime_bridge_guards.py:102);
  - `committed_authority.wp_ending`;
  - `gather_artifact_presence` `get_wp_lane` (runtime_bridge_io.py:1619);
  - `_state_to_action` -> `preview_claimable_wp(feature_dir)` / `_find_first_wp_by_lane` (decision.py:500-533).
- `_resolve_wp_board_action(owned=)` :476/:506.
- `query_current_state(owned=)` via `_query_resolve_mission_context` (query.py:457) :364.
- `_build_finalized_override_query_decision(owned=)` :176-183.
- `_with_guard_failure_paths(owned=)` :449-451.
- `emit_mission_next_invoked(owned=)` :341.

workflow.py:1261 and implement_support.py:274 are **non-owned** (`main_root` / bare `placement_seam`).

Hazard (from reading the code, not run): for an owned UNMATERIALIZED coordination Mission, `_dn_bootstrap` gets the composed coordination dir, which does not exist, so `feature_dir` falls to `primary_metadata_dir` = the owned checkout's own Mission dir (:448). Status consumers on `ctx.feature_dir` then read the owned checkout's copy of the log, which is not a declared source for a coordination Mission.

## 2. Do the reducers differ? (experiment)

`reducer_exp.py` ran over all **816** `kitty-specs/*/status.events.jsonl` logs at HEAD with five readers:
- `get_all_wp_lanes`;
- `get_all_wp_snapshots`;
- `materialize_snapshot` (`reduce_shared_state` = `spec_kitty_events.status.reduce`);
- a door-equivalent `materialize_status` (`status.reduce(transitions, annotations)`);
- `reduce(read_events)`, transitions only.

Results:
- Per-WP **lanes are identical in all 816 logs** across all five readers.
- `compute_weighted_progress(...).percentage` rounded to 1 dp is **identical in all 816** for materialize_snapshot, the door and transitions-only.
- The only difference: in 479 Missions the door snapshot's WP dicts lack `implementer_of_record`. That field is projected only by `materialize_snapshot` (reducer.py:419-420). The progress computation does not read it. Top-level `mission_number`, `mission_type` and `retrospective` also come only from `materialize_snapshot` and are not read by progress.

Edge cases (`edge.py`):
- A corrupt line raises `StoreError` in all three readers.
  - In `_compute_wp_progress` the lanes leg (`_get_wp_lanes`) lets `StoreError` propagate.
  - The weighted leg is under `except Exception` (decision.py:310), which drops `weighted_percentage`.
- An absent log:
  - `get_all_wp_lanes` raises `CanonicalStatusNotFoundError`, which `_get_wp_lanes` turns into `{}`.
  - The door returns `[]`, which also gives `{}`.
  - `materialize_snapshot` on a nonexistent dir returns an empty snapshot, so weighted is `0.0` (present, not dropped).
  - `_count_wp_endings` gives (0,0) both ways, and `_wp_task_surface_error` gives `None` both ways.

**Verdict.** On these 816 logs and edge cases, a port that reads a surface's events and reduces them with `status.reduce` (or `materialize_status`) gives byte-identical `progress` counts and `weighted_percentage` to today on every path source. Two parity notes remain:
1. Error polarity must be kept per leg: the lanes leg raises `StoreError`, the weighted leg swallows it.
2. The ADR-intended change: a ref source now yields real lanes where today it yields an empty board.

This is not a proof over every possible log. The prior note's "path sources must keep `materialize_snapshot(surface.path)`" is unnecessary for the progress numbers. It matters only if a caller needs `implementer_of_record`, `mission_number` or `retrospective`, and no runtime/next consumer does.

## 3. The owned arm: legacy resolver vs the door

**Legacy owned arm** (`_mission_context_for_owned` resolution.py:1267-1340 -> `_owned_read_dir_for_kind` :1343-1369 -> `_resolve_status_surface_dir_owned` :1571-1655). It has no landed check.

| Owned topology / coordination state | Legacy `mission_context_for(owned=)` STATUS_STATE | `resolve_status_read(owned=)` (read_surface.py:180-200) |
|---|---|---|
| single_branch, lanes (or `coordination_branch` missing) | `owned.mission_dir` (P) (:1617-1618) | single_branch/lanes: `WRITE_CHECKOUT` = `owned.mission_dir` (:189-197), no landed check. **Coord topology with no `coordination_branch` in meta: the door goes to `decide_status_read(R)` -> the root checkout's primary dir, not P (divergence).** |
| coord / lanes_with_coord MATERIALIZED | the coordination dir under R (:1636-1637) | `COORD_WORKTREE`, same dir |
| ... EMPTY | raises `ActionContextError(OWNED_COORDINATION_WORKSPACE_UNAVAILABLE)` (:1651-1655), even with `tolerate` | `COORD_BRANCH_REF` (or pre-seed `WRITE_CHECKOUT` on **R's** primary dir) |
| ... UNMATERIALIZED, `tolerate_unmaterialized_coord=True` | the composed coordination dir, which does not exist (:1639-1642) | `COORD_BRANCH_REF` / pre-seed on R |
| ... UNMATERIALIZED, no tolerate (`placement_seam(owned=)`, `_resolve_wp_board_action` :476) | raises `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` -> board **DECLINE** (:501-506) | `COORD_BRANCH_REF` |
| ... NONE (no mid8) | raises `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` | the door's `_coord_mid8` path (behaviour not verified) |
| ... DELETED | `CoordinationBranchDeleted` | `CoordinationBranchDeleted` (unchanged) |
| landed | no landed check; reads per state | `CONSOLIDATED_TARGET` from **R's** primary meta (`decide_status_read(owned.repository_root, ...)`, :198-199) |

Notes:
- ADR 2026-11-06-2 (lines 106-107) says: "Owned checkouts of a coordination Mission follow the same rule instead of raising (FR-003)". Losing the STATUS-read refusal for EMPTY/UNMATERIALIZED is therefore ADR-intended, not a regression. This corrects the prior note's "b regr" label.
- Divergence to decide: for an owned coordination Mission, the door's pre-seed `WRITE_CHECKOUT` and its landed check anchor on R (`owned.repository_root`) rather than P. The ADR's `WRITE_CHECKOUT` definition (line 101) says "the validated owned checkout when `owned` is given". `test_stale_merged_copy_in_r_does_not_short_circuit_*` (test_owned_next_runtime.py:849, :862) pins "R's stale merged copy never short-circuits", but only for the single_branch fixture.
- Owned `query_current_state` on coord EMPTY today (from reading the code, not run): `_query_resolve_mission_context` gets `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, which is not in `_READ_PATH_ERROR_CODES` (query.py:57-63), so it raises **`MissionNotFoundError`** (:475). That is a wrong classification the door would remove.

Owned refusal codes to keep (they come from places other than the status read):
- **`OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` from the registry and decision-log wrap.** `_wrap_with_decision_git_log` raises `CoordinationWorkspaceUnavailable` / `ActionContextError` -> `_owned_coordination_unavailable_decision` (runtime_bridge.py:389-406, :509-523); the predicate is `_is_owned_coordination_unavailable` (decision_log.py:340-345).
  - Pinned by: test_owned_next_runtime.py:301, :333, :362 (zero-byte commondir, subprocess seam, each worktree subcommand); the controls :292, :317, :352; test_owned_lifecycle_acceptance_next.py:276-301 (O8 CLI envelope, `git worktree list` injected).
- **Hazard.** The door raises `WorktreeRegistryUnavailable` (`error_code = WORKTREE_REGISTRY_UNAVAILABLE`, surface_resolver.py:138-146) and `StatusSurfaceRefUnreadable` (status_service.py:218). `_is_owned_coordination_unavailable` does not map either one. If `_dn_bootstrap` calls the door *before* the decision-log wrap, an injected `git worktree list` failure could escape as a traceback, or hit a different code, instead of the O8 typed blocked decision. Order the door read after the wrap, or map these codes.
- `OWNED_TOPOLOGY_UNSUPPORTED` (resolution.py:1312-1319) and the handle-mismatch refusal (`_refuse_owned_handle_mismatch` :155) come from the context build, which stays for PRIMARY kinds.
- `test_wp04_unmaterialized_surface_refusal_is_also_the_typed_blocked_decision` (test_owned_next_runtime.py:376-397) monkeypatches `mission_runtime.mission_context_for` to raise for any owned call. It is a mechanism pin: it stays green only while bootstrap still calls `mission_context_for(owned=)`.
- Lower-level owned pins: tests/mission_runtime/test_placement_seam_owned.py:374-483, :662-726 and test_coord_read_seam_callers.py:299-310. They pin `mission_context_for` / `placement_seam` themselves and are out of scope unless the Mission changes the resolver.

## 4. Test inventory

B = behaviour pin (end-to-end outcome; should survive a correct port). M = mechanism pin (spy, monkeypatch, or a Path-signature call that a door move makes stale or forces to migrate). X = **behaviour pin that contradicts the ADR's COORD_BRANCH_REF rule** (needs an explicit decision).

| Test | Kind | What it pins |
|---|---|---|
| tests/runtime/test_next_board_authority.py:601 `test_unmaterialized_coord_surfaces_typed_blocked_reason` | **X** | UNMATERIALIZED -> board blocked reason contains "unmaterializ" and `doctor coordination --fix`, and must NOT contain "no actionable". Through the door the board reads the ref. That ref has a log but no WP lanes, so the board becomes `blocked:no_actionable_wp`, which this test forbids. |
| tests/specify_cli/cli/commands/test_coordination_remedy_5113.py:170-176, :264 (case `runtime_bridge`) | **X** | same "unmaterializ" reason from `_resolve_wp_board_action`, then a doctor `--fix` round trip |
| test_next_board_authority.py:655 deleted-branch flatten reason | B | unchanged (the door raises `CoordinationBranchDeleted` too) |
| test_next_board_authority.py:315, :346, :374, :392-:558, :698, :735 | B | coord / lanes_with_coord dispatch, the blocked floors, snapshot byte-identity |
| tests/runtime/test_runtime_bridge_read_path_branches.py:131 (`len(probes) == 1` on a fake `placement_seam.read_dir`), :169 (fake seam + `contexts == [_MISSION]`) | M | the probe call shape of `_resolve_wp_board_action` |
| tests/next/test_runtime_bridge_unit.py:1068 (patches `decision_mapping.get_all_wp_snapshots`), :1806/:1825 (patch `mission_context_for` for query read-path passthrough) | M | the module-attribute seam / the context call |
| tests/next/test_query_mode_unit.py:433-782 (9x `patch(...runtime_bridge_query._compute_wp_progress)`), :859 | M | name-level patches; break if progress moves to another symbol |
| tests/next/test_runtime_bridge_blocked_paths.py:209-372 (4x `patch.object(rb, "_compute_wp_progress")`); tests/next/test_next_command_integration.py:553 | M | same, on `runtime_bridge._compute_wp_progress` |
| tests/specify_cli/next/test_next_invocation_lifecycle_seam.py:439, :607 (monkeypatch `next_invocation_lifecycle.mission_context_for`) | M | how `emit_mission_next_invoked` resolves its directory; the degrade-to-None branch |
| tests/integration/test_owned_next_runtime.py:376 | M | see §3 |
| test_owned_next_runtime.py:123 (lanes_with_coord query non-error), :162 (P's WP set, `total_wps == 2`), :301-:374 (O8), :418, :438, :457, :580, :653, :782 (guard-failure paths name P), :849/:862/:874/:887 | B | owned outcomes |
| tests/integration/test_owned_lifecycle_acceptance_next.py:276 | B | O8 envelope through the CLI |
| tests/next/test_finalized_task_routing.py (6 `_compute_wp_progress`, 10 `_finalized_task_board_override_step`, 6 `_resolve_wp_board_action`) | B + M (Path signatures) | board routing; calls the helpers with Path args |
| tests/next/test_decision_unit.py (3 `_compute_wp_progress`, 5 `_find_first_wp_by_lane`); tests/runtime/test_run_state_hardening.py (2); tests/specify_cli/status/test_progress_integration.py (3, weighted parity across surfaces) | B + M (Path signatures) | progress numbers |
| tests/next/test_next_claimable_payload.py (14 `preview_claimable_wp`), tests/integration/test_next_preview_primary_routing.py (4), tests/integration/test_coord_loop_workflow.py (4 + 2 `_preview_claimable_wp_for_mission`) | B + M (Path signatures) | claimability; `status_dir=` keyword |
| tests/next/test_next_dependency_wedge_5669.py; tests/integration/test_implement_review_retrospect_smoke.py | B + M (Path signatures) | #5669 / smoke |
| tests/runtime/test_bridge_decide_next.py:252-408 (direct `_dn_bootstrap`), :201-239 (monkeypatch `_dn_bootstrap`); tests/next/test_next_concurrency.py | B / M | bootstrap |
| tests/next/test_guard_failure_paths_3883.py:69-240; tests/runtime/test_analyze_step.py:420-437 | B | guard-failure paths (non-owned arm; :149 patches `io_seam.artifact_search_paths`) |
| tests/specify_cli/cli/commands/agent/test_read_seam_migration_agent.py:70; tests/specify_cli/cli/commands/agent/test_workflow.py | B | workflow preview raises `CoordinationBranchDeleted` |
| tests/architectural/test_status_read_single_door.py, `_baselines.yaml:28` | gate | each moved key must be deleted; lower the floor and baseline with it |
| tests/specify_cli/cli/commands/test_next_owned_fact.py:55-57 | M | `_boom` on `placement_seam` / `mission_context_for` in next_cmd (verify it is not on the moved path) |

Not covered by any test found: non-owned EMPTY and non-owned UNMATERIALIZED through `query_current_state`, i.e. the bug cells in §5.

## 5. Bug cells the move would fix (observed)

Repro: `PYTHONPATH=. .venv/bin/python kitty-specs/runtime-status-read-door-01M73HHB/research/repro/repro_cells.py MATERIALIZED EMPTY UNMATERIALIZED`. Setup:
1. `scaffold_coord_software_dev(T.COORD, wps={WP01: planned, WP02: for_review})`.
2. Commit the coordination worktree so the branch holds the log.
3. Then either `rm -rf` the coordination Mission dir (EMPTY) or `git worktree remove --force` (UNMATERIALIZED).

| Cell | Door (`resolve_status_read` + `materialize_status`) | Legacy STATUS dir | `query_current_state` today | `_resolve_wp_board_action` today |
|---|---|---|---|---|
| MATERIALIZED (control) | `coord_worktree`; WP01 planned, WP02 for_review; 30.0 | the coordination dir, exists | `query`, mission_state `implement`, wp_id WP01; progress planned 1 / for_review 1, weighted 30.0 | `implement WP01` |
| **EMPTY**, log on branch | `coord_branch_ref`; same lanes; 30.0 | the composed coordination dir, **absent** | `query`, mission_state **`blocked`**, reason **"no actionable wp"**, wp_id None; progress all 0 (total 2), weighted **0.0** | **`blocked:no_actionable_wp`** "No actionable work package (no actionable wp)..." |
| **UNMATERIALIZED**, log on branch | `coord_branch_ref`; same lanes; 30.0 | the composed coordination dir, absent | same wrong `blocked` / "no actionable wp" / 0.0 (non-owned query uses `tolerate=True`) | blocked, "Coordination surface ... is not readable ... doctor coordination --fix" (the probe raises). The X pins in §4 fix this as expected. |

Other cells:
- **Pre-seed** (`repro_preseed.py`): not reached. Today's create path seeds the coordination branch's log (#5440), so the door answered `coord_branch_ref` with an empty WP map, and query and board agreed (blocked, no actionable). From the code, a true pre-seed with an UNMATERIALIZED worktree reads the composed nonexistent dir today and the root checkout's log through the door (read_surface.py:504-519). A repro needs a Mission whose coordination branch lacks `kitty-specs/<dir>/status.events.jsonl`.
- **MISSION_BRANCH_REF** (sketch, not run): a `topology_source: default` Mission whose topic branch no checkout holds (switch the root checkout away). Legacy STATUS dir = the root checkout's primary dir (read_surface.py:456-464), so `query_current_state` reads whatever stale copy, or no log, R has. The door reads `refs/heads/<mission_branch>`. Entry: `spec-kitty next --agent x --mission <m> --json` (query) after `git switch main` in the root checkout. Mission resolution may fail earlier if R lacks the dir; this is unverified.
- **`emit_mission_next_invoked`** in EMPTY/UNMATERIALIZED (from the code): the target dir is absent, so `append_event_log_lines` raises `FileNotFoundError`. `emit_event` logs a warning and the `MissionNextInvoked` row is dropped. When the worktree is MATERIALIZED, the row is appended untracked into the coordination worktree (#5938). This is the write seam's job, not the door's.
- **Owned coord EMPTY** (from the code): `decide_next` -> blocked `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` (bootstrap :441-444); `query_current_state` -> `MissionNotFoundError` (§3).
- Owned UNMATERIALIZED `decide_next`: per the fixture docstring at test_next_board_authority.py:607-617, bootstrap's decision-log wrap materializes the worktree first, so the cell is not observable through advance.

## 6. Open issues on the same surface

Search: `gh api search/issues`, `is:issue is:open`.
- **#7310** Status read single-door gate and migration of remaining legacy read sites: owner of this drain.
- **#7408** [S5] Finish the one status read door: parent.
- **#4518** [Perf 3] `next` re-reads and re-reduces the whole status log several times per invocation: `_find_first_wp_by_lane` x5, `_get_wp_lanes`, `materialize_snapshot`'s double read. A surface-typed port that reduces once per call would address it; fold candidate or cross-ref.
- **#5938** consolidate refuses next-driven coordination Missions: `mission-events.jsonl` left untracked in the coordination worktree. Same site as `emit_mission_next_invoked`, write side.
- **#5764** mark-status on an unmaterialized coordination Mission writes into an unregistered `-coord` husk, so the board is all genesis. Same class (empty board from a wrong dir); the write side.
- **#5936** `agent status emit` in a teammate's clone refuses `COORDINATION_WORKTREE_UNMATERIALIZED`. That is the write side; the read side of this cell (fresh clone, UNMATERIALIZED) is the `next` empty board / named-blocked board above.
- **#6299** orchestrator-api reports `mission_type ""` on coordination Missions (identity read from the status-only coordination dir). Same "status dir used as Mission dir" smell as `_dn_bootstrap` / `_with_guard_failure_paths` `feature_dir = status_dir if is_dir()`.
- **#5929** `next --result success` rewinds a finalized Mission to discovery. Board/override path; adjacent, not the same cause.
- **#7434** record-analysis `--report-only` in an owned checkout records R's charter digest. An owned R-vs-P anchoring precedent; same family as the §3 R-anchored landed check and pre-seed.
- **#7493** / PR **#7499** implement claim ignores the decisions lock: holds the `_ensure_repo_root_checkout_available` move.
- **#6608** one canonical event writer: owns the `mission-events.jsonl` write.
- No open issue was found for "query/board blocked no actionable wp on an EMPTY coordination worktree with a log on the branch". The §5 EMPTY cell appears unfiled (searched: next board empty, unmaterialized next, no_actionable_wp, COORD_BRANCH_REF, OWNED_COORDINATION_WORKSPACE_UNAVAILABLE).
