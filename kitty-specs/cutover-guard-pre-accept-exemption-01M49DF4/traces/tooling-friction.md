# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-07 · claude · (observed 2026-10-06) First agent mission create --pr-bound --start-branch run left a malformed, untracked scaffold on main (start branch not created; meta.json declared a nonexistent coordination branch); an identical re-run succeeded. Not reproduced, not filed.

2026-10-07 · claude · (observed 2026-10-06) setup-plan JSON reports feature_dir under the coordination worktree while plan_file is in the repository root checkout: two locations for one Mission in one payload.

2026-10-07 · claude · (observed 2026-10-06/07) record-analysis, accept and consolidate all refuse on ANY untracked file in the repository root checkout, including other Missions' files. Needed operator-authorised tagged stash/apply around each; the auto-mode permission classifier blocks git stash -u until the operator explicitly authorises it.

2026-10-07 · claude · (observed 2026-10-07) The specify-time Decision Moment record (decisions/DM-*.md, index.json) is never committed by decision resolve or spec-commit; implement later refuses with Planning artifacts not committed.

2026-10-07 · claude · (observed 2026-10-07) implement's planning-artifact check does not honour .gitignore: the empty, gitignored decisions/index.json.lock left by decision commands blocks it. Removed by hand.

2026-10-07 · claude · (observed 2026-10-07) implement writes vcs/vcs_locked_at into meta.json and never commits it. A stash/apply around accept then silently reverted the status_phase stamp accept had already committed; repaired by hand (HEAD content + lock fields).

2026-10-07 · claude · (observed 2026-10-07) Default squash consolidate refused deterministically (3 runs) because the coordination branch was also the lane-merge branch: planning markdown entered the projection window and no-driver paths fail even when byte-identical. Filed #5847; workaround --abort then --strategy merge.

2026-10-07 · claude · (observed 2026-10-07) tracer-append commits only on the Mission's recorded target branch; appending from a follow-up branch is refused (safe_commit HEAD mismatch), so post-consolidation tracer notes need the original target branch checked out.

2026-10-07 · claude · (observed 2026-10-07) Targeted arch-gate selection missed test_status_module_boundary.py, test_lifted_root_meta_fail_closed_census.py and test_no_dead_symbols.py, plus the changelog house-style lint; a reviewer also wrongly claimed backfill_runtime_state.py is on the ruff-format exclude ratchet. Run ruff format --check . repo-wide and those gates when touching status/cli seams.
