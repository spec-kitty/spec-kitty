# Implementation Plan: [MISSION]

**Branch**: `[###-mission-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/kitty-specs/[###-mission-name]/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `src/doctrine/missions/software-dev/command-templates/plan.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Add a fail-closed idempotency guard to the single mission-create seam
, placed with the
other early guards (git-repo / unborn-HEAD / detached-HEAD) **before any scaffold or
branch is written**. Approach:

-  already enumerates existing missions under
  ; read each candidate's  (, ) to
  find a **same-slug + same-type** prior mission.
- Classify each prior match as **abandoned** (canceled, or genesis / no 
  progress / spec never committed) vs **live** via the status event log; only a live match
  triggers the guard.
- Thread a new  param through  (mirrors
  the existing  /  opt-ins) and
  expose  on  (and ); the
  factory passes it. On a live match with , raise
   naming the existing mission (slug + mid8) + the override.

No new dependencies; no schema change.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.

  If multiple developers/agents will work on this mission, add a "Parallel Work
  Organization" section below showing the dependency graph and agent assignments.
-->

**Language/Version**: Python 3.11+ (CI 3.12)
**Primary Dependencies**: none new — existing , , status event log reader
**Storage**: N/A (reads meta.json + status.events.jsonl under kitty-specs/)
**Testing**: pytest — tests/core (owning subsystem); red-first @regression repro through create_mission_core
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single (CLI/library)
**Performance Goals**: negligible — one directory scan + per-candidate meta/event read at create time
**Constraints**: guard before scaffold write (no orphan on refusal, NFR-002); fail-closed on ambiguity (C-002); single seam (C-001)
**Scale/Scope**: one guard + one flag + abandonment classifier in mission_creation.py; flag surfaced on 2 CLI paths

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
[Identify what must be built sequentially vs what can be done in parallel]
Example:
Foundation (Day 1) → Wave 1 (Days 2-3, parallel) → Wave 2 (Days 4-5, parallel) → Integration (Day 6)
```

### Work Distribution

- **Sequential work**: [What must be done first before parallel work can begin]
- **Parallel streams**: [Independent work that can be done simultaneously]
- **Agent assignments**: [Who owns which files/modules to avoid conflicts]

### Coordination Points

- **Sync schedule**: [When parallel workers merge their changes]
- **Integration tests**: [How to verify parallel work integrates correctly]
