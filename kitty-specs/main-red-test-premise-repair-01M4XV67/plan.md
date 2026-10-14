# Implementation Plan: Restore green main: stale test premises after the requirement-grammar scoping and the events 10.4.6 bump

**Branch**: `issue-6240-main-red-test-premise-repair` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/main-red-test-premise-repair-01M4XV67/spec.md`

## Summary

Two tests on `main` are red because their premises lagged shipped changes. Neither is a product defect.

1. **#6240.** `_is_well_formed_declaration(token, mission_type)` gained a required argument in c0f455d068. `tests/specify_cli/test_requirement_id_lint.py:313-325` still calls it with one argument. Re-pin the test and cover the new Mission-type branch and the placeholder rejection.
2. **#6238.** `build_recovery_repo(full=True)` (`tests/architectural/test_upgrade_recovery_preservation.py:341`) exports pinned commit `c0054153b9`. In that commit, `kitty-specs/079-post-555-release-hardening/status.json` predates the operator-sanctioned re-materialization under spec-kitty-events 10.4.6 (2ff2f1deb5, listed in `_OPERATOR_SANCTIONED_CORRECTIONS`, `tests/architectural/test_archive_root_byte_identical.py:250`). The strict audit therefore reports `SNAPSHOT_DRIFT` on 079: WP03 and WP07 are `in_progress` in the snapshot but `planned` in the reducer. The issue named 078; grounding showed the drifting directory is 079. The fix applies the sanctioned corrections to the fixture as a separate fixture commit. It takes the paths from that same list (25 of them exist in the export) and the bytes from pinned commit 2ff2f1deb5, not HEAD, so the fixture stays deterministic. The count is asserted.
3. **Routing (operator ruling).** `uv.lock`, and not `pyproject.toml`, fans out to the `upgrade` and `status` module shards through a new non-src group. This follows the #6166 `mission_type_definitions` precedent (5908cbbec2).

## Technical Context

**Language/Version**: Python 3.11+ (tests and CI scripts); GitHub Actions YAML (ci-router)
**Primary Dependencies**: pytest, spec-kitty-events 10.4.6 (pinned in uv.lock), dorny/paths-filter (ci-router)
**Storage**: N/A (files in a throwaway git fixture repository)
**Testing**: targeted pytest files only (`NO_FULL_HEAVY_SUITES_IN_MISSION`): the two red test files, `tests/architectural/test_upgrade_recovery_preservation.py`, `tests/architectural/test_archive_root_byte_identical.py`, `tests/ci/test_fanout_derivation.py`, `tests/architectural/test_gate_selection_authority.py`, `tests/architectural/test_workflow_coherence.py`, `tests/architectural/test_consumer_census_routing.py`, `tests/ci/` routing tests
**Target Platform**: Linux CI runners and developer machines
**Project Type**: single
**Performance Goals**: the routing change adds at most 2 module shards, only to PRs that touch `uv.lock`
**Constraints**: no `src/` change (C-001); one authority for sanctioned paths (C-002); `pyproject.toml` excluded from the new group (C-003)
**Scale/Scope**: about 4 to 6 files and under 150 changed lines

## Charter Check

- **Test remediation discipline (Standing Order 4)**: both reds are judged stale tests, so they are re-pinned. The judgment rests on evidence. For #6240, every production caller passes `mission_type` (issue body). For #6238, the live corpus audits clean, and the failure is exactly the sanctioned 10-line diff. Red-first: both tests are red at the base commit `dcbabeb3ff`. That is recorded as the pre-fix proof, and no new `regression`-marked test is needed, because the existing tests are the repros.
- **Single canonical authority**: the fixture reads `gate._OPERATOR_SANCTIONED_CORRECTIONS` and keeps no copy. The new routing group is added in lockstep across the router YAML, `GROUP_MODULE_FANOUT` and the coherence pins, exactly as in #6166.
- **Architectural gate discipline**: no allowlist growth. No classifier tolerance. The audit stays strict (NFR-001).
- **No full heavy suites**: targeted files only.
- Pass. No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/main-red-test-premise-repair-01M4XV67/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
tests/specify_cli/test_requirement_id_lint.py           # IC-01
tests/architectural/test_upgrade_recovery_preservation.py  # IC-02 (build_recovery_repo)
.github/workflows/ci-router.yml                         # IC-03 (filter group + output)
scripts/ci/gate_selection.py                            # IC-03 (GROUP_MODULE_FANOUT)
tests/architectural/test_workflow_coherence.py          # IC-03 (lockstep pin)
tests/architectural/test_gate_selection_authority.py    # IC-03 (fan-out pin, if pinned per group)
```

**Structure Decision**: existing single-project layout; there are no new modules.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Re-pin the requirement-ID well-formedness test (#6240)

- Parametrize over `(token, mission_type, expected)`. The five existing cases use `"software-dev"`.
- Add the research cases: `DR-001` is `True` under `research` and `False` under `software-dev`. Add a placeholder (`FR-00N`) that is `False` under both types.
- Files: `tests/specify_cli/test_requirement_id_lint.py`. Requirements: FR-001, FR-002, SC-001.

### IC-02 — Apply the sanctioned corrections to the full-corpus fixture (#6238)

- In `build_recovery_repo`, after the historical commit (and only when `full=True`, or whenever a sanctioned path exists in the export), write the bytes at pinned `SANCTIONED_AT` (2ff2f1deb5) of every `gate._OPERATOR_SANCTIONED_CORRECTIONS` path that exists in the export (25 paths; the count is asserted). Commit them as a second fixture commit named for the operator-sanctioned corrections, with a comment citing #6061 and #6205.
- Before choosing the scope, confirm that `recover()` and the byte-identity assertions in this file do not compare 079 against the original bytes. If the non-full fixture is unaffected, limit the overlay to `full=True`.
- Files: `tests/architectural/test_upgrade_recovery_preservation.py`. Requirements: FR-003, NFR-001, C-002, SC-002.

### IC-03 — Lock-file fan-out to the upgrade and status shards (operator ruling)

- Add a new non-src filter group, for example `reducer_lock: ['uv.lock']`, with a matching output line to `ci-router.yml`. Add a separate non-census `DEPENDENCY_MODULE_FANOUT["reducer_lock"] = {"upgrade", "status"}` (not `GROUP_MODULE_FANOUT`, which the pack census validates) and the lockstep pins (`_DELIBERATELY_UNGATED_FILTER_GROUPS` or equivalent in `test_workflow_coherence.py`, plus the census and allowlist checks in `tests/ci/test_fanout_derivation.py` if they apply). `pyproject.toml` is not added.
- Add a focused test: lock-only selection includes `upgrade` and `status`, and manifest-only selection gets no `upgrade` from this group.
- Files: `.github/workflows/ci-router.yml`, `scripts/ci/gate_selection.py`, the routing test files above. Requirements: FR-004, NFR-002, C-003, SC-004.
