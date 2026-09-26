# Implementation Plan: Terminus Projection Driver-Replay Attribution

**Branch**: `fix/terminus-projection-driver-replay` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/terminus-projection-driver-replay-01M3EC1K/spec.md`

## Summary

Fix #5038: the DEFAULT-squash projection proof false-REFUSEs a legitimate, lossless union of a
coord-partition bookkeeping path (edited on both the target and an approved lane) by demanding
`coord_bytes == target_bytes`. Replace that byte-equality check with **driver-replay attribution** —
prove the landed blob byte-equals the registered merge driver's own deterministic output from
`(%O = checkpoint blob, %A = pre-merge-target blob, %B = coord blob)`. This PASSes a legitimate
driver union (flipping `test_5038_p1`) while still REFUSing a landed blob that is not the driver's
output (genuine coord-content loss/tampering — the re-grounded `test_5038_p2` floor). The
attribution-axis product-content 3-way residual (#5021-r2) is soundly unfixable and stays a
strict-xfail with a narrowed reason plus a dedicated tracked issue.

Approach is fully grounded by Phase R (3 profile-loaded opus lenses; see [research.md](./research.md)).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git (invokes the `spec-kitty merge-driver-*` union drivers via `.gitattributes`); typer/rich (CLI); pytest; mypy --strict; ruff. No new third-party dependency.
**Storage**: git object store / working tree (blobs read via `git show`, subprocess byte-reads)
**Testing**: pytest — real-CLI terminus repros (`tests/terminus/`), reconciliation/executor units (`tests/merge/`, `tests/coordination/`); `PWHEADLESS=1 .venv/bin/python -m pytest`
**Target Platform**: Linux/macOS/Windows dev + CI (cross-platform CLI)
**Project Type**: single (CLI/library — `src/specify_cli/merge/`)
**Performance Goals**: merge stays within the <2s CLI target for typical projects; probe is O(#projected paths), each a bounded blob read + one driver invocation
**Constraints**: `coord==target` byte-check replaced by driver-replay; fail-closed on unevaluable probe; never green-wash the floor (charter SO#9); `executor.py`/`bookkeeping_projection.py`/`git_probes.py` are `[tool.ruff.format].exclude` (surgical edits, no reformat); `reconciliation.py` normally format-gated
**Scale/Scope**: ~2 source files edited (`bookkeeping_projection.py` proof helper + a small driver-replay probe; `executor.py` assertion call-site), plus test re-grounding; complexity ≤15/function

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (DIRECTIVE_044)**: the driver-replay probe reuses the EXISTING registered `spec-kitty merge-driver-*` commands (the same code git invokes during the squash) — no second resolution authority is introduced. PASS.
- **Architectural alignment (DIRECTIVE_001)**: the probe lives at the projection seam (`merge/bookkeeping_projection.py`) / probe layer (`merge/git_probes.py`), consistent with the existing partition (projection axis = bookkeeping paths; attribution axis = product paths). PASS.
- **ATDD-first / red-first (DIRECTIVE_041, C-011)**: `test_5038_p1` is RED (strict-xfail) through the real `spec-kitty merge` CLI on the base and flips GREEN after the fix; the re-grounded `test_5038_p2` is committed to be RED-on-loss before the proof change lands. PASS by construction.
- **Architectural gate discipline (DIRECTIVE_043)**: the fix preserves the fail-closed floor (unevaluable probe → REFUSE) and the product-content data-loss guard (untouched attribution axis). The 13 guardian tests are the non-vacuity floor. PASS.
- **Red-main / honest-red (SO#9, ADR 2026-07-17-1)**: re-grounding `test_5038_p2` is authorized ONLY by the operator ruling (`DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`) that its byte-equality premise is disproven for union-driver paths, and only onto a genuinely-lossy scenario. #5021-r2 stays honest xfail. PASS.
- **Readable/consistent PRs (DIRECTIVE_046)**: small, logically-sliced commits on a `fix/` branch; non-draft PR to `main`; operator merges. PASS.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/terminus-projection-driver-replay-01M3EC1K/
├── plan.md              # This file
├── research.md          # Phase 0 — Phase R consolidation
├── data-model.md        # Phase 1 — the driver-replay probe contract
├── quickstart.md        # Phase 1 — how to reproduce & verify
├── tracers/             # 3 mission tracer files (SO#3)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/merge/
├── bookkeeping_projection.py   # projected_content_matches_target → driver-replay proof (EDIT; format-excluded, surgical)
├── executor.py                 # _assert_squash_projected_content_landed call-site (EDIT if needed; format-excluded, surgical)
├── git_probes.py               # candidate home for a reusable driver-replay/registered-driver probe helper (EDIT; format-excluded, surgical)
└── reconciliation.py           # UNCHANGED for the fix; only #5021-r2 xfail-reason narrowing lives in its test (format-gated normally)

src/specify_cli/cli/commands/merge_driver.py   # the deterministic driver impls to replay (READ / reuse; do not fork logic)

tests/
├── terminus/test_repro_5038.py               # P1 flips green; P2 re-grounded (EDIT)
├── merge/test_reconciliation.py              # #5021-r2 xfail reason narrowed (EDIT)
├── merge/test_bookkeeping_projection_seam.py # new probe unit coverage (EDIT/ADD)
└── (guardians: test_repro_4945/4977/4981/5001/5018/5022 — MUST stay green, no edit)
```

**Structure Decision**: single-project CLI/library layout; all edits inside `src/specify_cli/merge/` and its tests. The driver-replay helper is a new bounded primitive; its exact home (`git_probes.py` vs a new small module) is a WP-level decision confirmed by the brownfield scout.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

## Parallel Work Analysis

Single logical fix; not meaningfully parallelizable. Sequenced as one implementation lane plus a
small documentation/disposition slice for #5021-r2. WP breakdown is finalized by `/spec-kitty.tasks`,
but the intended shape is:

- **WP01 (core fix, sequential)**: driver-replay probe + rewire `projected_content_matches_target` /
  `_assert_squash_projected_content_landed`; flip `test_5038_p1`; re-ground `test_5038_p2`; probe
  unit tests. ATDD red-first from the lane worktree.
- **WP02 (residual disposition, depends on nothing in WP01's code)**: narrow the #5021-r2 xfail
  reason; author the dedicated follow-up issue reference; CHANGELOG entry. Docs/test-comment only.

### Coordination Points

- The re-grounded `test_5038_p2` design is the single highest-risk artifact (green-wash hazard) —
  it gets the post-tasks adversarial lens and the pre-merge data-loss lens.
- Foreign-coverage baseline (`.github/ci-foreign-coverage-baseline.json`) recaptured to the MEASURED
  value if a new real-CLI repro is added under `tests/terminus/`.
