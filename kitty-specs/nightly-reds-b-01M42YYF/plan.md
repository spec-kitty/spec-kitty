# Implementation Plan: Nightly reds B (2026-10-04)

**Branch**: `kitty/nightly-reds-b-2026-10-04` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

Repair eleven red nightly node-id groups across three suites, each for a root cause named in [`research/nightly-red-memo.md`](research/nightly-red-memo.md): one stress fixture, three integration oracles that lag the coordination single-home change (`5b5699e50`), one product regression in `agent config sync` (vibe pointer recovery), and three harness defects the new nightly integration slice exposed (shallow checkout, `CI=true` summary format, an unmaterialized characterization fixture). One further red (bare-slug coordination consolidate) is a product regression that needs a design decision and is left red (spec C-004).

## Technical Context

**Language/Version**: Python 3.11 (the nightly integration slice runs on `.python-version` = 3.11; stress runs on the same).
**Primary Dependencies**: pytest, pytest-xdist (`--dist loadfile`), git.
**Testing**: named node ids only, `PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" <ids>`; the stress file opts in through `-m ""`; `CI=true` for the status-guard row; a `git clone --depth 1` for the corpus row.
**Target Platform**: GitHub Actions `ubuntu-24.04` nightly runners.
**Constraints**: spec NFR-001/NFR-002 and C-001..C-004.

## Charter Check

- Standing Order #4 (test remediation): each test is judged, not blamed — stale oracles are re-pinned with a rationale; the one valid failing test whose product fix is in scope (vibe) gets a product fix; the bare-slug consolidate red is a valid failing test whose fix is a design decision and stays red.
- Standing Order #9 / ADR `2026-07-17-1`: no row is a `@pytest.mark.regression` marker (checked per test); nothing is green-washed.
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: targeted runs only.
- Red-first: every repaired node id is red on `bc8d53d09`; the product fix's failing test (`test_initialized_clone_vibe_pointer_recovery_and_repeat`) already exists on the base, so it is the red-first test and is not re-authored.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-reds-b-01M42YYF/
├── spec.md
├── plan.md
├── research/nightly-red-memo.md
├── tasks.md
└── tasks/WP0*.md
```

### Source Code (repository root)

```
tests/stress/test_concurrent_emits.py
tests/integration/test_placement_partition_golden_path.py
tests/integration/test_coord_read_residuals_proof.py
tests/integration/test_owned_lifecycle_acceptance_finalize.py
src/specify_cli/cli/commands/agent/config.py
tests/characterization/test_trio_json_envelope.py
tests/test_repo_root_status_guard.py
.github/workflows/ci-nightly.yml
docs/changelog/CHANGELOG.md
```

**Structure Decision**: edits stay in the files that own each failure; no shared helper is introduced.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Stress fixture shape

- **Purpose**: make the concurrent-emit stress fixture a well-formed coordination Mission (`meta.json` with `coordination_branch`; `mid8 == mission_id[:8]`).
- **Relevant requirements**: FR-001
- **Affected surfaces**: `tests/stress/test_concurrent_emits.py`
- **Sequencing/depends-on**: none
- **Risks**: the stress file is also pinned by `tests/architectural/test_timing_coverage_invariant.py`; the correctness test body must stay verbatim.

### IC-02 — Coordination single-home oracles

- **Purpose**: re-pin three integration oracles to the intended `5b5699e50` contract (create-time seed, STATUS through `write_dir`, +2 ledger reads).
- **Relevant requirements**: FR-002, FR-003, FR-004
- **Affected surfaces**: the three integration test files above
- **Sequencing/depends-on**: none
- **Risks**: an exact ledger is easy to bump blindly; the re-pin names the frame chain that added the reads.

### IC-03 — Vibe pointer recovery

- **Purpose**: restore the gitignored `.vibe/config.toml` pointer for an already-installed vibe agent during `agent config sync --create-missing`, without touching the pinned manifest.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/config.py`
- **Sequencing/depends-on**: none
- **Risks**: must not regress the "normal sync does not rewrite pinned manifests" contract from `f4a2e63ed`.

### IC-04 — Integration-slice harness

- **Purpose**: let the slice run in its real environment: full-history checkout, CI-mode summary parsing, materialized coordination worktree in the recover characterization.
- **Relevant requirements**: FR-006, FR-007, FR-008
- **Affected surfaces**: `.github/workflows/ci-nightly.yml`, `tests/test_repo_root_status_guard.py`, `tests/characterization/test_trio_json_envelope.py`
- **Sequencing/depends-on**: none
- **Risks**: `tests/ci/` may pin the nightly workflow's shape; run those pins.
