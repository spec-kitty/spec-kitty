# Implementation Plan: Cross-OS Primitive Unification

**Branch**: `feat/cross-os-primitive-unification` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/cross-os-primitive-unification-01M2T1CM/spec.md`

## Summary

Close the recurring cross-OS `PermissionError` bug class (root of #4703) **by
construction**: give the safe-delete, OS-detection, and file-lock primitives one
canonical owner each, and add DIRECTIVE_043-governed gates so they cannot
re-fork. The lock primitive is seeded from the already-sidecar-safe, pure-stdlib
`MachineFileLock` (`src/specify_cli/core/file_lock.py`) — a **move + sync-surface
extension**, validated below as import-clean for a kernel home.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11–3.13; Windows 3.13 is the #4703 environment)
**Primary Dependencies**: stdlib only for the new primitives (`msvcrt`/`fcntl`/`os`/`stat`/`asyncio`/`socket`/`json`) + the already-sanctioned `kernel.clock`; **removes** `filelock>=3.13.0` (`pyproject.toml:84`) on the full-scope path
**Storage**: filesystem (lock sidecars, managed assets); no datastore
**Testing**: pytest (unit + `tests/architectural/` gates); cross-OS parity via POSIX simulation of Windows mandatory-lock semantics (not Windows CI alone)
**Target Platform**: Windows + POSIX (the whole point)
**Project Type**: single (library/CLI monorepo, `src/kernel` … `src/specify_cli`)
**Performance Goals**: N/A — behaviour-preserving consolidation; no new hot-path cost
**Constraints**: kernel is zero-third-party-dep (C-001); enforced layer chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` (NFR-002); every new branch tested (diff-cover ≥90%), complexity ≤15 (NFR-006)
**Scale/Scope**: 3 primitive families across ~15 files; 1 safe-delete util, 1 OS seam, 1 lock primitive, 2 non-vacuous gates

### Phase-0 validation of A-04 (kernel home)

- `MachineFileLock`'s only non-stdlib import is `kernel.clock` (`file_lock.py:35`);
  moving it to `kernel/locks.py` makes that intra-kernel. **No upward import → a
  kernel home is a clean move.** Confirmed by grep; recorded in research.md.
- `src/kernel/` imports no `specify_cli` (layer rule holds).
- **Decision: home = C1 `kernel/locks.py`** (ratifies spec A-04). Adding an
  `asyncio`-bearing module to kernel requires the `landscape` fixture
  (`tests/architectural/conftest.py`), `test_layer_rules.py`, and
  `test_pyproject_shape.py` to accept it — a cross-cutting arch change handled in
  the lock WP and re-checked in the post-merge arch sweep.

## Constitution Check (Charter)

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

| Charter principle / directive | Status | Notes |
|---|---|---|
| Single canonical authority (DIRECTIVE_044) | ✅ aligned | The mission's entire thesis: one owner per primitive; chase unification, not parity. |
| Architectural alignment (DIRECTIVE_001) | ✅ aligned | Homes chosen against the enforced layer chain; kernel zero-dep respected (C-001). |
| Close defect classes by construction (DIRECTIVE_043) | ✅ central | Two non-vacuous gates (lock ban FR-010, OS-detection ban FR-012) with concrete floor + self-mutation + shrink-only allowlist, modelled on `test_clock_import_ban.py`/`test_clock_call_ban.py`. |
| DDD + tiered rigour | ✅ aligned | Core primitives (locks) get the higher rigour; more tests on the new branches. |
| ATDD-first / red-first (DIRECTIVE_041/034) | ✅ planned | Cross-OS parity + symlink-negative tests are red-first; per-defect `@regression` repros through the pre-existing entry point. |
| Campsite cleaning (DIRECTIVE_025) | ✅ planned | Tidy-first WPs (OS-seam, safe-delete) precede the functional lock work; anchor-path + `_children_tolerated` folded where the file is already touched. |
| Canonical sources (DIRECTIVE_044) | ✅ aligned | Gate template reused from the clock ban; no hand-rolled equivalents. |
| Version governance (C-006, DIRECTIVE_048) | ⚠️ watch | No `__init__.py` change is planned (argv detectors deferred, NG-01); if any WP touches it, bump `pyproject.toml` + CHANGELOG. |

No unjustified violations. No new directive minted (C-005).

## Project Structure

### Documentation (this mission)

