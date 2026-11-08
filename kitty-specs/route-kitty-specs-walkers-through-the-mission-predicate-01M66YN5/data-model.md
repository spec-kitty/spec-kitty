# Data Model: Route the remaining `kitty-specs/` walkers through the Mission predicate

This Mission adds no persisted data. Its "model" is the classification every one of the six
walkers now performs and the shape each surface emits for a Mission versus a residue child.

## Entity: `kitty-specs/` child

A directory under `kitty-specs/`. Two classes, decided by
`context.mission_resolver.is_selectable_mission_dir(path, repo_root=..., tracked=...)`:

| Class | Rule (in order) | Fields the walkers read |
| --- | --- | --- |
| Mission | `meta.json` on disk with a non-empty `mission_id`; or an id-less `meta.json` whose `meta.json`/`spec.md` git tracks; or any `meta.json` on a non-git root | `meta.json` (`topology`, `flattened`, `friendly_name`, `created_at`), `tasks/WP*.md` frontmatter, `status.events.jsonl`, `lanes.json` |
| Read-side residue | everything else: no `meta.json`; an untracked id-less `meta.json` in a git repository; an unreadable `meta.json` with no tracked marker | none — no walker reads it |

Invariants:

- A child the predicate rejects is never reported, scanned, materialized or published as a
  Mission by any of the six walkers.
- A child the predicate accepts keeps every behaviour it had before this Mission.
- The audit engine's `is_mission_dir` population is deliberately **not** consulted here
  (C-001): audit-engine residue remains a separate sense with its own reporter.

## Per-walker output contract

| Walker | Output | Residue child before | Residue child after |
| --- | --- | --- | --- |
| `_collect_topology_rows` | `list[dict]` rows (`slug`, `topology`, `flattened`, `error`, `finding`, `remedy`) | row with `topology: null`, `error: "meta.json not found"` | no row |
| `_resolve_mission_dirs` | `list[Path]` | path included | path excluded |
| `_mission_dirs_for` | `list[Path]` | path included | path excluded |
| `_mission_dirs_to_process` | `list[(slug, status_dir)]` plus `errors[]` | target appended (and a coordination-worktree probe attempted) | not appended, no probe, no `errors[]` entry |
| `_collect_inflight_missions` | `list[AffectedMission]` | scanned | not scanned |
| `build_changelog_block` | `(markdown, slugs)` | slug in `slugs` (when its `tasks/` look accepted) | not in `slugs` |

The `doctor topology --json` envelope keeps its shape: `{"missions": [...]}` is a list of
Mission rows. No field is renamed or removed; a residue row simply does not appear.

## Predicate memo lifecycle (one per walk)

```
TrackedMissionPaths(repo_root)         # created once by the walker
  └─ .get()                            # first child that needs git -> one `git ls-files`
       ├─ frozenset[...]               # usable git: markers compared against it
       └─ None                         # non-git root / broken index: file-presence mode
```

- Children carrying a `mission_id` never trigger the probe, so a repository of modern
  Missions costs zero git calls (NFR-001).
- A broken git index degrades to file presence with one warning per checkout root and run
  (`probe_tracked_mission_paths`); a timeout propagates.

## Accepted behavioural loss (charter-activate warning)

The in-flight warning no longer scans a read-side residue folder, so an in-flight lane recorded there is
not reported. Accepted, and stated in the spec's edge cases: a folder selection never lists cannot be
resolved or advanced by the runtime, so an in-flight lane in it is stale state; `doctor identity` reports
the folder with a reason and a remedy, which is the surface an operator can act on.

## State transitions

None. Every surface is read-only; no walker writes to `kitty-specs/` and therefore none
takes the write-seam predicate `is_kitty_specs_residue` (C-004).
