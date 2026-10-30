# Research: changelog-wp-lane-reducer-01M66FMR

Discovery findings for issue spec-kitty/spec-kitty#6612, gathered on `main@512567ee` before specification.

## Decisions

- **D-1 (fix shape).** `_wp_lane_from_event_log` will resolve the mission's status surface through the placement seam (`placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)`) and read the WP's lane through the canonical lane reader (`specify_cli.status.get_wp_lane`). This is the same authority pair the retrospective gate, consolidation preflight and `MissionStatus` aggregate use; it makes `get_wp_lane`'s reducer (`diary.reduce_parsed`, ordered by `at` then `event_id`, with from-lane continuity and the approved-departure lift) the single lane authority for the changelog.
- **D-2 (failure policy).** Three deliberate arms, matching the established precedents:
  - *No canonical surface* (legacy mission, missing/malformed `meta.json`, or a coordination mission whose worktree is not materialized — the fresh-clone window): fall back to the legacy path. For missing placement this means the mission dir itself (today's behavior, preserved for pre-3.x features); for `CoordinationWorktreeUnmaterialized` it means the frontmatter fallback — never the stale primary copy, which is the split-brain class (#1735) this fix closes. Precedent: `consolidation/run_state.py::_status_surface_ref` treats unresolvable placement as "no status surface"; `retrospective/gate.py::_resolve_events_path` falls back on `(FileNotFoundError, ValueError)`.
  - *No event log on the resolved surface*: `get_wp_lane` raises `CanonicalStatusNotFoundError` → the existing YAML-frontmatter `status` fallback keeps working (pre-3.x features). `Lane.UNINITIALIZED` (log exists, WP absent from the reduced snapshot) → same fallback, matching today's "no events for this WP" arm.
  - *Corrupt log* (`StoreError` from `read_events`) and *deleted coordination branch* (`CoordinationBranchDeleted`): propagate. Both are existing loud-fail contracts shared by every other reader (#1848 data-loss guard; `store.read_events_raw` raises `StoreError` with the 1-based line number).
- **D-3 (scope).** In scope: `release/changelog.py`, its owning test suite, the `[Unreleased]` changelog entry, and the G-13 row in `docs/architecture/event-ledger-writers-and-readers.md`. The other G-13 item (preflight `_latest_actor_for_transition` append order) is documented as deliberate and stays; the retrospective Lamport folds and the Java read API are out of scope.

## Evidence

- **Reproduced on main (out-of-order log).** A mission whose `status.events.jsonl` is written `[approval (at=2026-05-02), departure to in_review (at=2026-05-01)]` (a continuous chain in reducer order, reversed on disk — the union-merge / clock-skew shape): `_wp_lane_from_event_log` returns `in_review` (last `to_lane` in file order) while `get_wp_lane` returns `approved`. `build_changelog_block` therefore omits a WP the reducer considers accepted.
- **Reproduced on main (coordination topology).** In a git fixture with a coordination branch and a materialized coordination worktree carrying `WP01 → approved`, plus a stale primary copy carrying `WP01 → in_review`: `build_changelog_block` omits the mission. `placement_seam(repo, slug).read_dir(MissionArtifactKind.STATUS_STATE)` resolves the coordination worktree's mission dir and `get_wp_lane` on it returns `approved`.
- **Reproduced on main (corrupt log).** A log line that is not valid JSON is silently skipped by `_wp_lane_from_event_log` (`except json.JSONDecodeError: continue`), while `store.read_events` raises `StoreError("Invalid JSON on line N")`.
- **Post-consolidation missions stay on the primary surface.** Consolidation's on-disk flatten clears `coordination_branch` from `meta.json` (`consolidation/phase_teardown.py`), so the changelog's dominant case — past, consolidated missions — resolves `STATUS_STATE` to the primary mission dir. Verified against every `kitty-specs/*/meta.json` in this checkout: none declares a `coordination_branch`.
- **No supersession.** `git log -S _wp_lane_from_event_log` shows the function only in its introducing commit (4cf851c4f4, mission 079); no later fix, no changelog entry, no referenced ADR change. The issue cites gap G-13 in `docs/architecture/event-ledger-writers-and-readers.md`, whose "Fix direction" column names this exact change: "Changelog through `get_wp_lane` and the placement seam".

## Prior art (read-path precedents studied)

- `retrospective/gate.py::_resolve_events_path` — resolves the events path through `resolve_status_surface`, falls back to `feature_dir` only on `(FileNotFoundError, ValueError)`.
- `consolidation/preflight.py::_current_lanes_or_empty` — `reduce(read_events(resolve_status_surface(...).parent))`, empty-dict degrade on unreadable surface.
- `status/aggregate.py::MissionStatus` — `get_wp_lane(self.read_dir, wp_id)` over the placement-seam-resolved read dir.
- `mission_runtime/resolution.py::PlacementSeam.read_dir` — the kind-aware placement authority; `STATUS_STATE` is a COORD-partition kind (`status.events.jsonl` → `MissionArtifactKind.STATUS_STATE` in the file→kind classifier).

## Open questions

- None blocking. The failure-policy arms (D-2) were the only design choice with more than one defensible answer; they follow the strongest in-repo precedents and are pinned by tests.
