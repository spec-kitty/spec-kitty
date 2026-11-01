# Implementation Plan: Action-critical charter sections resolve in the active charter

**Branch**: `issue-6968-action-critical-sections-resolve` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/action-critical-sections-resolve-01M6BTST/spec.md`
**Issue**: #6968

## Summary

`spec-kitty charter context` advertises three action-critical charter sections
(`Terminology Canon`, `Code Review Checklist`, `Regression Vigilance`) from a
hard-coded list in core code. When the active `charter.md` lacks a heading, the
renderer still emits a `Run: spec-kitty charter context --include section:<slug>`
stanza, and the follow-up fetch returns the "has not yet authored" placeholder —
so a governed agent in a consumer project is told that loading governance it
never authored is action-critical.

Fix: filter the configured action-critical heading set against the headings the
active `charter.md` actually carries. Advertise only resolving headings, with
the existing verbatim body plus recovery fetch stanza; drop a heading the charter
never authored (and its empty-block header) from the advertised set. The direct
`--include section:<slug>` surface keeps its honest-degrade placeholder.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), rich (rendering), ruamel.yaml; stdlib `re` for the existing heading extractor
**Storage**: files — `.kittify/charter/charter.md` read from disk; no database
**Testing**: pytest, targeted packages (`tests/charter/`, `tests/specify_cli/next/test_wp_prompt_governance_contract.py`); at least 90% diff coverage on changed lines
**Target Platform**: Linux, macOS, Windows 10+ (pure-Python CLI library code)
**Project Type**: single (Python CLI package under `src/charter/activation/`)
**Performance Goals**: no measurable regression against the CLI's <2s typical-command budget; at most one extra bounded scan of `charter.md` per render
**Constraints**: no new resolution pass, no project-config override, no pack edits (`packs/built-in` is fetched from `spec-kitty-open-packs`), preserve the ATDD anchors for present sections
**Scale/Scope**: 1 renderer module (`section_bodies.py`) + its call sites, 1 updated contract document, 1-2 unit-test files, 1 new regression test through the production entry point

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status |
| --- | --- |
| Single canonical authority (`DIRECTIVE_044`) | Pass — the heading list stays in `section_bodies.py`; the fix filters it, adding no second list and no config override. |
| Architectural integrity (`DIRECTIVE_001`) | Pass — change stays inside the charter activation renderer package; callers already handle an empty block. |
| ATDD-first / test-first bug fixing (`DIRECTIVE_034`) | Pass — a failing regression test on a minimal consumer charter precedes the fix. |
| Terminology canon (Mission, not Feature) | Pass — spec, plan and tests use "mission"/"charter section". |
| Locality of change (`DIRECTIVE_024`) | Pass — one renderer, its tests, and the one contract document that pins the behaviour. |
| No full heavy suites in mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | Pass — targeted test files only; CI owns the matrix. |
| Changelog for user-facing change | Pass — `[Unreleased]` entry under `docs/changelog/CHANGELOG.md`. |

No violations requiring justification. Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/action-critical-sections-resolve-01M6BTST/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding, decisions)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

`data-model.md`, `quickstart.md` and `contracts/` are not produced: the mission
introduces no new entity, no user-facing workflow step and no API interface
(`meta.json` records `"contracts": "none"` with its rationale).

### Source Code (repository root)

```
src/charter/activation/context_renderers/
├── section_bodies.py           # action-critical heading set + renderer (change)
├── bootstrap_text.py           # bootstrap caller (no change; already skips empty blocks)
├── compact_governance.py       # compact caller (no change)
└── token_budget.py             # per-heading split-out (no change; only sees rendered headings)

tests/charter/
├── test_context_section_bodies.py       # update the missing-heading expectations
└── test_context_display_charter_md.py   # check empty-charter expectations

tests/specify_cli/next/
└── test_wp_prompt_governance_contract.py  # ATDD anchors for present sections (must stay green)

kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/
└── charter-context-resolver.md  # the contract row this behaviour change updates

docs/changelog/CHANGELOG.md      # [Unreleased] entry (#6968)
```

**Structure Decision**: the repository's existing single-package layout is
unchanged. All production code stays in the charter activation renderer package;
no new module is introduced.

## Implementation Concern Map

### IC-01 — Filter the advertised action-critical heading set

- **Purpose**: Advertise only action-critical charter headings the active charter resolves, so no consumer is told to fetch a placeholder.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, C-001, C-003
- **Affected surfaces**: `src/charter/activation/context_renderers/section_bodies.py` (`render_critical_section_bodies`, a new private predicate); `bootstrap_text.py` and `compact_governance.py` consume the result unchanged
- **Sequencing/depends-on**: none
- **Risks**: the renderer is also consumed by token-budget substitution — the split-out must not manufacture a selector for a heading that is no longer rendered (it derives from the text, so it cannot).

### IC-02 — Keep direct selector fetch honest, and prove it

- **Purpose**: A direct `--include section:<slug>` for a heading the charter lacks still returns the honest placeholder instead of crashing, and tests prove the absence probe is non-vacuous on the same fixture.
- **Relevant requirements**: FR-004, FR-005, NFR-001
- **Affected surfaces**: `render_critical_section_include` (behaviour kept, docs clarified); `tests/charter/test_context_section_bodies.py`; a production-entry-point regression test
- **Sequencing/depends-on**: IC-01
- **Risks**: the existing unit test that pins missing-heading *advertising* must be rewritten to the filtered-set rule; the ATDD anchors for present sections must keep passing untouched.

### IC-03 — Contract, docstrings and changelog agree with the shipped rule

- **Purpose**: The resolver contract row, renderer docstrings and the changelog state the filtered-set rule so the behaviour cannot silently regress.
- **Relevant requirements**: FR-006, SC-004
- **Affected surfaces**: `kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md`, `src/charter/activation/context_renderers/section_bodies.py` module docstring, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: none; documentation only.
