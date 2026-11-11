# Mission intake debrief: runtime/next status readers onto the one read door (#7310)

Reader: the operator and the specify/plan agents for the follow-up Mission.
Branch: `refactor/7310-status-read-door-s5` (the Mission lands on the same topic branch, after
Op `01M726T6`). Base: origin/main @ 9518fb71.
Sources:
- research-squad notes beside this file: `code-grounding.md`, `architecture-options.md`,
  `op-time-grounding.md`;
- ADR `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`.

## 1. Where things stand

- Done in the Op:
  - three lanes readers moved;
  - gate allowlist 45 -> 42, `_baselines.yaml` 42, `_LIVE_HIT_FLOOR` 43.
- Held: `lanes/implement_support._ensure_repo_root_checkout_available`. The move is
  no-behaviour-change and pinned. It lands after PR #7499 (#7493), which edits the same lines.
- In Mission scope: 8 runtime/next allowlist entries (9 hits) plus the held lanes site.

## 2. What each runtime site really is

| Site | Kind | Destination |
|---|---|---|
| `runtime_bridge_query.query_current_state` | status read (board + progress) | door + read-once board value |
| `runtime_bridge_query._build_finalized_override_query_decision` | status read (`preview_claimable_wp`) | same |
| `runtime_bridge_decision_mapping._resolve_wp_board_action` artifact | status read (board) | same |
| `runtime_bridge_decision_mapping._resolve_wp_board_action` read_dir | probe: exists only to catch `CoordinationWorktreeUnmaterialized` | decide from `surface.source` or a small door-level state classifier (DM-2) |
| `runtime_bridge._dn_bootstrap` | mixed: `feature_dir` identity + progress read | door read after the owned decision-log wrap; identity part via seam threading |
| `decision._with_guard_failure_paths` | directory identity (planning-artifact presence), not a log read | pass the seam explicitly to `guard_failure_artifact_paths` (DM-3) |
| `runtime_bridge_io._artifact_presence_seam` | seam identity (maps a status dir back to a seam) | same seam threading; entry drops |
| `next_invocation_lifecycle.emit_mission_next_invoked` | a WRITE of `mission-events.jsonl` | write seam (`write_dir`), plus a read-after-write test (`runtime_bridge_composition.py:352-394` reads it) |

## 3. Bugs the Mission fixes (reproduced by the grounding lens; non-owned, coord topology, log committed on the coordination branch)

| Coordination worktree | Today (`query_current_state` / board) | Through the door |
|---|---|---|
| present (control) | implement WP01, weighted 30.0 | same |
| EMPTY (no Mission dir) | blocked "no actionable wp", all counts 0, weighted 0.0 | real lanes, 30.0 |
| UNMATERIALIZED | query: same wrong empty board. Board: "unmaterialized" block | real lanes (board: see DM-2) |

- The EMPTY cell has no open issue: file one, or fold it into this Mission.
- `emit_mission_next_invoked` silently drops its row in the EMPTY and UNMATERIALIZED cells
  (from reading the code).
- The MISSION_BRANCH_REF cell is a repro sketch only and was not run.
- The pre-seed cell is unreachable since #5440, because creation seeds the coordination log.

## 4. Corrections to the Op-time grounding

- **Owned arm: not a P-vs-R regression.**
  - The owned coordination log is already read under the repository root R
    (`resolution.py:1571-1660`).
  - ADR §2 (lines 106-107): owned coordination checkouts read `COORD_BRANCH_REF` "instead of
    raising (FR-003)". So dropping the status-read `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` for
    EMPTY/UNMATERIALIZED is the ADR's intent; the operator decides it as DM-1.
  - The real door gap: `resolve_status_read(owned=...)` for a coordination topology locates the
    Mission and reads `meta.json` in R's `kitty-specs/` (`read_surface.py:183-192`), not in
    `owned.mission_dir`. A Mission that exists only in the owned checkout P raises. The fix goes
    in the door.
  - Its landed check and pre-seed fallback also anchor on R.
- **Reducer parity holds on real data.** All five readers agree on per-WP lanes and
  `weighted_percentage` (1 dp) across all 816 `kitty-specs/*/status.events.jsonl`:
  - `get_all_wp_lanes`, `get_all_wp_snapshots`, `materialize_snapshot`, `materialize_status`,
    and `reduce` over transitions.
  - The only difference: `implementer_of_record`, which runtime/next does not read.
  - This is not a proof over every possible log; pin it with a parity test.
  - A corrupt line raises `StoreError` everywhere. Keep today's split: the lanes step propagates
    it, the weighted step swallows it (`decision.py:310`).
- **Consistency gap today.** `agent tasks status` already reads the door with `owned`
  (`tasks_status_cmd.py:388-405`), so for an owned coordination Mission the board and `next`
  can disagree.

## 5. Recommended design (architect lens)

- **Read once, then pass a value.** Read through the door once per decision, reduce once into a
  frozen `BoardStatus` (lanes, per-WP states, log present, weighted %).
  - The pure consumers take that value: `_compute_wp_progress`, `_find_first_wp_by_lane`,
    `_count_wp_endings`, `_has_claimable_planned_wp`, `_wp_task_surface_error`,
    `_finalized_task_board_override_step`, `preview_claimable_wp`.
  - Today one decision reads and reduces the same log up to about 8 times; #4518 is the fold
    candidate.
  - Follows the #7335 precedent (`_st_reduce_surface`).
  - `status_dir=` stays as a thin adapter for the outside callers: `workflow.py:1261`
    (`preview_claimable_wp`) and `runtime_bridge_guards.py:102` (`_wp_task_surface_error`).
