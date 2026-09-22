# Implementation Plan: Verdict-matrix RMW preservation (#4858 + #4868)

**Branch**: `fix/verdict-matrix-rmw-preservation` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/spec.md`

## Summary

Close the **verdict-matrix RMW-preservation** defect class — a verdict-recording command
silently dropping previously-committed rows from its coordination-resident matrix and exiting
success — across both verdict matrices:

- **#4858 (P0, acceptance / concurrency)**: two concurrent `acceptance-verdict` writers for
  different entries lose a committed row because the write is an unlocked read-modify-write that
  overwrites the whole matrix from a pre-check snapshot; `overall_verdict` flips fail→pass.
  **Fix (Option A)**: run the slow custom check outside the lock, then inside
  `status/locking.py::feature_status_lock(repo_root, matrix_dir.name)` re-read the on-disk
  matrix, splice in only the owned entry, and write+commit; route the shared
  `write_acceptance_matrix` through `kernel.atomic.atomic_write`.
- **#4868 (P1, issue / serial migration)**: `issue-verdict` on a coord mission migrates the
  wrong source directory on first JSON write (`issue_verdict.py::_migrate_if_needed` hands the
  primary `feature_dir` to `migrate_issue_matrix_to_json` instead of the coord-aware `read_dir`),
  so existing issue verdicts vanish. **Fix**: give `migrate_issue_matrix_to_json` an optional
  `read_dir` and read the legacy matrix from `read_dir or feature_dir`; keep the write staged on
  primary so the write-seam still materializes coord and cleans residue.

Both fixes are grounded (`research/grounding-4858.md`, `research/grounding-4868.md`) and their
test contracts hardened by two post-spec adversarial squads.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no new dependencies added
**Storage**: JSON matrix files on disk (`acceptance-matrix.json`, `issue-matrix.json`) resolved via the placement seam (primary / coordination surface); git commits via the write-seam
**Testing**: pytest (unit + integration); `.venv/bin/python -m pytest` (editable install → exercises the fix directly)
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (CLI/library)
**Performance Goals**: verdict command stays well within existing CLI budgets; the #4858 held critical section is only re-read+merge+write+commit (slow check runs outside the lock)
**Constraints**: kernel.locks only (no raw fcntl/msvcrt/filelock — `test_lock_primitive_ban.py`); atomic write via `kernel.atomic.atomic_write`; no new `--feature` CLI surface; no changes to `src/specify_cli/__init__.py`; ATDD red-first per root
**Scale/Scope**: two disjoint fix loci, ~2 source files each; no schema/API contract change; no dependency change

## Constitution Check (Charter Check)

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **Single canonical authority** ✅ — reuses the existing sanctioned primitives
  (`feature_status_lock`, `kernel.atomic.atomic_write`, the placement-seam `read_dir` resolver);
  introduces no second locking/atomic authority.
- **Architectural alignment** ✅ — judgement stays in `specify_cli`; only mechanical write/lock
  delegate to `kernel` (direction `specify_cli → kernel`, allowed). No layer violation
  (validated by the post-spec architecture lens).
- **ATDD-first (C-011 charter / Standing Order #4)** ✅ — a failing reproduction is committed as
  a distinct commit before implementation for EACH root; reviewer verifies red-on-base →
  green-on-fix per root.
- **DDD + tiered rigour** ✅ — core concurrency/preservation logic gets focused tests; the two
  matrices are separate bounded contexts kept separate.
- **Terminology canon** ✅ — no new `feature`/`--feature` surface; internal
  `feature_dir`/`feature_slug`/`read_dir` are the tolerated exception.
- **Supply-chain safety** ✅ N/A — no dependency add/upgrade/remove; nothing to vet.
- **Locking-primitive ban gate** ✅ — #4858 uses `kernel.locks` via `feature_status_lock` only.
- **Dead-symbol discipline (C-007)** ✅ — uses the live `kernel.atomic.atomic_write`; does NOT
  activate the deferred `write_if_changed` (confirmed absent), avoiding a dead-symbol red.
- **No `__init__.py` coupling (C-009)** ✅ — changes avoid `src/specify_cli/__init__.py`, so no
  version-bump/CHANGELOG coupling is forced (a CHANGELOG entry is still added for the fix).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/
├── plan.md              # This file
├── spec.md              # Hardened spec
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/           # Phase 1 output (this command)
├── checklists/requirements.md
├── research/            # grounding-4858.md, grounding-4868.md, hardened-4858-spec-draft.md
└── tracer-*.md          # design-decisions, approach, tooling-friction, squad-findings
```

### Source Code (repository root) — files this mission touches

