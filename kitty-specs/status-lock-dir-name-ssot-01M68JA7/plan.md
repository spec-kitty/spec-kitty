# Implementation Plan: Status lock directory name single-source

**Branch**: `issue-6516-status-lock-dir-name-ssot` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/status-lock-dir-name-ssot-01M68JA7/spec.md`
**Input**: Mission specification from `kitty-specs/status-lock-dir-name-ssot-01M68JA7/spec.md`, grounded on issue spec-kitty/spec-kitty#6516.

## Summary

The runtime-state directory name (`".spec-kitty"`) is spelled by hand in
`src/specify_cli/status/locking.py` (as `_NON_GIT_LOCK_HOME`, #6367) and in
`src/specify_cli/review/lock.py` (as `LOCK_DIR`). Both name a **repository-**
local runtime directory, not the user-global home, so both are currently
exempted from the runtime-home audit gate — the `status/locking.py` exemption
added by #6582 is the blind allowlist #6516 rejects.

The plan names the directory once, in the existing runtime-state path authority
(`src/specify_cli/paths/windows_paths.py`, the gate's sanctioned keystone), has
`get_runtime_root()` itself use that constant, and re-points both consumers at
it. No path changes: the lock locations, the review lock, and the global home
all resolve to the same strings as today. The two audit-gate exemptions are
deleted, and a new assertion scans with an empty allowlist so the `status`
exemption cannot be restored without going red.

## Technical Context

**Language/Version**: Python 3.11 (repository minimum; the touched modules are `from __future__ import annotations` code)
**Primary Dependencies**: stdlib only (`pathlib`), plus `platformdirs` already imported by `specify_cli.paths.windows_paths`; no new dependency
**Storage**: filesystem paths only — no database, no state store
**Testing**: pytest (`tests/audit/`, `tests/status/`, `tests/review/`, `tests/paths/`), ruff (`check` + `format --check`), mypy
**Target Platform**: cross-platform CLI (POSIX + Windows), so the name constant must not assume a separator or a home layout
**Project Type**: single Python package tree (`src/specify_cli`, `src/kernel`, `src/charter`)
**Performance Goals**: none — module-level constants and one function body; no new I/O, no new imports at call time
**Constraints**: zero behaviour change in lock placement (C-001); `_HOME_LITERAL_ALLOWLIST` must shrink and never grow (C-002); `paths/windows_paths.py` stays an import leaf (NFR-001)
**Scale/Scope**: 2 source modules converted, 1 constant added to the authority, 1 audit test module extended, 0 test assertions changed

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Verdict |
| --- | --- |
| Single canonical authority | PASS — the constant moves *toward* one owner, out of two call sites. |
| ATDD-First Discipline (red before fix) | PASS — the red step is removing the #6582 exemption and watching the existing gate fail on `status/locking.py:65`; no new acceptance surface is invented. |
| Architectural gate discipline / gate non-vacuity | PASS — the guard shrinks (2 exemptions drained, 0 added); an allowlist-bypassed scan pins the exemption out of existence (tactic `architectural-gate-non-vacuity`, "shrink-only allowlist"). |
| `DIRECTIVE_044` (one source per literal) | PASS — the literal becomes a named constant in the module that already owns the runtime-state path. |
| Locality of change / smallest viable diff | PASS — three source edits, one test addition, no public API renaming (`LOCK_DIR` keeps its name; `_NON_GIT_LOCK_HOME` is private). |
| Terminology canon (Mission vs feature) | PASS — no new user-facing prose beyond the changelog entry. |
| No behaviour change without a requirement | PASS — C-001 forbids moving the lock; the plan only changes where the name comes from. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS — targeted files only (below), no whole-repo run. |

No violations, so **Complexity Tracking** stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/status-lock-dir-name-ssot-01M68JA7/
├── spec.md              # mission specification
├── research.md          # discovery findings (D1–D5)
├── plan.md              # this file
├── data-model.md        # entities + invariants for the two constants
├── quickstart.md        # how to verify the change by hand
└── tasks.md             # written by the tasks step
```

