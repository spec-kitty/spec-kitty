# Research: Harden the mission-type capability contract (#6330)

Grounded on `main` @ `287a226cfe` (2026-11-01). Static inspection reproduced the
issue's triage comment; each item is confirmed against the current tree.

## Decisions

### D-01 — Thread the run, keep the rule

`gather_artifact_presence` already accepts `run_dir` (added by #6315) but no
production caller supplies it. `_wp_driven_fact`
(`src/runtime/next/runtime_bridge_io.py:1505-1519`) therefore always re-resolves
the run from `feature_dir.name` and returns `False` on any selector error — the
WP-advance guard is then skipped for a custom WP-driven family.

Decision: thread `ctx.run_dir` from the two live dispatch sites
(`_dn_dependency_gate` → `_check_cli_guards`; `_dn_composition_dispatch` →
`_dispatch_via_composition` → `_check_composed_action_guard`) into the fact port.
The fact port stops deriving a handle from `feature_dir.name`; it takes an
**explicit** `mission_slug` for the read-only index fallback (used only by
callers that hold no run). `wp_driven` keeps the single kernel rule
(`step_ids_declare_wp_iteration`) — only its input changes.

### D-02 — The silent `except` is behind the activation seam

The issue names `mission_check_prerequisites._requires_substantive_spec`; that
helper now delegates to `charter.activation.api.requires_substantive_spec_for`,
whose `except Exception: return builtin_default` (no log) is the real silent
site (`src/charter/activation/mission_type_profiles.py:1042-1055`). A type that
authored `requires_substantive_spec: true` and whose resolution transiently
throws is silently downgraded to `False` → a stub spec passes.

Decision: keep the non-crashing contract (the resume probe must not crash) but
log one `WARNING` naming the mission type key and the failure. Fixing it at the
seam fixes every consumer, and avoids a second copy in the CLI helper.

### D-03 — `wp_driven` is advisory on the DTO; the frozen DAG is authoritative

`ResolvedMissionType.wp_driven` is derived from curated `action_sequence`
(`mission_type_profiles.py:708`); the guard reads the frozen runtime DAG
(`runtime_bridge_io.mission_declares_wp_iteration`). They agree for every
built-in, and the guard side is authoritative by design. Nothing in the code
says so, so a future change could "align" the wrong side.

Decision: document the authority split on the DTO field and pin it with a
curated-away fixture (type whose `action_sequence` omits `implement`, frozen DAG
declares it): DTO reports `False`, guard still gates.

## Evidence

- `rg "_check_cli_guards\(" src/` → two production call sites, both inside
  `_dn_dependency_gate` (`runtime_bridge.py:835`, `:887`), with `ctx.run_dir` in
  scope.
- `_dispatch_via_composition` is called only from `_dn_composition_dispatch`
  (`runtime_bridge.py:1031`), again with `ctx.run_dir` in scope.
- The only test caller relying on the implicit `feature_dir.name` fallback is
  `tests/runtime/test_wp_driven_guard.py::_guard`; it already has the real run
  from `get_or_start_run`, so it can pass `run_dir`.
- Built-in guard tables (`_GUARD_TABLES`) never read `wp_driven`, and
  `software-dev` short-circuits before it (`mission == "software-dev"`), so the
  four built-in types are unaffected by construction.
- `tests/runtime/_next_mission_scaffold.scaffold_custom_analyze_mission` already
  builds an activated custom family with a real frozen DAG; the type YAML leaves
  `action_sequence` unset, so a curated-away variant is possible by passing the
  DAG steps while declaring an explicit `action_sequence` on the type.

## Open questions

- None blocking. The mismatch case (a `run_dir` that belongs to a different
  mission than `feature_dir`) is out of scope: both values derive from one
  `DecideNextContext`, and this mission does not add a cross-check. Recorded on
  the new parameter's docstring as an explicit non-goal.
