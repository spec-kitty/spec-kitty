---
affected_files: []
cycle_number: 1
mission_slug: accept-fails-closed-01M3HS4V
reproduction_command:
reviewed_at: '2026-09-27T19:26:32Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review — cycle 1 (reviewer-renata / claude): CHANGES REQUESTED

Targeted surface is green (408 passed, 2 skipped). The readiness gate, error-data shape, the contract bump to 1.7.0, and the docs are correct. Two issues block approval.

## Issue 1 (BLOCKER): coord-topology accept writes to one directory and reads back from another, so it records acceptance and then crashes with a raw traceback

`src/specify_cli/orchestrator_api/commands.py` `_stamp_mission_acceptance_or_fail` (~L2067-2078):
- `_stamp_acceptance_record(summary, ...)` writes `meta.json` into `summary.feature_dir`, the PRIMARY anchor (`acceptance/__init__.py` ~L1366-1367, `_primary_anchor_feature_dir`).
- Then `load_meta_strict(mission_dir)` reads `meta.json` back from `mission_dir`. That is the coord-aware STATUS dir from `_resolve_mission_dir_or_fail`, which for coord-topology missions is the coordination worktree. That directory holds no `meta.json`.

Empirical repro: your `_seed_acceptable_mission`, plus `ensure_coordination_branch`, plus `coordination_branch` in meta, plus status events and the matrix copied into `coord_feature_dir`, with `.worktrees/` gitignored. Result:
- Post-WP03: primary `meta.json` GETS `accepted_at` stamped, then `FileNotFoundError: No meta.json in .../.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>` escapes as a raw traceback, not a JSON envelope. The side effect is committed while the caller sees a crash.
- Base (da741824): the same crash, but nothing was recorded. So this WP turns a pre-existing clean failure into a partial write followed by a crash.

Fix: read `accepted_at` back from the directory the stamp wrote to (`summary.feature_dir`), not from `mission_dir`. Add a regression test that drives the real CLI on a coord-topology acceptable mission. Assert success, a JSON envelope, and `accepted_at` in the PRIMARY `meta.json` that equals `data.accepted_at`. You can build the fixture from `tests/orchestrator_api/test_issue_4889_caller_independence.py` (`ensure_coordination_branch` + `coord_feature_dir`).

## Issue 2: the explicit `strict_metadata=True` pin (FR-007 / C-001) has no test

Mutation `strict_metadata=True` -> `strict_metadata=False` at commands.py ~L2127 leaves the targeted accept suite fully green (9/9). Add one test where a WP reaches approved/done but its claim event carries no `policy_metadata={"agent": ...}`, so the implementer-of-record is missing. The test must assert `MISSION_NOT_READY` with a non-empty `outstanding["metadata"]` (or whichever bucket strict mode fills) and nothing recorded. Your own change to `_emit_planned_to_done` / `_emit_planned_to_approved` shows this failure path exists.

## Nits (non-blocking)

- `_MISSION_READINESS_FAILURE_MESSAGE` (commands.py ~L2035) is a second literal copy of `acceptance/__init__.py` ~L1860, and its comment says "not a new, drifting copy". Hoist the string into a constant in `specify_cli.acceptance` and import it from both places, or reword the comment.
- The cross-module private import `from specify_cli.acceptance import _stamp_acceptance_record` has precedent in this file (`_mark_wp_merged_done`, `_create_mission_for_specify_json`, `_read_snapshot`), and no architectural gate forbids it, so it is acceptable. A public alias (e.g. `stamp_acceptance_record`) would still be cleaner now that two entry points depend on it.

## Verified OK

- The incomplete-WP refusal is preserved, and the gate runs before any write.
- Refusal paths write nothing: no `accepted_at` / `acceptance_mode` / `acceptance_history`, HEAD unchanged.
- An `AcceptanceError` (guard refusal or lock timeout) maps to `MISSION_NOT_READY`.
- `validate_outbound_payload` is intact.
- Contract is 1.7.0 with a ledger entry. `MIN_PROVIDER_VERSION` is unchanged. `upstream_contract.json` is untouched.
- `WORKFLOW_EVIDENCE_REQUIRED` is never raised in `orchestrator_api/`, so removing the accept-mission row is justified. The global error-code list keeps it.
- Adding `policy_metadata` to the shared emit helpers only adds data. The list-ready and start-implementation users are unaffected.
- ruff, format and mypy are clean. Complexity is ≤15. No `feature` terminology.

Mutations: skipping the gate killed 2 tests. Bypassing the guard with a bare `record_acceptance` killed 2 tests. Flipping `strict_metadata` to False SURVIVED (Issue 2).