No `contracts/` — this mission introduces no interface, wire format or CLI
surface; `meta.json` records `"contracts": "none"` with the rationale, so
`spec-kitty accept` waives the directory.

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── paths/
│   │   ├── __init__.py           # re-export the new constant
│   │   └── windows_paths.py      # OWNER: names the runtime-state directory once
│   ├── status/
│   │   └── locking.py            # consumer: non-git lock fallback directory
│   └── review/
│       └── lock.py               # consumer: worktree review lock directory
└── kernel/
    └── paths.py                  # unchanged (allowlisted kernel-floor mirror)

tests/
├── audit/test_no_legacy_path_literals.py   # exemption drained + bypass-scan pin
├── status/test_lock_fallback_never_mints_marker.py  # unchanged assertions
├── review/                                  # unchanged assertions
└── paths/                                   # runtime-root parity/contract tests
```

**Structure Decision**: single Python package tree; the change stays inside
`src/specify_cli/paths`, `src/specify_cli/status` and `src/specify_cli/review`,
with the audit gate as the structural pin. `src/kernel/paths.py` keeps its own
allowlisted default-home fallback (a separate kernel-floor mirror pinned to the
same value by `tests/kernel/test_runtime_root_resolver_parity.py`) — collapsing
it is a different boundary and out of scope.

## Complexity Tracking

*No Charter Check violations, so this section stays empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.

### IC-01 — Name the runtime-state directory once, in its owning module

- **Purpose**: Give the runtime-state directory a single named owner so no other
  module re-types it, without changing any resolved path.
- **Relevant requirements**: FR-002, FR-003, NFR-001
- **Affected surfaces**: `src/specify_cli/paths/windows_paths.py`,
  `src/specify_cli/paths/__init__.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: `windows_paths.py` is a documented leaf — the constant must be a
  plain `str`, no import added. Adding it to `__all__` is required so consumers
  import from the package facade, not a private module path.

### IC-02 — Re-point the two repository-local consumers

- **Purpose**: Delete the hand-rolled literals from the status lock fallback and
  the review lock while keeping the values, the public names and the behaviour
  identical.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-006, C-001, SC-003, SC-005
- **Affected surfaces**: `src/specify_cli/status/locking.py`,
  `src/specify_cli/review/lock.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `LOCK_DIR` is imported by `cli/commands/agent/workflow.py` and four
  test modules; its *name* must not change, only its value source. The status
  module's constant is private and only referenced in its own docstrings.

### IC-03 — Drain the audit-gate exemptions and pin them out

- **Purpose**: Put both converted modules back under the runtime-home guard and
  make the exemption impossible to re-add silently.
- **Relevant requirements**: FR-001, FR-005, C-002, SC-001, SC-002, SC-004
- **Affected surfaces**: `tests/audit/test_no_legacy_path_literals.py`
- **Sequencing/depends-on**: IC-02 (the red step runs first: remove the entries,
  watch the gate fail on both modules, then land IC-01/IC-02)
- **Risks**: the guard's non-vacuity pin must stay honest — the bypass scan
  asserts exactly the canonical-owner modules remain and nothing new (including
  `status/locking.py`) appears. `kernel/paths.py` keeps its exemption: it is the
  kernel-floor mirror of the same default, not a consumer copy.

### IC-04 — Changelog, docs and the deferred follow-up

- **Purpose**: Record the user-visible (operator-visible) outcome and hand the
  issue's CI-routing half to the maintainer as a filed follow-up.
- **Relevant requirements**: C-003
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`; a new GitHub issue for
  per-PR routing of `tests/audit/**`
- **Sequencing/depends-on**: IC-03
- **Risks**: the changelog entry must stay under 1,200 characters, lead bold and
  impact-first with `(#6516)`, and must not claim the routing gap is fixed.
