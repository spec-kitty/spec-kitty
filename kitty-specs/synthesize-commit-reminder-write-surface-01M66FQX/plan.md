# Implementation Plan: Synthesize Commit Reminder Names the Whole Write Surface

**Branch**: `issue-6631-synthesize-reminder-write-surface` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/spec.md`
**Input**: Mission specification from `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/spec.md` (issue spec-kitty/spec-kitty#6631)

## Summary

`charter synthesize` prints a `spec-kitty safe-commit` recipe whose path list
(`_SYNTHESIS_ARTIFACT_PATHS`, `src/specify_cli/cli/commands/charter/_synthesis.py`)
omits `.kittify/charter/synthesized-artifacts.yaml` — the per-kind
created-artifacts record written by the same run — and the activation write
target written when a first-time slug joins an explicit `activated_<kind>s`
list. The fix derives the reminder from the write surface: the
activation-append seam (`append_synthesized_activations`,
`src/charter/activation/synthesizer/reach_only.py`) returns the repo-relative
paths it wrote alongside its warnings; `charter synthesize`'s real-run report
threads those paths into `_print_synthesis_commit_reminder`, which renders the
base synthesis paths plus exactly those (FR-001, FR-002). An end-to-end
regression test runs the real synthesize on the canonical fixture, executes
the printed command, and asserts `git status --porcelain .kittify/` is empty —
the anti-drift pin (FR-003). The governance skill's step 7 and the
`charter-artifact-structure.md` tables are updated to name the record
(FR-004), plus the changelog entry (FR-005).

## Technical Context

**Language/Version**: Python 3.11+ (repository `pyproject.toml`; the venv runs 3.13)
**Primary Dependencies**: typer (CLI), ruamel.yaml, pytest (typer.testing.CliRunner)
**Storage**: N/A (in-repository source and docs; no data storage)
**Testing**: pytest via `uv run pytest`; the mission's new tests live beside the suites that own the contracts — `tests/charter/synthesizer/` for the append seam and the end-to-end regression, `tests/agent/cli/commands/test_charter_synthesize_cli.py` for the reminder rendering. No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION); run the touched shards plus targeted files.
**Target Platform**: Linux/macOS/Windows CLI (pure Python)
**Project Type**: single (monorepo CLI package `specify_cli` + `charter`)
**Performance Goals**: N/A (no hot path; the append already runs under the synthesis lock)
**Constraints**: no behavior change to what synthesis writes (NFR-001); no new CLI flag/command or JSON envelope field (NFR-002); the reminder must never hard-code the activation-surface paths (NFR-003)
**Scale/Scope**: ~5 source files, ~6 test files, 2 doc files, 1 changelog entry; single-lane mission

## Charter Check

- Single canonical authority — satisfied: "which paths did the activation
  append write" is answered in exactly one place (the append seam itself);
  the reminder renders, never restates, that answer (NFR-003).
- ATDD-first — satisfied: FR-003's end-to-end regression test is written
  red-first against the pre-existing entry point (`charter synthesize` CLI +
  printed command) before the fix.
- Locality of change / smallest viable diff — satisfied: no changes outside
  the reminder path-list derivation, its callers, the docs, and tests.
- No pack-manifest regen needed: the skill references under
  `src/charter/offering/skills/` are committed in core, not fetched pack
  content (verified — no copy exists under `packs/` after `make sync-packs`).
- Docs change is user-facing → changelog `[Unreleased]` entry required
  (FR-005).

## Project Structure

### Documentation (this mission)

```
kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/
├── plan.md              # This file
├── research.md          # Grounding findings
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── charter/activation/
│   ├── api.py                                  # re-export of the append seam result type
│   └── activation/synthesizer/reach_only.py    # FR-001: report written paths
├── specify_cli/cli/commands/charter/
│   ├── _synthesis.py                           # FR-002: reminder takes extra paths; _emit_real_run_report threads them
│   └── synthesize.py                           # FR-002: adapt append call, pass written paths
│   └── resynthesize.py                         # FR-002: adapt append call (warnings only)
└── charter/offering/skills/spk-charter-governance/references/
    ├── charter-governance-workflow.md          # FR-004: step 7 names the record
    └── charter-artifact-structure.md           # FR-004: authority + git-tracking tables

tests/
├── charter/synthesizer/
│   ├── test_synthesize_activation_append.py    # FR-001 seam tests + FR-003 e2e regression home
│   ├── test_reach_only_delivery.py             # adapt to new result shape
│   └── test_styleguide_reach_only.py           # adapt to new result shape
├── agent/cli/commands/test_charter_synthesize_cli.py  # reminder rendering assertions
└── acceptance/test_persistent_deactivation.py  # adapt to new result shape

docs/changelog/CHANGELOG.md                     # FR-005
```

**Structure Decision**: single-project layout; the change is confined to the
charter activation seam, the charter CLI command modules, their tests, and two
committed skill-reference docs.

## Implementation Concern Map

### IC-01 — Activation-append seam reports its writes

- **Purpose**: Make `append_synthesized_activations` the single authority for
  which activation-surface files a synthesis run wrote, so the reminder can be
  derived instead of restated.
- **Relevant requirements**: FR-001, NFR-001, NFR-003
- **Affected surfaces**: `src/charter/activation/synthesizer/reach_only.py`,
  `src/charter/activation/api.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: the return-shape change touches internal callers and several test
  files mechanically; keep the warnings content byte-identical so
  warning-assertion tests only change shape, not meaning.

### IC-02 — Reminder derivation and CLI threading

- **Purpose**: Render the safe-commit recipe from base paths + the append's
  reported written paths, deduplicated, stable order; adapt both production
  callers.
- **Relevant requirements**: FR-002, NFR-002, C-003
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/_synthesis.py`,
  `synthesize.py`, `resynthesize.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the fresh-project seed reminder path must stay unchanged (no
  append call there); `--json` output must not change.

### IC-03 — Regression pin, docs and changelog

- **Purpose**: The generic end-to-end cleanliness test (red-first), the
  skill/doc text, and the changelog entry.
- **Relevant requirements**: FR-003, FR-004, FR-005
- **Affected surfaces**: `tests/charter/synthesizer/test_synthesize_activation_append.py`,
  `src/charter/offering/skills/spk-charter-governance/references/*.md`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02
- **Risks**: the e2e test must execute the printed command through the real
  `safe-commit` surface in an initialized test repo (branch non-protected,
  identity configured) — follow `tests/specify_cli/cli/commands/test_safe_commit_cli.py`'s
  pattern.
