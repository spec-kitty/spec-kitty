# Contract: WP acceptance classification in `spec-kitty agent release prep`

## Command

```
spec-kitty agent release prep --channel <alpha|beta|stable> [--repo <root>] [--json]
```

Implemented by `build_changelog_block` / `build_release_prep_payload`
(`src/specify_cli/release/`), which decide which work packages a release
changelog draft lists as accepted (#6612).

## Inputs

- `kitty-specs/<mission>/` directories on the main checkout's root
  (the same anchor the placement seam uses; `--repo` may be a linked
  worktree, the scan still reads the main root).
- Each mission's resolved status surface: under a coordination topology
  the coordination branch's mission dir, resolved through the placement
  seam (`placement_seam(...).read_dir(STATUS_STATE)`), never the primary
  checkout's possibly-stale copy.

## Classification rule

- A work package is accepted exactly when the canonical reduced lane —
  `status.lane_reader.get_all_wp_lanes` (wall clock `at`, then
  `event_id`, with the approved-departure lift), read once per mission —
  puts it in `approved` or `done`. File order of `status.events.jsonl`
  never decides.
- When no authoritative log is readable (unmaterialized coordination
  worktree; no event log on a pre-3.x feature; unreadable log file), the
  legacy YAML frontmatter `status` field decides (`done`, `accepted`,
  `merged` count as accepted).

## Failure modes (loud, never silent mis-classification)

- Corrupt `status.events.jsonl` line: `StoreError` naming the mission and
  the line; the command exits 1 (clean error in `--json` mode too).
- Declared coordination branch deleted from git: `CoordinationBranchDeleted`
  with its `spec-kitty doctor coordination --fix` remediation; exit 1.
- The stale primary copy is never read as a fallback.

## Guarantees

- Same lane authority as every other CLI lane read: one reducer, one
  resolved status surface.
- No network calls (FR-014); git is probed once per mission for surface
  resolution, plus one tag lookup.