```
src/specify_cli/
├── cli/commands/agent/
│   ├── acceptance_verdict.py     # #4858: lock + re-read + single-row splice; slow check outside lock
│   └── issue_verdict.py          # #4868: pass read_dir into _migrate_if_needed's migrate call
├── acceptance/
│   └── matrix.py                 # #4858: write_acceptance_matrix → kernel.atomic.atomic_write
└── tasks/
    └── issue_matrix_migration.py # #4868: migrate_issue_matrix_to_json gains optional read_dir

# Reused unchanged:
src/specify_cli/status/locking.py   # feature_status_lock (git-common-dir keyed)
src/kernel/atomic.py                # atomic_write

tests/
├── specify_cli/acceptance/test_acceptance_verdict_command.py   # #4858 flat + criterion concurrency
├── integration/test_accept_matrix_coord_partition.py           # #4858 coord (reuse _build_coord_mission_for_matrix)
├── integration/test_issue_verdict_coord_legacy_md_preservation.py  # #4868 NEW integration repro
└── specify_cli/cli/commands/agent/test_issue_verdict_command.py    # #4868 flat control (cite, don't rewrite)
```

**Structure Decision**: Single-project CLI. Two disjoint fix loci (acceptance vs issue), no new
modules, no new package boundaries.

## Complexity Tracking

*No Constitution Check violations — none.*

## Implementation Concerns → (translated to Work Packages by /spec-kitty.tasks)

Two independent concerns, disjoint file sets → parallelizable, each ATDD red-first:

- **Concern A (#4858, P0) — acceptance-verdict concurrency lost-update.**
  1. Red-first: deterministic serialized `read1→run2→finish1` harness (no threads) with the
     command-module-bound one-shot seam wrapper; disk-reload + fail→pass assertions; lock spy
     (key == matrix_dir.name, path under common dir); **strict order `lock.enter → read → write →
     lock.exit`** (re-read inside the lock); call-order (check before lock); atomic-write spy;
     **fail-closed-on-timeout** (patch lock to raise → no write, non-zero exit); **reported
     `overall_verdict` == disk**; flat + coord (two worktree roots) + criterion-mode variants.
     (Site the coord concurrency test in `test_acceptance_verdict_command.py`, which already
     imports `_build_coord_mission_for_matrix`; do not edit the shared fixture file.)
  2. Fix in `acceptance_verdict.py`: run the slow check outside the lock; **materialize the coord
     worktree, then acquire `feature_status_lock` with a bounded timeout (fail closed on
     timeout)**; re-read the on-disk matrix (surface == commit surface); **recompute
     criterion index / unknown-criterion from the re-read**; splice the single owned row —
     criterion by id, NI via a *replace-or-append-judged-row* helper (NOT
     `_register_negative_invariant`); write+commit; **emit `overall_verdict` from the re-read+
     spliced matrix**. In `matrix.py`: `write_acceptance_matrix` → `atomic_write` (tempfile in
     `matrix_dir`, no residue).
- **Concern B (#4868, P1) — issue-verdict wrong-source migration.**
  1. Red-first: integration repro (real write-seam) via `_build_coord_mission_for_matrix` (new
     file `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py`); seed coord
     legacy `.md` with #A; record #B; assert both survive + `migrated is True`; **spy that the
     migration's `write_issue_matrix` received `feature_dir == primary`** (mutation-tested RED vs
     the `read_dir`-as-write variant — a residue-only check is insufficient); 2nd-call
     idempotency (`migrated=False`, rows preserved); malformed-`.md` → structured
     `IssueVerdictError`.
  2. Fix: `migrate_issue_matrix_to_json(feature_dir, *, read_dir=None, ...)` reads legacy from
     `read_dir or feature_dir`; `_migrate_if_needed` passes `read_dir=read_dir`; write staging on
     primary unchanged (C-011); translate a malformed-`.md` validation failure into a structured
     `IssueVerdictError`.

## Parallel Work Analysis

### Dependency Graph

```
Concern A (#4858)  ─┐
                    ├─►  (independent, disjoint files)  ─►  aggregate review + CHANGELOG/docs
Concern B (#4868)  ─┘
```

### Work Distribution

- **Sequential work**: none between the two concerns — they touch disjoint files
  (`acceptance_verdict.py`/`matrix.py` vs `issue_verdict.py`/`issue_matrix_migration.py`).
- **Parallel streams**: Concern A and Concern B can be implemented in parallel lanes.
- **Agent assignments**: one lane per concern; no file overlap → no coordination conflict.

### Coordination Points

- **Sync**: `spec-kitty merge` consolidates both lanes into local `main` (then a topic branch +
  PR to `skupstream/main`).
- **Integration tests**: run the full blast-radius surface after both lanes land (both grounding
  reports' blast radii, union).

## Supply-Chain / Adversarial Evidence

- **Supply-chain**: N/A — no dependency add/upgrade/remove.
- **Adversarial evidence**: two post-spec squads ran (3 lenses on #4858, 2 on #4868 + fold
  coherence); all contested findings folded (`accepted`/`changed`), none dropped. A post-plan
  squad runs next per the mission's point-cut cadence, and a pre-merge squad before the PR.
