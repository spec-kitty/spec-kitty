# Implementation Plan: Codex `.agents/skills` manifest-drift idempotency

**Branch**: `issue-702-codex-skills-drift` | **Date**: 2026-10-12 | **Spec**: `kitty-specs/codex-skills-drift-01M4RXXH/spec.md`
**Input**: Mission specification from `kitty-specs/codex-skills-drift-01M4RXXH/spec.md` (GitHub #702)

## Summary

Make the DERIVED, git-ignored command-skill projection (`.agents/skills/spec-kitty.<command>/SKILL.md`) idempotent against its tracked manifest. The command-skill installer currently classifies a **manifest-owned** projection whose on-disk bytes match neither the recorded `content_hash` nor the current render as a drifted *user edit* (`consent_required`) and keeps it. Because the surface is DERIVED/IGNORED (never committed, always regenerable) and the drift is a legitimate cross-checkout/stale-output disagreement, the correct behaviour is to **regenerate** it to the canonical render during the install/upgrade/sync/init reconcile. Non-manifest / third-party paths stay untouched (installer NFR-002).

## Technical Context

**Language/Version**: Python 3.11+ (repo runs 3.13 locally; CI matrix includes 3.11+).
**Primary Dependencies**: internal — `specify_cli.skills.command_installer`, `command_renderer`, `manifest_store`; `specify_cli.tool_surface.providers.command_skills`; `specify_cli.state.contract`.
**Storage**: filesystem — `.agents/skills/` (ignored) + `.kittify/command-skills-manifest.json` (tracked).
**Testing**: pytest; red-first ATDD through the real `spec-kitty upgrade`/`init` reconcile entry point, plus focused installer unit coverage. `make test-fast` + `tests/specify_cli/skills/` + `tests/agent/` + doctor/agent-config suites.
**Target Platform**: Linux/macOS/Windows CLI.
**Project Type**: single (CLI).
**Performance Goals**: N/A — a reconcile touches O(commands × agents) files; no new hot path.
**Constraints**: ruff + `ruff format --check` + mypy zero issues; complexity ≤ 15; no suppressions; change confined to the DERIVED command-skill surface (C-001).
**Scale/Scope**: ≤ ~5 lines of behavioural change in `command_installer.preserve()` plus a state-contract-premise guard; test updates for the superseded policy; docs + CHANGELOG.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** ✓ — the regenerate decision is grounded in the one authority for this surface's class, `state/contract.py` `shared_skills_projection` (DERIVED/IGNORED); a guard test pins that premise (C-003).
- **Architectural alignment** ✓ — change stays inside the module that already owns all `.agents/skills/` mutations; no new cross-module coupling, no shared-package-boundary impact.
- **DDD + tiered rigour** ✓ — one bounded behaviour (install-time drift disposition) in one aggregate (the installer plan).
- **ATDD-first** ✓ — red-first regression through the real entry point precedes the fix.
- **Terminology adherence** ✓ — no new/retired terms; "command skill", "projection", "manifest", "disposition" are canonical.
- **Smallest-viable-diff / locality-of-change** ✓ — single decision branch flipped; consent plumbing left intact for the explicit-repair path.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/codex-skills-drift-01M4RXXH/
├── spec.md              # mission spec
├── plan.md              # this file
├── research/            # Phase 0 — diagnosis-702.md (reproduction + root cause)
├── analysis-report.md   # cross-artifact consistency
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── tasks/WP01-*.md      # the single work package
```

### Source Code (repository root)

```
src/specify_cli/skills/
├── command_installer.py     # EDIT: preserve() drift branch → regenerate for the DERIVED surface
├── command_renderer.py       # (read only) canonical render
├── manifest_store.py         # (read only) fingerprint + manifest I/O
└── verifier.py               # (read only) drift/gap scanner used by doctor skills
src/specify_cli/state/contract.py   # (read only) shared_skills_projection = DERIVED/IGNORED authority

tests/specify_cli/skills/
├── test_command_installer.py                 # UPDATE: tests pinning the superseded consent-on-drift policy
└── test_command_installer_derived_regeneration_702.py  # NEW: red-first regression through the real reconcile

docs/ + docs/changelog/CHANGELOG.md            # policy clarification + [Unreleased] entry
```

**Structure Decision**: Single CLI project. The behavioural edit is localized to `src/specify_cli/skills/command_installer.py`; the state contract is read to justify (and a guard pins) the DERIVED classification.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

### IC-01 — Derived-surface drift disposition

- **Purpose**: Make a drifted, manifest-owned command-skill projection regenerate to the canonical render instead of landing in `consent_required`, because the surface is DERIVED/IGNORED and always regenerable.
- **Relevant requirements**: FR-001, NFR-001, NFR-003, C-003.
- **Affected surfaces**: `src/specify_cli/skills/command_installer.py` (`preserve()` drift branch); premise guard against `state/contract.py` `shared_skills_projection`.
- **Sequencing/depends-on**: none.
- **Risks**: Must not widen to the `existing is None` (non-manifest) branch — that would clobber user content (FR-002/NFR-002). Must not regress the clean version-upgrade re-render path (on-disk == recorded hash, ≠ new render) which already works. The superseded policy is pinned by existing tests that must be updated with #702 justification (not deleted silently).

### IC-02 — Documentation & verification clarity

- **Purpose**: State the generated/ignored policy, the idempotent-regeneration repair, and fresh-clone behaviour in docs + CHANGELOG, per #702's acceptance criteria.
- **Relevant requirements**: FR-003, SC-004.
- **Affected surfaces**: Codex / agent-skills docs; `docs/changelog/CHANGELOG.md` `[Unreleased]`.
- **Sequencing/depends-on**: IC-01 (describe the shipped behaviour).
- **Risks**: Terminology guard (`test_no_legacy_terminology.py`) and docs-freshness index if a doc page/ADR is added.
