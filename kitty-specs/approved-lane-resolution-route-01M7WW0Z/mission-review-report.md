---
generator: spec-kitty review
verdict: pass_with_notes
mode: post-merge
reviewed_at: 2026-11-26T20:12:43.858125+00:00
findings: 10
gates_recorded:
  - id: gate_1
    name: wp_lane_check
    command: spec-kitty review (internal gate 1)
    exit_code: 0
    result: pass
  - id: gate_2
    name: dead_code_scan
    command: spec-kitty review (internal gate 2)
    exit_code: 1
    result: fail
  - id: gate_3
    name: ble001_audit
    command: spec-kitty review (internal gate 3)
    exit_code: 0
    result: pass
issue_matrix_present: true
mission_exception_present: false
---

## Findings

- **dead_code** `src/specify_cli/consolidation/approved_bound.py` — `kept_one_side`: no non-test callers found
- **dead_code** `src/specify_cli/consolidation/merge_attribute_guard.py` — `MergeAttributeRefused`: no non-test callers found
- **dead_code** `src/specify_cli/consolidation/merge_attribute_guard.py` — `RegisteredDriver`: no non-test callers found
- **dead_code** `src/specify_cli/consolidation/merge_attribute_guard.py` — `merge_probe_env`: no non-test callers found
- **dead_code** `src/specify_cli/consolidation/wp_attribution.py` — `wp_windows`: no non-test callers found
- **dead_code** `src/specify_cli/lanes/auto_rebase_record.py` — `recorded_merges`: no non-test callers found
- **dead_code** `src/specify_cli/lanes/incorporate.py` — `merge_message`: no non-test callers found
- **dead_code** `src/specify_cli/review/context_block.py` — `resolution_command`: no non-test callers found
- **dead_code** `src/specify_cli/upgrade/migrations/m_4_0_0rc9_exclude_project_local_codex_home.py` — `ExcludeProjectLocalCodexHomeMigration`: no non-test callers found
- **dead_code** `src/specify_cli/upgrade/migrations/m_4_0_0rc9_report_newly_visible_agent_files.py` — `ReportNewlyVisibleAgentFilesMigration`: no non-test callers found
