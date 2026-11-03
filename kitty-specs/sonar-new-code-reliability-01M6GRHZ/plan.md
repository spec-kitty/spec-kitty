# Implementation Plan: Sonar new-code reliability blockers removed at source

**Branch**: `kitty/mission-sonar-new-code-reliability-01M6GRHZ` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/sonar-new-code-reliability-01M6GRHZ/spec.md`
**Input**: Mission specification from `kitty-specs/sonar-new-code-reliability-01M6GRHZ/spec.md`

## Summary

Three findings make up the whole of the SonarCloud new-code reliability debt that this repository can fix itself, and two of them (`python:S5756`, `python:S3827`) are the only reason the rating is E. This plan removes each at its source with a behaviour-preserving edit — a name lookup instead of a call on a functional-API `Enum`, an `import` placed before the function-local annotation that names it, and an explicit narrowing in place of a provably-dead `None` guard — and records the adjudication of everything else rather than editing it.

Technical approach: no analyzer config change, no suppression comment, no scan-scope change. Each edit stays inside the flagged function; a single new architectural guard test pins both the absent construct and the behaviour it must preserve; the PR body and the mission's evidence record carry the query and the per-finding disposition.

## Technical Context

**Language/Version**: Python 3.11 (repo `requires-python >= 3.10`, tested on 3.11/3.12/3.13); the touched surfaces are Python only.
**Primary Dependencies**: `typer` (the `events` command surfaces), `charter.activation` internals, `specify_cli.mission_metadata` and `specify_cli.upgrade.tracked_meta_notice` for the migration seam. No new dependency.
**Storage**: N/A (filesystem + git reads only).
**Testing**: `pytest`; new guard module in the architectural (source-shape) family carrying the fast-tier markers the sibling files use; existing module tests run as the behavioural blast radius.
**Target Platform**: Linux/macOS/Windows CI (pure Python, no platform-specific behaviour touched).
**Project Type**: single project (CLI package under `src/`).
**Performance Goals**: the new test module completes in under 5 s alone; no runtime hot path changes.
**Constraints**: no SonarCloud token or UI access (C-001); `acceptance-jvm` scan scope is a documented maintainer decision (C-002); the 19 pre-existing findings are out of scope (C-003); no gate or ratchet is relaxed (C-004).
**Scale/Scope**: 3 source files, ~6 changed lines total; 1 new test module; 1 changelog fragment.

## Charter Check

*GATE: re-checked after design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | `SUPPORTED_LOG_KINDS` stays the one registry the `--kind` choices and the default are derived from; the fix moves the *default's* derivation to a name lookup on the same registry rather than introducing a second literal. |
| ATDD-first / red-first | The guard test is written first and fails on today's tree for each of the three sites; it then passes. Behaviour tests exercise both branches of each site. |
| Locality of change (`DIRECTIVE_024`) | Each edit is inside the flagged function; no refactor, no rename, no signature change. |
| Smallest viable diff (`change-apply-smallest-viable-diff`) | No analyzer config, no suppression markers, no scan-scope change (NFR-001). |
| Architectural gate discipline | The new guard is a normal fast-tier test in the established `tests/architectural/` source-shape family; no baseline or allowlist is touched. |
| Pre-existing debt is not this mission's (`DIRECTIVE_025`) | The 19 pre-existing findings are classified and reported, not rewritten (C-003). |
| Terminology canon | "Mission", "finding", "new-code window" used as defined; no bare `routing`/`residue`/`primary` in the new prose. |
| Agent operating discipline | Draft PR first, `pr:pause-ci`, never merge, never push `main`. |

No violations to justify.

## Project Structure

### Documentation (this mission)

```
kitty-specs/sonar-new-code-reliability-01M6GRHZ/
├── plan.md                      # This file
├── spec.md                      # Mission specification
├── tasks.md                     # /spec-kitty.tasks output
├── traces/                      # approach / design-decisions / tooling-friction
└── evidence/                    # the SonarCloud query transcript behind the split
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/events.py                     # S5756 site (FR-001)
src/charter/activation/compiler.py                         # S3827 site (FR-002)
src/specify_cli/migration/backfill_identity.py             # S2583 site (FR-003)
src/specify_cli/upgrade/tracked_meta_notice.py             # the helper whose precondition the S2583 fix states
tests/architectural/test_new_code_reliability_shapes.py    # the guard (FR-001..FR-005)
docs/changelog/unreleased/<pr>.internal.md                 # changelog fragment
```

**Structure Decision**: single project. The guard lives in `tests/architectural/` because it asserts a
source shape across three modules that no single runtime test file owns; the behavioural assertions
for each site sit in the same module so one file reads as the whole contract for the change.

## Complexity Tracking

*None — the Charter Check has no violations.*

## Implementation Concern Map

### IC-01 — The two BLOCKER constructs, removed at source

- **Purpose**: Make the E rating's cause disappear from the code rather than from the analyzer's view, by rewriting each flagged construct in place without changing behaviour.
- **Relevant requirements**: FR-001, FR-002, FR-005, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/cli/commands/events.py` (`_LOG_KIND_DEFAULT`), `src/charter/activation/compiler.py` (`_default_active_charter_service`)
- **Sequencing/depends-on**: none
- **Risks**: the `Enum` built by the functional API is `Any` to mypy, so the name lookup must not lose the annotation that keeps the default typed; the compiler fix must keep the import function-local (module-level import would risk the cycle the local import exists to avoid).

### IC-02 — The dead branch behind S2583

- **Purpose**: Replace a `None` guard that cannot be false in its own branch with an explicit statement of the invariant, so the code and the analyzer agree.
- **Relevant requirements**: FR-003, FR-005
- **Affected surfaces**: `src/specify_cli/migration/backfill_identity.py` (`_tracked_mission_id`), docstring of `specify_cli.upgrade.tracked_meta_notice.tracked_meta_refusal`
- **Sequencing/depends-on**: none (independent of IC-01)
- **Risks**: `tracked_meta_refusal` has exactly one caller today; the narrowing must not silently remove the `None` case from the helper's contract for a future caller, so the precondition is documented at the helper.

### IC-03 — The adjudication record

- **Purpose**: Ship the evidence that the rating is analyzer-driven rather than a regression, and the disposition of the 19 pre-existing findings and the Java finding, where a maintainer can re-check it.
- **Relevant requirements**: FR-004, SC-004, C-002, C-003
- **Affected surfaces**: `kitty-specs/sonar-new-code-reliability-01M6GRHZ/evidence/`, the PR body's `## Change` / `## Deferred`
- **Sequencing/depends-on**: none (can be written from the grounding transcript at any point)
- **Risks**: the split is time-sensitive — the new-code window rolls over at the next release — so the evidence must record the query, the date and the window anchor (`previous_version` 4.0.0rc7) rather than only the conclusion.
