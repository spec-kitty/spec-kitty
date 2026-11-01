# Implementation Plan: Harden the mission-type capability contract

**Branch**: `issue-6330-run-dir-threading` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/mission-type-capability-hardening-01M6BTT4/spec.md`

## Summary

Three narrow hardenings of the mission-type capability contract that #6315 (#6332, merged) introduced, none of which re-opens a built-in regression:

1. **Thread the in-hand `run_dir`** through `_check_cli_guards` / `_dispatch_via_composition` → `_check_composed_action_guard` → `gather_artifact_presence` so `wp_driven` is decided by the run the caller already resolved. The fact port stops deriving a mission handle from `feature_dir.name`; an explicit `mission_slug=` argument is the only fallback, and production never needs it.
2. **Make the `requires_substantive_spec` fail-open observable**: `requires_substantive_spec_for` keeps returning the built-in default on a resolution error but logs one WARNING naming the type key and the error.
3. **Pin the advisory `wp_driven` facet**: document `ResolvedMissionType.wp_driven` as advisory with the frozen runtime DAG authoritative, and prove it with a curated-away fixture where the two disagree and the guard follows the DAG.

No new module, no schema change, no ADR: the mission implements an existing kernel rule (`step_ids_declare_wp_iteration`) and an existing documented split of authority (`AGENTS.md`: `feature_dir.name` is not a mission handle).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing only — `runtime.next.runtime_bridge*` (guard/bridge cluster), `runtime.next.runtime_bridge_io` (fact port), `charter.activation.mission_type_profiles` + `charter.activation.api` (capability seam); pytest for tests
**Storage**: none new — reads the run's `mission_template_frozen.yaml` (already read today) and `feature-runs.json` (only on the explicit-fallback path)
**Testing**: pytest, red-first; targeted node ids locally; CI owns the full sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: cross-platform CLI + library
**Project Type**: single
**Performance Goals**: no new selector/index read on the `next` hot path when the caller holds a run (NFR-001); the fallback read is unchanged and only reached by callers that supply no `run_dir`
**Constraints**: one kernel rule (C-001); activation access only through `charter.activation.api` (C-002); no gate weakening (C-003); ruff/mypy clean, cyclomatic complexity ≤ 15, diff-cover ≥ 90 % on changed lines
**Scale/Scope**: 4 source files (`runtime_bridge.py`, `runtime_bridge_composition.py`, `runtime_bridge_io.py`, `charter/activation/mission_type_profiles.py`), 3 test files, one `[Unreleased]` changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter `software-dev-default` (`.kittify/charter/charter.md`). Binding items and compliance:

- **Single canonical authority / no improvisation** — `wp_driven` keeps the one kernel rule; the mission moves *which run* is read, never the rule. No second definition is introduced. ✅
- **ATDD-first / red-first** — each of FR-001/FR-002/FR-003 starts as a failing test through the existing entry point (`_check_composed_action_guard`, `requires_substantive_spec_for`, `resolve_mission_type_context`). ✅
- **Architectural gate discipline** — the `charter.activation` boundary gate and the import-boundary gate for `runtime_bridge_cores` stay green; the fix only widens a fact-port kwarg list. ✅
- **Terminology canon** — `run_dir` (the resolved run directory), `mission_slug` (the mission handle), `feature_dir.name` (a directory name, explicitly *not* a handle). ✅
- **Test-first bug fixing (DIRECTIVE_034)** — the repro ships with the fix and stays as a regression test. ✅
- **Complexity ≤ 15 / mypy strict / ruff** — new code is a kwarg forward plus one log call; no new suppression. ✅

**New decision requiring an ADR**: none. The authority split (charter facet advisory, runtime DAG authoritative) is already the design; this mission only writes it down on the DTO.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-type-capability-hardening-01M6BTT4/
├── spec.md
├── plan.md                 # this file
├── research.md             # Phase 0 — grounding survey (already reflected in spec's table)
├── tasks.md                # Phase 2
├── traces/                 # approach.md, design-decisions.md, tooling-friction.md
└── tasks/WP*.md            # work packages
```

### Source Code (repository root) — surfaces this mission touches