```
kitty-specs/cross-os-primitive-unification-01M2T1CM/
├── plan.md              # This file
├── research.md          # Phase 0 output (A-04 validation, parity strategy, supply-chain note)
├── data-model.md        # Phase 1 output (primitive/gate "entities" + invariants)
├── quickstart.md        # Phase 1 output (how a caller uses each canonical primitive)
├── contracts/           # Phase 1 output (lock API contract, gate contract, safe-delete contract)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root) — surfaces this mission touches

```
src/kernel/
├── paths.py                    # promote _is_windows → public seam (FR-004)
└── locks.py                    # NEW canonical lock primitive (FR-006/007), seeded from core/file_lock.py

src/specify_cli/core/
├── safe_delete.py              # NEW canonical safe-delete util, lstat+S_IMODE (FR-001/002)
└── file_lock.py                # becomes a thin re-point/shim or is removed; MachineFileLock consumers repoint

src/specify_cli/runtime/
├── asset_preparation.py        # remove _is_windows + _force_writable copies; migrate _HELD_LOCKS locking (FR-003/005/008); fold FR-011
├── agent_skills.py             # remove safe-delete copy (FR-003)
├── home.py                     # remove _is_windows copy (FR-005)
└── bootstrap.py                # migrate _flock onto canonical primitive (FR-008)

src/specify_cli/skills/installer.py            # remove safe-delete copy (FR-003)
src/specify_cli/{tracker/credentials.py, paths/windows_migrate.py, review/pre_review_gate.py}  # migrate raw locks (FR-008)
src/specify_cli/{core/checkout_file_lock.py, status/locking.py, review/verdict_commit_queue.py,
                 auth/secure_storage/file_fallback.py, zeitgeist_client/{credentials,outbox_approval}.py}  # migrate off filelock (FR-009)

tests/architectural/
├── test_lock_primitive_ban.py      # NEW lock gate (FR-010): import + call ban, floor, self-mutation, shrink-only
└── test_os_detection_ban.py        # NEW OS-detection gate (FR-012)

pyproject.toml                       # remove filelock; accept kernel/locks.py in wheel packages + layer landscape
```

**Structure Decision**: Single-project monorepo. New canonical homes: `kernel/locks.py` (C1, lock), `kernel/paths.py::is_windows` (C1, OS seam, promoted in place), `specify_cli/core/safe_delete.py` (C2, safe-delete). Gates in `tests/architectural/`.

## Parallel Work Analysis

### Dependency Graph

```
Tidy-first, dependency-ordered (waves):

  Wave A (parallel, tidy-first, no lock dependency)
  ├─ WP: OS-detection kernel seam + gate (FR-004/005/012)   ── de-noises file_lock.py before it moves
  └─ WP: safe-delete canonical util + campsite folds (FR-001/002/003/011, SC-006)
        (no by-construction gate — see note below; FR-003 is count-only)

  Wave B (depends on Wave A OS-seam)
  └─ WP: kernel/locks.py primitive — sync+async sidecar (FR-006/007), layer/pyproject acceptance

  Wave C (depends on Wave B)
  ├─ WP: migrate stdlib-family lock sites incl. asset_preparation _HELD_LOCKS (FR-008)
  └─ WP: migrate filelock-family + retire filelock (FR-009)      ── deferral seam (A-01)

  Wave D (depends on B + shrinks as C lands)
  └─ WP: DIRECTIVE_043 lock gate — seeded fail-closed with ALL sites, shrink-only (FR-010)
         (May be authored in Wave B seeded-fail-closed, then burned down by C.)
