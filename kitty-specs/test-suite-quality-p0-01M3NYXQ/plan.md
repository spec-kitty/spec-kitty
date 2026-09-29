# Implementation Plan: Test suite quality (#5353)

**Branch**: `claude/p0-5353-test-suite-quality-g3tt8f` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Test-only mission. Three work packages in ROI order, split on disjoint file sets so they can run in parallel lanes:

1. **WP01 — Fix vacuous guards** (FR-001, FR-002, FR-006): the R1 H findings whose oracle can be made real without a harness rewrite.
2. **WP02 — Unstub gates in legacy harnesses** (FR-003, FR-002): the R2 H findings (`test_post_merge_unrelated_untracked`, `test_merge_status_commit`, `test_acceptance_cores`), moving to real-git fixtures or deleting with proof.
3. **WP03 — Retire top dev-assist scaffolding** (FR-004, FR-005): audit items with a verifiable covering guard; each commit names the guard.

## Technical Context

**Language/Version**: Python 3.11 · **Testing**: pytest, targeted files only (NFR-001) · **Project Type**: single repo, tests-only change.

## Charter Check

- DIRECTIVE_041 (keep-vs-delete, name the covering guard): every deletion cites a guard that was run green.
- DIRECTIVE_034 / 043: red-first via planted break; guards get a non-vacuity proof.
- NO_FULL_HEAVY_SUITES_IN_MISSION: targeted gate files only.
- Constraint: do not touch `ruff.toml` PT block or `tests/architectural/test_ruff_pytest_style_baseline.py` (PR #5355 owns them).

## Method

Red-proof protocol per fixed test: (1) apply a planted break to production (or the guarded input) in a scratch edit, (2) run the test — must FAIL, (3) revert the break, run — must PASS. Result is appended to `research/red-proofs.md`.

## Risks

- A finding turns out to expose a real product defect → fix red-first only if small, otherwise file an issue and mark the guard `xfail(strict=True)` with the issue link.
- Covering guard for a retirement cannot be verified → leave the test, record in the ledger.
