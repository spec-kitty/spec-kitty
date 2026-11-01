---
title: 'ADR: Retrospective Gate as Shared Module'
description: 'One shared completion-gate function owns retrospective enforcement, so the runtime hook and status-transition surfaces cannot drift into rival implementations.'
status: Accepted
date: '2026-04-27'
doc_status: active
kind: ADR
updated: '2026-04-27T00:00:00Z'
---

## Context

The retrospective learning loop (FR-011 through FR-016) requires a lifecycle gate
that decides, for a given mission, whether the transition to `done` is permitted
given the mission's current retrospective state and resolved governance mode
(`autonomous` vs. `human_in_command`).

The gate must be consulted from two independent surfaces:

1. **`specify_cli.next`** — the canonical control loop. Every mission completion
   path runs through this surface. When the last domain step succeeds, `next`
   must check the gate before signaling mission completion.
2. **Any future status-transition surface** that refuses mission-level completion
   (e.g., a direct API caller that asks to move the mission to `done`). These
   surfaces need to apply the same mission-level mode policy without knowing the
   internals of the `next` runtime.

Three placement options were evaluated:

- **(A)** Place the gate inside `specify_cli.status.transitions`, alongside the
  existing per-WP transition matrix.
- **(B)** Bury the gate inside `specify_cli.next` (the control-loop internals).
- **(C)** Place the gate in a new dedicated module `specify_cli.retrospective.gate`
  and have both callers invoke it through a published typed API.

## Decision

The lifecycle gate lives in **`src/specify_cli/retrospective/gate.py`** as a
single source of truth (option C). It exposes one public function:

```python
def is_completion_allowed(
    mission_id: MissionId,
    *,
    feature_dir: Path,
    repo_root: Path,
    mode_override: Mode | None = None,
) -> GateDecision: ...
```

Both callers stay thin:

- `specify_cli.next._internal_runtime.retrospective_hook` calls
  `gate.is_completion_allowed(...)` immediately before signaling mission
  completion; it does not re-implement any gate logic.
- Any status-transition surface that intends to complete a mission calls the same
  function; `specify_cli.status.transitions` is not modified.

The gate itself resolves mode through `specify_cli.retrospective.mode.detect()`
(charter override > explicit flag > environment > parent process; FR-016, C-013)
and consults the mission event log to find the latest retrospective event.
The decision is deterministic: the same event log and mode signals always produce
the same `GateDecision` (NFR-008).

## Consequences

- **No logic duplication**: both `next` and any status-transition surface call
  one function; changes to gate logic land in one file and are immediately
  visible to all callers.
- **Isolated testability**: `retrospective.gate` has no dependency on `next`
  internals or on `status.transitions`. It can be unit-tested by replaying event
  log fixtures and charter fixtures without spinning up a full runtime.
- **Explicit cross-package dependency**: `specify_cli.next` and any
  status-transition surface depend on the `retrospective` package. This is an
  intentional layering: the retrospective package owns mission-level governance
  policy; `next` and `status` are callers of that policy, not its authors.
- **WP-level transitions are unchanged**: per-WP transition guards in
  `specify_cli.status.transitions` remain governed by the existing per-WP
  transition matrix. Mission-level mode policy does not bleed into that module.
- **Performance**: when `retrospective.completed` is already present, the gate
  reads at most `meta.json`, the mission event log filtered to retrospective
  events, and (optionally) the retrospective YAML for hash verification — all
  constant-bounded reads. NFR-007 (< 500 ms on completion) is achievable.

## Alternatives considered

- **Option A — gate in `specify_cli.status.transitions`**: rejected. The
  `status.transitions` module encodes per-WP lifecycle guards; inserting
  mission-mode policy there conflates two orthogonal concerns (WP-level state
  machine vs. mission-level governance). The module would need to load charter
  overrides and parse retrospective events, which are not its responsibilities.
  Future readers would be surprised to find retrospective mode-detection logic
  inside the WP transition matrix.
- **Option B — gate buried in `specify_cli.next`**: rejected. `next` is the
  canonical control loop, but it is not the only path from which a mission
  `done` transition can be initiated. A status-transition surface that needs
  to refuse completion would have to reach into `next` internals — violating
  the architectural boundary that `_internal_runtime` is next-private. The gate
  would then be duplicated, or the status surface would take on a hard dependency
  on `next`'s internal module, which is worse.

## References

- AD-001 in mission plan: `kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/plan.md` (§Architecture Decisions, AD-001)
- Gate API contract: `kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/gate_api.md`
- Mission spec FR-011–FR-016, NFR-007, NFR-008, C-013: `kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/spec.md`
