# Implementation Plan: Anchor the sdist README include to the repository root

**Branch**: `issue-6926-sdist-readme-anchor` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/sdist-readme-anchor-01M6BRD9/spec.md`

## Summary

The source distribution's bare `README.md` and `CHANGELOG.md` include entries are gitignore-style and match at any depth, so 745 stray files from `kitty-specs/`, `docs/`, `tests/`, `scripts/` and `packs/README.md` ship. Anchor both entries to the repository root with a leading `/`, exclude `site/**`, and pin the result with a red-first packaging-safety test on the built archive. Planning questions were answered by the issue's Done-when and the operator brief (no further interview).

## Technical Context

**Language/Version**: Python 3.11+ (tests); TOML build configuration (`pyproject.toml`, hatchling build backend)
**Primary Dependencies**: hatchling (pinned by `uv.lock`; compiles patterns with `pathspec.GitIgnoreSpec`), `build` (test extra, used by the shared `build_artifacts` fixture)
**Storage**: N/A
**Testing**: pytest; `tests/cross_cutting/packaging/test_packaging_safety.py` (archive tests are `slow` + `integration`, sharing the once-per-run build); `make test-fast`; config readers `tests/ci/test_mission_status_api_build.py`, `tests/cross_cutting/packaging/test_companion_version_lock.py`; gate `tests/architectural/test_pyproject_shape.py`
**Target Platform**: the published sdist (`spec_kitty_cli-<version>.tar.gz`)
**Project Type**: single project
**Performance Goals**: no second build; new tests add < 1 s beyond the shared build (NFR-001)
**Constraints**: wheel unchanged (C-001); `packs/internal/` never ships, built-in content unchanged (C-002); `services/**` / `contracts/**` lines untouched (C-003, PR #7004); no `site/` folder (C-004); red first (C-005)
**Scale/Scope**: two include entries changed, one exclude entry added, one test module extended

## Charter Check

- **Standing Order 4 (red first, bug-fix discipline):** the archive test lands failing on the base before the fix, through the pre-existing entry point (the real sdist build). PASS by plan.
- **Standing Order 5 (non-vacuous gate):** the archive check has a same-archive positive control and a planted self-test of its helper. PASS by plan.
- **Pack Tiers (CLAUDE.md):** built-in members compared before/after; internal pack assertions untouched. PASS by plan.
- **Smallest viable diff / locality:** two files of product+test change; no unrelated cleanup in the sdist block. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION:** targeted tests and the specific architectural gate only. PASS.
- **Changelog by fragment:** a `docs/changelog/unreleased/<id>.<section>.md` fragment, never `CHANGELOG.md`. PASS by plan.

No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/sdist-readme-anchor-01M6BRD9/
├── spec.md
├── plan.md
├── research.md
├── research/code-grounding.md
├── quickstart.md
├── traces/{approach,design-decisions,tooling-friction}.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
pyproject.toml                                         # [tool.hatch.build.targets.sdist] include + exclude
tests/cross_cutting/packaging/test_packaging_safety.py # archive check, helper self-test, config twin
docs/changelog/unreleased/6926.<section>.md            # changelog fragment
```

**Structure Decision**: single project; the change stays in the packaging config and its existing safety test module.

No data model and no interfaces: `meta.json` records `"contracts": "none"` with a rationale.

## Implementation Concern Map

### IC-01 — Red-first archive check

- **Purpose**: fail on the base when any sdist member sits under `docs/`, `kitty-specs/` or `site/`.
- **Relevant requirements**: FR-003, FR-004, C-005, NFR-001, NFR-002
- **Affected surfaces**: `tests/cross_cutting/packaging/test_packaging_safety.py`
- **Sequencing/depends-on**: none
- **Risks**: a vacuous pass on an empty archive (mitigated by the positive control).

### IC-02 — Anchor the include and exclude `site/**`

- **Purpose**: ship only the root `README.md` / `CHANGELOG.md`; keep `site/` out.
- **Relevant requirements**: FR-001, FR-002, FR-004, C-001, C-002, C-003
- **Affected surfaces**: `pyproject.toml`, changelog fragment
- **Sequencing/depends-on**: IC-01
- **Risks**: textual conflict with PR #7004 (disjoint hunks; whoever lands second rebases).
