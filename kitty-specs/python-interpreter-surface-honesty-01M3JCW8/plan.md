# Implementation Plan: Python interpreter surface honesty

**Branch**: `claude/project-thread-hjiqjz` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/python-interpreter-surface-honesty-01M3JCW8/spec.md`

## Summary

Python 3.13 stopped raising from non-strict `Path.resolve()` on a symlink loop. The loop component now comes back unresolved, as if the path were fine. Guards written against 3.11/3.12 relied on that exception: the dashboard containment seam, the command-skills input observation, and about ten confinement and ownership guards the brownfield scout confirmed. On 3.13+ they quietly accept a loop, or reach a different verdict than on 3.11/3.12.

The approach has three parts:

- Restore one interpreter-invariant contract in a single kernel primitive. A symlink loop always raises `OSError(errno.ELOOP)`; everything else matches non-strict `resolve()`.
- Route the enumerated guards through the primitive, so each reaches the verdict its authors wrote (most already `except OSError` expecting the loop to land there).
- Close the class with a non-vacuous architectural gate against hand-rolled loop handling around resolution.

The declared-versus-tested guard and the advisory 3.14 job edit the same workflow and helper surface as open PR #5244. They are sequenced after it and are not part of this plan's work packages (spec C-001).

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python >=3.11`); verified locally on CPython 3.11.15, 3.12.3, 3.13.12 and 3.14.7
**Primary Dependencies**: standard library only (`pathlib`, `os`, `errno`); no new dependency
**Storage**: N/A (filesystem path resolution only)
**Testing**: pytest; red-first regression tests with real symlink loops built in `tmp_path` (skipped where `os.symlink` is unavailable); one architectural AST gate under `tests/architectural/`
**Target Platform**: Linux, macOS, Windows 10+ (Windows reports loops as `winerror 1921`, `ERROR_CANT_RESOLVE_FILENAME`)
**Project Type**: single Python project (`src/` layered packages)
**Performance Goals**: no measurable CLI latency change; at most one extra `stat` per resolution on 3.13+ (NFR-002)
**Constraints**: kernel stays a leaf (C-004); complexity ≤ 15; ruff, ruff format and mypy strict clean with no new suppressions (NFR-004); no full heavy suites in mission work (C-005)
**Scale/Scope**: 1 new kernel module, about 11 guard sites across `specify_cli` and `charter`, 1 architectural gate

## Charter Check

| Charter rule | How this plan complies |
|---|---|
| Single canonical authority / DIRECTIVE_044 | One primitive owns loop semantics. The existing `ensure_within_directory` / `ensure_within_any` seams stay the containment authority and delegate resolution to it. The hand-rolled translation in `command_installer._resolve_observed_input` is deleted, not duplicated. |
| Architectural alignment / layer rules | The primitive lives in `src/kernel/` because consumers exist in both `specify_cli` and `charter` (`org_pack_config`, `path_guard`). It imports only the stdlib. |
| ATDD / red-first (DIRECTIVE_034, ADR 2026-07-17-1) | Each site gets a real-loop test that is red on at least one interpreter before its fix. The two witnessed reds are the pre-existing entry points. Repro tests start as `@pytest.mark.regression` pinned to #3189 and are converted to plain focused tests before review. |
| Close defect class by construction (DIRECTIVE_043) | The architectural gate has a concrete floor, a self-mutation test and a reasoned shrink-only allowlist. |
| Campsite cleaning (DIRECTIVE_025) | Scoped to the touched functions only. No drive-by refactors outside the enumerated sites. |
| Tiered rigour | Containment seams (security-relevant) get paired positive and negative controls. Diagnostic-only sites (`saas_client`, `analysis_report`) get one focused test each. |
| No full heavy suites | Validation runs the touched modules' test files plus the named gate file. |

No violations; the Complexity Tracking table is not needed.

## Design

### The primitive — `kernel.resolution`

```python
def resolve_rejecting_loops(path: Path) -> Path: ...
def is_symlink_loop_error(exc: BaseException) -> bool: ...
```

`resolve_rejecting_loops` behaves like non-strict `path.resolve()`, with one change: a symlink loop anywhere in the path always raises `OSError(errno.ELOOP, ..., str(path))`.

