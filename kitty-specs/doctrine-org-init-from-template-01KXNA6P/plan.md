# Implementation Plan: Doctrine Org Init From Template

**Branch**: `feat/doctrine-org-init-from-template` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/kitty-specs/doctrine-org-init-from-template-01KXNA6P/spec.md`

**Audience**: Operators who create their own doctrine by extending
`spec-kitty doctrine org init` (template consumed as-is; no template-maintainer role).

## Summary

Extend the existing `spec-kitty doctrine org init` command so that, when
`--template` is supplied, it renders an existing local or git template into
**PACK_PATH** (full tree minus `.templateignore`), after validating **ORG_NAME**
and resolving **LOCAL_PATH** (distinct from PACK_PATH; default `pack`). When
`--template` is omitted, keep today’s minimal three-file scaffold.

Approach: thin Typer options on `org_init`; pure helpers in a new
`specify_cli.doctrine.template_render` module for validation, template URL/path
parse, ignore filtering, copy, and token substitution. Reuse
`specify_cli.doctrine.sources.git_source.GitSource` for git fetch into a temp
workspace. Reject inventing a second org-init command surface.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer, Rich (existing CLI); stdlib `pathlib` /
`fnmatch` / `tempfile` / `shutil`; existing `GitSource` for git clones
**Storage**: Local filesystem only (destination PACK_PATH; ephemeral temp for git)
**Testing**: pytest unit tests for helpers + CliRunner extensions in
`tests/cli/test_doctrine_org_commands.py` (ATDD-first)
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows 10+) where git is
available for git TEMPLATE URLs
**Project Type**: single (spec-kitty-cli package)
**Performance Goals**: Local template render under 30s for a doctrine-template-sized tree (NFR-003); git network time excluded
**Constraints**: No silent ORG_NAME sanitising; PACK_PATH ≠ LOCAL_PATH concepts; plain-text `{{ORG_NAME}}` / `{{LOCAL_PATH}}` only; no new templating engine; complexity ≤15 per function (Sonar/Ruff)
**Scale/Scope**: One CLI command extension + one focused doctrine module + tests; template repos themselves out of scope

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / standing order | Status | Notes |
|---|---|---|
| Single canonical authority | Pass | Extend existing `org init`; reuse `GitSource` rather than a parallel clone path |
| Architectural alignment | Pass | Logic under `src/specify_cli/doctrine/`; CLI stays in `cli/commands/doctrine.py` |
| ATDD-first | Pass | Extend/add RED tests before implementation WPs |
| Terminology (Mission, not Feature) | Pass | Spec/plan use Mission / org pack / operator |
| Canonical sources | Pass | ORG_NAME rules from doctrine-template downstream contract (C-001) |
| Git/workflow discipline | Pass | Work on `feat/doctrine-org-init-from-template`; PR to origin/main later |
| Campsite / complexity ceiling | Pass | Extract helpers to keep `org_init` and render pipeline ≤ complexity 15 |

**Post-design re-check**: No new charter conflicts. Design does not author or mutate external templates.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctrine-org-init-from-template-01KXNA6P/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli-org-init-template.md
└── tasks.md             # /spec-kitty.tasks — not created here
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/doctrine.py          # Extend org_init options + dispatch
└── doctrine/
    ├── sources/git_source.py         # Reuse for git TEMPLATE resolve
    └── template_render.py            # NEW: validate, parse, ignore, copy, substitute

tests/
├── cli/test_doctrine_org_commands.py           # Extend CliRunner coverage
└── specify_cli/doctrine/test_template_render.py  # NEW unit tests for helpers
```

**Structure Decision**: Keep CLI thin; put all render pipeline logic in
`template_render.py` with pure functions / small dataclasses for testability.
Do not add a separate command (e.g. `org render`).

## Complexity Tracking

No charter violations requiring justification.

## Planning Answers (locked)

| Topic | Decision |
|---|---|
| Copy unit | Entire template tree minus `.templateignore` (project scaffold) |
| LOCAL_PATH default | `pack` when omitted on template path |
| Git branch surface | Both `--branch` and branch encoded in TEMPLATE; conflict → error |
| Audience | Operators who create their own doctrine |
| Template role | Template consumed as-is; no template-maintainer workflow in scope |

## Implementation Concern Map

### IC-01 — ORG_NAME / LOCAL_PATH validation

- **Purpose**: Enforce doctrine-template downstream validation rules fail-closed with rule-named errors.
- **Relevant requirements**: FR-004, FR-005, FR-006, C-001, C-002, C-004
- **Affected surfaces**: `src/specify_cli/doctrine/template_render.py`; CLI error printing in `doctrine.py`
- **Sequencing/depends-on**: none
- **Risks**: Diverging from documented regex/length/reserved rules; silent sanitising must not creep in

### IC-02 — Template resolve (local + git + branch)

- **Purpose**: Resolve TEMPLATE to a readable source tree; support HTTPS/SSH; branch via `--branch` and/or TEMPLATE encoding; conflict detection.
- **Relevant requirements**: FR-003, FR-010
- **Affected surfaces**: `template_render.py` (URL parse); `GitSource` reuse; temp dir lifecycle
- **Sequencing/depends-on**: IC-01 (validate before write; resolve can run after validate)
- **Risks**: Partial clones left behind; token leakage in git errors (GitSource already redacts); Windows path edge cases

### IC-03 — Copy with `.templateignore` + built-in excludes

- **Purpose**: Copy full tree to PACK_PATH excluding ignore matches; always exclude `.git/` and `.templateignore` deliverable copy convention.
- **Relevant requirements**: FR-007, FR-010
- **Affected surfaces**: `template_render.py` ignore matcher + copy
- **Sequencing/depends-on**: IC-02
- **Risks**: Over/under-matching ignore patterns; copying `.git` if built-in exclude omitted

### IC-04 — Token substitution + leftover detection

- **Purpose**: Plain-text replace `{{ORG_NAME}}` / `{{LOCAL_PATH}}` across copied text files; fail if tokens remain.
- **Relevant requirements**: FR-008, FR-009, C-003
- **Affected surfaces**: `template_render.py` substitute walk
- **Sequencing/depends-on**: IC-03
- **Risks**: Binary files; encoding errors — skip or fail-closed on undecodable files with clear message

### IC-05 — CLI wiring + minimal-scaffold compatibility

- **Purpose**: Add `--template`, `--org-name`, `--local-path`, `--branch`; preserve no-template behaviour and `--force`.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/cli/commands/doctrine.py`; `tests/cli/test_doctrine_org_commands.py`
- **Sequencing/depends-on**: IC-01–IC-04
- **Risks**: Breaking existing CliRunner tests; requiring ORG_NAME when TEMPLATE omitted (must not)
