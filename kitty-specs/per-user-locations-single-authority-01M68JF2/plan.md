# Implementation Plan: One authority for per-user cache and state locations

**Branch**: `issue-6488-per-user-locations-single-authority` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/per-user-locations-single-authority-01M68JF2/spec.md`

**Note**: Discovery research is in [research.md](research.md); it carries the six
verified `platformdirs` 4.9.6 behaviours this plan relies on. The planner has no
outstanding questions: the operator triage on #6488 fixes the rule, the scope list and
the cleanup policy, and this host is Linux, so the macOS and Windows branches are pinned
by faked platform seams (spec C-005).

## Summary

Six callers resolve per-user cache, state and config directories and disagree: three use
the `kernel.user_dirs` XDG-only helpers, two call `platformdirs` directly, and one uses
the state helper whose fallback is `~/.cache`. On macOS that splits the upgrade, pack and
service caches from the upgrade-nag cache into two trees. The plan makes
`kernel.user_dirs` the single authority, implementing `platformdirs` semantics (the
operator's ruling) with an explicitly selected platform class so every branch is testable
on a Linux host; routes all six callers through it; deletes the two unreachable
`ImportError` fallbacks and the `windows_local_appdata=False` opt-out that let callers
diverge; discards the pre-convergence locations once per CLI start without ever touching
a path that is current for any kind; and adds one convergence test that fails when any
caller reinvents the rule.

## Technical Context

**Language/Version**: Python 3.11 (project floor; `pyproject.toml` `requires-python`), ruff + mypy clean under the repo's `ruff.toml`.
**Primary Dependencies**: `platformdirs>=4.9.2` (already a hard dependency, `pyproject.toml:63`); no new dependency; kernel layer keeps `platformdirs` as its only third-party import.
**Storage**: Per-user filesystem only — the upgrade-check cache, the upgrade-nag cache, the open-packs cache, the service-asset cache, the runtime-cutover marker and `upgrade.yaml`. No database, no network.
**Testing**: pytest with `pytest.mark.unit`/`fast`; platform branches faked through `kernel.paths.is_windows()`, `sys.platform` and the environment (`tests/kernel/_user_dirs_pins.py` already fakes this seam). Mutation proof for the convergence test (revert one caller at a time).
**Target Platform**: Linux, macOS, Windows. CI runs Linux; the macOS and Windows branches are exercised by faked seams, which is why the authority must select its `platformdirs` class explicitly instead of relying on import-time platform detection.
**Project Type**: single project — `src/kernel/` (authority and cleanup), `src/specify_cli/`, `src/charter/`, `src/runtime/` (callers), `tests/`.
**Performance Goals**: resolution stays a pure environment read (no stat, no mkdir); cleanup adds at most one `stat` per legacy candidate and runs once per process; the existing CLI startup performance tests stay green.
**Constraints**: never delete a directory that is current for any kind; never follow a symlink out of the enumerated roots; never delete through a git checkout; cleanup failures never change a command's exit code.
**Scale/Scope**: 6 callers, 3 directory kinds, 4 legacy candidates, ~9 source files touched, ~7 test files (5 rewritten pins + 2 new).

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule (`.kittify/charter/charter.md`, `AGENTS.md`) | Status |
|---|---|
| Single canonical authority | **Pass** — the whole Mission removes five competing implementations and leaves one, in `kernel.user_dirs`. |
| Architectural alignment / kernel layer rule | **Pass** — `kernel/` gains one module that imports only stdlib, `kernel.*` and `platformdirs`; `tests/architectural` allowlists are unchanged (NFR-001). |
| ATDD-first / red-first | **Pass** — the convergence test is written first and must be red on the pre-fix tree (one caller group resolves `~/.cache/spec-kitty` on macOS while another resolves `~/Library/Caches/spec-kitty`). |
| Locality of change (`DIRECTIVE_024`) | **Pass** — every edit is at a resolution call site or in the module that owns resolution; no caller's own logic changes. |
| Boy-scout rule (`DIRECTIVE_025`) | **Pass** — the dead fallbacks, the zombie `windows_local_appdata` opt-out and the false docstring are in-scope debt named by the issue. |
| Terminology canon (Mission vs Feature) | **Pass** — product vocabulary unchanged; no new domain term is introduced ("per-user directory kind", "legacy location" are used descriptively in the spec only). |
| Pre-existing Failure Reporting Rule | **Pass** — the PR cites the batch's known reds (#6798, #6801, #6816, #5927) in `## Deferred` if any appear, and files nothing new unless a new red appears. |
| Standing order: no full heavy suites in mission | **Pass** — targeted test modules only; CI owns the full sweep. |
| Standing order: proof trail / tracer files | **Pass** — `traces/` records the approach, design decisions and tooling friction as the work proceeds. |
| Documentation Standards | **Pass** — changelog entry plus the three how-to pages that name a cache path. |
| Dual-source-of-truth ban | **Pass** — the plan's acceptance test asserts *equality between callers*, which is the invariant, not a copy of the paths. |

No violations. `## Complexity Tracking` is therefore empty by design.

## Project Structure

### Documentation (this mission)

```
kitty-specs/per-user-locations-single-authority-01M68JF2/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 (platformdirs behaviour, moves, decisions)
├── data-model.md        # Phase 1: the directory kinds, callers, legacy locations, invariants
├── quickstart.md        # Phase 1: how to verify the convergence and the move by hand
├── traces/              # approach.md, design-decisions.md, tooling-friction.md
└── tasks/               # Phase 2 (work packages)
```

`contracts/`: **none**. The Mission defines no externally visible interface: the
resolution functions are internal Python callables, and the only observable effect is a
filesystem path. `meta.json` records `"contracts": "none"` with a rationale, as the plan
prompt requires for interface-free Missions.

