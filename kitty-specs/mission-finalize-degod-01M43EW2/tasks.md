# Tasks: Decompose mission_finalize god-module

**Mission**: `mission-finalize-degod-01M43EW2` · **Branch**: `claude/modest-keller-6mvhd4` (single_branch) · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Extract the seven phase modules verbatim (AST-driven split) | WP01 | |
| T002 | Re-export every moved name and patch seam from `mission_finalize` | WP01 | |
| T003 | Route patched names and cross-module calls through the lazy `_mf` seam bridge | WP01 | |
| T004 | Re-point source-reading structural pins; add the family-source test helper | WP01 | |
| T005 | Add the focused seam tests (re-export, no module-scope cycle, interception, logger) | WP01 | |
| T006 | Static gates: ruff, format, mypy (incl. the 2 carried mypy findings) | WP01 | |
| T007 | Behaviour-parity run over the finalize corpus; classify every red against base | WP01 | |
| T008 | Add a module map to `docs/api/finalize-tasks-internals.md` and fix its stale code pointer | WP02 | |
| T009 | Regenerate the docs retrieval index; run the docs freshness and terminology gates | WP02 | |

## Phase 1 — Foundation

### WP01 — Phase extraction with a stable patch surface

**Prompt**: [tasks/WP01-phase-extraction.md](tasks/WP01-phase-extraction.md) · **Priority**: P1 · **Dependencies**: none · **Est. prompt**: ~250 lines

**Goal**: split `mission_finalize.py` into seven phase modules with identical behaviour. Re-point every source-reading pin in the same change, so no commit goes red.

**Independent test**: the finalize corpus passes with no assertion edits, and the new seam tests pass.

**Subtasks**:

T001 Extract the seven phase modules verbatim (WP01)
T002 Re-export every moved name and patch seam from `mission_finalize` (WP01)
T003 Route patched names and cross-module calls through the lazy `_mf` seam bridge (WP01)
T004 Re-point source-reading structural pins; add the family-source test helper (WP01)
T005 Add the focused seam tests (WP01)
T006 Static gates (WP01)
T007 Behaviour-parity run; classify reds against base (WP01)

**Risks**: a patch that resolves but no longer intercepts; a pin that silently loses coverage; ruff `--fix` dropping a seam-only import. See the prompt.

## Phase 2 — Polish

### WP02 — Developer documentation: finalize module map

**Prompt**: [tasks/WP02-finalize-module-map-docs.md](tasks/WP02-finalize-module-map-docs.md) · **Priority**: P3 · **Dependencies**: WP01 · **Est. prompt**: ~120 lines

**Goal**: maintainers can find a finalize phase from the internals doc.

**Subtasks**:

T008 Module map plus stale code pointer fix (WP02)
T009 Docs index regeneration and freshness/terminology gates (WP02)

## MVP

WP01 delivers the whole behavioural value. WP02 is documentation polish.
