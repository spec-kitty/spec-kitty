# #7310 / #7408 S5 — code grounding (runtime/next + lanes readers)

Base: origin/main @ 9518fb71. Read-only; nothing edited.

## Gate
`tests/architectural/test_status_read_single_door.py`: `LEGACY_READ_ALLOWLIST` (45 keys, shrink-only:
a stale key fails), `_LIVE_HIT_FLOOR = 40` (live scan sees 46 hits). Size baseline
`tests/architectural/_baselines.yaml` `test_status_read_single_door.legacy_read_allowlist: 45`,
enforced by `test_ratchet_baselines.py` (growth fails, shrink warns).

## #7490 overlap
`src/specify_cli/coordination/status_transition.py` (4 `_WRITE_SIDE` entries). Not in the
runtime/next or lanes groups, so it is out of this PR anyway.

## Why "byte-for-byte onto the door" mostly does not exist
Two legacy resolvers sit behind these sites:
- `mission_context_for(...).artifact(STATUS_STATE).read_dir` -> `resolve_status_surface` ->
  `_Decision.legacy_path.parent`. It shares the door's decision, but projects ref cells
  (COORD_BRANCH_REF from EMPTY/UNMATERIALIZED, MISSION_BRANCH_REF, pre-seed UNMATERIALIZED,
  unreadable ref) to a Path. That Path usually has no log, so the reader sees an empty board.
  The owned arm (`_resolve_status_surface_dir_owned`) anchors on P and refuses EMPTY/NONE.
- `placement_seam(...).read_dir(STATUS_STATE)` -> `_classify_artifact_surface`. It has no
  landed check, sends EMPTY to PRIMARY, and RAISES on UNMATERIALIZED/DELETED.

Through the door, a ref cell is `path=None` (the reader gets real lanes from the ref), and
an owned coordination Mission resolves in R (`read_surface.py:189-192`), not P. Every
consumer downstream is Path-typed (get_all_wp_lanes, _compute_wp_progress ->
materialize_snapshot, preview_claimable_wp, check_claim_ancestry, get_wp_lane).

## Per-site verdict
(a) byte-for-byte  (b) behaviour change  (c) not a status read / blocked

| Site | V | Note |
|---|---|---|
| lanes `_ensure_repo_root_checkout_available` | a | `reduce(read_status_events(resolve_status_read(...)))` + Lane coercion; same lines as #7493 -> after #7493 |
| lanes `_writers_in_write_checkout` | a* | identical except default Mission + fail-closed branch check + unheld topic (root copy -> topic ref; a fix) |
| lanes `_lane_mates_writing` | b fix | UNMATERIALIZED / landed-deleted today crash implement/review advisory |
| lanes `scan_recovery_state` | b | UNMATERIALIZED fail-loud is pinned (`test_lanes_recovery_scan_recovery_state_fails_loud_sanely`) |
| lanes `_canonical_wp_lane_value` | c/b | DESTROYED_LANE verdicts change; the door cannot express "unreadable on UNMATERIALIZED" |
| lanes `reenter_lane_self_heal` | c | Path flows into the shared `check_claim_ancestry` (workflow.py:1809, wp_lifecycle.py:214); moving it alone splits self-heal from the gate |
| next `_with_guard_failure_paths` | c | directory identity for planning-artifact presence, not a log read |
| next `emit_mission_next_invoked` | c | a WRITE of mission-events.jsonl -> write seam, not the door |
| next `_dn_bootstrap` | b regr | owned coord EMPTY loses `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`; reads R |
| next `_resolve_wp_board_action` artifact | b fix | ref cells: empty board -> real board (#4959 class); needs surface-typed consumers |
| next `_resolve_wp_board_action` read_dir | c | materialization probe; needs a door-level coordination-state probe |
| next `_artifact_presence_seam` | c | seam identity; keep it on the seam |
| next `_build_finalized_override_query_decision` | b | as query_current_state |
| next `query_current_state` | b | fix for non-owned; regression for owned coord (R-anchored, FileNotFoundError) |

Port hazard: `_compute_wp_progress` gets `weighted_percentage` from `materialize_snapshot`
(`reduce_shared_state`). The door's `materialize_status` uses a different reduction, so path
sources must keep `materialize_snapshot(surface.path)`.

## Fold candidates
None that share this surface and keep the PR small. Related: #3462 (aggregate read degrade),
#3071 (write-seam routing), #6608 (one writer), #7449, #7439.
Churn: the clone is shallow (50 commits), so 90-day counts cannot be measured here.
