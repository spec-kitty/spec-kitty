# Contract: the mission-type capability fact the guards consume

**Mission**: `mission-type-capability-hardening-01M6BTT4` · **Issue**: #6330 · **Base**: `287a226cfe`

This mission hardens three seams of the capability contract that #6315 (#6332)
introduced. This file is the durable statement of what those seams promise; the
tests named below are the executable form of each clause.

## C-1 — `wp_driven` has one rule and two inputs

| Surface | Derived from | Authority |
|---|---|---|
| `ArtifactPresenceSnapshot.wp_driven` (the fact both guards read) | the run's **frozen runtime DAG** (`mission_template_frozen.yaml`), via `kernel.mission_runtime_shape.step_ids_declare_wp_iteration` | **authoritative** |
| `ResolvedMissionType.wp_driven` (charter DTO) | the type's curated `action_sequence`, same kernel rule | **advisory** — a cheap capability read for CLI/external consumers, never consumed by the guard |

A type that curates `action_sequence` away from its DAG reports `False` on the
DTO and still gates at `implement`/`review`. Pinned by
`tests/runtime/test_wp_driven_parity.py`.

## C-2 — the fact port's run-directory precedence

`gather_artifact_presence(..., run_dir=None, mission_slug=None)`:

1. `run_dir` — the run the caller already resolved — is authoritative.
2. `mission_slug`, explicitly supplied, is the only fallback: the run recorded for
   it is read read-only (`feature-runs.json`); a run is never started.
3. Neither supplied → `wp_driven=False`. `feature_dir.name` is **never** treated
   as a mission handle (`AGENTS.md`, Terminology Canon).

Runtime callers thread `ctx.run_dir` through `_check_cli_guards`,
`_dispatch_via_composition` and `_check_composed_action_guard`. A caller that
supplies neither input accepts "not WP-driven" rather than a guess. Pinned by
`tests/runtime/test_wp_driven_guard.py`.

**Non-goal**: a `run_dir` belonging to a different mission than `feature_dir` is
the caller's contract to keep; the fact port does not cross-check it.

## C-3 — the substantive-spec capability never crashes, but is never silent

`charter.activation.api.requires_substantive_spec_for` returns
`resolve(...).requires_substantive_spec`, and on any resolution error returns the
built-in default for the type **and logs one WARNING** naming the mission type
and the failure. The resume probe (`mission_check_prerequisites`) depends on this
seam and stays non-crashing either way. Pinned by
`tests/charter/test_resolved_mission_type_context.py::TestRequiresSubstantiveSpecFailOpenIsObservable`.

## C-4 — built-in types are untouched

`software-dev` short-circuits before the fact; `research`, `documentation` and
`plan` are `_GUARD_TABLES` entries that never read it. Their guard results and
composed-dispatch payloads are byte-identical to `main`. Ratcheted by the
existing suites listed in the mission's `tasks.md`.
