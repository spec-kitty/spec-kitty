# Contract: runtime_bridge surface after the mission

## Kept public names (callers outside `src/runtime/next/`)

| Name | Binding | Guarantee |
|------|---------|-----------|
| `get_or_start_run` | `from runtime.next.runtime_bridge_io import get_or_start_run` | `runtime_bridge.get_or_start_run is runtime_bridge_io.get_or_start_run` |
| `build_operational_context_for_claim` | `from runtime.next.runtime_bridge_io import build_operational_context_for_claim` | `runtime_bridge.build_operational_context_for_claim is runtime_bridge_io.build_operational_context_for_claim` |

Both stay in `runtime_bridge.__all__`. Every other public name the bridge defines today is
unchanged (`query_current_state`, `answer_decision_via_runtime`, `decide_next_via_runtime`,
`QueryModeValidationError`, …).

## Removed names

The 36 names in [../data-model.md](../data-model.md), less the two above, no longer exist on
`runtime_bridge`. Accessing one raises `AttributeError`.

## Patch-point rule

A test that wants to replace a seam-owned function patches the owning seam module. Inside
`src/runtime/next/`, every call site looks the name up on its owner, so that single patch
intercepts every internal caller. Patching `runtime_bridge.get_or_start_run` /
`runtime_bridge.build_operational_context_for_claim` intercepts only callers that look the name
up on the bridge (the CLI modules), not the runtime package itself.

## Enforcement

`tests/runtime/test_bridge_no_compat_delegates.py` (new) checks, per seam: no top-level
definition of a removed name in the bridge, no `_rb.<removed name>` lookup in any seam, the two
re-export identities, and (self-mutation) that the scanner flags a synthetic forwarding module.