- **Fix the door's owned entry** for coordination topologies: take the Mission dir and
  `meta.json` from `owned.mission_dir`, and probe coordination state under R.
- **Rejected: dual-typed `Path | StatusReadSurface` params.** Every consumer keeps its own read,
  and the Path arms hide from the gate.
- **Hazard.** The door raises `WorktreeRegistryUnavailable` / `StatusSurfaceRefUnreadable`, and
  `_is_owned_coordination_unavailable` does not map them. Read after the owned decision-log
  wrap (`runtime_bridge.py:389-406`, `:509-523`), or map them.

## 6a. Operator answers (2026-11-10, interview)

- **DM-1, chosen:** read the committed coordination ref for query and progress, and refuse only an
  advancing dispatch with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`. The ADR gets an amendment
  naming this split.
- **DM-2, chosen:** keep the "materialize it" block (decided from `surface.source`, not a seam
  raise). **New scope:** add an `--auto-remediate` option to `next` that materializes the
  coordination worktree for the user right away and then continues. It is opt-in; without the
  flag the behaviour is unchanged.
- **DM-3, chosen:** pass the placement seam explicitly to `gather_artifact_presence` /
  `guard_failure_artifact_paths`. Both identity entries drop.
- **DM-4, chosen:** file the EMPTY-cell bug as an issue and fix it in this Mission as an FR with
  a red-first test. Filed as **#7507** (P2, Bug, sub-issue of #7408); the PR closes it.

## 6. Decision Moments for the operator (as asked)

- **DM-1: owned coordination Mission whose coordination worktree is EMPTY or UNMATERIALIZED.**
  - (A) Read the committed ref, per the ADR.
  - (B) Keep the refusal; the door gains a refusal policy and the ADR is amended.
  - (C) Read the ref for query and progress; refuse only on an advancing dispatch.
    Architect recommends C.
- **DM-2: non-owned, UNMATERIALIZED, advancing board.**
  - Keep the "materialize it" block (decided from `surface.source`; behaviour-preserving;
    recommended).
  - Or dispatch from the ref board. That flips two pins: `tests/runtime/test_next_board_authority.py:601`
    and `tests/specify_cli/cli/commands/test_coordination_remedy_5113.py` (the `runtime_bridge`
    case).
- **DM-3: the two identity sites.** Thread the seam explicitly so both entries drop (recommended).
  Or relabel the reasons and defer.
- **DM-4: the EMPTY-cell bug.** File it as its own issue, or carry it as an FR of this Mission.

## 7. Proposed WP slicing

| WP | Content | Allowlist after |
|---|---|---|
| WP01 (tidy-first enabler) | `BoardStatus` value + builder, parity test vs `materialize_snapshot`, no call-site change | 42 |
| WP02 | Door owned-entry fix + DM-1 (ADR amendment if B or C), red-first | 42 |
| WP03 | `_resolve_wp_board_action` (both forms), `query_current_state`, `_build_finalized_override_query_decision` onto the door + `BoardStatus`; EMPTY-cell red tests | 38 |
| WP04 | Seam threading: `_dn_bootstrap`, `_with_guard_failure_paths`, `_artifact_presence_seam` | 35 |
| WP05 | `emit_mission_next_invoked` onto the write seam; `_ensure_repo_root_checkout_available` once #7499 merges | 33 |

- Every WP lowers `_baselines.yaml` and `_LIVE_HIT_FLOOR` in the same commit.
- WP03 and WP04 both touch `runtime_bridge*` and `decision.py`: run them in sequence.
- No overlap with #7490 (`status_transition.py`).
- Tests that go stale because they patch mechanism:
  - `test_runtime_bridge_read_path_branches.py:131,169`
  - `test_runtime_bridge_unit.py:1068,1806,1825`
  - `test_query_mode_unit.py` (9 patches)
  - `test_runtime_bridge_blocked_paths.py` (4)
  - `test_next_invocation_lifecycle_seam.py:439,607`
  - `test_owned_next_runtime.py:376`
- Owned refusal pins to keep or adjudicate under DM-1: `test_owned_next_runtime.py:301-374`,
  `test_owned_lifecycle_acceptance_next.py:276`.

## 8. Candidate FRs / success criteria

- FR: one door read and one reduction per `next` decision / query.
- FR: a non-owned coordination Mission with an EMPTY or UNMATERIALIZED worktree shows the real
  lanes from the committed ref (query and progress; board per DM-2).
- FR: an owned Mission that exists only in P resolves through the door; refusal codes stay
  where DM-1 keeps them.
- FR: weighted-progress parity with `materialize_snapshot` (pinned).
- FR: `MissionNextInvoked` is written through the write seam and is visible to the next read.
- FR: a deleted coordination branch still gives the flatten guidance.
- SC: gate allowlist 42 -> 33 (35 if DM-3 defers), with the floor and baseline lowered per WP.

## 9. Left for other slices (after this Mission)

These are the remaining allowlist entries at the gate's ~33 target:
- Path-typed consumers, including `implement_support.reenter_lane_self_heal` and its shared
  `check_claim_ancestry`.
- `lanes/worktree_allocator._canonical_wp_lane_value`: the #4889 fail-loud guard. It needs a
  decision; DESTROYED_LANE verdicts change.
- Five existence probes; they could reuse the door-level state classifier from DM-2.
- Four write-side entries (#7490 / #6608).
- Three partition entries, two planning-pin entries (#5702), two WorkPackage entries, two
  delegators.
- One each: seam arm, aggregate (#3462), drift, owned identity, handed ref, writes-through-read.

## 10. Related open issues

#4518 (fold candidate), #5938, #5764, #5936, #6299, #5929, #7434, #6608, #7493 / PR #7499.
The relevance of each is in `code-grounding.md`.
