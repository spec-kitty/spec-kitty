# Implementation Plan: Fail-closed acceptance-matrix merge driver (#4880)

**Branch**: `fix/acceptance-matrix-merge-fail-closed` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/spec.md`

## Summary

Close the silent verdict-corruption class in the acceptance/issue matrix git merge driver **by construction**. Today `_merge_field` returns a `_field_conflict_marker(...)` string on a both-sides-diverged field and the driver exits 0, so a merge commits a matrix whose `overall_verdict` recomputes to `fail`. The fix makes `_merge_field` **raise `RowMatrixMergeError`** on a genuine add/add field conflict, reusing the driver's existing `RowMatrixMergeError → typer.Exit(1) → git merge --abort` spine, so the merge fails closed and a human resolves the conflict. `_field_conflict_marker` becomes dead code and is removed. A read-side guard in `AcceptanceMatrix.from_dict` rejects marker-laden values as defense-in-depth. Because the current behavior is contract- and test-pinned, the same change amends ADR `2026-07-23-2`, contract `merge-driver-algorithm.md:29`, completed-mission `01KZPG7V` FR-004, and re-anchors the two tests that green-pin the bug.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none added/changed (stdlib `json`; existing `typer`, `pytest`)
**Storage**: JSON gate artifacts on disk (`kitty-specs/**/acceptance-matrix.json`); no datastore
**Testing**: pytest (`tests/merge/`, `tests/specify_cli/cli/commands/`, `tests/acceptance/`, `tests/architectural/`)
**Target Platform**: Linux/macOS/Windows dev + CI (git custom merge driver)
**Project Type**: single (library/CLI — `src/specify_cli`)
**Performance Goals**: N/A (merge-time reconciliation, not a hot path)
**Constraints**: no new cross-layer import (stay within `specify_cli`); review-cycle driver unchanged; `overall_verdict` recompute semantics unchanged in this mission
**Scale/Scope**: ~2 product files (`cli/commands/merge_driver.py`, `acceptance/matrix.py`) + test re-anchors + decision/doc amendments

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **DDD + tiered rigour**: merge domain + acceptance domain; a verdict-authority artifact is high-rigour — fail-closed is the correct default. ✅
- **Close defect classes by construction (DIRECTIVE_043)**: raising in the shared `_merge_field` mechanism removes the marker-embed path entirely rather than guarding one field. ✅
- **Canonical sources (DIRECTIVE_044)**: the read guard reuses the existing `AcceptanceMatrixParseError`; no new parallel validator. ✅
- **ATDD / red-first**: FR-003 requires a failing repro before the fix (the two existing tests currently green-pin the bug). ✅
- **Decision documentation (DIRECTIVE_003)**: the behavior reversal is recorded (ADR amendment + contract + mission FR-004). ✅ (see Phase 0)
- **No new cross-layer coupling**: changes stay in `specify_cli`. ✅
- **Supply-chain**: no dependency added/changed → section N/A (recorded in research.md).

## Project Structure

### Documentation (this mission)

```
kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/
├── plan.md            # this file
├── research.md        # Phase 0: decision record + alternatives + recorded-decision reversal
├── data-model.md      # Phase 1: AcceptanceMatrix invariants
├── contracts/         # Phase 1: merge-driver-algorithm amendment note
├── quickstart.md      # Phase 1: how to reproduce + verify fail-closed
└── tasks.md           # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/merge_driver.py      # _merge_field (raise instead of embed); delete _field_conflict_marker
└── acceptance/matrix.py              # AcceptanceMatrix.from_dict marker-reject guard (FR-004)

tests/
├── merge/test_gate_artifact_merge_drivers_2804.py         # re-anchor lesser-variant pin; keep test_a4 control
├── specify_cli/cli/commands/test_row_aware_merge_driver.py # re-anchor pass_fail-conflict pin → expect refusal
├── acceptance/  (+ tests/specify_cli/acceptance/)          # FR-004 from_dict marker-reject test
└── architectural/test_merge_reconciliation_class_guard.py  # touch only if reconciler raise-surface changes

docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md  # amend: qualify "no consolidation abort" to exclude gate/verdict artifacts
docs/changelog/CHANGELOG.md                                                        # consumer-facing entry
kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md  # amend line 29
```

**Structure Decision**: Single-project library/CLI. The fix lands at the shared field-merge mechanism in `merge_driver.py` (covers both matrix drivers) plus a read-guard in `acceptance/matrix.py`; everything else is test re-anchors and recorded-decision amendments.

## Implementation Concerns (feeds `/spec-kitty.tasks`)

1. **IC-1 — Fail-closed mechanism.** `_merge_field` raises `RowMatrixMergeError` on a both-sides-diverged field (the `merge_driver.py:424` branch — same row key present on both sides with different non-base values) instead of returning `_field_conflict_marker(...)`; delete the now-unreachable `_field_conflict_marker`. Verify both matrix drivers surface `Exit(1)` and `_merge_branch_into` aborts. **Exception-type hardening (brownfield finding):** broaden both matrix drivers' `except RowMatrixMergeError` to also catch `AcceptanceMatrixParseError` (raised by IC-3's `from_dict` guard at `matrix.py:129`), so a marker that ever reaches `from_dict` still exits via the clean `Exit(1)` + `--abort` spine rather than propagating uncaught. (FR-001, FR-002, FR-005; NFR-002 review-cycle untouched)
2. **IC-2 — Red-first repro + re-anchor pins.** The pre-fix behavior is already green-pinned by three tests that assert marker-embed + "must not raise" — each is a genuine same-key both-sides field conflict that RAISES under IC-1 and must be re-anchored to expect refusal:
   - `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py::test_acceptance_matrix_same_field_conflict_never_silent_pick` (:379) — acceptance `pass_fail` pending→pass/fail (the direct #4880 repro; today flips `overall_verdict` to `fail`).
   - `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py::test_issue_matrix_same_field_divergence_is_structured_conflict_not_silent_pick` (:194) — issue-matrix `verdict` unknown→fixed/wontfix.
   - `tests/merge/test_gate_artifact_merge_drivers_2804.py::test_a3_evidence_survives_inside_conflict_marker` (:178) — the **lesser variant**: `pass_fail` equal, prose (`evidence`/`notes`) diverges → markers embedded today.
   Red-first proof: run each against the pre-fix `merge_driver.py` (marker asserted today) → after IC-1 they expect refusal. **Keep GREEN, do NOT touch:** `test_a4_control_invalid_pass_fail_still_fails` (authored out-of-domain token → `fail` is correct), the disjoint-key add/add tests, `test_issue_3231_*`, and all review-cycle driver tests. (FR-003, SC-003)
3. **IC-3 — Read-side guard.** `AcceptanceMatrix.from_dict` raises `AcceptanceMatrixParseError` on any field value containing a conflict marker; focused test. (FR-004; SC-002 lesser variant)
4. **IC-4 — Amend recorded decisions.** ADR `2026-07-23-2` qualification, contract `merge-driver-algorithm.md:29`, mission `01KZPG7V` FR-004 negative-control note. (FR-006, C-003)
5. **IC-5 — Docs/changelog.** Consumer-facing `docs/changelog/CHANGELOG.md` entry. (landing)

## Parallel Work Analysis

### Dependency Graph

```
IC-1 (mechanism) ─┬─→ IC-2 (repro + re-anchor pins)   # tests depend on the raise behavior
                  └─→ IC-4 (decision amendments cite the new behavior)
IC-3 (read guard) ── independent of IC-1 (different module) → parallelizable
IC-5 (changelog) ── after IC-1..IC-4 land
```

### Work Distribution

- **Sequential**: IC-1 → IC-2 (repro must witness the pre-fix flip, then go green on the raise). IC-4 records IC-1's behavior.
- **Parallel**: IC-3 (`acceptance/matrix.py`) is a different module from IC-1 (`merge_driver.py`) — can run alongside.
- **File ownership**: IC-1 owns `merge_driver.py`; IC-3 owns `matrix.py`; IC-2 owns the two driver test files; IC-4 owns the ADR/contract/mission docs; IC-5 owns the changelog. No shared-file contention except IC-1↔IC-2 (mechanism then its tests — sequence).

### Coordination Points

- Red-first proof gate: IC-2's repro must fail on the pre-fix `merge_driver.py` and pass after IC-1.
- Architectural gate: run `tests/architectural/` on the rebased tip before declaring green (terminology + reconciler class guard).

## Brownfield verification (post-plan point-cut, 2026-09-22)

A brownfield completeness point-cut pressure-tested the blast radius. Outcomes folded above:

- **Confirmed complete/correct**: symbol callers are contained (`_field_conflict_marker`'s only caller is `_merge_field`; deletion breaks no import); registration/install sites (`.gitattributes`, the m_3_2_6 migrations, `lanes/merge.py`, `init.py`) encode only command-name wiring — no touch; `test_merge_reconciliation_class_guard.py` and the terminology gate do not trip on the raise-surface change.
- **Folded into IC-2**: two additional genuine divergence pins beyond the direct repro (`test_issue_matrix_same_field_divergence…` and `test_a3_evidence_survives…`).
- **Folded into IC-1**: the `AcceptanceMatrixParseError` exception-type hardening.
- **False alarm refuted (recorded so it is not re-raised)**: `tests/merge/test_issue_2804_merge_resets_gate_artifacts.py` was flagged as a hard red / #2804 semantic reversal. **It is NOT a red under IC-1.** The FILLED matrix (criterion_ids `FR-001`/`FR-003`) and the PLACEHOLDER matrix (`AC-001`) have **disjoint keys**, so every row resolves via `_reconcile_added_row` (one-sided) and the `_merge_field:424` conflict branch is never reached. IC-1's raise does not fire there; #2804's "filled survives" guarantee is unaffected. (Verified by reading the fixture, not the summary.)

## Complexity Tracking

No Charter violations to justify. The mechanism-level altitude is the *simpler* option that closes the whole class (the per-field guard was rejected as whack-a-field — see research.md).
