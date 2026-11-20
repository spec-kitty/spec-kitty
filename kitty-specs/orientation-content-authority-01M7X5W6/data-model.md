# Data Model

## ExpectedOrientation (value: `SessionPresenceContent`)

| Field | Source | Rule |
|-------|--------|------|
| version | installed `spec-kitty-cli` | ValueError when unavailable |
| project_slug | `project.slug` → git remote repo name → "unknown" | never the directory name |
| health | constant | always "healthy" in committed content |
| available_version | constant | always None in committed content |
| specify_invocation | `orientation_invocation()` | unchanged |

## LiveOrientation (SessionStart hook)

Same `project_slug` and version; `health`/`available_version` from the compat planner and upgrade cache.

## Drift (per orientation file)

- absent block → not drift (missing is reported separately)
- stamped version ≠ installed → drift
- canonical block ≠ expected rendering → drift
- hand-edited block, version current → not drift (preserved)
