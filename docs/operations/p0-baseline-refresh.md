---
title: Baseline Refresh — P0 Test Failures
description: 'Targeted P0 test-failure baseline refresh of 2026-06-01: per-cluster results for issues #1301/#1303 and others, marking which still reproduce versus went stale.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-06-01'
related:
- docs/operations/index.md
---
# Baseline Refresh — P0 Test Failures

**Date**: 2026-06-01
**Commit SHA**: 29a34c70884f5082e0c4e5d6e144d94a55c6a0fc
**Full suite result**: Full suite run in progress at time of targeted analysis (see note below)

## Targeted Cluster Results

The four P0 clusters were run individually with `--tb=short` to get fast, clean failure
evidence. The full suite run was initiated concurrently but had not completed by the time
targeted analysis was finished (still at ~44% through the suite).

| Issue | Cluster | Targeted failures | Status |
|-------|---------|-------------------|--------|
| #1301 | tests/sync/ + tests/contract/ | 1 | STILL REPRODUCES |
| #1303 | tests/charter/synthesizer/ | 0 | STALE (resolved by prior commits) |
| #1304 | tests/charter_offering/ | 0 | STALE (resolved by prior commits) |
| #1305 | tests/next/ | 0 | STALE (resolved by prior commits) |

### Cluster Details

**#1301 — STILL REPRODUCES**

Command: `pytest tests/sync/ tests/contract/ -q --tb=short -p no:cacheprovider`
Result: `1 failed, 1949 passed, 9 skipped, 17 warnings in 125.47s`

Failing test:
```
FAILED tests/sync/test_runtime_event_emitter.py::TestSyncRuntimeEventEmitter::test_adapter_emits_mission_run_and_lifecycle_sequence
```

Root cause: The adapter emits 6 events but the test expects 8. Specifically,
`DecisionInputRequested` and `DecisionInputAnswered` events are missing from the emitted
sequence. The assertion diff shows:

```
At index 4 diff: 'MissionRunCompleted' != 'DecisionInputRequested'
Right contains 2 more items, first extra item: 'MissionRunCompleted'
```

This confirms the shared-package events adapter does not implement
`emit_decision_input_requested` / `emit_decision_input_answered` handlers (or they do not
enqueue events). This is a genuine #1301 defect.

**#1303 — STALE**

Command: `pytest tests/charter/synthesizer/ -q --tb=short -p no:cacheprovider`
Result: `372 passed in 19.77s`

All synthesizer tests pass. The non-determinism issue described in #1303 is resolved.

**#1304 — STALE**

Command: `pytest tests/charter_offering/ -q --tb=short -p no:cacheprovider`
Result: `1975 passed, 84 warnings in 56.88s`

All doctrine/glossary tests pass. Anchor drift issue described in #1304 is resolved.

**#1305 — STALE**

Command: `pytest tests/next/ -q --tb=short -p no:cacheprovider`
Result: `464 passed, 4 warnings in 67.63s`

All `next` tests pass. The exit-code regressions described in #1305 are resolved.

## Fix Scope

WPs to execute: **#1301** — 1 failing test in `tests/sync/test_runtime_event_emitter.py`

WPs to skip (stale): #1303, #1304, #1305 — all resolved by prior commits

## Out-of-Scope Failures

From the cluster #1301 targeted run, `tests/contract/` had 0 failures (all 1949
tests/contract + tests/sync tests ran, 1 failed in tests/sync only).

The full suite is still running. Any failures outside the four clusters that surface in the
full suite result are **out of scope** for this mission. If the full suite result is
available before WP02 begins, it should be appended to this document.

## Recommendation

Only **WP02 and beyond** need to address the single remaining failure. WPs targeting #1303,
#1304, and #1305 can be marked as skipped/stale. Mission scope is effectively reduced to
fixing `tests/sync/test_runtime_event_emitter.py::TestSyncRuntimeEventEmitter::test_adapter_emits_mission_run_and_lifecycle_sequence`.

## WP03 Post-Fix Results

