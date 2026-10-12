# Red-first reproductions — origin/main @ 8a911083ad633d (events 10.4.4, spec-kitty 4.0.0rc7)

All commands run from repo root with .venv active, `.venv/bin/python -m pytest`.
Integration tests run `-p no:xdist` (serial) per orchestrator note.

## #6073 (specify-cli-out-of-matrix) — 4 FAILED
cmd: pytest tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py::test_post_merge_validation_reads_in_branch_status_path tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py::{test_skip_lanes_flag_is_what_enables_genuine_completion,test_skip_lanes_completion_rolls_back_on_post_mutation_failure,test_resume_without_reflagging_skip_lanes_auto_honors_persisted_choice} -p no:xdist

- test_post_merge_validation_reads_in_branch_status_path: typer.Exit 1 ->
  "Post-merge target validation failed: merged WPs did not reach done in target branch history. Offending WPs: WP01=approved"
- test_skip_lanes_flag_is_what_enables_genuine_completion: exit 1 ->
  "Mission is not merge-ready — WP(s) missing review approval: WP01. No lane consolidation and no mission_number bake have occurred; the mission is unchanged."
- test_skip_lanes_completion_rolls_back_on_post_mutation_failure: retry exit 1 -> same "missing review approval: WP01"
- test_resume_without_reflagging_skip_lanes_auto_honors_persisted_choice: resume exit 1 -> "Error: No interrupted merge to resume."

## #6071 (integration) — 3 FAILED (serial)
cmd: pytest tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed tests/integration/test_merge_lane_planning_data_loss.py::test_a_run_killed_inside_the_fold_gets_advice_that_leads_to_a_successful_consolidation -p no:xdist

- test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed (#5651): assert exit_code==0 fails, exit 1.
  Error: "coordination teardown incomplete: a commit on coordination branch 'kitty/mission-retention-override-01KX0000' changes files outside kitty-specs/retention-override/ that the target 'main' does not have, and only Mission-directory files are landed during teardown: kitty-specs/retention-override-01KX0000/status.events.jsonl, kitty-specs/retention-override-01KX0000/status.json."
  SMELL: mission dir = kitty-specs/retention-override/ (bare slug); offending paths carry mid8 suffix kitty-specs/retention-override-01KX0000/. bare-slug vs <slug>-<mid8> detection mismatch in teardown.
  log: coord_seed carried=('status.events.jsonl','status.json') coord_commit=085ed62
- test_a_run_killed_inside_the_fold_...[status-pair-only] and [every-coordination-kind]: resume fails with
  MergeLockError: "Merge lock already held for '__global_merge__'" at executor.py:889 (raise MergeLockError). The killed first run left the lock held; resume cannot acquire it. Real resume regression (fails serially too).