```

### Work Distribution

- **Sequential**: OS-seam before the lock primitive (routes `file_lock.py`'s inline check through the seam *as it moves*). Lock primitive before any lock-site migration. The lock gate is seeded fail-closed early and burns down as migrations land.
- **Parallel streams**: OS-seam ∥ safe-delete (Wave A); stdlib-family migration ∥ filelock-family migration (Wave C) once the primitive exists.
- **Agent assignments**: one WP per lane; implement=sonnet (profile-loaded), review=opus (reviewer-renata). No two WPs own the same file (see the Implementation Concern Map).

### Coordination Points

- **Integration**: the lock gate is the coordination artifact — every migration WP must shrink its own allowlist entry and leave the gate green at its fold commit (per-commit greenness for rebase-merge).
- **Parity**: the cross-OS simulation test (SC-004) is authored with the lock primitive (Wave B) and each migration WP proves its site against it.

## Implementation Concern Map (owned surfaces — no overlap)

| Concern | Owning wave/WP | Primary files (owned) | FR/SC |
|---|---|---|---|
| OS-detection seam + gate | Wave A | `kernel/paths.py`, `tests/architectural/test_os_detection_ban.py`; routed edits across the zoo | FR-004/005/012, SC-002 |
| Safe-delete util + campsite (no gate) | Wave A (util); Wave C (asset_prep copy) | `specify_cli/core/safe_delete.py`, `skills/installer.py`, `runtime/agent_skills.py` (WP02); `runtime/asset_preparation.py` delete-helpers + FR-011 (WP04) | FR-001/002/003/011, SC-001/006 |
| Lock primitive | Wave B | `kernel/locks.py`, `specify_cli/core/file_lock.py` (repoint), `pyproject.toml` (wheel/landscape), `tests/architectural/conftest.py` | FR-006/007, NFR-001/002 |
| Stdlib-family lock migration | Wave C | `runtime/asset_preparation.py` (`_HELD_LOCKS`), `runtime/bootstrap.py`, `tracker/credentials.py`, `paths/windows_migrate.py`, `review/pre_review_gate.py` | FR-008, SC-003 |
| Filelock-family migration + retire | Wave C | `core/checkout_file_lock.py`, `status/locking.py`, `review/verdict_commit_queue.py`, `auth/secure_storage/file_fallback.py`, `zeitgeist_client/{credentials,outbox_approval}.py`, `pyproject.toml` (drop filelock) | FR-009, SC-003 |
| Lock ban gate | Wave B→D | `tests/architectural/test_lock_primitive_ban.py` | FR-010, NFR-003, SC-005 |

**Overlap note (`asset_preparation.py`):** the safe-delete WP owns its delete-helpers + FR-011 folds; the stdlib-lock WP owns its `_HELD_LOCKS` locking. `/tasks` must sequence these (safe-delete Wave A before lock-migration Wave C) so the file is not co-edited across concurrent lanes — a rationale-backed leeway within one file, not a no-overlap violation.

## Post-tasks squad folds (planner-priti, 2026-09-18)

- **Gate scan corpus = `src/` only** (MF-1): a deliberate divergence from the
  clock-ban template's `SCAN_ROOTS=(src,tests,scripts)`. `tests/`/`scripts/`
  legitimately exercise raw `msvcrt`/`fcntl` and inline platform checks (the lock
  parity harness *must* simulate raw locking). The gates prevent re-forking in
  *production* code; scanning tests would red on ~51 lock + ~41 OS-detection
  legitimate hits with no clean terminal state. Recorded in each gate's docstring.
- **MF-2/3 routing**: `compat/{cache,config,history,_detect/runtime}.py` +
  `auth/secure_storage/abstract.py` are routable OS-detection sites now owned by
  WP01; `_detect/runtime.py`'s `Literal["posix","windows"]` normalizer consumes
  the seam (one authority). The gate's sanctioned-raw allowlist is the
  module-scope C-module import guards ONLY; routable branches
  (`token_manager:109`→WP03, `pre_review_gate:260`→WP04) are routed, not allowlisted.
- **FR-003 is count-only, no gate** (MF-4): a re-forked safe-delete helper is
  duplication, not a crash class, and a reliable AST gate for the
  chmod-then-unlink idiom is unreliable. FR-003/SC-001 are enforced by
  copy-removal + review, verifiable only once WP02 + WP04 both land.
- **S-1 idioms**: gates ban all four (`os.name=="nt"`, `sys.platform=="win32"`,
  `platform.system()=="Windows"`, `sys.platform.startswith("win")`).
- **S-2 per-WP exemption files**: `_exemptions/lock-ban-wp04.txt` /
  `lock-ban-wp05.txt` so parallel migration WPs don't collide; orchestrator runs
  WP04→WP05 sequentially as belt-and-suspenders.
- **NFR-002 is CI-certified** (N-4): WP03's `conftest.py` landscape edit is
  cross-cutting; the full `tests/architectural/` suite must not run locally, so
  layer-integrity is certified by CI and flagged in the PR body.

## Complexity Tracking

No Charter violations to justify. The one notable structural change — adding an
`asyncio`-bearing module to the zero-dep `kernel` layer — is justified by A-04
(lower layers already *sense* locks; a C2 home fails-open to a future layer
violation) and is validated import-clean above.
