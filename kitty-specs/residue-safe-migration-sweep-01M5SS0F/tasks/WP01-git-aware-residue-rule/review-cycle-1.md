---
affected_files: []
cycle_number: 1
mission_slug: residue-safe-migration-sweep-01M5SS0F
reproduction_command:
reviewed_at: '2026-10-25T17:03:02Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review (reviewer-renata) — changes requested

The core rule is right: cheap checks first, both modes, the accepted-cost case asserted, the deleted-tracked-spec.md case, every fallback setting, the sentinel, no import cycle, C901 <= 15, no noqa or type: ignore. 127/127 on the prescribed suite. Four items block approval.

**Issue 1 (blocking, review-guidance check fails): second residue text in an owned file.**
`src/specify_cli/migration/runtime_state_cutover.py:422` logs `"Skipping %s: not a Mission (residue directory)"`. This file is in WP01's owned_files. The WP's Review Guidance says `git grep -n "not a Mission (residue"` must find RESIDUE_NOTICE only; today it finds 3 hits. Fix: log the shared text, e.g. `logger.info("Skipping %s", residue_notice(<repo-relative POSIX path>))`, or reword the log line so it no longer restates a residue reason. Do not use the bare slug: it is ambiguous across worktrees (M6).

**Issue 2 (blocking per the same check; needs a recorded out-of-map edit or an orchestrator ruling): doctor residue reason.**
`src/specify_cli/cli/commands/_cutover_doctor.py:75` `_RESIDUE_REASON = "not a Mission (residue directory) -- nothing to cut over"`. It is operator-facing, names no folder and gives no remedy, so it does not meet FR-008's "working remedy". No WP owns this file. Choose one:
(a) Make a small recorded out-of-map edit that derives the reason from `residue_notice(...)`, and update `tests/specify_cli/cli/commands/test_cutover_doctor.py` if it pins the text.
(b) Get an explicit orchestrator ruling that narrows the guidance to upgrade-step warnings, and record it in the WP history.

**Issue 3 (blocking, NFR-003 is not actually measured): the git spy misses half the git calls.**
`tests/context/test_is_kitty_specs_residue_git_aware.py` patches only `specify_cli.context.mission_resolver.run_git`. `kernel.git.tracked_paths` and `kernel.git.is_tracked` call `kernel.git` `run_git` internally, so the spy never sees `ls-files`. I measured it with a subprocess-level counter:
- `tracked_mission_paths()` runs 2 real git processes; the spy sees 1.
- A 50-folder walk with omitted `tracked=` runs 100 real processes; the spy sees 50.

The docstring "Measured: 1 (rev-parse) + 1 (ls-files) = 2" is therefore not what the test measures. A regression back to per-marker `is_tracked` probing, which costs 3 real calls per folder, would still pass `<= 2 + 2*50`.
Fix: count at the process boundary (wrap `subprocess.run`/`Popen` for argv[0] == git), or patch the kernel runner as well. Then assert the exact measured numbers:
- `== 2` for the set plus a 50-folder walk with `tracked=`;
- `== 0` for explicit `None`;
- `== 0` for the identity-bearing folder;
- `== 2` for an omitted probe.
Correct the docstring to match.

**Issue 4 (blocking, spec Edge Case "unusable checkout ... no upgrade step crashes"): wider crash surface.**
The lazy probe now runs for folders that hold Mission content but no marker (`tasks.md`, `plan.md`, `status.json`, ...). Base returned False for these with no git call. In a checkout where `rev-parse` succeeds but `ls-files` fails, `tracked_mission_paths` raises `GitCommandError`, which now escapes `is_kitty_specs_residue` through `build_baseline_feature_meta` and `cutover_mission`.
Repro: `git init`, commit a Mission, write garbage to `.git/index`, then call `kitty-specs/002-t/{tasks/,tasks.md}`. The new code raises (exit 128); base returns False.
Fix: in `is_kitty_specs_residue`'s own lazy probe, treat a `GitCommandError` from `tracked_mission_paths` as "git unusable" and use the file-presence branch. Keep `tracked_mission_paths`'s propagate contract for its other callers. Add a corrupt-index test. If you deliberately keep the raise, record the decision and the spec conflict in the WP history; the orchestrator must agree.

**Non-blocking observations**
5. RESIDUE_NOTICE is true in both modes. In file-presence mode the folder also has no mission_id, no spec.md and no meta.json, and is not tracked. But "not a tracked Mission" is vacuous in a non-git or ignored `kitty-specs/` project, and it may suggest that committing the folder fixes it, which it does not in git-aware mode. Optional rewording: "no spec.md or meta.json on disk or in git, and no mission_id". Not a defect; the remedy sentence works in both modes.
6. `residue_notice_path` has no production caller yet. T003 sanctions this, because WP04, which depends on WP01, consumes it. Acceptable.
7. `cutover_repo` still calls `is_kitty_specs_residue(feature_dir)` per folder with no `tracked=`, so the mode check costs 2 git processes per identity-less folder. Content-bearing, marker-less folders used to cost 0. This is within NFR-003 and follows the T002 note. plan.md:80 says "tracked= when walking": if WP05 does not pick that up, pass the walk's `tracked=` there.
