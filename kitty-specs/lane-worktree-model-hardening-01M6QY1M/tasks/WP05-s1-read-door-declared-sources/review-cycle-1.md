---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T14:55:30Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review, cycle 1 (claude::reviewer-renata): changes requested

## Blocking

### B1. The FR-061 CLI test does not test the routing (it passes when the routing is removed)

`tests/specify_cli/cli/commands/agent/test_context_resolve_primary_partition.py::test_context_resolve_mission_dir_is_primary_partition_location`
builds a default Mission whose topic branch is held by the repository root checkout. In that case the
PRIMARY-partition location equals today's (target) placement (`mission.root_mission_dir`), so the
`context resolve` and `check-prerequisites` assertions pass with or without the new hunk in
`mission_feature_resolution._primary_anchored_feature_dir`.

Mutation proof: on a copy of HEAD with the three lines
`topic_dir = resolve_primary_partition_dir(...)` / `if topic_dir is not None: return topic_dir`
removed, the file still passes (2 passed). At the red commit 21437f5c47 the file was red only by
`ModuleNotFoundError: specify_cli.status.read_surface`, which is not a behavioural red (C-011).

Fix: add a CLI case in which the topic branch is checked out in ANOTHER checkout (the door test
`test_default_mission_topic_branch_in_another_checkout_reads_that_checkout` already builds this
fixture). Both `agent context resolve --json` (`mission_dir`) and `check-prerequisites --json --paths-only`
must report `<holder>/kitty-specs/<dir>`, and the case must fail with the hunk reverted. Keep the
explicit-topology control.

## Non-blocking (record; no action needed in this WP unless cheap)

- N1. MISSION_BRANCH_REF and the write seam disagree until WP14. A default Mission whose root
  checkout moved to a branch that still carries the Mission dir: `placement_seam(...).write_dir(STATUS_STATE)`
  returns the root checkout's dir, while the door reads `refs/heads/<mission_branch>`. Probe: an
  `emit_status_transition` into the write dir leaves `read_status_events(resolve_status_read(...))`
  at 3 events (the new row is invisible). Before WP05 both sides used the root copy. The read
  choice is consistent with ruling 8 and FR-061; the write arm must follow in WP14 (T088 covers
  `single_branch_write_ref`; make sure the STATUS_STATE write location in this state is covered,
  or refused, with a read-after-write test). ADR update for the new source goes to WP18.
- N2. `_write_checkout_decision` / `resolve_primary_partition_dir` do not check that the topic-branch
  holder is not a registered LANE worktree (invariant 1). Unreachable through spec-kitty itself
  (lane worktrees hold lane branches), but a `classify_worktree_topology` guard is cheap.
- N3. When the holder holds the topic branch but has no Mission dir, the decision quietly falls
  back to the root checkout's copy. Consider a typed refusal or a declared reason.
- N4. Legacy projection: for a POST-FIX EMPTY coordination worktree, `resolve_status_surface_with_anchor`
  now names the composed coordination path (missing), so legacy path readers read an empty history
  until WP06/WP07 migrate them (before: the root's stale copy with a warning). Same for the
  `StatusSurfaceRefUnreadable` catch that re-decides with `for_write=True`. Transitional; WP06/WP07
  must close it.
- N5. `mission_runtime.mission_has_landed` is a verbatim copy of
  `runtime.next.runtime_bridge._primary_mission_is_completed`. Make the runtime bridge delegate (or
  record it for WP14) so there is one landed reader.
- N6. Two enums named `StatusReadSource` (`coordination.status_service` and `status.read_surface`).
  Unify in WP06/WP07.
- N7. The dead-symbol allowlist entry names #7277 and "burns down when WP06 lands", but WP06's prompt
  does not mention removing it. Add it to WP06's DoD.

## Verified OK

Red-first ordering; the ADR source table cell by cell (landed check before any coordination probe,
pre-seed before ABSENT, deleted branch raises); the four rewritten coordination tests follow the
ADR's reversal of FR-017/C-002 and `test_deleted_coordination_branch_raises` keeps the hard fail;
NFR-001 test counts one `cat-file --batch`; `ref_exists` -> `ref_names_object` rename complete;
ruff, format, mypy --strict, C901 clean; no new suppressions.
