# Implementation Plan: [MISSION]

**Branch**: `[###-mission-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/kitty-specs/[###-mission-name]/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `src/doctrine/missions/software-dev/command-templates/plan.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Two independent, outcome-preserving robustness edits to the charter **directive**
resolution path (epic #2519; deferred from #4194/#4185):

- **#4239 (memoization):** in `src/charter/activation/kind_vocabulary.py`,
  `resolve_config_id` calls `resolve_artifact_urn` per candidate stem, each of which
  re-invokes `_iter_artifact_paths` (an `rglob` over every layer) — O(D×S) filesystem
  work. Introduce a per-resolution memo of the per-layer scan (and the stem→id map
  `_directive_ids_by_stem` already computes) so each layer is walked once. Keep
  `_iter_artifact_paths`'s high→low precedence as the sole ordering authority (C-002).
- **#4240 (diagnostic):** in `src/charter/activation/resolver.py` `directives`
  property, the `except UnknownArtifactIdError` branch best-effort normalizes a
  fully-unresolvable token via `normalize_directive_id` with no signal. Emit a
  per-token `logging` WARNING naming the raw token and the normalized form; the
  resolution result is unchanged (C-003).

Technical approach: a small memo helper keyed on `(path, mtime)` (or a
resolution-pass-scoped cache) consumed by the existing resolution functions; a
`logging.getLogger(__name__).warning(...)` on the unresolved fallback. No new
dependencies, no API/schema change, no new data entities.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.

  If multiple developers/agents will work on this mission, add a "Parallel Work
  Organization" section below showing the dependency graph and agent assignments.
-->

**Language/Version**: Python 3.11+ (CI on 3.12)
**Primary Dependencies**: none new — stdlib `logging`, existing `charter.activation` internals (`_iter_artifact_paths`, `resolve_artifact_urn`, `resolve_config_id`, `_directive_ids_by_stem`, `normalize_directive_id`)
**Storage**: N/A (reads doctrine files on disk; no persistence change)
**Testing**: pytest — `tests/charter/` (owning subsystem), incl. `test_directive_identity_mapping.py`, `test_resolver_directive_activation_keying.py`, `test_drg_activation_gate.py`; new scan-count and warning tests
**Target Platform**: Linux/macOS/Windows CLI (same as spec-kitty)
**Project Type**: single (library/CLI); source under `src/charter/activation/`
**Performance Goals**: ≤ 1 filesystem scan per doctrine layer per directive resolution pass (down from up-to layers×stems)
**Constraints**: no resolution-outcome change (C-001); single overlay-precedence authority preserved (C-002); ruff/format/mypy clean, complexity ≤15, new branches tested (NFR-003)
**Scale/Scope**: two files, ~2 small helpers + a WARNING; tens of directives × tens of stems typical org layout

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this mission)

```
kitty-specs/[###-mission]/
├── plan.md              # This file (/spec-kitty.plan command output)
├── research.md          # Phase 0 output (/spec-kitty.plan command)
├── data-model.md        # Phase 1 output (/spec-kitty.plan command)
├── quickstart.md        # Phase 1 output (/spec-kitty.plan command)
├── contracts/           # Phase 1 output (/spec-kitty.plan command)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks command - NOT created by /spec-kitty.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this mission. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

## Parallel Work Analysis

*Include this section if multiple developers/agents will implement this mission*

### Dependency Graph

```
WP01 (#4239 memoization, kind_vocabulary.py)  ─┐
                                                ├─ independent (different files) → integrate
WP02 (#4240 diagnostic, resolver.py)          ─┘
```

### Work Distribution

- **Sequential work**: none — the two WPs touch disjoint files.
- **Parallel streams**: WP01 owns `src/charter/activation/kind_vocabulary.py` + its tests; WP02 owns `src/charter/activation/resolver.py` + its tests. No shared file.
- **Agent assignments**: one implementer per WP (sonnet, profile-loaded); reviews opus.

### Coordination Points

- **Integration test**: the full `tests/charter/` suite passes unchanged after both land (NFR-002).
