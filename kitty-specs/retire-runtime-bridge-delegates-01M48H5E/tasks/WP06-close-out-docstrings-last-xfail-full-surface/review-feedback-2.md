# WP06 review feedback (cycle 2) - reviewer: claude-reviewer (reviewer-renata)

Verdict: changes requested. One one-line docstring fix; everything else is resolved and green.

## Blocking (T024 / FR-010: false claim about current behaviour in a WP06-owned file)

1. `src/runtime/next/runtime_bridge_cores.py:21-23` (module docstring, item 2):
   "(`_check_cli_guards`, `_check_composed_action_guard`,
   `_check_requirement_mapping_ready` — all three still *reachable* at
   `runtime_bridge.<name>`, ...)". This is false since this mission removed the
   bridge's `_check_composed_action_guard` forwarder (it is in the gate's removed-name
   table): `hasattr(runtime_bridge, "_check_composed_action_guard")` is `False`.
   It matched the requested sweep regex (`REACH`) and was missed in cycle 1 too.
   Fix: say where each one is defined, for example "`_check_cli_guards` and
   `_check_requirement_mapping_ready` stay in `runtime_bridge`;
   `_check_composed_action_guard` is owned by `runtime_bridge_composition`; their
   branch-heavy decisions now live here".

## Cycle-1 items: all resolved

- `runtime_bridge_composition.py` `_resolve_step_binding`, `_composition_dispatch_inputs`, `_has_generated_docs`:
  the new wording is accurate. I checked it against the code: composition.py:171/214 call it module-globally,
  runtime_bridge.py:1856 calls `_composition._composition_dispatch_inputs`, and io.py:1455 reaches `_has_generated_docs` on the seam.
- `runtime_bridge_io.py:1175-1183` and the extra `runtime_bridge_cores.py:478-482` rewording are accurate. Both
  `_check_cli_guards` (runtime_bridge.py:816) and `_check_composed_action_guard`
  (composition.py:514, via `_rb._should_advance_wp_step`) set `wp_advance_ready`.
- `git grep -nE "compat guard|compat reach|residual delegate|native delegate|residual guard" src/runtime/next`
  finds only the history line at identity.py:8, which is fine to keep.
- Gate scaffolding removal (nit): 58 ids collected before (03788550) and after, `diff` identical. The check
  bodies are unchanged, and nothing else references the removed names.

## Broad sweep judgement (126 hits)

All the other hits are fine: unrelated senses (backward-compat, unreachable, delegated_llm, sentinel), the
mission's "residual" term for `runtime_bridge.py`, accurate ownership prose, or WP18 history comments.
The only hit that is false is item 1 above.

## Verified green

Gate + characterisation 70 passed; the gate, characterisation, composition_gate_widening, bridge_engine and bridge_io suites
163 passed; the 5 architectural gates 247 passed; ruff, format and C901 are clean; mypy has 21 errors (the baseline); all seams import;
the characterisation file is unchanged; C-001 holds (only src/runtime/next changed).
