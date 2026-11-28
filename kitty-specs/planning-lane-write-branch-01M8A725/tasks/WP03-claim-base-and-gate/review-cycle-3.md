---
affected_files: []
cycle_number: 3
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T04:30:47Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review cycle 3 feedback (reviewer: claude::reviewer-renata)

Reviewed fold commit e4af2b36 on lane-c (diff against 60aeb939). The three cycle-2 findings are folded:

- **Item 1:** `_fail_workspace_resolution` now drops `error_code` from the `to_dict()` spread, and the duplicate `reason` is gone from that branch. `test_a_mission_branch_no_checkout_holds_reports_planning_checkout_missing_in_data` asserts `"error_code" not in data`.
- **Item 2:** the occupied and wrong-branch tests in `test_single_branch_repo_root_workspace.py` now parse the envelope. They assert `LANE_ALLOCATION_FAILED`, the matching `data.workspace_error_code`, and no `data.error_code`. The out-of-map rationale is recorded in add-history.
- **Item 3:** a `record_claim_base` `RuntimeError` is enveloped as `LANE_ALLOCATION_FAILED` with `data.error_type: "RuntimeError"`.
  - My probe (scratchpad `wp03-review3-probe/test_rt_probe.py`) confirms that the call writes no status event (1 event before, 1 after) and records no claim base.

No reader of `data.error_code` on these failure envelopes exists in src, tests or `docs/api/orchestrator-api.md`. The other `data["error_code"]` hits in tests are top-level envelope reads. The API doc, the envelope history and the changelog describe the final keys (`data.workspace_error_code`, `data.error_type`).

One small item remains.

## 1. LOW: the new RuntimeError test does not pin "no status event is written", which is what the fix claims

- Location: `tests/orchestrator_api/test_planning_start_7860.py::test_a_claim_base_that_cannot_be_recorded_is_an_envelope`.
- What it asserts: the envelope only (`success`, `error_code`, `data.error_type`, `message`).
- What it does not assert: the fail-closed property in the inline comment, "stops the claim before any status event". If a later change moves the claim-base record after `start_implementation_status`, this test stays green while the WP is left `claimed` / `in_progress` with no claim base. That is the exact strand the guard exists to prevent.
- Fix: in the same test, read `read_events(mission.mission_dir)` before and after `_start`, then assert that the count is unchanged or that no event for `PLANNING_WP` moved past `planned`. Optionally also assert that `read_claim_base(...)` is None. That assertion is trivially true under the monkeypatch, so the event check is the one that matters.

## Tests run (reviewer)

- Blast (`-n 4 --dist loadfile`): tests/orchestrator_api, tests/specify_cli/orchestrator_api, tests/contract, tests/lanes, tests/coordination, tests/specify_cli/workspace, tests/specify_cli/cli/commands/agent, tests/docs/test_orchestrator_api_verb_doc_presence.py, tests/integration/test_7860_planning_evidence_window.py. 8258 passed, 12 skipped, 3 xfailed, 2 failed (log `wp03-review3-blast.log`). Both failures are the expected non-WP03 reds: `..._on_the_topic_branch_...` fails with `IMPLEMENTATION_MISSING` over `<base>..main` (WP04 axis), and `..._where_implement_puts_it_...` refuses with a recorded claim base in the Mission-branch checkout (WP05 re-pin).
- ruff check, `ruff format --check --force-exclude`, and ruff C901 on the three changed files: clean.
- mypy on the three changed files: clean. The 4 remaining findings are in `tests/utils.py` (2) and `test_single_branch_implement_refusals.py` (2). The same 4 reproduce at 60aeb939, and neither file has changed since 9dcf5f48. They are pre-existing.
