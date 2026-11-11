---
affected_files: []
cycle_number: 1
mission_slug: cli-owns-its-commits-01M75NTA
reproduction_command:
reviewed_at: '2026-11-11T17:21:15Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

**Issue 1 (must fix): the return annotations in next_cmd.py are on the wrong wrappers. This introduces three mypy errors that the module-level `ignore_errors` override on `specify_cli.cli.commands.next_cmd` hides.**

The fix commit (9275092c5) changed `_pair_previous_lifecycle_record` (src/specify_cli/cli/commands/next_cmd.py:645-651) to `-> MissionNextInvokedWrite | None`, although its body still returns nothing (line ~672). `_emit_mission_next_invoked` (next_cmd.py:1296-1303) still says `-> None`, although it now does `return _seam_emit_mission_next_invoked(...)` (line 1316). `_dispatch_advancing_mode` then reads `event_row.in_coordination_worktree` (line 486) on a value that is typed `None`.

Running mypy on a copy of the module outside the override gives exactly these three new errors:
- `next_cmd.py:478: error: "_emit_mission_next_invoked" does not return a value (it only ever returns None)  [func-returns-value]`
- `next_cmd.py:645: error: Missing return statement  [return]`
- `next_cmd.py:1316: error: No return value expected  [return-value]`

The CLAUDE.md "Code Style" rule says new code must pass mypy with zero issues, and a debt override does not exempt new code.

Fix:
- Put `-> MissionNextInvokedWrite | None` on `_emit_mission_next_invoked`.
- Restore `-> None` on `_pair_previous_lifecycle_record`.

**Issue 2 (should fix, small): `_commit_next_event_row` takes `json_output` but never uses it** (next_cmd.py:1319). The warning always goes to stderr. That behaviour is correct in both modes, so either drop the parameter or use it. Do not leave it as a dead keyword.

**Observation for the operator, not a must-fix: C-004 tension in the lane-guard exemption.** `tasks_shared.py:782` adds a filename-shaped exemption (`is_mission_event_log_path`) to the lane `kitty-specs/` guard. C-004 says "No gate gains a new filename exemption". The commit message says why it is needed: without it, every coordination lane cut after `next` refuses `for_review`. It is depth-exact, and it is no wider than the existing slug-blind `is_coord_residue_churn` exemption beside it. It also touches no dirty gate, so #5669 is intact (the predicate's only other caller is implement_cores' pre-existing claim exception, now deduplicated).

It has two weaknesses:
- It is slug-blind: any Mission's `kitty-specs/<m>/mission-events.jsonl` passes.
- It is content-blind: a lane can edit the log, which has live research-gate readers, and consolidation treats the Mission's own copy as bookkeeping.

A structural alternative would exempt the file only when the lane's blob equals the coordination branch's blob (inherited, not authored). Record the operator's decision on this. It does not block this WP.

**Follow-up, out of WP03 scope:** `orchestrator_api/decision_verbs.py:777` (`answer-decision`) calls `emit_mission_next_invoked` too and still leaves the row uncommitted in the coordination worktree. That is the same #5938 shape on the orchestrator path.

Everything else checks out:
- Only the one log path is staged. The operator file stays untracked (C-001), and the test covers it.
- The commit target is `resolve_placement_only(STATUS_STATE)` on the COORD surface only, and `ProtectedBranchRefused` is caught and becomes a warning.
- The owned path is unchanged.
- Landed Missions return `in_coordination_worktree=False`.
- No new specify_cli module-level import in runtime.
- The changelog is accurate.
- Red-first was respected for the main defect.
- 199/199 targeted tests pass.
