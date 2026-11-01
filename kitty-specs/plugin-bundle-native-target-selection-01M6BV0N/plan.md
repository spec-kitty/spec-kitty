# Implementation Plan: Plugin bundle native target selection

**Branch**: `issue-6273-plugin-bundle-native-target-selection` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/spec.md`

## Summary

A plugin bundle must carry one rendering per agent member, and that rendering must be the one its
distribution target can consume. Today every configured tool's agent profile is mapped into the
target's filename shape, so a Claude+Codex project merges `.claude/agents/<id>.md` with a renamed
`.codex/agents/<id>.toml` and the shared-member guard refuses the whole batch. The fix gives each
projector an ordered, explicit list of accepted agent tool keys (native first, Markdown-family
fallback second, non-Markdown never), keeps the conflict guard for genuine same-family
disagreements, and repairs the reporting path so a failed `--fix` names its surfaces and exits 1
instead of exiting 0 silently.

## Technical Context

**Language/Version**: Python 3.11+ (`pyproject.toml`, mypy strict on `src/`)
**Primary Dependencies**: typer, pydantic, pytest — no new dependency
**Storage**: project filesystem only (`dist/spec-kitty-plugins/` staging tree, gitignored)
**Testing**: pytest unit/integration suites under `tests/specify_cli/tool_surface/`; red-first
through the existing entry points (`PluginBundleProvider.assess/repair`, `run_tool_surfaces`,
`doctor tool-surfaces`)
**Target Platform**: CLI on macOS/Linux/Windows (no platform-specific API added)
**Project Type**: single Python package with a CLI boundary
**Performance Goals**: no measurable change; selection drops instances before they are read
**Constraints**: no publish/install side effect; incomplete assessments write nothing; OPTIONAL
missing surfaces keep `ok: true`
**Scale/Scope**: 3 bundle targets, 5 source files, ~1 test module plus CLI integration coverage

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the accepted-tool-key list belongs to each projector (the owner of
  its distribution target), not to the CLI or the provider. No second selection table.
- **Locality of change (DIRECTIVE_024) / smallest viable diff** — edit the existing merge loop and the
  existing repair plumbing; do not restructure the bundle pipeline.
- **ATDD-first (C-011)** — the issue reproduction is the acceptance fixture: the red test drives
  `run_tool_surfaces(..., fix=True)` on a claude+codex+copilot project before the fix.
- **No weakening of a gate** — the shared-member conflict refusal stays; the change is which sources
  are candidates, not whether conflicts are tolerated.
- **Pre-existing Failure Reporting Rule** — no known red is being worked around; the reproduction is
  deterministic and local.
- **Burn-down / no new allowlists** — no ratchet baseline or allowlist entry is added.
- **Terminology canon** — "distribution target", "bundle member", "repair outcome" per the canvas.

No violation requires a Complexity Tracking row.

## Project Structure

### Documentation (this mission)

```
kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/
├── plan.md
├── research.md
├── reasons-canvas.md
├── data-model.md
├── quickstart.md
├── contracts/plugin-bundle-selection.md
├── issue-matrix.json
└── tasks/                 # created by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/tool_surface/
├── bundles/projection.py          # entry selection + member merge
├── bundles/claude.py              # accepted families for the Claude target
├── bundles/copilot.py             # accepted families for Copilot/VS Code targets
├── providers/plugin_bundle.py     # probe cause, repair findings
├── repair.py                      # carry findings_after into RepairResult
└── cli/commands/_command_surface_doctor.py   # human failure line + exit code

tests/specify_cli/tool_surface/
├── bundles/test_projection_selection.py       # new: selection/fallback/guard units
├── providers/test_plugin_bundle.py            # update pinned multi-harness contract
└── integration/test_doctor_tool_surfaces_cli.py  # repair-failure reporting + exit code
```

**Structure Decision**: stay inside the existing `tool_surface` bounded context. The bundle
projectors own layout and accepted renderings; the provider owns diagnostics; the repair service owns
result aggregation; the CLI owns rendering and exit codes.

## Implementation Concern Map

### IC-01 — Target-native agent selection

- **Purpose**: Give each projector an ordered accept-list of tool keys per rendered kind (agent
  profiles, command/charter skills) so one bundle member takes exactly one native rendering, with
  the other Markdown family as fallback; name agent members from their own native suffix.
- **Relevant requirements**: FR-001, FR-002, FR-003, C-001
- **Affected surfaces**: `bundles/projection.py` (`bundle_entries_for_plans`), `bundles/claude.py`,
  `bundles/copilot.py`, `bundles/vscode.py`
- **Sequencing/depends-on**: none
- **Risks**: the merge loop also serves the shared-member conflict guard; ranking must replace only
  lower-ranked candidates, and equal-rank sources must still merge and refuse on differing bytes.

### IC-02 — Repair and probe diagnostics

- **Purpose**: Keep the provider's cause when a staged bundle is incomplete, and carry
  `findings_after` from provider repair into `RepairResult` so the CLI can print it.
- **Relevant requirements**: FR-004, FR-005, NFR-003, C-002
- **Affected surfaces**: `providers/plugin_bundle.py`, `repair.py`
- **Sequencing/depends-on**: none
- **Risks**: `RepairResult` is a public-ish result type; adding a field with a default keeps existing
  constructors and JSON consumers compatible.

### IC-03 — CLI failure rendering and exit code

- **Purpose**: Print failed surfaces with their reasons and exit 1 when a `--fix` repair failed.
- **Relevant requirements**: FR-004, SC-003
- **Affected surfaces**: `cli/commands/_command_surface_doctor.py`
- **Sequencing/depends-on**: IC-02 (needs `findings_after` on the result)
- **Risks**: the audit-only path and OPTIONAL-policy exit code must not change; only a repair failure
  escalates.

### IC-04 — Tests, changelog and docs

- **Purpose**: Prove the reproduction red-first, pin the new selection contract, and record the
  user-facing repair-reporting change.
- **Relevant requirements**: SC-001..SC-004, NFR-001, NFR-002
- **Affected surfaces**: `tests/specify_cli/tool_surface/**`, `docs/changelog/CHANGELOG.md`, the
  tool-surface docs page that describes `--fix`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the existing `test_canonical_multi_harness_profile_conflict_is_read_only` test pins the
  old refusal for a claude+codex tree; it must be rewritten to assert successful native staging while
  a genuine same-family conflict test keeps the refusal.

## Complexity Tracking

No charter violations.