### Source Code (repository root)

```
src/
├── kernel/
│   ├── user_dirs.py            # REWRITTEN: the single authority (cache/state/config)
│   ├── user_dirs_legacy.py     # NEW: legacy roots + bounded, best-effort discard
│   ├── service_artifacts.py    # cache caller -> authority
│   └── tree_removal.py         # reused as-is (ownership proof for the discard)
├── charter/offering/packs/
│   └── pack_fetch.py           # cache caller -> authority
├── runtime/next/
│   └── _runtime_pkg_notice.py  # state caller -> authority, docstring corrected
└── specify_cli/
    ├── __init__.py             # startup housekeeping: register the discard owner
    ├── core/upgrade_notifier.py# cache caller -> authority
    └── compat/
        ├── cache.py            # -> authority; dead fallback deleted
        └── config.py           # -> authority (config); dead fallback deleted

tests/
├── kernel/
│   ├── _user_dirs_pins.py      # shared fake-platform fixture (extended)
│   ├── test_user_dirs.py       # REWRITTEN: branch pins per platform/kind
│   ├── test_user_dirs_convergence.py  # NEW: red-first divergence guard
│   ├── test_user_dirs_legacy.py       # NEW: discard bounds and safety
│   └── test_service_artifacts.py      # cache-root pin updated
├── charter_offering/test_pack_fetch_cache_root.py  # pin updated
├── core/test_upgrade_probe_and_notifier.py         # pin updated
├── next/test_runtime_pkg_notice_unit.py            # pin updated
└── specify_cli/compat/test_config.py               # fallback-path test removed/retargeted
```

**Structure Decision**: the repository's existing split is respected — the authority and
its cleanup live in `kernel/` (the lowest layer, which is where #6481 put the helper), and
every caller keeps its own file. No caller imports another caller. `specify_cli/__init__.py`
is the only place the discard is wired in, because that file already owns per-invocation
startup housekeeping via `prepare_startup_assets`.

## Design decisions carried from research

- **D1** — the authority returns the *full* app directory (`.../spec-kitty`); callers append
  only their own subpath. The app name appears once in the codebase.
- **D2** — `platformdirs` semantics with `appauthor=False`, matching
  `kernel.paths.get_kittify_home()` and `specify_cli.paths.windows_paths`, so the Windows
  cache is `%LOCALAPPDATA%\spec-kitty\Cache` and not the doubled
  `%LOCALAPPDATA%\spec-kitty\spec-kitty\Cache`.
- **D3** — the platform class (`Windows`/`MacOS`/`Unix`) is constructed explicitly from
  `kernel.paths.is_windows()` and `sys.platform`, because `platformdirs` binds its class at
  import time and a Linux host could otherwise not exercise macOS at all.
- **D5** — cleanup skips any candidate that is the current directory of *any* kind; on
  Linux this makes the whole step a no-op, which is what keeps `~/.cache/spec-kitty` (the
  live, shared pack cache) safe.
- **D6** — the discard is a fourth owner in `prepare_startup_assets`, not a side effect of
  the resolvers, so resolution stays a pure environment read.

## Risk and rollback

| Risk | Mitigation |
|---|---|
| Cleanup deletes live data | D5's "current for any kind" guard plus `remove_tool_owned_tree`'s in-root and no-git-checkout proof plus a symlink refusal; a test plants both a legacy root and a current root on one fixture and asserts one disappears and one survives. |
| A future caller re-diverges | The convergence test enumerates callers explicitly and is proven by mutating each caller back to a hand-rolled rule. |
| macOS/Windows pinned wrongly from a Linux host | The pins read `platformdirs`' own class outputs, so a `platformdirs` upgrade that changes a layout fails the pin instead of shipping a surprise. |
| Moving files breaks a user mid-upgrade | The moved files are disposable caches and one re-showable marker; the changelog names the new paths and says nothing is migrated. |
| Rollback | Every change is additive or a straight substitution at a call site; reverting the branch restores the #6481 behaviour exactly, and no state is written that a revert cannot ignore. |

## Phase 0 — Research (complete)

Consolidated in [research.md](research.md): D1–D7, the verified `platformdirs` 4.9.6
table, the per-platform before/after move table, and the four open questions (all
resolved). No `NEEDS CLARIFICATION` remains.

## Phase 1 — Design and artifacts (complete)

- [data-model.md](data-model.md) — the three kinds, the six callers, the four legacy
  candidates and the invariants the discard must hold.
- [quickstart.md](quickstart.md) — hand verification of the convergence, the macOS move
  and the discard, on a Linux host.

## Implementation Concern Map

**IC-01 — The authority.** `kernel/user_dirs.py` returns cache, state and config
directories with the platformdirs rule and an explicit platform class; the
`windows_local_appdata` opt-out is deleted. Owns FR-001, FR-002, FR-004, FR-008.

**IC-02 — Caller convergence.** Six call sites stop composing their own paths. Owns
FR-003, FR-007, FR-011 (docstring half).

**IC-03 — Platform and divergence pins.** The rewritten branch pins and the new
convergence guard, including the mutation proof. Owns FR-005, FR-006.

**IC-04 — Legacy discard.** The new removal module, its wiring into the startup owners,
and its bounds. Owns FR-009, FR-010.

**IC-05 — Docs and changelog.** The `[Unreleased]` entry, the three how-to pages, and the
docs freshness check. Owns FR-011 (docs half) and SC-005.

IC-01 and IC-02 are sequential (the callers need the authority's shape); IC-03 depends on
both; IC-04 depends on IC-01 only; IC-05 lands last. Nothing here justifies more than four
work packages.
