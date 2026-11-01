---
title: 'ADR 7: Separate Research Deliverables from Planning Artifacts'
description: Sends evidence logs to the Mission's planning directory and research output to the repository proper, so finished work is no longer stranded in a worktree.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-25'
---

## Context and Problem Statement

Research missions conflate two distinct types of artifacts:

1. **Spec Kitty planning artifacts** in `kitty-specs/###/research/` (evidence-log.csv, source-register.csv)
2. **Research deliverables** (the actual output of the research - component inventories, best practices docs, etc.)

Currently, agents put research deliverables in `research/` at project root within worktrees. These files:
- Exist only in worktree branches
- Never get merged to main
- Result in "done" WPs with work stuck in worktrees

## Decision Drivers

- Research deliverables are the PRODUCT of the mission, not planning metadata
- Worktree-based workflow enables parallelization (like software-dev)
- Planning artifacts must remain in `kitty-specs/` for sprint tracking
- Existing merge workflow should work without modification

## Considered Options

### Option 1: All research in kitty-specs/ (edit in main)

- **Pros:** Simple, no new paths to manage
- **Cons:** No parallelization possible, everything in main, merge conflicts likely

### Option 2: All research in worktrees

- **Pros:** Full parallelization
- **Cons:** Planning artifacts (evidence-log.csv) can't be shared across WPs during planning

### Option 3: Separate planning artifacts from deliverables (CHOSEN)

- **Pros:** Clear separation of concerns, enables parallelization for deliverables while keeping planning artifacts shared
- **Cons:** Requires specifying `deliverables_path` during planning

## Decision Outcome

**Chosen option:** "Option 3 - Separate planning artifacts from deliverables"

### Implementation

- Planning artifacts remain in `kitty-specs/###/research/` (sparse-excluded, edit in main)
- Research deliverables go in configurable `deliverables_path` (in worktree, merge to main)
- Path stored in `meta.json` during planning phase

### Two Types of Artifacts

| Type | Location | Edited Where | Purpose |
|------|----------|--------------|---------|
| **Sprint Planning** | `kitty-specs/###-feature/research/` | Main repo | Evidence/sources for planning THIS sprint |
| **Research Deliverables** | `deliverables_path` from meta.json | Worktree | Actual research outputs (your work product) |

### meta.json Schema Change

```json
{
  "mission": "research",
  "deliverables_path": "docs/research/001-cancer-cure/",
  "created_at": "2025-01-25T...",
  ...
}
```

### Validation Rules

- `deliverables_path` must NOT be inside `kitty-specs/`
- `deliverables_path` should not be at project root (ambiguous)
- Recommended patterns: `docs/research/<feature>/`, `research-outputs/<feature>/`

## Consequences

### Positive

- Clear separation of concerns - planning vs deliverables
- Research workflow matches software-dev (worktree → merge)
- Existing merge command works without modification
- Each project controls where research lives
- Parallelization enabled for research WPs

### Negative

- Requires specifying `deliverables_path` during planning phase
- Migration needed for existing research features (default path provided)
- Two locations for "research" content may require documentation

### Neutral

- Agents must understand the distinction (documented in implement.md template)

## Confirmation

- Research WP deliverables appear in main after merge
- No orphaned worktree content
- Agents can work in parallel on research WPs
- Planning artifacts (evidence-log.csv, source-register.csv) remain accessible during planning

## Related ADRs

- ADR 1: Record Architecture Decisions
- ADR 3: Centralized Workspace Context Storage (workspace-per-WP pattern)

## Implementation Files

- `src/specify_cli/missions/research/templates/plan-template.md` - Deliverables location section
- `src/specify_cli/missions/research/command-templates/implement.md` - Two-artifact documentation
- `src/specify_cli/missions/research/command-templates/specify.md` - Prompt for deliverables_path
- `src/specify_cli/cli/commands/agent/workflow.py` - Read deliverables_path from meta.json
- `src/specify_cli/mission.py` - `get_deliverables_path()` helper function