- **3.11/3.12**: `pathlib` raises `RuntimeError("Symlink loop from ...")` with an `OSError(ELOOP)` (or Windows `winerror 1921`) as `__context__`. The primitive re-raises that as `OSError(ELOOP)`. Any other `RuntimeError` propagates untouched, so a programmer defect is never masked.
- **3.13+**: non-strict `resolve()` returns the unresolved path. The primitive then does the same post-resolve `os.stat` probe that 3.11/3.12 `pathlib` did internally. It raises `OSError(ELOOP)` only when that probe fails with ELOOP. Any other probe failure (missing path, dangling link, permission) is swallowed, preserving non-strict semantics.
- **Cost**: one `stat` per call on 3.13+. That is the call 3.11/3.12 already made inside `resolve()`, so relative to the 3.11 baseline the cost is zero (NFR-002, argued rather than counted).

`is_symlink_loop_error` is the one predicate for "this `OSError` is a loop": `errno == ELOOP` or `winerror == 1921`.

### Refusal contracts per site (spec FR-002 / FR-004)

| Site | Today, 3.11/3.12 | Today, 3.13+ | After (all interpreters) |
|---|---|---|---|
| `core/utils.ensure_within_directory` | leaks `RuntimeError` | accepts | `ValueError` refusal (documented contract) |
| `core/utils.ensure_within_any` | leaks `RuntimeError` | accepts | `ValueError` refusal |
| `dashboard/handlers/features._artifact_path_is_contained` | `False` | `True` ✗ | `False` (via seam; no code change needed) |
| `skills/command_installer._resolve_observed_input` | `OSError(ELOOP)` (hand-rolled) | returns path ✗ | `OSError(ELOOP)` via primitive; hand-rolled translation deleted |
| `skills/command_installer._ensure_project_confined` | leaks `RuntimeError` | accepts | `InstallerError("unsafe_path")` (its `except OSError` as authored) |
| `coordination/atomic_write._confine_path_to_worktree` (+ `_resolve_confined_artifact_path`) | leaks `RuntimeError` | accepts; a final-component loop symlink gets **replaced by a regular file** | `ValueError` (its `except OSError` as authored) |
| `decisions/ownership._mission_dirs` | crashes (`RuntimeError`) | loop counted absent (intended) | absent (ELOOP handled by the existing errno split) |
| `decisions/ownership._read_ledger` | crashes | `unreadable=True` (intended) | `unreadable=True` |
| `charter/.../org_pack_config.resolve_relative_path_within_root` | leaks `RuntimeError` | accepts | `OrgPackSubdirEscapeError` |
| `charter/.../path_guard.PathGuard._assert_allowed` | leaks `RuntimeError` | allows | `PathGuardViolation` |
| `upgrade/skill_update.is_external_symlink` | crashes | `False` | `False` (its `except OSError` as authored) |
| `analysis_report._relativize_or_raise` | leaks `RuntimeError` | returns a path | `PathRelativizationError` |
| `tracker/saas_client` project root | `SaaSTrackerClientError` | constructs | `SaaSTrackerClientError` |

Each `ensure_within_*` caller is audited for the new `ValueError` (spec FR-002): `upgrade/skill_update:164`, `core/owned_mission:35,104`, `merge/bookkeeping_projection:90,123,178,205`, `coordination/atomic_write:348,403`, `invocation/writer:130`, `status/store:205`, `migration/backfill_runtime_state:1595,1606`, `migration/runtime_state_cutover:571,582`. On 3.11/3.12 every one of them already received an exception (`RuntimeError`) for a loop, so moving to `ValueError` narrows what they receive rather than introducing a new failure. The audit records, per caller, whether `ValueError` is caught and what the operator sees.

### The gate — `tests/architectural/test_loop_aware_resolution.py`

- **Predicate**: an AST `Try` node under `src/` whose body calls an attribute or function named `resolve` or `realpath`, and which has a handler that catches `RuntimeError` (bare or in a tuple) or whose body references `ELOOP`.
- **Exclusions**: the primitive's own module. A reasoned, shrink-only allowlist covers sites the scout confirmed interpreter-identical, each with a one-line reason. `O_NOFOLLOW` `ELOOP` checks do not match, because their try-body is an `open`, not a resolution.
- **Floor (non-vacuity)**: the scanner must see at least 8 `resolve_rejecting_loops` call sites and at least 100 `resolve`/`realpath` call sites. A stale allowlist entry (no longer matching) fails.
- **Self-mutation**: inject a synthetic offender module in `tmp_path` and assert the scanner reports it.

