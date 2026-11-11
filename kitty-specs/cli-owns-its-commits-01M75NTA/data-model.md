# Data Model: Mission-scoped dirt

No persisted data changes. One in-memory value type is added.

## `DirtScope` (enum)

| Value | Meaning | Example (this Mission `m-01AB`) |
|---|---|---|
| `OWN` | inside this Mission's directory, or one of its aliases | `kitty-specs/m-01AB/spec.md`, `kitty-specs/m-01AB/` |
| `OTHER_MISSION` | inside another Mission's directory, including a collapsed directory entry | `kitty-specs/other-01CD/`, `kitty-specs/other-01CD/tasks/WP01.md` |
| `OUTSIDE` | not inside any Mission directory | `src/app.py`, `.kittify/evidence/…`, `kitty-specs/README.md` |

Invariants:
- Classification is purely structural: it reads only the path string and the Mission's own
  directory names, never the file system and never git.
- A path that is exactly `kitty-specs/` or `kitty-specs` (a collapsed parent of every Mission)
  is `OUTSIDE`, so it is never silently dropped: it may hide this Mission's own files.

## `MissionDirt` (value)

`own`, `other_mission`, `outside`: tuples of the paths in each scope, in input order. A gate
chooses which scopes refuse and which are reported as warnings (research D2).
