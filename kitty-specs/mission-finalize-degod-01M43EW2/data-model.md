# Data Model: Decompose mission_finalize god-module

No persisted data changes. `meta.json`, `lanes.json`, WP frontmatter, the status event log and every JSON payload are untouched.

## Code-structure entities

| Entity | Owner module | Invariant |
|---|---|---|
| Finalize module family | `mission_finalize` + 7 phase modules | Top-level names are unique across the family. Each is defined once. |
| Re-export surface | `mission_finalize` | `mission_finalize.<n> is <phase_module>.<n>` for every top-level name `n` of every phase module. |
| Patch seam | `mission_finalize` attribute | A phase-module call to a patched name resolves through `mission_finalize` at call time. |
| Routing import | phase-module function body | Never at module scope (cycle safety). |
| Finalize logger | `mission_finalize_seams.logger` | Name stays `specify_cli.cli.commands.agent.mission_finalize`. |