```
src/runtime/next/
├── runtime_bridge_io.py         # gather_artifact_presence(+run_dir, +mission_slug), _wp_driven_fact
├── runtime_bridge.py            # _check_cli_guards(+run_dir), both _dn_dependency_gate call sites
└── runtime_bridge_composition.py # _check_composed_action_guard / _dispatch_via_composition(+run_dir)

src/charter/activation/
└── mission_type_profiles.py     # requires_substantive_spec_for logging; ResolvedMissionType.wp_driven docstring

tests/runtime/
├── test_wp_driven_guard.py      # FR-001 red test (renamed dir + run_dir), FR-003 curated-away parity
└── test_artifact_presence_placement.py  # presence fact-port contract (run_dir wins, no implicit name)

tests/charter/
└── test_resolved_mission_type_context.py  # FR-002 observable fail-open (caplog) + DTO doc contract

docs/changelog/CHANGELOG.md      # [Unreleased] entry
```

**Structure Decision**: single project; the change stays inside the existing runtime/charter seams with no new package, module, or public CLI surface.

## Phase 0 — Research

Grounded on `main` @ `287a226cfe` (table in `spec.md`). Findings that shape the design:

- `gather_artifact_presence` already *accepts* `run_dir` (added by #6315) but no production caller supplies it; `_wp_driven_fact` therefore always re-resolves. The fix is a threading exercise, not new logic.
- `_check_cli_guards` has exactly two production call sites, both in `_dn_dependency_gate`, and `ctx.run_dir` is in scope at both.
- `_dispatch_via_composition` is called from `_dn_composition_dispatch`, again with `ctx.run_dir` in scope.
- The only test caller that depends on the implicit `feature_dir.name` fallback is `tests/runtime/test_wp_driven_guard.py`; it already builds the run, so it can pass `run_dir` explicitly.
- The broad `except` the issue names moved during the earlier refactor: the CLI helper delegates to `charter.activation.api.requires_substantive_spec_for`, whose `except Exception` is the silent one. Fixing it there fixes every consumer of the seam.
- `tests/runtime/_next_mission_scaffold.scaffold_custom_analyze_mission` already builds an activated custom family with a real frozen DAG; a curated-away variant only needs the DAG steps passed independently of the type's `action_sequence` (which the scaffold's `mission_types/<id>.yaml` leaves unset).

## Phase 1 — Design

**FR-001 (threading).** `gather_artifact_presence` gains `mission_slug: str | None = None`; `_wp_driven_fact(step_id, run_dir, repo_root, mission_slug)` uses `run_dir` when given, else the read-only index lookup for an *explicitly supplied* slug, else `False`. Call order of precedence: `run_dir` > `mission_slug` > no fact. `feature_dir.name` is never consulted by the fact port again. `_check_cli_guards`, `_check_composed_action_guard` and `_dispatch_via_composition` each gain `run_dir=` / `mission_slug=` pass-through kwargs; the two `_dn_dependency_gate` call sites and the one `_dn_composition_dispatch` call site thread `ctx.run_dir`.

**FR-002 (observable fail-open).** `requires_substantive_spec_for` catches the same exceptions and returns the same default, but logs `WARNING` with the mission type key and the exception (`logger.warning(..., exc_info=True)` on the activation module logger). The success path logs nothing (positive control in the test).

**FR-003 (advisory facet).** Docstring on the `wp_driven` field states it is derived from the curated `action_sequence`, is advisory for CLI/external consumers, and that the guard reads the frozen runtime DAG. A curated-away test asserts DTO `False` and guard gating on one fixture.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Removing the implicit fallback regresses a caller nobody noticed | Grep-verified: only test callers; the one relying on it is updated to pass the run it already holds. `_check_cli_guards` production call sites are threaded. |
| Built-in paths change (AC-14-style) | `software-dev` short-circuits before `wp_driven`; the other three built-ins are guard-table entries and never read the fact. Existing suites are the positive control. |
| Logging noise on every unresolved custom type | The log fires only on an exception, and only for callers of the resume-probe seam (one call per probe). |
| Test-only scaffolding masks a production wiring gap | FR-001's test drives `_dispatch_via_composition` (the production dispatch path), not only the guard helper. |
