# Implementation Plan: Guard `safe_commit` against hook-staged paths

**Branch**: `issue-5903-safe-commit-hook-staged-paths` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/safe-commit-hook-staged-paths-01M4RKV7/spec.md`

## Summary

Primary requirement: `safe_commit` must never silently commit paths the operation did not request
when a pre-commit hook stages files (`git add -u`). Technical approach: one shared **post-landing
check** inside `safe_commit`, called from the two affected routes — the default `--only` route and
the FR-022 temp-index route (`_commit_with_index_deletions`). The check compares
`git diff-tree --name-only` of the new commit against the requested path set (plus the FR-022
`index_deletions`); on a mismatch the commit has already landed, so it re-syncs the operator's real
index for the extra paths and raises a new `SafeCommitRecoveryFailed` subclass
(`SafeCommitUnrequestedPaths`, `error_code = "SAFE_COMMIT_UNREQUESTED_PATHS"`) carrying the landed
`commit_sha` and naming the extra paths. The expected-parent route is unchanged (negative control).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git CLI (via `subprocess`), typer/rich (CLI), pytest/mypy/ruff (dev)
**Storage**: N/A (git index/commit state)
**Testing**: `tests/specify_cli/git/test_commit_helpers.py` (owning module); contract gates in
`tests/contract/` and `tests/specify_cli/core/`; `tests/specify_cli/orchestrator_api/` for the
contract version.
**Target Platform**: Linux/macOS/Windows (git required)
**Project Type**: single (CLI/library)
**Performance Goals**: no measurable regression; the clean path adds one `git diff-tree` read.
**Constraints**: expected-parent route unchanged; clean no-hook commit byte-identical; hooks still
run (no `--no-verify`); complexity ≤ 15; mypy/ruff clean.
**Scale/Scope**: a surgical fix in one module (`src/specify_cli/git/commit_helpers.py`) plus the
contract registration (`upstream_contract.json` + mirror + envelope) and its tests.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (C-001): new error code lives once in `upstream_contract.json`;
  its docs mirror and the envelope changelog are updated in the same change. ✅
- **ATDD / red-first** (SO 4, C-011): red reproduction committed before the fix. ✅ (done)
- **Red-main discipline** (SO 9): a P0 reproduction is landed; no test is weakened; the fix is the
  root cause. ✅
- **Locality of change / smallest viable diff**: one new helper + two call sites + one new error
  class + contract registration. No new gate, no ratchet. ✅
- **No full heavy suites in mission** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run the owning test
  module, the named contract-parity/version gates, and `make test-fast`; never the bare
  `tests/architectural/` directory. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/safe-commit-hook-staged-paths-01M4RKV7/
├── spec.md
├── plan.md                 # this file
├── research/
│   └── defect-diagnosis-5903.md
├── traces/
│   ├── tooling-friction.md
│   ├── approach.md
│   └── design-decisions.md
└── tasks.md                # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/git/commit_helpers.py        # new error class + shared post-landing check, wired
                                              #   into the --only route and _commit_with_index_deletions
src/specify_cli/core/upstream_contract.json  # register SAFE_COMMIT_UNREQUESTED_PATHS
docs/contracts/upstream-3.0.0-shape.json      # JSON-equal mirror (gate-enforced)
src/specify_cli/orchestrator_api/envelope.py  # CONTRACT_VERSION 1.14.0 -> 1.15.0 + changelog line

tests/specify_cli/git/test_commit_helpers.py                      # repro + controls (added)
tests/specify_cli/orchestrator_api/test_contract_version.py        # version pin update
docs/changelog/CHANGELOG.md                                        # [Unreleased] entry
```

**Structure Decision**: single project; the change is confined to the git-ops seam and the
orchestrator-api contract surface it feeds.

## Complexity Tracking

No Charter Check violations. The shared helper is extracted specifically to keep both call sites and
`safe_commit`/`_commit_with_index_deletions` under the complexity ceiling (≤ 15).

## Implementation Concern Map

> One architectural concern; it becomes a single work package.

- **IC-01 — Post-landing requested-paths guard.** Add `SafeCommitUnrequestedPaths`
  (`SafeCommitRecoveryFailed` subclass) and a shared `_assert_committed_paths_requested(...)` helper;
  call it from the `--only` success path and from `_commit_with_index_deletions` after
  `_sync_real_index_after_commit`; re-sync the real index for the extra paths before raising;
  register the new code in `upstream_contract.json` + the docs mirror + the envelope changelog
  (bump `CONTRACT_VERSION` to 1.15.0) and update the pinning test. FR-001…FR-006, NFR-001…003,
  C-001…C-003.