### Sequenced out: surface guard and advisory 3.14 job

These land after #5244, reusing its `_setup_python_version` / `_sync_step_pins_python` helpers and its shard roster (post-spec squad F1/F2). The PR body records the design the post-spec squad agreed:

- a gating/advisory classification;
- an advisory job key outside the `interpreter-matrix*` namespace;
- a literal `continue-on-error: true`;
- no escalation;
- a `$GITHUB_STEP_SUMMARY` verdict;
- a named subset.

## Project Structure

### Documentation (this mission)

```
kitty-specs/python-interpreter-surface-honesty-01M3JCW8/
├── spec.md
├── plan.md
├── research.md
├── tracer/  (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md / tasks/  (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/kernel/resolution.py                              # NEW primitive
src/specify_cli/core/utils.py                         # ensure_within_directory / ensure_within_any
src/specify_cli/skills/command_installer.py           # _resolve_observed_input, _ensure_project_confined
src/specify_cli/coordination/atomic_write.py          # _confine_path_to_worktree, _resolve_confined_artifact_path
src/specify_cli/decisions/ownership.py                # _mission_dirs, _read_ledger
src/charter/offering/drg/org_pack_config.py           # resolve_relative_path_within_root
src/charter/activation/synthesizer/path_guard.py      # PathGuard._assert_allowed
src/specify_cli/upgrade/skill_update.py               # is_external_symlink
src/specify_cli/analysis_report.py                    # _relativize_or_raise
src/specify_cli/tracker/saas_client.py                # project-root resolution
tests/kernel/test_resolution.py                       # NEW
tests/architectural/test_loop_aware_resolution.py     # NEW gate
tests/<mirror of each touched module>                 # per-site loop tests
```

**Structure Decision**: single project. The new code goes in `src/kernel/`, and edits stay inside the enumerated functions.

## Implementation Concern Map

### IC-01 — Interpreter-invariant loop-aware resolution primitive

- **Purpose**: one canonical definition of "resolve, but a loop is always `OSError(ELOOP)`".
- **Relevant requirements**: FR-001, NFR-001, NFR-002, C-004
- **Affected surfaces**: `src/kernel/resolution.py`, `tests/kernel/test_resolution.py`, `src/kernel/README.md`
- **Sequencing/depends-on**: none
- **Risks**: the `__context__` shape differs on Windows (`winerror`), so the predicate covers both. The test must behave the same on 3.11 and 3.14.

### IC-02 — Containment seams and the two witnessed divergences

- **Purpose**: fix the security-relevant seams and turn the two witnessed 3.13 reds green.
- **Relevant requirements**: FR-002, FR-003
- **Affected surfaces**: `core/utils.py`, `skills/command_installer.py`, their tests, the existing `tests/dashboard/test_artifact_containment.py` and `tests/specify_cli/tool_surface/providers/test_command_skills.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the caller audit for the `ValueError` refusal.

### IC-03 — Remaining enumerated guards

- **Purpose**: bring the other scout-confirmed guards to one verdict.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `coordination/atomic_write.py`, `decisions/ownership.py`, `charter/offering/drg/org_pack_config.py`, `charter/activation/synthesizer/path_guard.py`, `upgrade/skill_update.py`, `analysis_report.py`, `tracker/saas_client.py`
- **Sequencing/depends-on**: IC-01; independent of IC-02
- **Risks**: `ownership.py` carries load-bearing ordering comments, so it must keep them. `saas_client`'s existing mocked `RuntimeError` test must stay meaningful.

### IC-04 — Class-closing architectural gate

- **Purpose**: stop new hand-rolled loop handling around resolution.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `tests/architectural/test_loop_aware_resolution.py`
- **Sequencing/depends-on**: IC-02, IC-03 (the allowlist is computed on the migrated tree)
- **Risks**: over-matching legitimate `except (OSError, RuntimeError)` sites that are identical across interpreters. Each gets a reasoned allowlist entry or migrates.
