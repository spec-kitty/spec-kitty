# Implementation Plan: Fix the plugin bundle wrapper's uvx fallback

**Branch**: `kitty/mission-plugin-wrapper-uvx-fallback-01M68ZHZ` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/plugin-wrapper-uvx-fallback-01M68ZHZ/spec.md`
**Input**: Mission specification from `kitty-specs/plugin-wrapper-uvx-fallback-01M68ZHZ/spec.md`

## Summary

The generated Claude bundle bootstrap (`bin/spec-kitty-wrapper` and
`bin/spec-kitty-wrapper.cmd`) delegates to `uvx "spec-kitty-cli==<version>"` when no
`spec-kitty` is on PATH. That argument names a *distribution*, and uvx runs the
executable named after the distribution — the distribution ships `spec-kitty`, not
`spec-kitty-cli`, so uvx exits 1 without running anything. Change both templates to
`uvx --from "<requirement>" spec-kitty …`; gate the unconditional PATH preference on
the CLI's version being inside the pinned build's `<major>.<minor>` series; retry the
uvx resolution with the series range so an unpublished pin (operator finding on #6476)
still resolves to the newest published release of that line; and replace the
`pip install spec-kitty-cli` remedy with the uv/pipx guidance the rest of the plugin
docs use. One pure helper in the wrapper module derives the series, so both templates
and the retry range share a single authority.

## Technical Context

**Language/Version**: Python 3.11+ (project floor); generated artefacts are POSIX `sh`/bash and Windows `cmd.exe` batch
**Primary Dependencies**: stdlib only in the changed module (`re`, `stat`, `pathlib`); `uvx`/`uv` and `pipx` at runtime on the user's machine
**Storage**: N/A — the module renders two text files under a caller-supplied bundle directory
**Testing**: pytest; `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py` (unit + subprocess-level content/runtime assertions), `tests/specify_cli/tool_surface/bundles/test_claude_bundle.py` and `test_plugin_build_codex.py` for the build path
**Target Platform**: POSIX shells (bash/sh) and Windows `cmd.exe`
**Project Type**: single — CLI/package in `src/specify_cli`
**Performance Goals**: the resupported-PATH-CLI happy path adds one `--version` probe and no uvx resolution (NFR-001)
**Constraints**: content rendering stays offline and deterministic (NFR-004); no new console script (C-002); bundle layout untouched (C-001)
**Scale/Scope**: two templates, one pure helper, one test module, one how-to page, one changelog entry

## Charter Check

The charter governs: single canonical authority, architectural alignment, ATDD-first,
terminology adherence, and the Quality & Tech-Debt Standing Orders (red-first,
campsite cleaning, tracer files, no gate weakening).

| Gate | Verdict | Evidence |
|------|---------|----------|
| Single canonical authority | Pass | The version→series rule lives in one helper in `claude_wrapper.py`; both templates and the retry range consume it. No second copy in docs or tests. |
| Architectural alignment | Pass | Change stays inside the existing bundle-projection boundary (`tool_surface/bundles`); no new module, no import from a forbidden layer (module already imports only stdlib plus its own package for staging). |
| ATDD-first / red-first | Pass | The defect is proven by a failing subprocess test through the pre-existing entry point (`write_wrappers` → generated script → shell) before the template changes. |
| Terminology adherence | Pass | Uses the repo's canonical terms ("bundle", "wrapper", "supported series" defined in the spec); no new vocabulary. |
| Locality of change (`DIRECTIVE_024`) | Pass | Edits are confined to the wrapper module, its test module, the plugin install how-to and the changelog. |
| No gate weakening | Pass | No test selection, marker, or CI gate is relaxed. |
| Bundle layout (#6479) | Out of scope | `bin/` placement untouched by design (C-001). |

No violations; Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/plugin-wrapper-uvx-fallback-01M68ZHZ/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks/               # Work-package files (/spec-kitty.tasks output)
├── traces/              # approach.md, design-decisions.md, tooling-friction.md
└── status.events.jsonl  # Runtime event log
```

### Source Code (repository root)

```
src/specify_cli/tool_surface/bundles/
├── claude_wrapper.py     # CHANGED: templates + pure series helper
├── claude.py             # unchanged caller (renders both wrappers into the bundle)
└── projection.py         # unchanged guarded staging/apply path

tests/specify_cli/tool_surface/bundles/
├── test_claude_wrapper.py  # CHANGED: red-first fallback/version tests
├── test_claude_bundle.py   # unchanged: build-path assertions
└── test_plugin_build_codex.py  # unchanged: cross-target wrapper effect assertion

docs/guides/how-to/installation/install-claude-code-plugin.md  # CHANGED: resolution order
docs/changelog/CHANGELOG.md                                    # CHANGED: [Unreleased] entry
```

**Structure Decision**: single project. The change is a local edit to one existing
module in the bundle-projection package plus its tests, its how-to page and the
changelog; no new package, no new module, no new public API.

## Complexity Tracking

Empty — no charter violations require justification.

## Implementation Concern Map

### IC-01 — Wrapper content: `--from`, series gate, series-range retry

- **Purpose**: Make both generated wrappers invoke a CLI that exists, and choose the
  pinned/limited version deliberately instead of by PATH accident.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, NFR-004
- **Affected surfaces**: `src/specify_cli/tool_surface/bundles/claude_wrapper.py`
- **Sequencing/depends-on**: none
- **Risks**: the POSIX series probe must stay a single `--version` call (NFR-001) and
  must treat unparseable output as "no compatible CLI" rather than a crash under
  `set -euo pipefail`; the CMD retry requirement contains `<` and `>` and must be
  quoted or `cmd.exe` reads it as redirection; the #623 invariant (`EXIT /B
  %ERRORLEVEL%` never inside a parenthesized block) must survive the new branches.

### IC-02 — Red-first proof and regression pins

- **Purpose**: A failing test through the pre-existing entry point before the fix, and
  tests that pin each independent half of the change so reverting one turns the suite
  red.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, SC-001, SC-002, SC-003, SC-004, SC-005
- **Affected surfaces**: `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py`
- **Sequencing/depends-on**: IC-01 (the red is written first; the fix lands under it)
- **Risks**: the runtime tests execute a generated script, so they need a hermetic
  `PATH` (stub `uvx`, stub `spec-kitty`) and must not depend on the developer's real
  `uvx`, network, or an installed `spec-kitty`.

### IC-03 — Operator-facing docs and changelog

- **Purpose**: The install how-to and the changelog describe the resolution order that
  actually ships, instead of the broken `uvx spec-kitty-cli==<version>` and the
  `pip install` remedy.
- **Relevant requirements**: FR-006, FR-007, SC-004
- **Affected surfaces**: `docs/guides/how-to/installation/install-claude-code-plugin.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (documented behaviour must match the shipped templates)
- **Risks**: the how-to is index-referenced; keep the heading structure so the docs
  freshness check and index stay green. Keep the changelog entry under 1,200
  characters with the impact-first bold lead and `(#6476)`.
