# Implementation Plan: Hermetic legacy-charter Git identity fixtures

**Branch**: `issue-7061-legacy-charter-git-identity` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/legacy-charter-git-identity-01M6TZ9E/spec.md`

All planning questions are answered by the operator's narrow remediation and the completed investigation; no clarification remains.

## Summary

Repair the three active #7061 failures at their test-setup boundary. In the two affected setups in `tests/specify_cli/migration/test_legacy_charter_gate.py`, persist `user.name=t` and `user.email=t@t` with repository-local `git config` immediately after `git init`. The existing bootstrap commits, later `safe_commit` path, and every assertion stay unchanged. Prove the same three nodes red before editing and green afterward, then prove the four-case matrix and owning file.

Research evidence: `reports/Main Red Issue Causes.md` and `research_notes/Main Red Issue Causes/issue_7061.md` in the operator's investigation checkout, reconfirmed against `origin/main@f47114a75f3d85b1ebc7f1fb7c534aab4133a23c` and the still-open, nightly-red issue before claiming.

## Technical Context

**Language/Version**: Python 3.11+; the target nightly uses Python 3.13
**Primary Dependencies**: pytest, Git, existing Spec Kitty CLI `safe_commit` path
**Storage**: Temporary Git repositories and linked worktrees created by pytest
**Testing**: Existing CLI-level tests through `.venv/bin/python -m pytest`; Ruff lint/format
**Target Platform**: Isolated Linux CI workers with no ambient Git identity
**Project Type**: Test-fixture repair only
**Performance Goals**: No new performance work; targeted tests only
**Constraints**: Four configuration commands across two setups; no production-source or assertion changes
**Scale/Scope**: One work package, one test file, one required changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

PASS. The change preserves architecture and production behavior, uses the existing tests for ATDD/red-first evidence, and follows the smallest-viable-diff/locality resolution recorded in `tracer-design-decisions.md`. No campsite refactor is proportionate to this four-command fixture repair. Validation is limited to the exact nodes, behavior matrix, owning file, and targeted lint/format; no heavy suite is authorized. The issue is claimed and recorded in `issue-matrix.json`.

### Focused planning lenses

- **Alignment lens**: #7061 was open and its 2026-11-07 nightly comment still named exactly these three nodes. Current `origin/main` still had process-local `git -c user.*` only; searched open/closed PR references found no equivalent active fix. Proceed rather than duplicate.
- **Scope lens**: The two loops at the owned-Mission creation test and startup-claim test are the complete edit set. Similar bootstrap loops elsewhere in the file do not exercise a later identity-dependent commit and stay untouched. Exclusions remain #7206, #6788, startup performance, recovered failures, #7273, and #7287.
- **Pre-tasks review**: One WP covers both independent fixture insertions because the acceptance matrix is one coherent behavior surface. Red-first commands and non-vacuity controls are mandatory; no extra helper or test abstraction is warranted.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/legacy-charter-git-identity-01M6TZ9E/
├── spec.md
├── plan.md
├── issue-matrix.json
├── tracer-tooling-friction.md
├── tracer-approach.md
├── tracer-design-decisions.md
├── tasks.md
└── tasks/WP01-hermetic-git-identity.md
```

### Source Code (repository root)

```text
tests/specify_cli/migration/
└── test_legacy_charter_gate.py  # Only production-tree file edited; fixture setup only

docs/changelog/unreleased/
└── 7319.internal.md                         # Required changelog fragment named for the draft PR
```

**Structure Decision**: Reuse the owning migration test file and existing test entry point. No source module, new helper, architectural gate, or additional test file is needed.

## Implementation and Validation Sequence

1. Re-run the three exact nodes before editing and capture **3 failed**, each with the Git identity signature.
2. Insert `git config user.name t` and `git config user.email t@t` immediately after initialization in both affected setup loops.
3. Re-run those exact nodes and require **3 passed**.
4. Run both affected test functions together and require **4 passed**, including `[True]`.
5. Run the full owning test file and targeted Ruff lint/format checks.
6. Update tracers, complete the WP review record, and hand off a draft PR. Do not claim #7061 closed until Python 3.13 nightly shard 5 is green on the merged commit.

## Complexity Tracking

No charter violations or complexity exceptions.
