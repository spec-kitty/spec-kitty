---
title: Charter as Central Path Resolver — Gap Analysis
description: Gap analysis of using the charter as the central path resolver, surfaced by WP09 of the mission-template-repository-refactor (058), with recommendations.
doc_status: deprecated
updated: '2026-04-07'
---
# Charter as Central Path Resolver — Gap Analysis

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Date**: 2026-03-30
**Origin**: WP09 (058-mission-template-repository-refactor)
**Status**: Vision captured, implementation pending

## Context

WP09 introduced `ProjectMissionPaths` and `MissionType` in
`src/specify_cli/charter/mission_paths.py` to centralize
`.kittify/missions/` path construction.  This stops filesystem layout
details from leaking into `manifest.py`, `mission.py`, and
`cli/commands/agent/config.py`.

During implementation, the HiC identified a broader principle:

> The charter serves as the "local doctrine override and project
> configuration" entry point.  Most CLI and runtime calls should route
> through it.

`ProjectMissionPaths` is the first step.  The gaps below capture
what remains.

## Gaps

### 1. Charter path not routed through `ProjectMissionPaths`

Charter files (`.kittify/charter/charter.md`,
`references.yaml`, `context-state.json`) are resolved ad-hoc in:

- `src/specify_cli/dashboard/charter_path.py`
- `src/specify_cli/charter/sync.py`
- `src/specify_cli/charter/context.py`

**Action**: Extend `ProjectMissionPaths` (or a sibling
`ProjectCharterPaths`) to cover charter path resolution.

### 2. Doctrine defaults location — RESOLVED

`defaults.yaml` has been moved from `src/doctrine/charter/` to
`src/charter/defaults.yaml`. The charter package now owns its
own defaults via `importlib.resources.files("charter")`.

### 3. Kitty-specs path not centralized

`kitty-specs/<mission-slug>/` paths are constructed inline throughout:

- `src/specify_cli/core/project_resolver.py`
- `src/specify_cli/tasks_support.py`
- Various CLI commands

**Action**: Add `kitty_specs_dir_for(mission_slug)` to the path
resolver.

### 4. Global runtime paths (`~/.kittify/`)

Global paths are resolved in:

- `src/kernel/paths.py` (via `SPEC_KITTY_HOME` env var)
- `src/specify_cli/runtime/bootstrap.py`

These could be unified under a `GlobalPaths` counterpart to
`ProjectMissionPaths`.

### 5. Remaining hardcoded `.kittify/missions/` sites

Beyond the 3 files rerouted in WP09, grep shows additional inline
`.kittify/missions/` path construction in:

- Migration scripts (`src/specify_cli/upgrade/migrations/`)
- Runtime bootstrap (`src/specify_cli/runtime/bootstrap.py`)
- Template resolver (`src/specify_cli/runtime/resolver.py`)

These should be rerouted in a follow-up pass.

### 6. Config-driven path overrides

Currently all paths are convention-based (hardcoded directory names).
A future enhancement could add a `paths:` section to
`.kittify/config.yaml` allowing projects to override default locations:

```yaml
paths:
  missions: .kittify/missions       # default
  charter: .kittify/charter  # default
  kitty_specs: kitty-specs           # default
```

This would make `ProjectMissionPaths` read from config rather than
hardcoding the layout.

## Design Principles (from HiC)

1. **Charter is the configuration entry point** — project-local
   overrides and path resolution should route through it.
2. **No filesystem info leaks** — callers should not construct paths
   from string segments; they should call typed methods.
3. **`MissionType` over raw strings** — predefined constants for
   built-in missions, `with_name()` for custom types.
4. **Singleton for convenience** — `ProjectMissionPaths.get()` lazily
   discovers the repo root; `init()` for explicit setup.
