# Implementation Plan: Blocked-WP unblock path (alloc-failure recovery)

**Branch**: `fix/3937-blocked-wp-unblock` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/blocked-wp-unblock-path-01M29093/spec.md`

## Summary

Fix issue #3937 (findings F-50, F-51). A tooling/environment workspace-allocation failure during `spec-kitty implement` must leave the work package in `planned` (not manufacture an unrecoverable `blocked`), print the conflict's actionable resolution step, and the CLI's transition refusals must state the legal recovery instead of demanding a fabricated review-feedback artifact for a non-review transition. Root cause: transition policy is keyed on a single lane rather than the typed edge (source→target + cause), so `blocked` is overloaded and `→ planned` is hard-coded as "review rejection". The fix is two narrow, behavior-preserving-elsewhere edits plus honest messaging — no new lifecycle semantics.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), rich (console), existing `specify_cli.status` FSM (`wp_state.py`, `transitions.py`, `transition_pipeline.py`), `specify_cli.lanes.worktree_allocator`
**Storage**: append-only `status.events.jsonl` (event log) — sole authority for WP lane state; no schema change
**Testing**: pytest (`PWHEADLESS=1 .venv/bin/python -m pytest`) — mypy --strict, ruff
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (CLI/library)
**Performance Goals**: N/A (no hot path touched; CLI < 2s unchanged)
**Constraints**: Zero rows of `tests/status/fsm_parity_baseline.jsonl` may change (NFR-002); enumeration surfaced only on the CLI/emit refusal path, never the FSM-core string; no `blocked → in_progress` recovery driver (C-001); F-51 fixed by source-lane-scoped early-return, not guard-tuple reorder (C-002)
**Scale/Scope**: ~3 source files + their targeted tests; no new dependency

## Design (from the pre-spec research + review squad)

Anchors verified on this branch; full trace in `research.md`.

### F-50 — stop manufacturing a block on allocation failure (`R1`)
- `src/specify_cli/cli/commands/implement.py`: the `except` handler (~:1993-1998) calls `_emit_blocked_on_alloc_failure` (~:1445-1476), which emits `planned → blocked` even though `create_lane_workspace` (~:1952) ran *before* the claim (~:1966), so the WP is still `planned`.
- Change: on allocation failure, do NOT emit `blocked`; leave the WP `planned` and print the exception's `next_step` (`worktree_allocator.py:89` for `DependencyLaneMergeConflictError`; the analogous field on `PlanningCommitMergeConflictError`, ~:150-181) — an actionable resolution step, not a bare "re-run". The allocator already aborts + hard-resets and does not write `lanes.json`, so the persisted worktree is a reentrancy vehicle, not stranded state (no disk cleanup added).
- This aligns the CLI with the already-correct orchestrator-api path (`orchestrator_api/commands.py:1268-1303`), which never emits `blocked`.

### F-51 — honest, single-stage transition refusal (`R2`)
- `src/specify_cli/cli/commands/agent/tasks_transition_core.py`: `_guard_planned_rollback` (~:561-575) keys only on `target == PLANNED` and demands `--review-feedback-file` ("cannot be bypassed with --force") *before* any FSM legality check.
- Change: early-return from that guard when the **source** lane (`req.old_lane`, ~:109) is not a review-family lane, so a `blocked → planned` request falls through to FSM legality (`transition_pipeline.py:288` / `wp_state.py`), which reports the illegal edge. Do NOT reorder the `_GUARDS` tuple (would shift persist-signal prefixes at ~:716/:733) — C-002.
- Surface the legal targets: enumerate the current state's `allowed_targets()` on the **CLI/emit refusal path only**, never the machine-readable string at `wp_state.py:176/181` (that would change ~1500 `fsm_parity_baseline.jsonl` rows — NFR-002).
- `src/specify_cli/status/work_package_lifecycle.py:256`: the "cannot start implementation" reject (which a `blocked` WP hits after the PLANNED/CLAIMED/IN_PROGRESS checks) names the legal recovery command for the current state (message-only; FR-007).

## Constitution Check (charter)

*GATE: passes.*
- ATDD-first (C-011): each WP lands a RED-first acceptance test as its first commit, pinning observable STATE (NFR-001) — no `planned→blocked` event; refusal identity is illegal-transition; a fake feedback file cannot flip the verdict.
- Single canonical authority: enumeration is sourced from the authoritative per-state `allowed_targets()` — no second matrix.
- Architectural gate discipline / no fixture churn (NFR-002): change kept off the FSM-core string.
- Smallest-viable-diff + locality: two guarded edits + messaging; R3/#1711 recovery driver explicitly out of scope (C-001).
- Terminology canon: no new flags; messages use canonical terms (C-004).
- No new dependency → supply-chain section N/A.

## Project Structure

### Documentation (this mission)
```
kitty-specs/blocked-wp-unblock-path-01M29093/
├── plan.md              # this file
├── spec.md
├── research.md          # design rationale + adversarial evidence
├── data-model.md        # blocked-lane transition model
├── contracts/           # behavioral contract for the two findings
└── tasks.md             # /spec-kitty.tasks output (later)
```

### Source Code (repository root)
```
src/specify_cli/
├── cli/commands/
│   ├── implement.py                     # F-50: neuter alloc-failure blocked emit; print next_step
│   └── agent/tasks_transition_core.py   # F-51: source-lane-scoped early-return; enumerate legal targets
├── status/
│   └── work_package_lifecycle.py        # FR-007: start-implementation reject names recovery
└── lanes/worktree_allocator.py          # (read-only) source of the actionable next_step

tests/
├── integration/test_status_emit_on_alloc_failure.py   # rewrite the bug-encoding assertion as the F-50 AC test
├── status/test_transitions.py                          # F-51 refusal identity / legal-target enumeration
└── (targeted) tests/agent/…, tests/specify_cli/cli/commands/agent/…
```

**Structure Decision**: Single project. Edits are localized to the three named source files; the allocator is read-only (we consume its `next_step`).

## Parallel Work Analysis

### Dependency Graph
```
WP01 (F-50: implement.py alloc-failure) ─┐
                                          ├─→ (independent files; can be parallel lanes)
WP02 (F-51: transition refusal + reject) ┘
```

### Work Distribution
- **Sequential work**: none strictly required — the two findings touch disjoint files (`implement.py` vs `tasks_transition_core.py`/`work_package_lifecycle.py`).
- **Parallel streams**: F-50 and F-51 are independent; the tasks phase may slice them as two WPs (one lane each) or, given the small size, a single WP with two ATDD commits. Decision deferred to `/spec-kitty.tasks`.
- **Agent assignments**: python-pedro for both; reviewer-renata reviews (reviewer≠implementer).

### Coordination Points
- No shared file between the two findings → no lane-merge coordination needed beyond consolidation.
- Integration check: the required test surface (transitions, alloc-failure emit, move-task guards) plus `make test-fast` at consolidation.
