# Implementation Plan: Repo-relative retrospective record_path

**Branch**: `fix/retrospective-record-path-relative` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/retrospective-record-path-relative-01M4PG0M/spec.md`

## Summary

Fix #5868: `emit_captured` (`src/specify_cli/retrospective/lifecycle_events.py`)
persists `record_path=str(canonical_path)` — an absolute path — into the tracked
`RetrospectiveCaptured` event, leaking the operator's home directory/username
into the committed `status.events.jsonl`. Because `canonical_path =
resolve_retrospective_home(repo_root, slug) / RETROSPECTIVE_FILENAME` and that
home is always composed under `repo_root` (`_compose_primary_feature_dir` joins
`KITTY_SPECS_DIR`), the technical approach is to persist the repository-relative
POSIX path (`kitty-specs/<slug>/retrospective.yaml`) via
`canonical_path.relative_to(repo_root).as_posix()`. Forward-only (Decision
`specify.scope.migration`); land red-first with an issue-pinned regression.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.

  If multiple developers/agents will work on this mission, add an "Implementation
  Concern Map" section below to decompose architectural intent into IC-## concerns
  before generating tasks.
-->

**Language/Version**: Python 3.11+
**Primary Dependencies**: None new — standard library `pathlib.Path` only (`relative_to`, `as_posix`)
**Storage**: Append-only JSONL event log (`status.events.jsonl`); YAML record (`retrospective.yaml`)
**Testing**: pytest; red-first `@pytest.mark.regression` pinned to `#5868` through the real `emit_captured` entry point, plus the existing `tests/retrospective/test_events.py` suite
**Target Platform**: Linux/macOS CLI
**Project Type**: single (CLI library)
**Performance Goals**: N/A — one path transformation per capture
**Constraints**: `record_path` stays a `string`; envelope byte-identical except that field; ruff + mypy clean; complexity ≤ 15; no suppressions
**Scale/Scope**: One emit site; ~1 line of surface change + 1 regression test

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD / red-first (Standing Order, ADR 2026-07-17-1)**: satisfied — regression lands RED before the fix. ✅
- **Campsite / single canonical authority**: `emit_captured` is the sole site that assembles the `record_path` persisted to the event; no parallel authority introduced. ✅
- **Terminology**: no `feature*` terms introduced; `record_path` retained (contract field name). ✅
- **Tiered rigour**: trivial surface, proportionate single-WP plan + one focused test. ✅
- No new dependency → supply-chain directive DIRECTIVE_051 not engaged. ✅

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

*Fill ONLY if Charter Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

## Implementation Concern Map

*Include this section when the mission has multiple distinct architectural areas that inform how tasks are decomposed.*

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.
> `/spec-kitty.tasks` translates these into executable WPs — one concern may become
> multiple WPs; multiple small concerns may merge into one WP. Do not label concerns
> with WP-style IDs or sequencing language.

### IC-01 — [Name]

- **Purpose**: [One sentence: what this concern addresses and why it matters]
- **Relevant requirements**: [FR-### refs from spec.md]
- **Affected surfaces**: [File paths or module names this concern touches]
- **Sequencing/depends-on**: [IC-## IDs this concern must follow, or "none"]
- **Risks**: [Key coordination notes or implementation risks]

### IC-02 — [Name]

- **Purpose**: [One sentence]
- **Relevant requirements**: [FR-### refs]
- **Affected surfaces**: [Paths/modules]
- **Sequencing/depends-on**: [IC-## or "none"]
- **Risks**: [Notes]
