# Implementation Plan: Remote-only branch recovery remedy

**Branch**: `kitty/mission-remote-only-branch-remedy-01M7X5Z5` (lands on `issue-5287-remote-only-coord-remedy`) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/remote-only-branch-remedy-01M7X5Z5/spec.md`

## Summary

One pure remedy builder in `mission_runtime/coord_remedy.py` composes the canonical remote-only steps from local-only branch facts (resolved remote, tracking-ref presence). Three hand-written texts (the unmaterialized-coordination refusal's remote arm, the coordination doctor's remote-only steps, the coordination write refusal) delegate to it. The status read door classifies a failed ref read of a branch with no local head as remote-only and raises a new subtype of the unreadable-ref error carrying that remedy, at both ref sources (coordination branch, Mission topic branch). No new read source, no network contact.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); git via `kernel.git` (`kernel.git.remote.resolve_remote`, `tracking_ref`, `configured_remotes`, `kernel.git` runner)
**Storage**: git refs and config (read only)
**Testing**: pytest; fixtures `tests/_factories/coord_mission.py::make_prefix_coord_mission(..., remote_only=True)`; red-first ATDD per WP
**Target Platform**: Linux, macOS, Windows (cross-platform CLI)
**Project Type**: single
**Performance Goals**: 0 added git subprocesses on a healthy status read (classification runs only on the failure path)
**Constraints**: no remote contact (ADR 2026-10-06-3); one declared status source per cell, no fallback (ADR 2026-11-06-2); layer direction `kernel <- … <- mission_runtime <- specify_cli` with no ledger growth
**Scale/Scope**: ~5 source modules, ~8 test files

## Charter Check

- Single canonical authority: one builder replaces three hand-written remedy copies. PASS.
- Architectural alignment: builder in `mission_runtime`, imports `kernel` only; `specify_cli` imports it downward. PASS.
- ATDD-first: each WP starts with a red acceptance test through the pre-existing entry point (CLI `agent tasks status`, `CoordinationWorktreeUnmaterialized.for_mission`). PASS.
- Terminology: "remote-only branch", "Mission topic branch"; no "sync"; no bare "primary". PASS.
- Gates: `test_layer_rules.py`, `test_status_read_single_door.py`, `test_remote_contact_owner.py` must stay green with no allowlist growth. PASS (planned).
- ADR: a short Amendment to ADR 2026-11-06-2 "Ref reader" names the subtype. Within operator ruling 1.

## Project Structure

### Documentation (this mission)

```
kitty-specs/remote-only-branch-remedy-01M7X5Z5/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/mission_runtime/coord_remedy.py                     (new: facts + pure text)
src/mission_runtime/write_target_degrade.py             (remote arm → builder)
src/specify_cli/coordination/surface_resolver.py        (_compose_next_step remote arm → builder)
src/specify_cli/cli/commands/_coordination_doctor.py    (_coord_worktree_missing_remote_only_steps → builder)
src/specify_cli/coordination/status_service.py          (StatusSurfaceRefRemoteOnly subtype + code)
src/specify_cli/status/read_surface.py                  (classify at _coord_ref_decision prefetch and _ref_text)
docs/adr/4.x/2026-11-06-2-one-status-read-contract.md   (Amendment)
docs/changelog/unreleased/                              (fragment)
```

**Structure Decision**: existing single-project layout; one new module.

## Complexity Tracking

No charter violations. Design choice: `CoordState` is not extended (49 uses, 14 probe callers); the remote-only split is decided at the single ref-read failure point.

## Implementation Concern Map

### IC-01 — Canonical remote-only remedy

- **Purpose**: compose one truthful remedy from local branch facts and make the three remedy-emitting surfaces use it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005
- **Affected surfaces**: `mission_runtime/coord_remedy.py`, `surface_resolver.py`, `_coordination_doctor.py`, `write_target_degrade.py`; tests incl. the doctor golden.
- **Sequencing/depends-on**: none
- **Risks**: golden churn; the doctor's bare `git fetch` becomes `git fetch <remote> <b>`.

### IC-02 — Typed remote-only refusal at the status read door

- **Purpose**: a failed ref read of a branch with no local head raises `StatusSurfaceRefRemoteOnly` (code `STATUS_SURFACE_REF_REMOTE_ONLY`) carrying the IC-01 remedy.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009
- **Affected surfaces**: `status_service.py`, `read_surface.py`, ADR amendment, changelog; tests in `tests/status/`, `tests/coordination/`, the tasks-status CLI seam, the `next` board query.
- **Sequencing/depends-on**: IC-01
- **Risks**: a subclass must keep every `except StatusSurfaceRefUnreadable` working; the classification must not fire for a corrupt local ref.