**Date**: 2026-06-01
**Branch**: `kitty/mission-p0-test-failure-resolution-1298-1305-01KT1R2G-lane-a`

### Verification Run

Command: `pytest tests/sync/ tests/contract/ -q --tb=short -p no:cacheprovider`
Result: `1951 passed, 9 skipped, 17 warnings in 106.01s`

**Zero failures** in `tests/sync/` and `tests/contract/`.

### Target Test Status (T009-T012)

All four WP03 target tests pass after WP02's fix was applied to the lane-a branch:

| Test | Status |
|------|--------|
| `test_fixture_payload_passes_emitter_rules[WPCreated:01JMBYA1B2C3]` | PASS |
| `test_contract_example_round_trip[...check_docs_freshness.md::block-MISSING_FRONTMATTER]` | N/A (not collected — file is in legacy allowlist) |
| `test_init_emits_project_init_event_offline` | PASS |
| `test_event_queued_when_no_websocket` | PASS |

### FR-007 Regression Guard

WP02 resolved the root cause (#1301) by fixing `test_adapter_emits_mission_run_and_lifecycle_sequence` to align with the git-routed decision events architecture. WP02 also added a pyproject.toml version-pin guard that ensures `spec_kitty_events>=5.2.0` is enforced, preventing schema drift regression.

The existing fixture tests in `tests/contract/test_handoff_fixtures.py` serve as regression guards for future WPCreated schema drift — they validate all fixture payloads against the live emitter rules on every CI run.

### Summary

WP03's target fixes were absorbed by WP02: all #1301 cluster tests pass with zero failures across `tests/sync/` and `tests/contract/` (1951 passed). No code changes were required in WP03 scope.

## WP04 Post-Fix Results (#1305)

**Date**: 2026-06-01

**T014 Findings**: All four #1305 cluster tests were confirmed to pass before any code changes. The tests reside inside class bodies (`TestNextCommandCLI`, `TestResultSuccessStillAdvances`) and must be invoked with their fully-qualified class::method paths. The `assert 1 == 0` failures reported in the issue did not reproduce — these tests were already fixed upstream (likely resolved by the WP02 refactor that corrected the `decide_next` import path and exit-code contract).

**Target tests verified (all PASS)**:

| Test | Status |
|------|--------|
| `TestNextCommandCLI::test_blocked_result_exit_code` | PASS |
| `TestNextCommandCLI::test_terminal_state_exit_code_zero` | PASS |
| `TestNextCommandCLI::test_advancing_mode_with_result_still_advances_normally` | PASS |
| `TestResultSuccessStillAdvances::test_result_success_calls_decide_not_query` | PASS |

**Full `tests/next/` result**: 464 passed, 0 failed

**Regression check (`tests/sync/` + `tests/contract/`)**: 1951 passed, 9 skipped

**FR-007 Regression Guard**: The existing test suite provides the regression guard. `decide_next` is imported directly in tests from `specify_cli.next.decision` and invoked through the real CLI router via `CliRunner`, so any future path rename will cause immediate collection or import errors — no additional guard needed.

**Action taken**: WP04 closed as stale (no code changes required; all target tests passed pre-implementation).

## WP05 Post-Fix Results (#1304)

**Date**: 2026-06-01

**T019 Findings**: All four #1304 cluster tests were confirmed to pass before any code changes. The doctrine/glossary tests (`test_glossary_link_integrity` and `test_tactic_compliance`) all pass including the specific anchors `doctrine-pack` and `platform-darwin--platform-linux`, and the `five-paradigm-parallel-debugging` tactic YAML is schema-valid with no unresolved references.

**Full `tests/charter_offering/` result**: 1975 passed, 84 warnings, 0 failed

**FR-007 Regression Guard**: `tests/charter_offering/test_glossary_link_integrity.py` and `tests/charter_offering/test_tactic_compliance.py` contain no `xfail` or `skip` markers — they are fully active regression guards that run on every CI pass.

**Action taken**: WP05 closed as stale (no code changes required; all target tests passed pre-implementation, consistent with WP01 baseline assessment which recorded #1304 as STALE).
