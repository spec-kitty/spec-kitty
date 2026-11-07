---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T21:13:32Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP14
---

# WP14 review cycle 1 — REJECT (reviewer-renata)

Settlement, compensation, size rule, allowlist removal, gates: good (18+8+4 pass; layer rules 80, placement guards 19+18, orchestrator_api contract 15, dead symbols 37 serial — all green).
Blocking: two REQUIRED acceptance items are shipped as strict xfail. They are in WP14 scope (WP prompt + design-decisions WP05 obligation N1, newest WP14 entry); they are not deferrable follow-ups.

## B1. context resolve / check-prerequisites after settlement -> MISSION_NOT_FOUND
Test: tests/integration/test_default_mission_primary_placement.py::test_context_resolve_and_prerequisites_report_primary_location_after_settlement
Root cause: `specify_cli/context/mission_resolver.py` enumerates only `repo_root / KITTY_SPECS_DIR` (the single enumeration primitive near line 240-256). After settlement the root is on create_return_branch with no Mission dir.
Fix direction: in that one enumeration primitive (do not add a second walker), also yield Mission dirs held by the coordination worktree of a `topology_source: default`, unlanded Mission — reuse `status.read_surface.topic_holder_mission_dir` / the coord-worktree lookup already used by `_read_path_resolver._default_mission_topic_dir`, so there is ONE topic-holder authority. Then context resolve and check-prerequisites must report the topic-holder path as PRIMARY. Remove the xfail.

## B2. N1 write half: status event lands in the root's stale copy
Test: ...::test_status_write_after_root_moved_is_readable_through_the_door
Root cause: `coordination/status_transition.py::_canonical_primary_feature_dir` (line ~754, used at ~968) anchors on `placement_seam(...).read_dir(PRIMARY_METADATA)`, which still composes the root path; WP14 only patched read side (`read_primary_meta`, `resolve_planning_read_dir`).
Fix direction: make the seam's PRIMARY_METADATA read_dir (mission_runtime placement / read_dir_for) honour the same default-Mission topic-holder redirect, so the write anchor and the read door share one resolution — rather than patching status_transition separately. Add the read-after-write assertion (already written) green. Coordinate with WP07's door (lane-d): no second authority.

## Non-blocking
- `_read_path_resolver._default_mission_topic_dir` parses meta.json with raw `json.loads` and swallows corrupt meta (returns None); route through `load_meta_fail_closed` like the rest of the module (FR-007/#3162).
- resolution.py `_default_mission_facts` and `_default_mission_topic_dir` each re-derive the "default + unlanded + topic" predicate; consider one helper.
